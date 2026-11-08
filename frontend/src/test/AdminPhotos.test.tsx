import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AdminPhotosPage from '../pages/admin/AdminPhotosPage'
import { albumService } from '../services/albumService'
import { photoService, type AdminPhotoPage } from '../services/photoService'

vi.mock('../services/albumService', () => ({
  albumService: { listAlbums: vi.fn(), listEvents: vi.fn() },
  apiErrorMessage: (_error: unknown, fallback: string) => fallback,
}))
vi.mock('../services/photoService', () => ({
  photoService: { list: vi.fn(), preview: vi.fn(), approve: vi.fn(), reject: vi.fn(), bulkApprove: vi.fn(), remove: vi.fn() },
}))

const photo = {
  id: 'photo-1', original_filename: 'first-dance.png',
  album: { id: 'album-1', name: 'Our Wedding', slug: 'our-wedding' },
  event: { id: 'event-1', name: 'First Dance', slug: 'first-dance' },
  mime_type: 'image/png', file_size: 2048, width: 20, height: 14,
  status: 'pending' as const, uploaded_at: '2026-11-05T10:00:00Z', moderated_at: null, moderated_by: null,
}
const page: AdminPhotoPage = { items: [photo], total: 1, page: 1, page_size: 24, counts: { all: 1, pending: 1, approved: 0, rejected: 0, deletion_pending: 0 } }

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(albumService.listAlbums).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 })
  vi.mocked(photoService.list).mockResolvedValue(page)
  vi.mocked(photoService.preview).mockResolvedValue(new Blob(['image']))
  vi.mocked(photoService.approve).mockResolvedValue({ ...photo, status: 'approved' })
})
afterEach(cleanup)

describe('admin photo moderation', () => {
  it('lists pending photos and approves one', async () => {
    render(<MemoryRouter><AdminPhotosPage /></MemoryRouter>)
    expect(await screen.findByText('first-dance.png')).toBeInTheDocument()
    expect(screen.getByText('Our Wedding · First Dance')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(photoService.approve).toHaveBeenCalledWith('photo-1'))
    expect(await screen.findByRole('status')).toHaveTextContent('first-dance.png approved.')
  })

  it('bulk approves selected pending photos', async () => {
    vi.mocked(photoService.bulkApprove).mockResolvedValue({ results: [{ photo_id: photo.id, success: true, status: 'approved' }], succeeded: 1, failed: 0 })
    render(<MemoryRouter><AdminPhotosPage /></MemoryRouter>)
    await screen.findByText('first-dance.png')
    fireEvent.click(screen.getByRole('checkbox', { name: /Select first-dance.png/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Approve selected' }))
    await waitFor(() => expect(photoService.bulkApprove).toHaveBeenCalledWith(['photo-1']))
    expect(await screen.findByRole('status')).toHaveTextContent('1 photo approved')
  })

  it('retries a deletion-pending photo without asking for a second destructive confirmation', async () => {
    const deletionPhoto = { ...photo, status: 'approved' as const, deletion_state: 'pending' as const }
    const retryPage: AdminPhotoPage = { ...page, items: [deletionPhoto], counts: { ...page.counts, deletion_pending: 1 } }
    vi.mocked(photoService.list).mockImplementation(async (query) => query?.deletion_state ? retryPage : page)
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)

    render(<MemoryRouter><AdminPhotosPage /></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: 'Deletion retry' }))
    expect(await screen.findByText('This image is hidden from guests. Retry deletion when storage is available.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry deletion of first-dance.png' }))
    await waitFor(() => expect(photoService.remove).toHaveBeenCalledWith('photo-1'))
    expect(confirm).not.toHaveBeenCalled()
    expect(await screen.findByRole('status')).toHaveTextContent('first-dance.png deletion completed.')
    confirm.mockRestore()
  })
})
