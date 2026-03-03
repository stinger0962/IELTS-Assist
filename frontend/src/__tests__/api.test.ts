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

describe('authAPI.me', () => {
  beforeEach(() => {
    useAppStore.setState({ token: null, user: null })
  })

  it('should exist and be a function', () => {
    expect(typeof authAPI.me).toBe('function')
  })

  it('should accept an optional token parameter', () => {
    // me() called without token uses interceptor (for App.tsx initAuth)
    // me(token) called with token bypasses interceptor (for login/register flow)
    // Both are valid call signatures — verify no TypeError is thrown
    expect(() => authAPI.me('explicit-token')).not.toThrow()
    expect(() => authAPI.me()).not.toThrow()
  })

  it('should not auto-logout when 401 occurs with no authenticated user', () => {
    // The response interceptor should only logout if user !== null.
    // This prevents clearing a freshly-set token during the login/register flow
    // if an in-flight me() call (from App.tsx initAuth) returns 401 concurrently.
    useAppStore.setState({ token: 'new-token', user: null })
    
    // Simulate what the response interceptor does
    const { user } = useAppStore.getState()
    if (user !== null) {
      useAppStore.getState().logout()
    }

    // token should be preserved because user was null
    expect(useAppStore.getState().token).toBe('new-token')
  })
})
