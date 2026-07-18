// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
  #[cfg(target_os = "linux")]
  set_linux_webkit_compat_defaults();

  arcgdlw_lib::run();
}

/// WebKitGTK's Wayland + DMA-BUF hardware compositing path is unreliable
/// across GPU drivers/compositors - symptoms range from a Wayland protocol
/// error that kills the window outright to a blank gray window with
/// "Failed to create GBM buffer" in stderr. Falling back to XWayland and the
/// older (non-DMA-BUF) renderer is far more broadly compatible, so default
/// to that unless the user has already set these themselves.
#[cfg(target_os = "linux")]
fn set_linux_webkit_compat_defaults() {
  for (key, value) in [("GDK_BACKEND", "x11"), ("WEBKIT_DISABLE_DMABUF_RENDERER", "1")] {
    if std::env::var_os(key).is_none() {
      // SAFETY: called at the very start of main(), before any other
      // thread exists or reads the environment.
      unsafe { std::env::set_var(key, value) };
    }
  }
}
