import axios from 'axios'
import { API_BASE_URL } from '../config/api'

const client = axios.create({ baseURL: API_BASE_URL })

export type PublicAlbum = {
  name: string; slug: string; description: string | null; couple_names: string | null
  event_date: string | null; location: string | null; cover_image: { url?: string; reference?: string; alt_text?: string } | null
}
export type PublicEvent = {
  name: string; slug: string; description: string | null; event_date: string | null
  location: string | null; cover_image: PublicAlbum['cover_image']
}
export type AlbumGuestData = { album: PublicAlbum; events: Pick<PublicEvent, 'name' | 'slug'>[] }
export type EventGuestData = { album: PublicAlbum; event: PublicEvent; events: Pick<PublicEvent, 'name' | 'slug'>[] }
export type PhotoResult = { success: boolean; filename: string; photo_id?: string; status?: string; error?: string }
export type PublicPhoto = { id: string; image_url: string; mime_type: string; file_size: number; width: number; height: number; uploaded_at: string }
export type PublicPhotoPage = { items: PublicPhoto[]; total: number; page: number; page_size: number }

export const publicService = {
  async album(slug: string) {
    return (await client.get<AlbumGuestData>(`/public/albums/${encodeURIComponent(slug)}`)).data
  },
  async event(albumSlug: string, eventSlug: string) {
    return (await client.get<EventGuestData>(`/public/albums/${encodeURIComponent(albumSlug)}/events/${encodeURIComponent(eventSlug)}`)).data
  },
  async albumPhotos(albumSlug: string, page: number) {
    const data = (await client.get<PublicPhotoPage>(`/public/albums/${encodeURIComponent(albumSlug)}/photos`, { params: { page, page_size: 24 } })).data
    return { ...data, items: data.items.map((photo) => ({ ...photo, image_url: new URL(photo.image_url, API_BASE_URL).toString() })) }
  },
  async eventPhotos(albumSlug: string, eventSlug: string, page: number) {
    const data = (await client.get<PublicPhotoPage>(`/public/albums/${encodeURIComponent(albumSlug)}/events/${encodeURIComponent(eventSlug)}/photos`, { params: { page, page_size: 24 } })).data
    return { ...data, items: data.items.map((photo) => ({ ...photo, image_url: new URL(photo.image_url, API_BASE_URL).toString() })) }
  },
  async upload(album: string, event: string, files: { id: string; file: File }[], onProgress: (loaded: number, total: number) => void) {
    const session = (await client.post<{ token: string; max_files: number; max_file_bytes: number }>(
      `/public/albums/${encodeURIComponent(album)}/events/${encodeURIComponent(event)}/upload-session`,
    )).data
    const form = new FormData()
    form.append('upload_token', session.token)
    files.forEach(({ id, file }) => { form.append('upload_ids', id); form.append('files', file, file.name) })
    const { data } = await client.post<{ results: PhotoResult[]; succeeded: number; failed: number }>(
      `/public/albums/${encodeURIComponent(album)}/events/${encodeURIComponent(event)}/photos`, form,
      { onUploadProgress: (event) => onProgress(event.loaded, event.total || files.reduce((sum, item) => sum + item.file.size, 0)) },
    )
    return data
  },
}
