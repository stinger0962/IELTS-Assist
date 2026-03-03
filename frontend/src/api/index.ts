import axios from 'axios';
import { useAppStore } from '../store';

const API_URL = import.meta.env.VITE_API_URL || '/api';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = useAppStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAppStore.getState().logout();
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: (email: string, password: string) => 
    api.post('/auth/login', new URLSearchParams({ username: email, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    }),
  register: (data: { email: string; username: string; password: string; full_name?: string }) =>
    api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
  updateSettings: (data: { target_band?: number; test_date?: string; preferred_language?: string }) =>
    api.put('/auth/settings', data),
};

// Progress API
export const progressAPI = {
  getStats: () => api.get('/progress/stats'),
  getProgress: () => api.get('/progress'),
  updateProgress: (data: {
    skill: string;
    band_score?: number;
    correct_answers?: number;
    total_questions?: number;
    study_time_minutes?: number;
  }) => api.post('/progress', data),
  getSessions: (limit = 10) => api.get(`/sessions?limit=${limit}`),
  createSession: (data: { skill?: string; duration_minutes: number; notes?: string }) =>
    api.post('/sessions', data),
};

// Practice API
export const practiceAPI = {
  getReading: () => api.get('/practice/reading'),
  getDailyReading: () => api.get('/generate/daily-reading'),
  generateMore: (count = 1, topic = '') =>
    api.post(`/generate/generate-more?count=${count}`, { topic_hint: topic }),
  getListening: () => api.get('/practice/listening'),
  getWriting: () => api.get('/practice/writing'),
  getSpeaking: () => api.get('/practice/speaking'),
  submit: (data: {
    skill: string;
    exercise_id: string;
    score: number;
    total_questions: number;
    correct_answers: number;
    time_taken_seconds?: number;
  }) => api.post('/practice/submit', data),
  getHistory: (skill?: string, limit = 20) =>
    api.get(`/practice/history?skill=${skill || ''}&limit=${limit}`),
};

// Mistakes API
export const mistakesAPI = {
  getAll: (skill?: string, mistakeType?: string, limit = 50) =>
    api.get(`/mistakes?skill=${skill || ''}&mistake_type=${mistakeType || ''}&limit=${limit}`),
  create: (data: {
    skill: string;
    question: string;
    user_answer: string;
    correct_answer: string;
    mistake_type?: string;
    explanation?: string;
  }) => api.post('/mistakes', data),
  update: (id: number, data: { times_repeated?: number }) =>
    api.put(`/mistakes/${id}`, data),
  delete: (id: number) => api.delete(`/mistakes/${id}`),
  getStats: () => api.get('/mistakes/stats'),
};

// Topics API
export const topicsAPI = {
  getAll: (skill?: string, category?: string, limit = 50) =>
    api.get(`/topics?skill=${skill || ''}&category=${category || ''}&limit=${limit}`),
  getFlashcards: (skill?: string, limit = 10) =>
    api.get(`/topics/flashcards?skill=${skill || ''}&limit=${limit}`),
  review: (topicId: number, quality: number) =>
    api.post('/topics/review', { topic_id: topicId, quality }),
};

// Goals API
export const goalsAPI = {
  getAll: (completed?: boolean, limit = 20) =>
    api.get(`/goals?completed=${completed ?? ''}&limit=${limit}`),
  create: (data: { title: string; description?: string; target_date?: string; target_minutes?: number }) =>
    api.post('/goals', data),
  update: (id: number, data: { completed?: boolean }) =>
    api.put(`/goals/${id}`, data),
  delete: (id: number) => api.delete(`/goals/${id}`),
};

export default api;
