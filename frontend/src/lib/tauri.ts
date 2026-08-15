import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'

export interface BackendStatus {
  running: boolean
  message: string
}

export async function startBackend(): Promise<string> {
  return await invoke('start_backend')
}

export async function stopBackend(): Promise<string> {
  return await invoke('stop_backend')
}

export async function getBackendStatus(): Promise<BackendStatus> {
  return await invoke('get_backend_status')
}

export async function greet(name: string): Promise<string> {
  return await invoke('greet', { name })
}

export function onTauriReady(callback: () => void): Promise<() => void> {
  return listen('tauri-ready', callback)
}