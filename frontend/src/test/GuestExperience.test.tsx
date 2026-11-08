import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import GuestAlbumPage from '../pages/guest/GuestAlbumPage'
import GuestEventPage from '../pages/guest/GuestEventPage'
import { publicService } from '../services/publicService'
import PublicQrActions, { albumUrl, eventUrl } from '../components/admin/PublicQrActions'
import { PhotoUploader } from '../components/guest/PhotoUploader'

vi.mock('../services/publicService', () => ({
  publicService: {
    album: vi.fn(), event: vi.fn(), albumPhotos: vi.fn(), eventPhotos: vi.fn(), upload: vi.fn(),
  },
}))
vi.mock('qrcode.react', () => ({ QRCodeCanvas: ({ value }: { value: string }) => <canvas data-value={value} /> }))

const album = { name: 'Sharma Wedding', slug: 'sharma-wedding', description: 'A day together', couple_names: 'Anika & Rohan', event_date: null, location: null, cover_image: null }
const events = [{ name: 'Mehendi', slug: 'mehendi' }, { name: 'Wedding', slug: 'wedding' }]

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(publicService.albumPhotos).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 24 })
  vi.mocked(publicService.eventPhotos).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 24 })
})
afterEach(cleanup)

describe('guest album and event pages', () => {
  it('builds QR links from the configured public app origin', () => {
    expect(albumUrl('sharma wedding')).toBe(`${window.location.origin}/a/sharma%20wedding`)
    expect(eventUrl('sharma-wedding', 'mehendi')).toBe(`${window.location.origin}/a/sharma-wedding/e/mehendi`)
  })

  it('offers QR PNG download and copies the encoded public URL', async () => {
    const clipboardDescriptor = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue('data:image/png;base64,qr')
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    const url = albumUrl('sharma-wedding')
    render(<PublicQrActions url={url} label="Sharma Wedding" />)
    fireEvent.click(screen.getByRole('button', { name: 'QR & link' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download PNG' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Download PNG' }))
    fireEvent.click(screen.getByRole('button', { name: 'Copy URL' }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(url))
    expect(anchorClick).toHaveBeenCalledOnce()
    if (clipboardDescriptor) Object.defineProperty(navigator, 'clipboard', clipboardDescriptor)
    else delete (navigator as { clipboard?: Clipboard }).clipboard
  })

  it('renders actual event links and a real empty gallery state', async () => {
    vi.mocked(publicService.album).mockResolvedValue({ album, events })
    vi.mocked(publicService.event).mockImplementation(async (_album, eventSlug) => ({ album, event: { ...events.find((item) => item.slug === eventSlug)!, description: null, event_date: eventSlug === 'mehendi' ? '2026-02-14T00:00:00Z' : null, location: null, cover_image: null }, events }))
    vi.mocked(publicService.eventPhotos).mockResolvedValue({ items: [], total: 4, page: 1, page_size: 24 })
    render(<MemoryRouter initialEntries={['/a/sharma-wedding']}><Routes><Route path="/a/:albumSlug" element={<GuestAlbumPage />} /></Routes></MemoryRouter>)
    expect(await screen.findByRole('heading', { name: 'Sharma Wedding' })).toBeInTheDocument()
    const albumHero = screen.getByRole('heading', { name: 'Sharma Wedding' }).closest('header')
    expect(albumHero?.querySelector('img')).toBeNull()
    expect(albumHero).not.toHaveClass('min-h-[250px]')
    expect(screen.getByRole('link', { name: /Mehendi/ })).toHaveAttribute('href', '/a/sharma-wedding/e/mehendi')
    expect((await screen.findAllByText('4 photographs')).length).toBeGreaterThan(0)
    expect(screen.getByText('February 14, 2026')).toBeInTheDocument()
    expect(await screen.findByText('Approved photographs will appear here.')).toBeInTheDocument()
  })

  it('opens a gallery photo in the navigable, downloadable lightbox', async () => {
    vi.mocked(publicService.albumPhotos).mockResolvedValue({ items: [{ id: 'photo-1', image_url: 'http://localhost:8011/api/v1/public/photos/photo-1/image', mime_type: 'image/jpeg', file_size: 100, width: 1200, height: 800, uploaded_at: '2026-01-01' }], total: 1, page: 1, page_size: 24 })
    vi.mocked(publicService.album).mockResolvedValue({ album, events: [] })
    render(<MemoryRouter initialEntries={['/a/sharma-wedding']}><Routes><Route path="/a/:albumSlug" element={<GuestAlbumPage />} /></Routes></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: 'Open wedding photo 1' }))
    expect(screen.getByRole('dialog', { name: 'Photo preview' })).toBeInTheDocument()
    expect(document.documentElement.style.overflow).toBe('hidden')
    expect(screen.getByRole('dialog')).toHaveTextContent('1 / 1')
    expect(screen.getByRole('link', { name: 'Download photo' })).toHaveAttribute('href', expect.stringContaining('download=true'))
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Photo preview' })).not.toBeInTheDocument()
    expect(document.documentElement.style.overflow).toBe('')
  })

  it('keeps masonry items and images bounded within their responsive columns', async () => {
    vi.mocked(publicService.eventPhotos).mockResolvedValue({ items: [{ id: 'photo-2', image_url: 'http://localhost:8011/api/v1/public/photos/photo-2/image', mime_type: 'image/jpeg', file_size: 100, width: 2400, height: 600, uploaded_at: '2026-01-01' }], total: 1, page: 1, page_size: 24 })
    vi.mocked(publicService.event).mockResolvedValue({ album, event: { ...events[0], description: null, event_date: null, location: null, cover_image: null }, events })
    render(<MemoryRouter initialEntries={['/a/sharma-wedding/e/mehendi']}><Routes><Route path="/a/:albumSlug/e/:eventSlug" element={<GuestEventPage />} /></Routes></MemoryRouter>)
    const photo = await screen.findByRole('img', { name: 'Wedding memory 1' })
    const masonry = photo.parentElement?.parentElement
    expect(masonry).toHaveClass('columns-2', 'sm:columns-3', 'lg:columns-4')
    expect(photo.parentElement).toHaveClass('max-w-full')
    expect(photo).toHaveClass('h-auto', 'max-w-full')
    expect(photo).toHaveAttribute('width', '2400')
    expect(photo).toHaveAttribute('height', '600')
  })

  it('shows event navigation and previews multiple selected gallery files before upload', async () => {
    vi.mocked(publicService.event).mockResolvedValue({ album, event: { ...events[0], description: null, event_date: null, location: null, cover_image: null }, events })
    vi.mocked(publicService.upload).mockImplementation(async (_a, _e, files, onProgress) => {
      onProgress(100, 100)
      return { succeeded: files.length, failed: 0, results: files.map(({ file }) => ({ success: true, filename: file.name, status: 'pending' })) }
    })
    vi.spyOn(URL, 'createObjectURL').mockImplementation((file) => `blob:${(file as File).name}`)
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    render(<MemoryRouter initialEntries={['/a/sharma-wedding/e/mehendi']}><Routes><Route path="/a/:albumSlug/e/:eventSlug" element={<GuestEventPage />} /></Routes></MemoryRouter>)
    expect(await screen.findByRole('heading', { name: 'Mehendi' })).toBeInTheDocument()
    const eventHero = screen.getByRole('heading', { name: 'Mehendi' }).closest('header')
    expect(eventHero).toHaveClass('px-5', 'py-7')
    expect(eventHero?.querySelector('img')).toBeNull()
    expect(screen.getByRole('link', { name: 'Wedding' })).toHaveAttribute('href', '/a/sharma-wedding/e/wedding')
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const one = new File(['one'], 'one.jpg', { type: 'image/jpeg' })
    const two = new File(['two'], 'two.png', { type: 'image/png' })
    fireEvent.change(input, { target: { files: [one, two] } })
    expect(screen.getByText('Your selection')).toBeInTheDocument()
    expect(screen.getByText('one.jpg')).toBeInTheDocument()
    expect(screen.getByText('two.png')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Upload photos' }))
    await waitFor(() => expect(publicService.upload).toHaveBeenCalledWith('sharma-wedding', 'mehendi', expect.arrayContaining([expect.objectContaining({ file: one }), expect.objectContaining({ file: two })]), expect.any(Function)))
    expect(await screen.findByText('Your photos have been submitted successfully!')).toBeInTheDocument()
    expect(screen.getByText('Your photos are now awaiting approval. Once approved, they will appear in the wedding gallery.')).toBeInTheDocument()
    expect(screen.queryByText('Your selection')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Upload photos' })).not.toBeInTheDocument()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:one.jpg')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:two.png')
  })

  it('removes only successful files and retries only the failed file', async () => {
    vi.mocked(publicService.upload)
      .mockResolvedValueOnce({ succeeded: 2, failed: 1, results: [
        { success: true, filename: 'one.jpg', status: 'pending' },
        { success: false, filename: 'two.png', error: 'Image could not be saved.' },
        { success: true, filename: 'three.webp', status: 'pending' },
      ] })
      .mockResolvedValueOnce({ succeeded: 1, failed: 0, results: [
        { success: true, filename: 'two.png', status: 'pending' },
      ] })
    vi.spyOn(URL, 'createObjectURL').mockImplementation((file) => `blob:${(file as File).name}`)
    const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    render(<PhotoUploader albumSlug="sharma-wedding" eventSlug="mehendi" />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const files = [
      new File(['one'], 'one.jpg', { type: 'image/jpeg' }),
      new File(['two'], 'two.png', { type: 'image/png' }),
      new File(['three'], 'three.webp', { type: 'image/webp' }),
    ]
    fireEvent.change(input, { target: { files } })
    fireEvent.click(screen.getByRole('button', { name: 'Upload photos' }))

    expect(await screen.findByRole('status')).toHaveTextContent('2 photos uploaded successfully, 1 failed.')
    expect(screen.getByRole('heading', { name: /Your selection/ })).toHaveTextContent('(1)')
    expect(screen.queryByText('one.jpg')).not.toBeInTheDocument()
    expect(screen.getByText('two.png')).toBeInTheDocument()
    expect(screen.queryByText('three.webp')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry failed (1)' })).toBeInTheDocument()
    expect(revoke).toHaveBeenCalledWith('blob:one.jpg')
    expect(revoke).toHaveBeenCalledWith('blob:three.webp')
    expect(revoke).not.toHaveBeenCalledWith('blob:two.png')

    fireEvent.click(screen.getByRole('button', { name: 'Retry failed (1)' }))
    await waitFor(() => expect(publicService.upload).toHaveBeenCalledTimes(2))
    expect(publicService.upload).toHaveBeenLastCalledWith('sharma-wedding', 'mehendi', [expect.objectContaining({ file: files[1] })], expect.any(Function))
    expect(await screen.findByText('Your photos have been submitted successfully!')).toBeInTheDocument()
    expect(screen.queryByText('Your selection')).not.toBeInTheDocument()
    expect(revoke).toHaveBeenCalledWith('blob:two.png')
  })

  it('disables further submissions while an upload request is still running', async () => {
    let finishUpload: ((value: { succeeded: number; failed: number; results: { success: boolean; filename: string; status: string }[] }) => void) | undefined
    vi.mocked(publicService.upload).mockImplementationOnce(() => new Promise((resolve) => { finishUpload = resolve }))
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:once')
    render(<PhotoUploader albumSlug="sharma-wedding" eventSlug="mehendi" />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['one'], 'one.jpg', { type: 'image/jpeg' })
    fireEvent.change(input, { target: { files: [file] } })
    const uploadButton = screen.getByRole('button', { name: 'Upload photos' })
    fireEvent.click(uploadButton)
    expect(screen.getByRole('button', { name: 'Uploading…' })).toBeDisabled()
    expect(publicService.upload).toHaveBeenCalledTimes(1)
    finishUpload?.({ succeeded: 1, failed: 0, results: [{ success: true, filename: 'one.jpg', status: 'pending' }] })
    expect(await screen.findByText('Your photos have been submitted successfully!')).toBeInTheDocument()
  })

  it('explains camera fallback when getUserMedia is unavailable', async () => {
    const descriptor = Object.getOwnPropertyDescriptor(navigator, 'mediaDevices')
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: undefined })
    render(<PhotoUploader albumSlug="sharma-wedding" eventSlug="mehendi" />)
    fireEvent.click(screen.getByRole('button', { name: 'Take photos' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/Camera access is unavailable/)
    expect(screen.getByRole('button', { name: 'Use camera picker' })).toBeInTheDocument()
    if (descriptor) Object.defineProperty(navigator, 'mediaDevices', descriptor)
    else delete (navigator as { mediaDevices?: MediaDevices }).mediaDevices
  })
})
