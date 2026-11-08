import { apiClient } from './apiClient'

export type StorageProvider = 'local' | 'google_drive'
export type GoogleDriveStatus = {
  configured: boolean
  connected: boolean
  operational: boolean
  connected_email: string | null
  folder_status: string
  last_successful_check: string | null
}
export type StorageStatus = { provider: StorageProvider; google_drive: GoogleDriveStatus }

export const storageService = {
  async status() {
    return (await apiClient.get<StorageStatus>('/admin/storage/status')).data
  },
  async connect() {
    return (await apiClient.post<{ authorization_url: string }>('/integrations/google-drive/connect')).data
  },
  async disconnect() {
    return (await apiClient.post<{ disconnected: boolean; provider: StorageProvider }>('/integrations/google-drive/disconnect')).data
  },
  async selectProvider(provider: StorageProvider) {
    return (await apiClient.patch<{ provider: StorageProvider }>('/admin/storage/provider', { provider })).data
  },
}
