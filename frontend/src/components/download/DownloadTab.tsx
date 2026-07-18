import { useRef, useState } from "react";
import { api, openDownloadStream } from "../../api/client";
import { notify, pickFolder } from "../../lib/native";
import { Button } from "../ui/Button";
import { Checkbox, FieldLabel, Select, TextArea, TextField } from "../ui/Field";

export function DownloadTab() {
  const [urlsText, setUrlsText] = useState("");
  const [outputFolder, setOutputFolder] = useState("./downloads");
  const [targetFormat, setTargetFormat] = useState("gif");
  const [overrideFormat, setOverrideFormat] = useState(false);
  const [archiveFormat, setArchiveFormat] = useState<string | null>(null);
  const [logs, setLogs] = useState("");
  const [running, setRunning] = useState(false);
  const logRef = useRef<HTMLPreElement>(null);

  function appendLog(line: string) {
    setLogs((prev) => prev + line + "\n");
    requestAnimationFrame(() => logRef.current?.scrollTo({ top: logRef.current.scrollHeight }));
  }

  async function start() {
    const urls = urlsText
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean);
    if (urls.length === 0) {
      appendLog("⚠️ Error: Please enter at least one valid URL.");
      return;
    }

    setRunning(true);
    appendLog(`⏳ Starting download for ${urls.length} URL(s)...`);

    try {
      const { job_id } = await api.startDownload({
        urls,
        output_folder: outputFolder,
        target_format: targetFormat,
        override_format: overrideFormat,
        archive_format: archiveFormat,
      });

      const close = await openDownloadStream(job_id, (msg) => {
        if (msg.type === "log") {
          appendLog(msg.line);
        } else if (msg.type === "finished") {
          setRunning(false);
          if (msg.success) {
            appendLog("\n✅ All downloads complete!");
            notify("Download finished", "All downloads completed successfully.");
          } else {
            appendLog(`\n❌ Fatal Error: ${msg.error_message}`);
            notify("Download failed", "The download finished with errors — check the log.");
          }
          close();
        }
      });
    } catch (e) {
      setRunning(false);
      appendLog(`\n❌ Fatal Error: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <h1 className="text-xl font-bold text-app-text">Gallery Downloader</h1>

      <div>
        <FieldLabel>Gallery URLs (one per line)</FieldLabel>
        <TextArea
          rows={4}
          value={urlsText}
          onChange={(e) => setUrlsText(e.target.value)}
          placeholder={"https://gallery-url-1.com/...\nhttps://gallery-url-2.com/..."}
        />
      </div>

      <div>
        <FieldLabel>Output Folder</FieldLabel>
        <div className="flex gap-2">
          <TextField value={outputFolder} readOnly />
          <Button
            onClick={async () => {
              const folder = await pickFolder(outputFolder);
              if (folder) setOutputFolder(folder);
            }}
          >
            Browse
          </Button>
        </div>
      </div>

      <div>
        <FieldLabel>Target Format</FieldLabel>
        <div className="flex items-center gap-3">
          <Select className="w-32" value={targetFormat} onChange={(e) => setTargetFormat(e.target.value)}>
            {["gif", "mp4", "webm", "mkv"].map((fmt) => (
              <option key={fmt} value={fmt}>
                {fmt}
              </option>
            ))}
          </Select>
          <Checkbox
            label="Force conversion (Override)"
            checked={overrideFormat}
            onChange={setOverrideFormat}
            title="Force conversion even if duration/audio rules are not met."
          />
        </div>
      </div>

      <div>
        <FieldLabel>Archive Mode</FieldLabel>
        <Select
          className="w-36"
          value={archiveFormat ?? "None"}
          onChange={(e) => setArchiveFormat(e.target.value === "None" ? null : e.target.value)}
        >
          {["None", "zip", "cbz", "rar", "cbr"].map((fmt) => (
            <option key={fmt} value={fmt}>
              {fmt}
            </option>
          ))}
        </Select>
      </div>

      <div className="h-px bg-app-border" />

      <pre
        ref={logRef}
        className="min-h-0 flex-1 overflow-auto rounded-lg bg-black/20 p-3 font-mono text-[13px] text-app-text"
      >
        {logs || "(no log output yet)"}
      </pre>

      <Button variant="primary" disabled={running} onClick={start} className="py-2.5 text-[15px]">
        {running ? "Processing..." : "Start Download"}
      </Button>
    </div>
  );
}
