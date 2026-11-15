import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { useAppStore } from '../store';

export interface StudyPassStatus {
  enabled: boolean;
  status: 'none' | 'active' | 'expired';
  expires_at: string | null;
  writing_reviews_remaining: number | null;
  full_mock_access: boolean;
}

export function isStudyPassStatus(value: unknown): value is StudyPassStatus {
  if (!value || typeof value !== 'object') return false;
  const v = value as Record<string, unknown>;
  return typeof v.enabled === 'boolean' &&
    ['none', 'active', 'expired'].includes(String(v.status)) &&
    (v.expires_at === null || (typeof v.expires_at === 'string' && !Number.isNaN(Date.parse(v.expires_at)))) &&
    (v.writing_reviews_remaining === null || (Number.isInteger(v.writing_reviews_remaining) && Number(v.writing_reviews_remaining) >= 0)) &&
    typeof v.full_mock_access === 'boolean';
}

export function useStudyPass() {
  const token = useAppStore(state => state.token);
  const [result, setResult] = useState<{ token: string; status: StudyPassStatus } | null>(null);
  const generation = useRef(0);
  const refresh = useCallback(async () => {
    const request = ++generation.current;
    if (!token) return;
    try {
      const response = await api.get('/study-pass');
      if (request === generation.current) {
        setResult(isStudyPassStatus(response.data) ? { token, status: response.data } : null);
      }
    } catch {
      // An older server or transient outage must not break free practice.
      if (request === generation.current) setResult(null);
    }
  }, [token]);

  useEffect(() => {
    void refresh();
    const onFocus = () => { void refresh(); };
    window.addEventListener('focus', onFocus);
    return () => {
      ++generation.current;
      window.removeEventListener('focus', onFocus);
    };
  }, [refresh]);

  return { status: result?.token === token ? result.status : null, refresh };
}
