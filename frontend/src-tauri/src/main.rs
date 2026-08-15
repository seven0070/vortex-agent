//! Vortex Agent - Tauri 2.x Desktop Application Entry Point

use std::sync::Mutex;

use tauri::{Emitter, Manager, State};

/// Holds the running backend child process (if any).
struct BackendState(Mutex<Option<tauri_plugin_shell::process::CommandChild>>);

fn main() {
    // Initialize tracing for structured logging
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_os::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .manage(BackendState(Mutex::new(None)))
        .setup(|app| {
            // Get the main window
            let window = app.get_webview_window("main").unwrap();

            // Set window title
            window.set_title("Vortex Agent").unwrap();

            // Center window on screen
            window.center().unwrap();

            // Show window
            window.show().unwrap();

            // Emit ready event to frontend
            window.emit("tauri-ready", ()).unwrap();

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            greet,
            start_backend,
            stop_backend,
            get_backend_status
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

/// Simple greeting command for testing IPC
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! Welcome to Vortex Agent.", name)
}

/// Start the Vortex backend server (bundled executable or python dev mode).
#[tauri::command]
async fn start_backend(app: tauri::AppHandle, state: State<'_, BackendState>) -> Result<String, String> {
    use tauri_plugin_shell::ShellExt;

    // Refuse to double-start
    {
        let guard = state.0.lock().map_err(|_| "backend state poisoned")?;
        if guard.is_some() {
            return Ok("Backend already running".to_string());
        }
    }

    let shell = app.shell();

    // Prefer the PyInstaller-bundled executable (shipped next to the app);
    // fall back to `python -m uvicorn` for dev.
    let mut cmd = shell.sidecar("vortex-backend")
        .map_err(|_| "sidecar not configured")?;
    if !std::path::Path::new("vortex-backend").exists()
        && !std::path::Path::new("vortex-backend.exe").exists()
    {
        cmd = shell
            .command("python")
            .args([
                "-m", "uvicorn",
                "app.main:app",
                "--host", "0.0.0.0",
                "--port", "8000",
            ])
            .current_dir("../backend");
    }

    let (mut rx, child) = cmd
        .spawn()
        .map_err(|e| format!("Failed to spawn backend: {}", e))?;

    // Track the child so stop_backend can kill it
    {
        let mut guard = state.0.lock().map_err(|_| "backend state poisoned")?;
        *guard = Some(child);
    }

    // Read stdout/stderr for logging
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                tauri_plugin_shell::process::CommandEvent::Stdout(line) => {
                    tracing::info!("[Backend] {}", String::from_utf8_lossy(&line));
                }
                tauri_plugin_shell::process::CommandEvent::Stderr(line) => {
                    tracing::warn!("[Backend Err] {}", String::from_utf8_lossy(&line));
                }
                _ => {}
            }
        }
    });

    Ok("Backend started".to_string())
}

/// Stop the backend server: kill the tracked child process.
#[tauri::command]
async fn stop_backend(state: State<'_, BackendState>) -> Result<String, String> {
    let mut guard = state.0.lock().map_err(|_| "backend state poisoned")?;
    if let Some(child) = guard.take() {
        // Kill the process tree so uvicorn's reloader worker dies too.
        child.kill().map_err(|e| format!("Failed to kill backend: {}", e))?;
        Ok("Backend stopped".to_string())
    } else {
        Ok("Backend not running".to_string())
    }
}

/// Get backend status: whether we spawned a process, plus live health check.
#[tauri::command]
async fn get_backend_status(state: State<'_, BackendState>) -> Result<serde_json::Value, String> {
    let is_spawned = {
        let guard = state.0.lock().map_err(|_| "backend state poisoned")?;
        guard.is_some()
    };

    // Best-effort HTTP health check
    let healthy = match reqwest::blocking::get("http://localhost:8000/api/v1/health") {
        Ok(resp) => resp.status().is_success(),
        Err(_) => false,
    };

    Ok(serde_json::json!({
        "running": is_spawned || healthy,
        "spawned": is_spawned,
        "healthy": healthy,
        "message": if healthy { "Backend healthy" } else if is_spawned { "Backend starting" } else { "Backend not running" }
    }))
}
