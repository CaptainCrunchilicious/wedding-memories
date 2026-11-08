import { apiClient } from './apiClient'

export type Administrator = { email: string }

type LoginResponse = {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  admin: Administrator
}

type MeResponse = { authenticated: true; admin: Administrator }

export const authService = {
  async login(email: string, password: string): Promise<LoginResponse> {
    const { data } = await apiClient.post<LoginResponse>('/auth/login', { email, password })
    return data
  },

  async me(): Promise<MeResponse> {
    const { data } = await apiClient.get<MeResponse>('/auth/me')
    return data
  },

  async logout(): Promise<void> {
    await apiClient.post('/auth/logout')
  },
}
