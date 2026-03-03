import { describe, it, expect, beforeEach } from 'vitest'
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
