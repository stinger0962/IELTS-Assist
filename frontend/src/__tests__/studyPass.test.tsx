import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '../i18n';
import i18n from '../i18n';
import StudyPassPanel from '../components/StudyPassPanel';
import AIWritingView from '../components/practice/AIWritingView';
import { isStudyPassStatus, useStudyPass } from '../hooks/useStudyPass';
import type { StudyPassStatus } from '../hooks/useStudyPass';
import type { AIWritingPractice } from '../types';
import { api, practiceAPI } from '../api';
import { useAppStore } from '../store';

const pass: StudyPassStatus = {
  enabled: true, status: 'none', expires_at: null,
  writing_reviews_remaining: 1, full_mock_access: false,
};
const exercise = {
  practice_db_id: 12, meta: { essay_type: 'opinion' },
  prompt: { statement: 'A sample prompt.', instruction: 'Discuss.', notes: '250 words.' },
} as AIWritingPractice;
const essay = 'This is a sample essay written to test preservation of content when a paid review is not available for this account today.';

beforeEach(async () => {
  await i18n.changeLanguage('en');
  useAppStore.setState({ token: 'test-token' });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('Study pass panel', () => {
  it('renders nothing when disabled or unavailable', () => {
    const { rerender, container } = render(<StudyPassPanel status={null} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<StudyPassPanel status={{ ...pass, enabled: false }} />);
    expect(container).toBeEmptyDOMElement();
  });
  it('shows honest offer with no purchase action and collapsible details', () => {
    render(<StudyPassPanel status={pass} />);
    expect(screen.getByText(/one free AI writing review/)).toBeInTheDocument();
    fireEvent.click(screen.getByText('What is included?'));
    expect(screen.getByText(/Purchasing is not available yet/)).toBeVisible();
    expect(screen.queryByRole('button', { name: /buy|checkout/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('What is included?'));
    expect(screen.getByText(/Purchasing is not available yet/)).not.toBeVisible();
  });
  it('shows exhausted active pass accurately and Chinese localization', async () => {
    await i18n.changeLanguage('zh');
    render(<StudyPassPanel status={{ ...pass, status: 'active', writing_reviews_remaining: 0, expires_at: '2026-12-15T00:00:00Z', full_mock_access: true }} />);
    expect(screen.getByText(/剩余 0 次写作批改/)).toBeInTheDocument();
    expect(screen.queryByText(/免费体验/)).not.toBeInTheDocument();
  });
  it('does not promise another trial after it is used', () => {
    render(<StudyPassPanel status={{ ...pass, status: 'expired', writing_reviews_remaining: 0 }} />);
    expect(screen.getByText(/free writing review has been used/)).toBeInTheDocument();
    expect(screen.getByText(/pass has expired/)).toBeInTheDocument();
  });
  it('retains the existing VIP message instead of promising a trial', () => {
    render(<StudyPassPanel status={{ ...pass, writing_reviews_remaining: null, full_mock_access: true }} />);
    expect(screen.getByText(/existing VIP access is unchanged/)).toBeInTheDocument();
  });
});

describe('Study pass status', () => {
  it('rejects invalid responses', () => {
    expect(isStudyPassStatus(pass)).toBe(true);
    expect(isStudyPassStatus({ ...pass, writing_reviews_remaining: -1 })).toBe(false);
    expect(isStudyPassStatus({ ...pass, expires_at: 'invalid' })).toBe(false);
    expect(isStudyPassStatus({ enabled: true })).toBe(false);
  });
  it('handles unavailable endpoint without breaking practice', async () => {
    vi.spyOn(api, 'get').mockRejectedValue({ response: { status: 404 } });
    const { result } = renderHook(() => useStudyPass());
    await act(async () => { await result.current.refresh(); });
    expect(result.current.status).toBeNull();
  });
  it('ignores late responses belonging to a prior authentication', async () => {
    let resolveOld!: (value: unknown) => void;
    vi.spyOn(api, 'get').mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }));
    const { result } = renderHook(() => useStudyPass());
    act(() => { useAppStore.setState({ token: null }); });
    await act(async () => { resolveOld({ data: pass }); });
    expect(result.current.status).toBeNull();
  });
});

describe('Writing review interruption', () => {
  it.each([
    [402, { code: 'study_pass_required' }],
    [409, { code: 'writing_review_in_progress' }],
  ])('preserves the essay after status %s and supports retry', async (status, detail) => {
    const submit = vi.spyOn(practiceAPI, 'submitAIWriting').mockRejectedValue({ response: { status, data: { detail } } });
    render(<AIWritingView exercise={exercise} onBack={vi.fn()} studyPass={pass} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: essay } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit for Grading' }));
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByRole('textbox')).toHaveValue(essay);
    fireEvent.click(screen.getByRole('button', { name: 'Submit for Grading' }));
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(2));
    expect(screen.getByRole('textbox')).toHaveValue(essay);
  });
});
