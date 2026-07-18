import type { TaskStatus } from "../../api/types";

const STATUS_COLORS: Record<TaskStatus, string> = {
  PENDING: "#6c757d",
  RUNNING: "#0d6efd",
  COMPLETED: "#198754",
  ERROR: "#dc3545",
};

export function StatusBadge({ status }: { status: TaskStatus }) {
  const color = STATUS_COLORS[status];
  return (
    <span
      className="w-[86px] shrink-0 rounded-full px-2 py-1 text-center text-[11px] font-bold"
      style={{ background: `${color}22`, color, border: `1px solid ${color}55` }}
    >
      {status}
    </span>
  );
}
