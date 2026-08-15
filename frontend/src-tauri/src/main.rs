//! Vortex Agent - Tauri 2.x Desktop Application Entry Point

use tauri::{Emitter, Manager};

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
            // Backend commands will be registered here
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

/// Start the Vortex backend server
#[tauri::command]
async fn start_backend(app_handle: tauri::AppHandle) -> Result<String, String> {
    use tauri_plugin_shell::ShellExt;

    let shell = app_handle.shell();

    // Start the Python backend using the configured shell command
    let (mut rx, _child) = shell
        .command("python")
        .args([
            "-m", "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", "8000"
        ])
        .current_dir("../backend")
        .spawn()
        .map_err(|e| format!("Failed to spawn backend: {}", e))?;

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

/// Stop the backend server
#[tauri::command]
async fn stop_backend() -> Result<String, String> {
    // In a real implementation, we'd track the child process and kill it
    Ok("Backend stop requested".to_string())
}

/// Get backend status
#[tauri::command]
async fn get_backend_status() -> Result<serde_json::Value, String> {
    // In a real implementation, we'd check if the backend process is running
    // and possibly call its health endpoint
    Ok(serde_json::json!({
        "running": false,
        "message": "Status check not fully implemented"
    }))
}