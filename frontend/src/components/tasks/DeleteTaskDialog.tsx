import { useState } from "react";
import type { Task } from "../../api/types";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { Checkbox } from "../ui/Field";

interface DeleteTaskDialogProps {
  task: Task;
  onClose: () => void;
  onConfirm: (deleteFiles: boolean) => Promise<void>;
}

export function DeleteTaskDialog({ task, onClose, onConfirm }: DeleteTaskDialogProps) {
  const [deleteFiles, setDeleteFiles] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const hasFiles = task.output_files.length > 0;
  const count = task.urls.length;
  const archiveLabel = task.archive_format ?? "no archive";

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Delete "${task.name}"?`}
      width="440px"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="danger"
            disabled={deleting}
            onClick={async () => {
              setDeleting(true);
              try {
                await onConfirm(deleteFiles);
              } finally {
                setDeleting(false);
              }
            }}
          >
            {deleteFiles ? "Delete Task && Files" : "Delete Task"}
          </Button>
        </>
      }
    >
      <div className="space-y-3 text-sm text-app-muted">
        <p>
          {count} URL{count !== 1 ? "s" : ""} · {task.target_format} · {archiveLabel}
          <br />
          Output folder: {task.output_folder}
        </p>
        <div className="h-px bg-app-border" />
        <Checkbox
          label="Also delete the downloaded files from disk"
          checked={deleteFiles}
          onChange={setDeleteFiles}
          disabled={!hasFiles}
          title={
            hasFiles
              ? "Permanently deletes everything this task downloaded (archives or individual files). This cannot be undone."
              : "This task has no completed downloads on record to delete."
          }
        />
        {deleteFiles && (
          <p className="text-xs text-red-400">⚠ The downloaded files will be permanently deleted.</p>
        )}
      </div>
    </Dialog>
  );
}
