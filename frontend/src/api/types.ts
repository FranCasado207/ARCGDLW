export type TaskStatus = "PENDING" | "RUNNING" | "COMPLETED" | "ERROR";

export interface Task {
  id: string;
  name: string;
  urls: string[];
  output_folder: string;
  target_format: string;
  override_format: boolean;
  archive_format: string | null;
  cookies_file: string | null;
  create_subfolder: boolean;
  start_automatically: boolean;
  status: TaskStatus;
  preview_image: string | null;
  preview_url: string | null;
  error_message: string | null;
  created_at: string;
  output_files: string[];
  is_running: boolean;
}

export interface TaskInput {
  name: string;
  urls: string[];
  output_folder: string;
  target_format: string;
  override_format: boolean;
  archive_format: string | null;
  cookies_file: string | null;
  create_subfolder: boolean;
  start_automatically: boolean;
}

export interface DownloadInput {
  urls: string[];
  output_folder: string;
  target_format: string;
  override_format: boolean;
  archive_format: string | null;
}

export interface ConfigState {
  path: string | null;
  exists: boolean;
  content: string;
}

export interface Settings {
  gallery_dl_config: string | null;
}

export interface Paths {
  app_data_dir: string;
  config_dir: string | null;
}

export type TaskStreamMessage =
  | { type: "history"; content: string }
  | { type: "task_updated"; task: Task }
  | { type: "log"; line: string }
  | { type: "progress"; current: number; total: number }
  | {
      type: "finished";
      success: boolean;
      error_message: string;
      task: Task | null;
    };

export type JobStreamMessage =
  | { type: "log"; line: string }
  | { type: "finished"; success: boolean; error_message: string };
