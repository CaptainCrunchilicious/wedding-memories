import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'
import { AuthProvider } from '../context/AuthContext'
import { ADMIN_TOKEN_KEY } from '../config/api'
import { authService } from '../services/authService'
import { albumService } from '../services/albumService'

vi.mock('../services/authService', () => ({
  authService: {
    login: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
  },
}))

vi.mock('../services/albumService', () => ({
  albumService: { listAlbums: vi.fn() },
  apiErrorMessage: (_error: unknown, fallback: string) => fallback,
}))

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('admin authentication routes', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.mocked(authService.login).mockReset()
    vi.mocked(authService.logout).mockReset()
    vi.mocked(authService.me).mockReset()
    vi.mocked(authService.me).mockResolvedValue({ authenticated: true, admin: { email: 'owner@example.com' } })
    vi.mocked(albumService.listAlbums).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  })

  afterEach(() => cleanup())

  it('redirects unauthenticated visitors from the dashboard to login', async () => {
    renderAt('/admin')
    expect(await screen.findByRole('heading', { name: 'Administrator sign in' })).toBeInTheDocument()
  })

  it('signs in, stores the token in session storage, and logs out', async () => {
    const user = userEvent.setup()
    vi.mocked(authService.login).mockResolvedValue({
      access_token: 'opaque-test-access-token',
      token_type: 'bearer',
      expires_in: 1800,
      admin: { email: 'owner@example.com' },
    })
    vi.mocked(authService.logout).mockResolvedValue()
    renderAt('/admin/login')

    await user.type(await screen.findByLabelText('Email address'), 'owner@example.com')
    await user.type(screen.getByLabelText('Password'), 'correct horse battery staple')
    await user.click(screen.getByRole('button', { name: 'Sign in securely' }))

    expect(await screen.findByRole('heading', { name: 'Albums' })).toBeInTheDocument()
    expect(sessionStorage.getItem(ADMIN_TOKEN_KEY)).toBe('opaque-test-access-token')
    expect(screen.getAllByText('owner@example.com').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: /log out/i }))
    expect(await screen.findByRole('heading', { name: 'Administrator sign in' })).toBeInTheDocument()
    expect(sessionStorage.getItem(ADMIN_TOKEN_KEY)).toBeNull()
  })

  it('restores a valid session after a page refresh', async () => {
    sessionStorage.setItem(ADMIN_TOKEN_KEY, 'valid-session-token')
    renderAt('/admin')

    expect(await screen.findByRole('heading', { name: 'Albums' })).toBeInTheDocument()
    expect(authService.me).toHaveBeenCalledOnce()
  })

  it('clears an invalid session and redirects to login', async () => {
    sessionStorage.setItem(ADMIN_TOKEN_KEY, 'expired-session-token')
    vi.mocked(authService.me).mockRejectedValue(new Error('expired'))
    renderAt('/admin')

    expect(await screen.findByRole('heading', { name: 'Administrator sign in' })).toBeInTheDocument()
    await waitFor(() => expect(sessionStorage.getItem(ADMIN_TOKEN_KEY)).toBeNull())
  })

  it('keeps login failures generic and supports password visibility', async () => {
    const user = userEvent.setup()
    vi.mocked(authService.login).mockRejectedValue(new Error('private backend detail'))
    renderAt('/admin/login')

    const password = await screen.findByLabelText('Password')
    expect(password).toHaveAttribute('type', 'password')
    await user.click(screen.getByRole('button', { name: 'Show password' }))
    expect(password).toHaveAttribute('type', 'text')
    await user.click(screen.getByRole('button', { name: 'Hide password' }))
    await user.type(screen.getByLabelText('Email address'), 'owner@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrong password')
    await user.click(screen.getByRole('button', { name: 'Sign in securely' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('We couldn’t sign you in with those details. Please try again.')
    expect(screen.queryByText('private backend detail')).not.toBeInTheDocument()
  })

  it('redirects an authenticated administrator away from the login page', async () => {
    sessionStorage.setItem(ADMIN_TOKEN_KEY, 'valid-session-token')
    renderAt('/admin/login')

    expect(await screen.findByRole('heading', { name: 'Albums' })).toBeInTheDocument()
  })
})
