import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, ProgressStats } from '../types';

interface AppState {
  // Auth
  token: string | null;
  user: User | null;
  setAuth: (token: string, user: User) => void;
  setToken: (token: string) => void;
  logout: () => void;
  
  // Theme
  theme: 'light' | 'dark';
  setTheme: (theme: 'light' | 'dark') => void;
  
  // Language
  language: 'en' | 'zh';
  setLanguage: (language: 'en' | 'zh') => void;
  
  // Progress
  stats: ProgressStats | null;
  setStats: (stats: ProgressStats) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // Auth
      token: null,
      user: null,
      setAuth: (token, user) => set({ token, user }),
      setToken: (token: string) => set({ token }),
      logout: () => set({ token: null, user: null }),
      
      // Theme
      theme: 'light',
      setTheme: (theme) => set({ theme }),
      
      // Language
      language: 'en',
      setLanguage: (language) => set({ language }),
      
      // Progress
      stats: null,
      setStats: (stats) => set({ stats }),
    }),
    {
      name: 'ielts-assist-storage',
      partialize: (state) => ({
        theme: state.theme,
        language: state.language,
        token: state.token,
      }),
    }
  )
);