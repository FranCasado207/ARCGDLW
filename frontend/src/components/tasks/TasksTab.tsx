import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { Task, TaskInput } from "../../api/types";
import { Button } from "../ui/Button";
import { DeleteTaskDialog } from "./DeleteTaskDialog";
import { TaskCard } from "./TaskCard";
import { TaskFormDialog } from "./TaskFormDialog";

export function TasksTab() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [deletingTask, setDeletingTask] = useState<Task | null>(null);
  const [defaultOutputFolder, setDefaultOutputFolder] = useState("");

  useEffect(() => {
    api
      .listTasks()
      .then(setTasks)
      .finally(() => setLoading(false));
    // An absolute default, not a relative "./downloads" the frontend has no
    // consistent way to resolve - see get_default_output_dir() on the backend.
    api.getPaths().then((paths) => setDefaultOutputFolder(paths.default_output_dir));
  }, []);

  function upsertTask(task: Task) {
    setTasks((prev) => {
      const idx = prev.findIndex((t) => t.id === task.id);
      if (idx === -1) return [...prev, task];
      const next = [...prev];
      next[idx] = task;
      return next;
    });
  }

  async function handleCreate(data: TaskInput) {
    const task = await api.createTask(data);
    upsertTask(task);
    setFormOpen(false);
  }

  async function handleEditSubmit(data: TaskInput) {
    if (!editingTask) return;
    const task = await api.updateTask(editingTask.id, data);
    upsertTask(task);
    setFormOpen(false);
    setEditingTask(null);
  }

  async function handleRun(task: Task) {
    try {
      await api.runTask(task.id);
    } catch {
      // most likely already running / just deleted; the task list will
      // reflect the real state via the next WS/task_updated event
    }
  }

  async function handleDeleteConfirm(deleteFiles: boolean) {
    if (!deletingTask) return;
    await api.deleteTask(deletingTask.id, deleteFiles);
    setTasks((prev) => prev.filter((t) => t.id !== deletingTask.id));
    setDeletingTask(null);
  }

  return (
    <div className="flex h-full flex-col gap-3 p-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-app-text">Tasks</h1>
        <Button
          variant="primary"
          onClick={() => {
            setEditingTask(null);
            setFormOpen(true);
          }}
        >
          + Create Task
        </Button>
      </div>
      <div className="h-px bg-app-border" />

      <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto pr-1">
        {loading && <p className="text-sm text-app-muted">Loading tasks…</p>}
        {!loading && tasks.length === 0 && (
          <p className="text-sm text-app-muted">No tasks yet — create one to get started.</p>
        )}
        {tasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            onTaskUpdated={upsertTask}
            onRun={handleRun}
            onEdit={(t) => {
              setEditingTask(t);
              setFormOpen(true);
            }}
            onDelete={setDeletingTask}
          />
        ))}
      </div>

      {formOpen && (
        <TaskFormDialog
          key={editingTask?.id ?? "new"}
          open={formOpen}
          task={editingTask}
          defaultOutputFolder={defaultOutputFolder}
          onClose={() => {
            setFormOpen(false);
            setEditingTask(null);
          }}
          onSubmit={editingTask ? handleEditSubmit : handleCreate}
        />
      )}

      {deletingTask && (
        <DeleteTaskDialog
          task={deletingTask}
          onClose={() => setDeletingTask(null)}
          onConfirm={handleDeleteConfirm}
        />
      )}
    </div>
  );
}
