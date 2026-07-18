use std::sync::Mutex;
use std::time::Duration;

use tauri::{Manager, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

#[derive(Clone, serde::Serialize)]
struct BackendInfo {
    port: u16,
    token: String,
}

#[derive(Default)]
struct BackendState {
    info: Mutex<Option<BackendInfo>>,
    child: Mutex<Option<CommandChild>>,
}

/// The frontend calls this once on load to learn where the backend sidecar
/// ended up listening. setup() spawns it in the background and this just
/// waits for the two handshake lines it prints on startup to be parsed.
#[tauri::command]
async fn get_backend_info(state: State<'_, BackendState>) -> Result<BackendInfo, String> {
    for _ in 0..200 {
        if let Some(info) = state.info.lock().unwrap().clone() {
            return Ok(info);
        }
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
    Err("backend did not start in time".into())
}

fn spawn_backend(app: &tauri::AppHandle) {
    let (mut rx, child) = app
        .shell()
        .sidecar("arcgdlw-backend")
        .expect("failed to resolve backend sidecar")
        .args(["--serve", "--host", "127.0.0.1", "--port", "0"])
        .spawn()
        .expect("failed to spawn backend sidecar");

    let state: State<BackendState> = app.state();
    *state.child.lock().unwrap() = Some(child);

    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    let line = String::from_utf8_lossy(&bytes);
                    let line = line.trim();
                    let state: State<BackendState> = app_handle.state();
                    let mut info = state.info.lock().unwrap();
                    if let Some(port_str) = line.strip_prefix("ARCGDLW-PORT=") {
                        if let Ok(port) = port_str.parse::<u16>() {
                            let token = info.as_ref().map(|i| i.token.clone()).unwrap_or_default();
                            *info = Some(BackendInfo { port, token });
                        }
                    } else if let Some(token) = line.strip_prefix("ARCGDLW-TOKEN=") {
                        let port = info.as_ref().map(|i| i.port).unwrap_or(0);
                        *info = Some(BackendInfo { port, token: token.to_string() });
                    }
                }
                CommandEvent::Stderr(bytes) => {
                    log::warn!("[backend] {}", String::from_utf8_lossy(&bytes).trim());
                }
                CommandEvent::Error(err) => {
                    log::error!("[backend] failed to run: {err}");
                }
                _ => {}
            }
        }
    });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_notification::init())
        .manage(BackendState::default())
        .invoke_handler(tauri::generate_handler![get_backend_info])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            spawn_backend(app.handle());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| {
        // Covers window close, Cmd+Q, and any other exit path - the backend
        // sidecar is a child process and won't die with the parent on its
        // own on every platform, so it's killed explicitly here.
        if let tauri::RunEvent::ExitRequested { .. } = event {
            let state: State<BackendState> = app_handle.state();
            let child = state.child.lock().unwrap().take();
            if let Some(child) = child {
                let _ = child.kill();
            }
        }
    });
}
