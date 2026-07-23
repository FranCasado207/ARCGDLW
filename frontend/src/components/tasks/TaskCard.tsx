import { useEffect, useRef, useState } from "react";
import { fetchPreviewObjectUrl } from "../../api/client";
import type { Task } from "../../api/types";
import { useTaskStream } from "../../hooks/useTaskStream";
import { notify, openFolder, revealFile } from "../../lib/native";
import { Button } from "../ui/Button";
import { StatusBadge } from "./StatusBadge";

interface TaskCardProps {
  task: Task;
  onTaskUpdated: (task: Task) => void;
  onEdit: (task: Task) => void;
  onDelete: (task: Task) => void;
  onRun: (task: Task) => void;
}

export function TaskCard({ task, onTaskUpdated, onEdit, onDelete, onRun }: TaskCardProps) {
  const [logs, setLogs] = useState("");
  const [logsOpen, setLogsOpen] = useState(false);
  const [progress, setProgress] = useState<{ current: number; total: number } | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const logRef = useRef<HTMLPreElement>(null);

  useTaskStream(task.id, (msg) => {
    switch (msg.type) {
      case "history":
        setLogs(msg.content);
        break;
      case "task_updated":
        onTaskUpdated(msg.task);
        break;
      case "log":
        setLogs((prev) => prev + msg.line + "\n");
        setLogsOpen(true);
        break;
      case "progress":
        setProgress({ current: msg.current, total: msg.total });
        break;
      case "finished":
        setProgress(null);
        if (msg.task) onTaskUpdated(msg.task);
        notify(
          msg.success ? "Task completed" : "Task failed",
          msg.success
            ? `"${task.name}" finished successfully.`
            : `"${task.name}" failed: ${msg.error_message}`,
        );
        break;
    }
  });

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [logs]);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    if (task.preview_url) {
      fetchPreviewObjectUrl(task.preview_url)
        .then((url) => {
          if (cancelled) {
            URL.revokeObjectURL(url);
          } else {
            objectUrl = url;
            setPreviewUrl(url);
          }
        })
        .catch((e) => {
          console.error("Failed to load task preview", e);
          if (!cancelled) setPreviewUrl(null);
        });
    } else {
      setPreviewUrl(null);
    }

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [task.preview_url]);

  const running = task.status === "RUNNING";
  const count = task.urls.length;
  const archiveLabel = task.archive_format ?? "no archive";
  const completed = task.status === "COMPLETED" && task.output_files.length > 0;
  const singleArchive = completed && Boolean(task.archive_format) && task.output_files.length === 1;

  return (
    <div className="rounded-xl border border-app-border bg-app-surface/60 p-3.5">
      <div className="flex gap-3.5">
        <div className="group relative h-20 w-20 shrink-0 self-start overflow-hidden rounded-lg border border-app-border bg-black/5 dark:bg-white/5">
          {previewUrl ? (
            <>
              <img src={previewUrl} alt="" className="h-full w-full object-cover" />
              <div className="pointer-events-none absolute left-full top-0 z-10 ml-2 hidden max-w-[min(70vw,420px)] rounded-lg border border-app-border bg-app-surface p-1 shadow-2xl group-hover:block">
                <img src={previewUrl} alt="" className="max-h-[420px] max-w-full rounded" />
              </div>
            </>
          ) : (
            <div className="flex h-full w-full items-center justify-center text-2xl text-app-muted">?</div>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-bold text-app-text">{task.name}</div>
          <div className="mt-1 text-xs text-app-muted">
            {count} URL{count !== 1 ? "s" : ""} · {task.target_format} · {archiveLabel}
          </div>
          {task.status === "ERROR" && task.error_message && (
            <div className="mt-1.5 break-words text-xs text-red-400">{task.error_message}</div>
          )}
        </div>

        <StatusBadge status={task.status} />
      </div>

      {(running || progress) && (
        <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
          <div
            className="h-full bg-app-accent transition-all"
            style={
              progress && progress.total > 0
                ? { width: `${(progress.current / progress.total) * 100}%` }
                : { width: "40%", animation: "pulse 1.5s ease-in-out infinite" }
            }
          />
        </div>
      )}

      <div className="my-3 h-px bg-app-border" />

      <div className="flex flex-wrap items-center gap-1.5">
        <Button disabled={running} onClick={() => onRun(task)}>
          Run
        </Button>
        <Button disabled={running} onClick={() => onEdit(task)}>
          Edit
        </Button>
        <Button variant="danger" disabled={running} onClick={() => onDelete(task)}>
          Delete
        </Button>
        {singleArchive && (
          <Button onClick={() => revealFile(task.output_files[0])}>Open File</Button>
        )}
        {completed && !singleArchive && (
          <Button onClick={() => openFolder(task.output_folder)}>Open Folder</Button>
        )}
        <div className="flex-1" />
        <Button
          variant="ghost"
          onClick={() => setLogsOpen((v) => !v)}
        >
          {logsOpen ? "Hide Logs" : "Logs"}
        </Button>
      </div>

      {logsOpen && (
        <pre
          ref={logRef}
          className="mt-3 max-h-[220px] min-h-[110px] overflow-auto rounded-lg bg-black/20 p-2.5 font-mono text-xs text-app-text"
        >
          {logs || "(no log output yet)"}
        </pre>
      )}
    </div>
  );
}
