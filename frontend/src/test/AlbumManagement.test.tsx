import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import AdminAlbumsPage from '../pages/admin/AdminAlbumsPage'
import AlbumDetailsPage from '../pages/admin/AlbumDetailsPage'
import AlbumForm from '../components/admin/AlbumForm'
import EventForm from '../components/admin/EventForm'
import { albumService } from '../services/albumService'
import type { Album, Event, Page } from '../services/albumService'

vi.mock('../services/albumService', () => ({
  albumService: {
    listAlbums: vi.fn(), getAlbum: vi.fn(), createAlbum: vi.fn(), updateAlbum: vi.fn(),
    archiveAlbum: vi.fn(), restoreAlbum: vi.fn(), deleteAlbum: vi.fn(), listEvents: vi.fn(),
    getEvent: vi.fn(), createEvent: vi.fn(), updateEvent: vi.fn(), archiveEvent: vi.fn(),
    restoreEvent: vi.fn(), deleteEvent: vi.fn(),
  },
  apiErrorMessage: (_error: unknown, fallback: string) => fallback,
}))

const album: Album = {
  id: 'aaaaaaaaaaaaaaaaaaaaaaaa',
  name: 'Sharma Wedding 2026',
  slug: 'sharma-wedding-2026',
  description: 'A family celebration',
  couple_names: 'Anika & Rohan',
  event_date: '2026-12-05',
  location: 'Jaipur',
  cover_image: null,
  status: 'active',
  event_count: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const event: Event = {
  id: 'bbbbbbbbbbbbbbbbbbbbbbbb',
  album_id: album.id,
  name: 'Mehendi',
  slug: 'mehendi',
  description: 'An evening of music',
  event_date: '2026-12-03T18:00:00Z',
  location: 'Garden courtyard',
  cover_image: null,
  status: 'active',
  display_order: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function page<T>(items: T[]): Page<T> { return { items, total: items.length, page: 1, page_size: 20 } }

function renderAlbums() {
  return render(<MemoryRouter><AdminAlbumsPage /></MemoryRouter>)
}

function renderDetails() {
  return render(
    <MemoryRouter initialEntries={[`/admin/albums/${album.id}`]}>
      <Routes><Route path="/admin/albums/:albumId" element={<AlbumDetailsPage />} /></Routes>
    </MemoryRouter>,
  )
}

describe('album and event management UI', () => {
  beforeEach(() => {
    vi.mocked(albumService.listAlbums).mockReset()
    vi.mocked(albumService.getAlbum).mockReset()
    vi.mocked(albumService.listEvents).mockReset()
    vi.mocked(albumService.createAlbum).mockReset()
    vi.mocked(albumService.updateAlbum).mockReset()
    vi.mocked(albumService.createEvent).mockReset()
    vi.mocked(albumService.listAlbums).mockResolvedValue(page([]))
    vi.mocked(albumService.getAlbum).mockResolvedValue(album)
    vi.mocked(albumService.listEvents).mockResolvedValue(page([event]))
  })

  afterEach(() => cleanup())

  it('shows loading, albums, filtering controls, and the empty state', async () => {
    let resolveList!: (result: Page<Album>) => void
    vi.mocked(albumService.listAlbums).mockReturnValue(new Promise((resolve) => { resolveList = resolve }))
    renderAlbums()
    expect(screen.getByRole('status')).toHaveTextContent('Loading albums')
    resolveList(page([album]))
    expect(await screen.findByText('Sharma Wedding 2026')).toBeInTheDocument()
    expect(screen.getByText('Anika & Rohan')).toBeInTheDocument()
    expect(screen.getByText('1 event')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Filter album status' })).toBeInTheDocument()

    vi.mocked(albumService.listAlbums).mockResolvedValue(page([]))
    renderAlbums()
    expect(await screen.findByText('Your first album starts here')).toBeInTheDocument()
  })

  it('shows a useful album list API error', async () => {
    vi.mocked(albumService.listAlbums).mockRejectedValue(new Error('offline'))
    renderAlbums()
    expect(await screen.findByRole('alert')).toHaveTextContent('Albums could not be loaded. Please try again.')
  })

  it('validates and submits album create and edit forms', async () => {
    const user = userEvent.setup()
    const create = vi.fn().mockResolvedValue(undefined)
    const { rerender } = render(<AlbumForm onSubmit={create} onCancel={vi.fn()} />)
    await user.type(screen.getByLabelText(/Album name/), 'Verma Wedding 2027')
    expect(screen.getByText('/a/verma-wedding-2027')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Create album' }))
    await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Verma Wedding 2027', slug: null, event_date: null, cover_image: null,
    })))

    const update = vi.fn().mockResolvedValue(undefined)
    rerender(<AlbumForm initial={album} onSubmit={update} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/Album name/), { target: { value: 'Edited Wedding' } })
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(update).toHaveBeenCalledWith(expect.objectContaining({ name: 'Edited Wedding' })))
  })

  it('lists album events and validates the contextual event form', async () => {
    const user = userEvent.setup()
    renderDetails()
    expect(await screen.findByRole('heading', { name: 'Sharma Wedding 2026' })).toBeInTheDocument()
    expect(screen.getByText('Mehendi')).toBeInTheDocument()
    expect(screen.getByText('http://localhost:3000/a/sharma-wedding-2026/e/mehendi')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'New event' }))
    await user.type(screen.getByLabelText(/Event name/), '   ')
    await user.click(screen.getByRole('button', { name: 'Create event' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Event name is required.')
    expect(albumService.createEvent).not.toHaveBeenCalled()
  })

  it('validates event fields and passes album-independent data to the form callback', async () => {
    const user = userEvent.setup()
    const submit = vi.fn().mockResolvedValue(undefined)
    render(<EventForm onSubmit={submit} onCancel={vi.fn()} />)
    await user.type(screen.getByLabelText(/Event name/), 'Reception')
    expect(screen.getByText('/a/album/e/reception')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Display order'), { target: { value: '3' } })
    await user.click(screen.getByRole('button', { name: 'Create event' }))
    await waitFor(() => expect(submit).toHaveBeenCalledWith(expect.objectContaining({ name: 'Reception', display_order: 3 })))
    expect(submit.mock.calls[0][0]).not.toHaveProperty('album_id')
  })
})
