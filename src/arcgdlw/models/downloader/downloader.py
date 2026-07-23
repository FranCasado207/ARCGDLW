import json
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

from arcgdlw.paths import subprocess_env

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_UNSAFE_FILENAME_RE = re.compile(r'[\\/:*?"<>|]')


class _NonRetryableDownloadError(RuntimeError):
    """A gallery-dl failure that retrying won't fix (e.g. a filesystem limit
    tripped by the site's own filename template)."""


class Downloader:
    def __init__(
        self,
        outputFolder: str | Path,
        urls: list[str],
        targetFormat: str,
        overrideFormat: bool = False,
        archiveFormat: str | None = None,
        configFile: str | None = None,
        cookiesFile: str | None = None,
        createSubfolder: bool = False,
        archiveName: str | None = None,
    ) -> None:
        self.urls = urls

        # Resolved to absolute: output_files built from this are persisted and
        # later handed to the OS file manager (Tauri opener) by a different
        # process than this one, so a relative path here would resolve
        # against the wrong working directory there.
        self.outputFolder = Path(outputFolder).expanduser().resolve()
        self.outputFolder.mkdir(parents=True, exist_ok=True)

        self.targetFormat = targetFormat.lower().lstrip(".")
        self.overrideFormat = overrideFormat
        self.archiveFormat = (
            archiveFormat.lower().lstrip(".") if archiveFormat else None
        )
        self.configFile = configFile
        self.cookiesFile = cookiesFile
        self.createSubfolder = createSubfolder
        self.archiveName = archiveName

        self._verify_dependencies()

    def _verify_dependencies(self) -> None:
        required = ["gallery-dl", "ffmpeg", "ffprobe"]

        # If the user wants a RAR-based format, the proprietary `rar` CLI tool must be installed
        if self.archiveFormat in ["rar", "cbr"]:
            required.append("rar")

        for executable in required:
            if shutil.which(executable) is None:
                raise RuntimeError(f"Required executable not found: {executable}")

    def _download_with_gallery_dl(self, target_folder: Path, url: str) -> list[Path]:
        """Now processes a single URL at a time."""
        before = {p.resolve() for p in target_folder.rglob("*") if p.is_file()}

        cmd = ["gallery-dl", "-d", str(target_folder)]
        if self.configFile:
            cmd += ["-c", str(self.configFile)]
        if self.cookiesFile:
            cmd += ["--cookies", str(self.cookiesFile)]
        cmd.append(url)

        result = subprocess.run(
            cmd, capture_output=True, text=True, env=subprocess_env()
        )
        if result.returncode != 0:
            detail = _ANSI_RE.sub("", result.stderr or result.stdout or "").strip()
            tail = "\n".join(detail.splitlines()[-3:]) if detail else ""
            message = (
                f"gallery-dl failed (exit {result.returncode}): {tail}"
                if tail else f"gallery-dl failed with exit code {result.returncode}"
            )

            if "File name too long" in detail or "Errno 36" in detail:
                message += (
                    "\n\nThis site generated a filename/path longer than your filesystem "
                    "allows. Retrying won't help — fix it by adding a length limit to that "
                    "site's filename or directory template in your gallery-dl config "
                    "(Config tab), e.g. change {title} to {title:.100} to cap it at "
                    "100 characters."
                )
                raise _NonRetryableDownloadError(message)

            raise RuntimeError(message)

        after = {p.resolve() for p in target_folder.rglob("*") if p.is_file()}
        new_files = list(after - before)

        return sorted(new_files)

    def _video_info(self, file: Path) -> dict:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                str(file),
            ],
            capture_output=True,
            text=True,
            check=True,
            env=subprocess_env(),
        )

        data = json.loads(result.stdout)

        video_stream = next(
            stream for stream in data["streams"] if stream["codec_type"] == "video"
        )

        has_audio = any(stream["codec_type"] == "audio" for stream in data["streams"])

        # Extract the frame rate fraction (e.g., "30/1"). Default to "24/1" as a fallback.
        fps = video_stream.get("r_frame_rate", "24/1")
        if fps == "0/0":
            fps = "24/1"

        return {
            "duration": float(data["format"].get("duration", 0)),
            "width": int(video_stream["width"]),
            "height": int(video_stream["height"]),
            "has_audio": has_audio,
            "fps": fps,
        }

    def _should_convert_to_gif(self, info: dict) -> bool:
        if self.overrideFormat:
            return True

        return info["duration"] <= 15 and not info["has_audio"]

    def _convert_to_gif(self, mp4_file: Path, fps: str) -> Path:
        gif_file = mp4_file.with_suffix(".gif")
        palette_file = mp4_file.with_suffix(".palette.png")

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(mp4_file),
                "-vf",
                f"fps={fps},scale=iw:-1:flags=lanczos,palettegen",
                str(palette_file),
            ],
            check=True,
            env=subprocess_env(),
        )

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(mp4_file),
                "-i",
                str(palette_file),
                "-lavfi",
                f"fps={fps},scale=iw:-1:flags=lanczos[x];[x][1:v]paletteuse",
                str(gif_file),
            ],
            check=True,
            env=subprocess_env(),
        )

        # Cleanup the temporary palette and the original video file
        palette_file.unlink(missing_ok=True)
        mp4_file.unlink(missing_ok=True)

        return gif_file

    def _process_file(self, file: Path) -> Path:
        suffix = file.suffix.lower()

        if self.targetFormat != "gif":
            return file

        if suffix == ".gif":
            return file

        video_formats = {
            ".mp4",
            ".webm",
            ".mkv",
            ".mov",
            ".avi",
        }

        if suffix in video_formats:
            # Get video data once
            info = self._video_info(file)

            # Check condition passing the pre-fetched info
            if self._should_convert_to_gif(info):
                # Convert using the specific source FPS
                return self._convert_to_gif(file, fps=info["fps"])

        return file

    @staticmethod
    def _sanitize_archive_name(name: str) -> str:
        cleaned = _UNSAFE_FILENAME_RE.sub("_", name).strip()
        return cleaned or "download"

    def _archive_files(self, files: list[Path], dest_folder: Path, archive_base_name: str) -> Path:
        if not files:
            raise RuntimeError("No files to archive.")

        archive_path = dest_folder / f"{archive_base_name}.{self.archiveFormat}"

        # Prevent overwriting existing archives in the output folder
        counter = 1
        while archive_path.exists():
            archive_path = (
                dest_folder / f"{archive_base_name}_{counter}.{self.archiveFormat}"
            )
            counter += 1

        if self.archiveFormat in ["zip", "cbz"]:
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in files:
                    zf.write(file, arcname=file.name)

        elif self.archiveFormat in ["rar", "cbr"]:
            cmd = ["rar", "a", "-ep", str(archive_path)] + [str(f) for f in files]
            subprocess.run(cmd, check=True, capture_output=True, env=subprocess_env())

        return archive_path

    def download(self, log_callback=None, progress_callback=None, max_retries: int = 3, retry_delay: float = 5.0) -> list[Path]:
        """Loops through URLs sequentially to prevent archive collisions."""
        all_final_files = []
        total = len(self.urls)

        # When archiving, each URL's files are staged into their own
        # sub-directory (surviving the per-URL temp cleanup below) so we can
        # decide, once every URL is done, how to bundle them: one archive per
        # URL (named after gallery-dl's output folder, e.g. chapters/galleries
        # with several files each) or — only when *every* URL yielded exactly
        # one file (e.g. a run of single-image posts) — a single combined
        # archive.
        archive_staging_dir = Path(tempfile.mkdtemp()) if self.archiveFormat else None
        archive_groups: list[dict] = []  # [{"name": str, "files": [Path, ...]}, ...]

        try:
            for i, url in enumerate(self.urls):
                if progress_callback:
                    progress_callback(i, total)
                if log_callback:
                    log_callback(f"\n⏳ Processing URL: {url}")

                temp_dir_path = Path(tempfile.mkdtemp())

                try:
                    downloaded_files = None
                    non_retryable = False
                    for attempt in range(1, max_retries + 1):
                        try:
                            downloaded_files = self._download_with_gallery_dl(temp_dir_path, url)
                            break
                        except _NonRetryableDownloadError as e:
                            # Retrying deterministic failures (e.g. a filesystem
                            # filename-length limit) just wastes time — fail fast.
                            if log_callback:
                                log_callback(f"❌ {e}")
                            non_retryable = True
                            break
                        except Exception as e:
                            if log_callback:
                                log_callback(f"⚠️ Attempt {attempt}/{max_retries} failed for {url}: {e}")
                            if attempt < max_retries:
                                if log_callback:
                                    log_callback(f"🔄 Retrying in {retry_delay:.0f}s...")
                                time.sleep(retry_delay)
                                shutil.rmtree(temp_dir_path)
                                temp_dir_path.mkdir()

                    if non_retryable:
                        continue

                    if downloaded_files is None:
                        if log_callback:
                            log_callback(f"❌ All {max_retries} attempts failed for {url}, skipping.")
                        continue

                    if not downloaded_files:
                        if log_callback:
                            log_callback("⚠️ No new files found.")
                        continue

                    processed_files = [
                        self._process_file(file) for file in downloaded_files
                    ]

                    # 1. Archive requested — stage this URL's files as their
                    #    own group; bundling into one or several archives is
                    #    decided once all URLs have been processed.
                    if self.archiveFormat:
                        assert archive_staging_dir is not None
                        group_name = processed_files[0].parent.name
                        group_dir = archive_staging_dir / f"group_{i}"
                        group_dir.mkdir()

                        group_files = []
                        for file in processed_files:
                            dest = group_dir / file.name
                            counter = 1
                            while dest.exists():
                                dest = group_dir / f"{dest.stem}_{counter}{dest.suffix}"
                                counter += 1
                            shutil.move(str(file), str(dest))
                            group_files.append(dest)
                        archive_groups.append({"name": group_name, "files": group_files})

                    # 2. No archive requested (Flat files)
                    else:
                        for file in processed_files:
                            if self.createSubfolder:
                                # Preserve the folder structure gallery-dl generated
                                # for this URL (e.g. category/user/...) instead of
                                # dumping every file straight into the output folder.
                                dest = self.outputFolder / file.relative_to(temp_dir_path)
                                dest.parent.mkdir(parents=True, exist_ok=True)
                            else:
                                dest = self.outputFolder / file.name

                            # Prevent overwriting files with the same name
                            counter = 1
                            while dest.exists():
                                dest = (
                                    dest.parent
                                    / f"{dest.stem}_{counter}{dest.suffix}"
                                )
                                counter += 1

                            shutil.move(str(file), str(dest))
                            all_final_files.append(dest)

                            if log_callback:
                                log_callback(
                                    f"📄 Saved: {dest.relative_to(self.outputFolder)}"
                                )

                finally:
                    shutil.rmtree(temp_dir_path, ignore_errors=True)

            if self.archiveFormat and archive_groups:
                all_single_file = all(len(g["files"]) == 1 for g in archive_groups)

                if len(archive_groups) > 1 and all_single_file:
                    # Every URL was a single image — bundle them all into one archive.
                    combined_files = [f for g in archive_groups for f in g["files"]]
                    archive_base_name = (
                        self._sanitize_archive_name(self.archiveName)
                        if self.archiveName else "download"
                    )
                    try:
                        archive_path = self._archive_files(
                            combined_files, self.outputFolder, archive_base_name
                        )
                        all_final_files.append(archive_path)
                        if log_callback:
                            log_callback(f"📦 Created archive: {archive_path.name}")
                    except Exception as e:
                        if log_callback:
                            log_callback(f"⚠️ Archiving error: {e}")
                else:
                    # One archive per URL, named after gallery-dl's output folder.
                    for group in archive_groups:
                        try:
                            archive_path = self._archive_files(
                                group["files"], self.outputFolder, group["name"]
                            )
                            all_final_files.append(archive_path)
                            if log_callback:
                                log_callback(f"📦 Created archive: {archive_path.name}")
                        except Exception as e:
                            if log_callback:
                                log_callback(f"⚠️ Archiving error: {e}")
        finally:
            if archive_staging_dir:
                shutil.rmtree(archive_staging_dir, ignore_errors=True)

        if progress_callback:
            progress_callback(total, total)

        return all_final_files
