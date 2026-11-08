export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8011/api/v1'

export const PUBLIC_APP_URL = (import.meta.env.VITE_PUBLIC_APP_URL || window.location.origin).replace(/\/$/, '')

export const ADMIN_TOKEN_KEY = 'wedding-memories-admin-token'
export const AUTH_EXPIRED_EVENT = 'wedding-memories:auth-expired'
