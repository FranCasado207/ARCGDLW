import type { TaskStatus } from "../../api/types";

const STATUS_COLORS: Record<TaskStatus, string> = {
  PENDING: "#6c757d",
  RUNNING: "#0d6efd",
  COMPLETED: "#198754",
  ERROR: "#dc3545",
};

const STATUS_LABELS: Record<TaskStatus, string> = {
  PENDING: "Pending",
  RUNNING: "Running",
  COMPLETED: "Completed",
  ERROR: "Error",
};

export function StatusBadge({ status }: { status: TaskStatus }) {
  const color = STATUS_COLORS[status];
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 self-start rounded-full bg-black/5 px-2.5 py-1 text-xs font-medium text-app-text dark:bg-white/10">
      <span
        className={`h-1.5 w-1.5 shrink-0 rounded-full ${status === "RUNNING" ? "animate-pulse" : ""}`}
        style={{ background: color }}
      />
      {STATUS_LABELS[status]}
    </span>
  );
}
