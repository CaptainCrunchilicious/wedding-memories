import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AdminStoragePage from '../pages/admin/AdminStoragePage'
import { storageService, type StorageStatus, type StorageProvider } from '../services/storageService'

vi.mock('../services/storageService', () => ({
  storageService: { status: vi.fn(), connect: vi.fn(), disconnect: vi.fn(), selectProvider: vi.fn() },
}))

let selectedProvider: StorageProvider = 'local'
function status(): StorageStatus {
  return {
    provider: selectedProvider,
    google_drive: { configured: true, connected: true, operational: true, connected_email: 'owner@example.com', folder_status: 'ready', last_successful_check: '2026-11-06T06:00:00Z' },
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  selectedProvider = 'local'
  vi.mocked(storageService.status).mockImplementation(async () => status())
  vi.mocked(storageService.selectProvider).mockImplementation(async (provider) => {
    selectedProvider = provider
    return { provider }
  })
})
afterEach(cleanup)

describe('admin storage settings', () => {
  it('shows Drive health and confirms provider changes for new uploads', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<MemoryRouter><AdminStoragePage /></MemoryRouter>)
    expect(await screen.findByText('owner@example.com')).toBeInTheDocument()
    expect(screen.getByText('Connected and ready')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Use Google Drive for new uploads' }))
    await waitFor(() => expect(storageService.selectProvider).toHaveBeenCalledWith('google_drive'))
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('Existing photos will continue to use their current storage provider.'))
    expect(await screen.findByText('Google Drive', { selector: 'h2' })).toBeInTheDocument()
  })
})
