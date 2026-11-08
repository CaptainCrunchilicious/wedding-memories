import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ADMIN_TOKEN_KEY, AUTH_EXPIRED_EVENT } from '../config/api'
import { authService, type Administrator } from '../services/authService'

type AuthContextValue = {
  admin: Administrator | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<Administrator | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const clearSession = useCallback(() => {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY)
    setAdmin(null)
  }, [])

  useEffect(() => {
    let active = true
    const token = sessionStorage.getItem(ADMIN_TOKEN_KEY)
    if (!token) {
      setIsLoading(false)
      return () => { active = false }
    }

    authService.me()
      .then(({ admin: currentAdmin }) => { if (active) setAdmin(currentAdmin) })
      .catch(() => { if (active) clearSession() })
      .finally(() => { if (active) setIsLoading(false) })

    return () => { active = false }
  }, [clearSession])

  useEffect(() => {
    window.addEventListener(AUTH_EXPIRED_EVENT, clearSession)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, clearSession)
  }, [clearSession])

  const login = useCallback(async (email: string, password: string) => {
    const result = await authService.login(email, password)
    sessionStorage.setItem(ADMIN_TOKEN_KEY, result.access_token)
    setAdmin(result.admin)
  }, [])

  const logout = useCallback(async () => {
    try {
      if (sessionStorage.getItem(ADMIN_TOKEN_KEY)) await authService.logout()
    } catch {
      // Clear local credentials even when the server cannot be reached.
    } finally {
      clearSession()
    }
  }, [clearSession])

  const value = useMemo<AuthContextValue>(() => ({
    admin,
    isAuthenticated: admin !== null,
    isLoading,
    login,
    logout,
  }), [admin, isLoading, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
