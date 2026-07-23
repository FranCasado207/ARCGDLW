import { getBackendInfo } from "./backend";
import type {
  ConfigState,
  DownloadInput,
  Paths,
  Settings,
  Task,
  TaskInput,
  TaskStreamMessage,
  JobStreamMessage,
} from "./types";

async function httpBase(): Promise<string> {
  const { port } = await getBackendInfo();
  return `http://127.0.0.1:${port}`;
}

async function wsBase(): Promise<string> {
  const { port } = await getBackendInfo();
  return `ws://127.0.0.1:${port}`;
}

class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { token } = await getBackendInfo();
  const res = await fetch(`${await httpBase()}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    let detail = await res.text();
    try {
      const parsed = JSON.parse(detail);
      detail = typeof parsed.detail === "string" ? parsed.detail : detail;
    } catch {
      // not JSON, use raw text
    }
    throw new ApiError(detail || `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  listTasks: () => request<Task[]>("/api/tasks"),
  createTask: (body: TaskInput) =>
    request<Task>("/api/tasks", { method: "POST", body: JSON.stringify(body) }),
  updateTask: (id: string, body: TaskInput) =>
    request<Task>(`/api/tasks/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteTask: (id: string, deleteFiles: boolean) =>
    request<void>(`/api/tasks/${id}?delete_files=${deleteFiles}`, { method: "DELETE" }),
  runTask: (id: string) => request<{ status: string }>(`/api/tasks/${id}/run`, { method: "POST" }),

  startDownload: (body: DownloadInput) =>
    request<{ job_id: string }>("/api/download", { method: "POST", body: JSON.stringify(body) }),

  getConfig: () => request<ConfigState>("/api/config"),
  saveConfig: (content: string) =>
    request<{ path: string }>("/api/config", { method: "PUT", body: JSON.stringify({ content }) }),
  createDefaultConfig: () =>
    request<{ path: string }>("/api/config/create-default", { method: "POST" }),

  getSettings: () => request<Settings>("/api/settings"),
  updateSettings: (body: Settings) =>
    request<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(body) }),
  getPaths: () => request<Paths>("/api/paths"),
};

/**
 * Fetches the preview image as a blob and returns an object URL, instead of
 * pointing <img src> straight at a raw http://127.0.0.1:port URL. The
 * packaged app's page loads from a secure custom scheme (tauri://localhost),
 * and some WebKitGTK/webview configurations block that page from loading
 * plain-http subresources as mixed content - object URLs sidestep that
 * entirely since they never leave the page's own origin. Callers must
 * URL.revokeObjectURL() the result once done with it.
 */
export async function fetchPreviewObjectUrl(previewUrl: string): Promise<string> {
  const { token } = await getBackendInfo();
  const res = await fetch(`${await httpBase()}${previewUrl}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new ApiError(`Failed to load preview: ${res.status}`);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

async function openStream(path: string, onMessage: (raw: string) => void): Promise<() => void> {
  const { token } = await getBackendInfo();
  const ws = new WebSocket(`${await wsBase()}${path}?token=${token}`);
  ws.onmessage = (event) => onMessage(event.data);
  return () => ws.close();
}

export function openTaskStream(taskId: string, onMessage: (msg: TaskStreamMessage) => void) {
  return openStream(`/api/tasks/${taskId}/stream`, (raw) => onMessage(JSON.parse(raw)));
}

export function openDownloadStream(jobId: string, onMessage: (msg: JobStreamMessage) => void) {
  return openStream(`/api/download/${jobId}/stream`, (raw) => onMessage(JSON.parse(raw)));
}
