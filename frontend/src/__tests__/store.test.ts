import { describe, it, expect, beforeEach } from 'vitest'
import { useAppStore } from '../store'

describe('App Store', () => {
  beforeEach(() => {
    // Reset store state before each test
    useAppStore.setState({
      token: null,
      user: null,
      theme: 'light',
      language: 'en',
    })
  })

  it('should initialize with null token and user', () => {
    const state = useAppStore.getState()
    expect(state.token).toBeNull()
    expect(state.user).toBeNull()
  })

  it('should set auth token and user', () => {
    const mockUser = {
      id: 1,
      email: 'test@example.com',
      username: 'testuser',
      full_name: 'Test User',
      target_band: 7.0,
      preferred_language: 'en',
    }
    useAppStore.getState().setAuth('test-token', mockUser as any)
    
    const state = useAppStore.getState()
    expect(state.token).toBe('test-token')
    expect(state.user?.email).toBe('test@example.com')
  })

  it('should set token independently', () => {
    useAppStore.getState().setToken('my-token')
    expect(useAppStore.getState().token).toBe('my-token')
  })

  it('should logout and clear token and user', () => {
    useAppStore.getState().setAuth('test-token', { id: 1, email: 'test@example.com' } as any)
    useAppStore.getState().logout()
    
    const state = useAppStore.getState()
    expect(state.token).toBeNull()
    expect(state.user).toBeNull()
  })

  it('should toggle theme', () => {
    expect(useAppStore.getState().theme).toBe('light')
    useAppStore.getState().setTheme('dark')
    expect(useAppStore.getState().theme).toBe('dark')
  })

  it('should set language', () => {
    expect(useAppStore.getState().language).toBe('en')
    useAppStore.getState().setLanguage('zh')
    expect(useAppStore.getState().language).toBe('zh')
  })
})
