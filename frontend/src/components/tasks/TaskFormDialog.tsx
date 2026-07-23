import { useState } from "react";
import type { Task, TaskInput } from "../../api/types";
import { pickFile, pickFolder } from "../../lib/native";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { Checkbox, FieldLabel, TextArea, TextField } from "../ui/Field";
import { Select } from "../ui/Select";

interface TaskFormDialogProps {
  open: boolean;
  task: Task | null;
  defaultOutputFolder: string;
  onClose: () => void;
  onSubmit: (data: TaskInput) => Promise<void>;
}

function toInput(task: Task | null, defaultOutputFolder: string): TaskInput {
  if (task) {
    return {
      name: task.name,
      urls: task.urls,
      output_folder: task.output_folder,
      target_format: task.target_format,
      override_format: task.override_format,
      archive_format: task.archive_format,
      cookies_file: task.cookies_file,
      create_subfolder: task.create_subfolder,
      start_automatically: task.start_automatically,
    };
  }
  return {
    name: "",
    urls: [],
    output_folder: defaultOutputFolder,
    target_format: "gif",
    override_format: false,
    archive_format: null,
    cookies_file: null,
    create_subfolder: false,
    start_automatically: false,
  };
}

export function TaskFormDialog({ open, task, defaultOutputFolder, onClose, onSubmit }: TaskFormDialogProps) {
  const [form, setForm] = useState<TaskInput>(() => toInput(task, defaultOutputFolder));
  const [urlsText, setUrlsText] = useState(() => (task ? task.urls.join("\n") : ""));
  const [nameError, setNameError] = useState(false);
  const [urlsError, setUrlsError] = useState(false);
  const [saving, setSaving] = useState(false);

  if (!open) return null;

  const isEdit = Boolean(task);

  function reset() {
    const initial = toInput(task, defaultOutputFolder);
    setForm(initial);
    setUrlsText(task ? task.urls.join("\n") : "");
    setNameError(false);
    setUrlsError(false);
  }

  async function handleSubmit() {
    const name = form.name.trim();
    const urls = urlsText
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean);

    const nameOk = name.length > 0;
    const urlsOk = urls.length > 0;
    setNameError(!nameOk);
    setUrlsError(!urlsOk);
    if (!nameOk || !urlsOk) return;

    setSaving(true);
    try {
      await onSubmit({ ...form, name, urls });
      reset();
    } finally {
      setSaving(false);
    }
  }

  function handleClose() {
    reset();
    onClose();
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      title={isEdit ? "Edit Task" : "Create Task"}
      footer={
        <>
          <Button onClick={handleClose}>Cancel</Button>
          <Button variant="primary" disabled={saving} onClick={handleSubmit}>
            {isEdit ? "Save" : "Create"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <FieldLabel>Name</FieldLabel>
          <TextField
            value={form.name}
            placeholder="My task name"
            className={nameError ? "border-red-500" : ""}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          />
        </div>

        <div>
          <FieldLabel>Gallery URLs (one per line)</FieldLabel>
          <TextArea
            rows={4}
            value={urlsText}
            placeholder={"https://gallery-url-1.com/...\nhttps://gallery-url-2.com/..."}
            className={urlsError ? "border-red-500" : ""}
            onChange={(e) => setUrlsText(e.target.value)}
          />
        </div>

        <div>
          <FieldLabel>Output Folder</FieldLabel>
          <div className="flex gap-2">
            <TextField value={form.output_folder} readOnly />
            <Button
              onClick={async () => {
                const folder = await pickFolder(form.output_folder);
                if (folder) setForm((f) => ({ ...f, output_folder: folder }));
              }}
            >
              Browse
            </Button>
          </div>
        </div>

        <Checkbox
          label="Create a sub-folder"
          checked={form.create_subfolder}
          onChange={(v) => setForm((f) => ({ ...f, create_subfolder: v }))}
          title="Keep each URL's downloads in its own sub-folder (named automatically by gallery-dl) instead of dumping every file into the output folder."
        />

        <div>
          <FieldLabel>Target Format</FieldLabel>
          <div className="flex items-center gap-3">
            <Select
              className="w-32"
              value={form.target_format}
              onChange={(v) => setForm((f) => ({ ...f, target_format: v }))}
              options={["gif", "mp4", "webm", "mkv"].map((fmt) => ({ value: fmt, label: fmt }))}
            />
            <Checkbox
              label="Force conversion (Override)"
              checked={form.override_format}
              onChange={(v) => setForm((f) => ({ ...f, override_format: v }))}
              title="Force conversion even if duration/audio rules are not met."
            />
          </div>
        </div>

        <div>
          <FieldLabel>Archive Mode</FieldLabel>
          <Select
            className="w-36"
            value={form.archive_format ?? "None"}
            onChange={(v) => setForm((f) => ({ ...f, archive_format: v === "None" ? null : v }))}
            options={["None", "zip", "cbz", "rar", "cbr"].map((fmt) => ({ value: fmt, label: fmt }))}
          />
        </div>

        <div>
          <FieldLabel>Cookies File</FieldLabel>
          <div className="flex gap-2">
            <TextField value={form.cookies_file ?? ""} placeholder="Optional — path to cookies.txt" readOnly />
            <Button
              onClick={async () => {
                const file = await pickFile(undefined, ["txt"]);
                if (file) setForm((f) => ({ ...f, cookies_file: file }));
              }}
            >
              Browse
            </Button>
            <Button onClick={() => setForm((f) => ({ ...f, cookies_file: null }))}>Clear</Button>
          </div>
        </div>

        <Checkbox
          label="Start automatically after creation"
          checked={form.start_automatically}
          onChange={(v) => setForm((f) => ({ ...f, start_automatically: v }))}
        />
      </div>
    </Dialog>
  );
}
