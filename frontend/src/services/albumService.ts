import { apiClient } from './apiClient'

export type ResourceStatus = 'active' | 'archived'
export type CoverImageReference = { url?: string; reference?: string; alt_text?: string }

export type Album = {
  id: string
  name: string
  slug: string
  description: string | null
  couple_names: string | null
  event_date: string | null
  location: string | null
  cover_image: CoverImageReference | null
  status: ResourceStatus
  event_count: number
  created_at: string
  updated_at: string
}

export type Event = {
  id: string
  album_id: string
  name: string
  slug: string
  description: string | null
  event_date: string | null
  location: string | null
  cover_image: CoverImageReference | null
  status: ResourceStatus
  display_order: number
  created_at: string
  updated_at: string
}

export type Page<T> = { items: T[]; total: number; page: number; page_size: number }
export type AlbumInput = {
  name: string
  slug?: string | null
  description?: string | null
  couple_names?: string | null
  event_date?: string | null
  location?: string | null
  cover_image?: CoverImageReference | null
}
export type EventInput = {
  name: string
  slug?: string | null
  description?: string | null
  event_date?: string | null
  location?: string | null
  display_order?: number
  cover_image?: CoverImageReference | null
}

type ListOptions = { page?: number; page_size?: number; status?: ResourceStatus; search?: string }

export const albumService = {
  async listAlbums(options: ListOptions = {}): Promise<Page<Album>> {
    const { data } = await apiClient.get<Page<Album>>('/albums', { params: options })
    return data
  },
  async getAlbum(albumId: string): Promise<Album> {
    const { data } = await apiClient.get<Album>(`/albums/${albumId}`)
    return data
  },
  async createAlbum(input: AlbumInput): Promise<Album> {
    const { data } = await apiClient.post<Album>('/albums', input)
    return data
  },
  async updateAlbum(albumId: string, input: Partial<AlbumInput>): Promise<Album> {
    const { data } = await apiClient.patch<Album>(`/albums/${albumId}`, input)
    return data
  },
  async archiveAlbum(albumId: string): Promise<Album> {
    const { data } = await apiClient.patch<Album>(`/albums/${albumId}/archive`)
    return data
  },
  async restoreAlbum(albumId: string): Promise<Album> {
    const { data } = await apiClient.patch<Album>(`/albums/${albumId}/restore`)
    return data
  },
  async deleteAlbum(albumId: string): Promise<void> {
    await apiClient.delete(`/albums/${albumId}`)
  },
  async listEvents(albumId: string, options: Omit<ListOptions, 'search'> = {}): Promise<Page<Event>> {
    const { data } = await apiClient.get<Page<Event>>(`/albums/${albumId}/events`, { params: options })
    return data
  },
  async getEvent(albumId: string, eventId: string): Promise<Event> {
    const { data } = await apiClient.get<Event>(`/albums/${albumId}/events/${eventId}`)
    return data
  },
  async createEvent(albumId: string, input: EventInput): Promise<Event> {
    const { data } = await apiClient.post<Event>(`/albums/${albumId}/events`, input)
    return data
  },
  async updateEvent(albumId: string, eventId: string, input: Partial<EventInput>): Promise<Event> {
    const { data } = await apiClient.patch<Event>(`/albums/${albumId}/events/${eventId}`, input)
    return data
  },
  async archiveEvent(albumId: string, eventId: string): Promise<Event> {
    const { data } = await apiClient.patch<Event>(`/albums/${albumId}/events/${eventId}/archive`)
    return data
  },
  async restoreEvent(albumId: string, eventId: string): Promise<Event> {
    const { data } = await apiClient.patch<Event>(`/albums/${albumId}/events/${eventId}/restore`)
    return data
  },
  async deleteEvent(albumId: string, eventId: string): Promise<void> {
    await apiClient.delete(`/albums/${albumId}/events/${eventId}`)
  },
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response
    if (typeof response?.data?.detail === 'string') return response.data.detail
  }
  return fallback
}
