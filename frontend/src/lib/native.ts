/** Thin wrappers around Tauri plugins. Every call is wrapped in try/catch
 * since these are also no-ops (not errors) when the app runs outside a
 * Tauri webview, e.g. `vite dev` opened directly in a browser tab - but
 * real failures (bad path, missing permission, ...) are still logged so
 * they're visible in the webview's devtools instead of failing silently. */

export async function pickFolder(defaultPath?: string): Promise<string | null> {
  try {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const result = await open({ directory: true, defaultPath });
    return typeof result === "string" ? result : null;
  } catch (e) {
    console.error("pickFolder failed", e);
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
  } catch (e) {
    console.error("pickFile failed", e);
    return null;
  }
}

export async function revealFile(path: string): Promise<void> {
  try {
    const { revealItemInDir } = await import("@tauri-apps/plugin-opener");
    await revealItemInDir(path);
  } catch (e) {
    console.error("revealFile failed", path, e);
  }
}

export async function openFolder(path: string): Promise<void> {
  try {
    const { openPath } = await import("@tauri-apps/plugin-opener");
    await openPath(path);
  } catch (e) {
    console.error("openFolder failed", path, e);
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
  } catch (e) {
    console.error("notify failed", e);
  }
}
