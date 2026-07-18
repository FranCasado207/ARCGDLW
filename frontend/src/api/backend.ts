export interface BackendInfo {
  port: number;
  token: string;
}

let cached: Promise<BackendInfo> | null = null;

/**
 * In `npm run tauri dev`, the backend is started by hand (or by a dev
 * script) as a plain process on a known port with ARCGDLW_DEV_TOKEN set, so
 * .env.development just points straight at it. In the packaged app, the
 * Rust shell spawns the backend as a sidecar, captures its stdout-printed
 * port + token, and hands them back through the `get_backend_info` command.
 */
export function getBackendInfo(): Promise<BackendInfo> {
  if (!cached) {
    cached = resolve();
  }
  return cached;
}

async function resolve(): Promise<BackendInfo> {
  const devPort = import.meta.env.VITE_BACKEND_PORT;
  const devToken = import.meta.env.VITE_BACKEND_TOKEN;
  if (devPort && devToken) {
    return { port: Number(devPort), token: devToken };
  }

  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<BackendInfo>("get_backend_info");
}
