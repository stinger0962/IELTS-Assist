import { describe, it, expect } from 'vitest'
import { api } from '../api'

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
