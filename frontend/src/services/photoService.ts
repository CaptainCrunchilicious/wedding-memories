import { apiClient } from './apiClient'

export type PhotoStatus = 'pending' | 'approved' | 'rejected'
export type AdminPhoto = {
  id: string; original_filename: string
  album: { id: string; name: string; slug: string | null }
  event: { id: string; name: string; slug: string | null }
  mime_type: string | null; file_size: number | null; width: number | null; height: number | null
  storage_provider?: 'local' | 'google_drive'
  deletion_state?: 'pending' | null
  status: PhotoStatus; uploaded_at: string | null; moderated_at: string | null; moderated_by: string | null
}
export type AdminPhotoPage = {
  items: AdminPhoto[]; total: number; page: number; page_size: number
  counts: { all: number; pending: number; approved: number; rejected: number; deletion_pending: number }
}
export type PhotoQuery = { page?: number; page_size?: number; status?: PhotoStatus; deletion_state?: 'pending'; album_id?: string; event_id?: string; search?: string }
export type PhotoActionResult = { photo_id: string; success: boolean; status?: PhotoStatus; error?: string }

export const photoService = {
  async list(query: PhotoQuery = {}) {
    return (await apiClient.get<AdminPhotoPage>('/admin/photos', { params: query })).data
  },
  async preview(photoId: string) {
    return (await apiClient.get<Blob>(`/admin/photos/${photoId}/image`, { responseType: 'blob' })).data
  },
  async approve(photoId: string) {
    return (await apiClient.patch<AdminPhoto>(`/admin/photos/${photoId}/approve`)).data
  },
  async reject(photoId: string) {
    return (await apiClient.patch<AdminPhoto>(`/admin/photos/${photoId}/reject`)).data
  },
  async bulkApprove(photoIds: string[]) {
    return (await apiClient.post<{ results: PhotoActionResult[]; succeeded: number; failed: number }>(
      '/admin/photos/bulk-approve', { photo_ids: photoIds },
    )).data
  },
  async remove(photoId: string) {
    await apiClient.delete(`/admin/photos/${photoId}`)
  },
}
