/** Thin wrappers around Tauri plugins. Every call is wrapped in try/catch
 * because these are no-ops (not errors) when the app runs outside a Tauri
 * webview, e.g. `vite dev` opened directly in a browser tab. */

export async function pickFolder(defaultPath?: string): Promise<string | null> {
  try {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const result = await open({ directory: true, defaultPath });
    return typeof result === "string" ? result : null;
  } catch {
    return null;
  }
}

export async function pickFile(
  defaultPath: string | undefined,
  extensions: string[],
): Promise<string | null> {
  try {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const result = await open({
      directory: false,
      multiple: false,
      defaultPath,
      filters: [{ name: "Allowed files", extensions }],
    });
    return typeof result === "string" ? result : null;
  } catch {
    return null;
  }
}

export async function revealFile(path: string): Promise<void> {
  try {
    const { revealItemInDir } = await import("@tauri-apps/plugin-opener");
    await revealItemInDir(path);
  } catch {
    // not running inside Tauri; nothing we can do
  }
}

export async function openFolder(path: string): Promise<void> {
  try {
    const { openPath } = await import("@tauri-apps/plugin-opener");
    await openPath(path);
  } catch {
    // not running inside Tauri; nothing we can do
  }
}

export async function notify(title: string, body: string): Promise<void> {
  try {
    const { isPermissionGranted, requestPermission, sendNotification } = await import(
      "@tauri-apps/plugin-notification"
    );
    let granted = await isPermissionGranted();
    if (!granted) {
      granted = (await requestPermission()) === "granted";
    }
    if (granted) {
      sendNotification({ title, body });
    }
  } catch {
    // not running inside Tauri; nothing we can do
  }
}
