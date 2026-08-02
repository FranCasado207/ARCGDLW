import argparse
import sys

from arcgdlw.models.downloader.downloader import Downloader
from arcgdlw.paths import ensure_user_path


def run_cli(args) -> None:
    archive_format = None
    if args.zip:
        archive_format = "zip"
    elif args.cbz:
        archive_format = "cbz"
    elif args.rar:
        archive_format = "rar"
    elif args.cbr:
        archive_format = "cbr"

    downloader = Downloader(
        outputFolder=args.output,
        urls=args.urls,
        targetFormat=args.format,
        overrideFormat=args.override,
        archiveFormat=archive_format,
    )

    try:
        downloader.download(log_callback=print)
        print("\n✅ All downloads complete!")
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        sys.exit(1)


def main() -> None:
    ensure_user_path()

    parser = argparse.ArgumentParser(description="Download and process gallery links.")

    parser.add_argument(
        "urls", nargs="*", help="The URLs to download from (leave empty to launch GUI)"
    )
    parser.add_argument(
        "-o", "--output",
        default="./downloads",
        help="Target folder for the final archive or flat files",
    )
    parser.add_argument(
        "-f", "--format",
        default="gif",
        help="Target format to convert to (default: gif)",
    )
    parser.add_argument(
        "--override",
        action="store_true",
        help="Force conversion overriding duration/audio rules",
    )

    archive_group = parser.add_mutually_exclusive_group()
    archive_group.add_argument("--zip", action="store_true", help="Archive as .zip")
    archive_group.add_argument("--cbz", action="store_true", help="Archive as Comic Book Zip (.cbz)")
    archive_group.add_argument("--rar", action="store_true", help="Archive as .rar (Requires 'rar' installed)")
    archive_group.add_argument("--cbr", action="store_true", help="Archive as Comic Book Rar (.cbr)")

    args = parser.parse_args()

    if args.urls:
        run_cli(args)
    else:
        from arcgdlw.ui import launch_gui
        launch_gui()


if __name__ == "__main__":
    main()
