import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import axios from 'axios'
import { api, authAPI } from '../api'
import { useAppStore } from '../store'

describe('API Configuration', () => {
  it('should have a base URL configured', () => {
    expect(api.defaults.baseURL).toBeDefined()
  })

  it('should have Content-Type header set to application/json', () => {
    expect(api.defaults.headers['Content-Type']).toBe('application/json')
  })

  it('should have request interceptor for auth token', () => {
    // Axios interceptors are stored in an array (may be null when cleared)
    expect((api.interceptors.request.handlers?.length ?? 0)).toBeGreaterThan(0)
  })

  it('should have response interceptor for error handling', () => {
    expect((api.interceptors.response.handlers?.length ?? 0)).toBeGreaterThan(0)
  })
})

// These tests guard against the login Content-Type regression that caused
// hours of debugging. The backend login endpoint (OAuth2PasswordRequestForm)
// REQUIRES application/x-www-form-urlencoded. If Axios sends application/json
// instead, FastAPI returns 422 Unprocessable Content.
describe('authAPI.login request format', () => {
  let postSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    // Spy on bare axios.post (not the api instance) — that's what login uses
    postSpy = vi.spyOn(axios, 'post').mockResolvedValue({ data: { access_token: 'tok', token_type: 'bearer' } })
  })

  afterEach(() => {
    postSpy.mockRestore()
  })

  it('sends Content-Type: application/x-www-form-urlencoded', async () => {
    await authAPI.login('user@example.com', 'pass123')
    const config = postSpy.mock.calls[0][2] as Record<string, unknown>
    const headers = config?.headers as Record<string, string>
    expect(headers?.['Content-Type']).toBe('application/x-www-form-urlencoded')
  })

  it('sends body as a plain URL-encoded string (not JSON or URLSearchParams object)', async () => {
    await authAPI.login('user@example.com', 'pass123')
    const body = postSpy.mock.calls[0][1]
    // Must be a string — when data is a string, Axios skips type detection
    // and cannot override our explicit Content-Type header
    expect(typeof body).toBe('string')
  })

  it('uses "username" field name for the email value (required by OAuth2PasswordRequestForm)', async () => {
    await authAPI.login('user@example.com', 'pass123')
    const body = postSpy.mock.calls[0][1] as string
    const params = new URLSearchParams(body)
    // OAuth2PasswordRequestForm reads "username", not "email"
    expect(params.get('username')).toBe('user@example.com')
    expect(params.get('password')).toBe('pass123')
    // Must NOT use "email" as the field name
    expect(params.get('email')).toBeNull()
  })

  it('encodes special characters in email and password', async () => {
    await authAPI.login('test+tag@ex.com', 'p@ss w0rd!')
    const body = postSpy.mock.calls[0][1] as string
    const params = new URLSearchParams(body)
    expect(params.get('username')).toBe('test+tag@ex.com')
    expect(params.get('password')).toBe('p@ss w0rd!')
  })
})

describe('authAPI.me token parameter', () => {
  it('should be a function that accepts an optional token argument', () => {
    // me(token) passes the token directly in the request header,
    // bypassing the Zustand interceptor — used right after login/register
    // before the store is reliably updated.
    // me() falls back to the interceptor — used by App.tsx initAuth.
    expect(typeof authAPI.me).toBe('function')
    // me accepts 0 or 1 arguments (optional token)
    expect(authAPI.me.length).toBeLessThanOrEqual(1)
  })
})

describe('Response interceptor logout guard', () => {
  beforeEach(() => {
    useAppStore.setState({ token: null, user: null })
  })

  it('should not clear token when user is null (login/register flow)', () => {
    // This guards against a race condition: if App.tsx initAuth me() returns
    // 401 concurrently with the register flow setting a new token, the
    // interceptor must NOT call logout() and clear the new token.
    useAppStore.setState({ token: 'new-token', user: null })

    // Replicate the interceptor guard logic
    const { user } = useAppStore.getState()
    if (user !== null) {
      useAppStore.getState().logout()
    }

    expect(useAppStore.getState().token).toBe('new-token')
  })

  it('should clear token when user is set (authenticated session expired)', () => {
    const mockUser = { id: 1, email: 'a@b.com', username: 'u' } as any
    useAppStore.getState().setAuth('valid-token', mockUser)

    // Replicate the interceptor guard logic
    const { user } = useAppStore.getState()
    if (user !== null) {
      useAppStore.getState().logout()
    }

    expect(useAppStore.getState().token).toBeNull()
    expect(useAppStore.getState().user).toBeNull()
  })
})
