import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import FullMockPreviewPractice from '../components/experimental/FullMockPreviewPractice';
import type { FullMockPreview } from '../components/experimental/FullMockPreviewPractice';
import fixtures from './fixtures/fullMockPreview.json';

const reading = fixtures.reading as FullMockPreview;
const listening = fixtures.listening as FullMockPreview;
afterEach(cleanup);
const fillFirst = (value: string) => fireEvent.change(screen.getAllByRole('textbox')[0], { target: { value } });
const review = () => fireEvent.click(screen.getByRole('button', { name: 'Review submission' }));
async function submit() {
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Submit answers' })); });
}

describe('Unwired question-only practice component', () => {
  it('preserves exact audit identities and partial/blank answers, without network or bands', async () => {
    const receive = vi.fn();
    render(<FullMockPreviewPractice preview={reading} attemptId="attempt-a" onSubmit={receive} />);
    fillFirst('  Typed answer  ');
    fireEvent.change(screen.getAllByRole('textbox')[1], { target: { value: 'temporary' } });
    fireEvent.change(screen.getAllByRole('textbox')[1], { target: { value: '' } });
    fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: 'B' } });
    fireEvent.click(screen.getByRole('button', { name: 'Next section' }));
    fillFirst('第二部分');
    review();
    expect(receive).not.toHaveBeenCalled();
    await submit();
    expect(receive).toHaveBeenCalledExactlyOnceWith({
      schema_version: 'full_mock_raw_v2',
      answers: { 's1:q1': '  Typed answer  ', 's1:q2': '', 's1:heading2:1': 'B', 's2:q1': '第二部分' },
    });
    expect(screen.getByText('Answers submitted.')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Submit answers' })).not.toBeInTheDocument();
  });

  it('cancel confirmation preserves inputs and returns to editing', () => {
    render(<FullMockPreviewPractice preview={reading} attemptId="a" onSubmit={vi.fn()} />);
    fillFirst('draft');
    review();
    expect(screen.getAllByRole('textbox')[0]).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }));
    expect(screen.getAllByRole('textbox')[0]).toHaveValue('draft');
    expect(screen.getAllByRole('textbox')[0]).not.toBeDisabled();
  });

  it('blank attempt emits an explicit empty answer map, not fabricated defaults', async () => {
    const receive = vi.fn();
    render(<FullMockPreviewPractice preview={reading} attemptId="a" onSubmit={receive} />);
    review(); await submit();
    expect(receive).toHaveBeenCalledExactlyOnceWith({ schema_version: 'full_mock_raw_v2', answers: {} });
  });

  it('resets section and answers for a new attempt and for changed content', () => {
    const receive = vi.fn();
    const { rerender } = render(<FullMockPreviewPractice preview={reading} attemptId="a" onSubmit={receive} />);
    fillFirst('old');
    fireEvent.click(screen.getByRole('button', { name: 'Next section' }));
    fillFirst('old section two');
    rerender(<FullMockPreviewPractice preview={reading} attemptId="b" onSubmit={receive} />);
    expect(screen.getByRole('heading', { name: 'Section 1/3' })).toBeVisible();
    expect(screen.getAllByRole('textbox')[0]).toHaveValue('');
    fillFirst('another');
    const changed = structuredClone(reading);
    changed.sections[0].questions[0].prompt = 'A different question ___';
    rerender(<FullMockPreviewPractice preview={changed} attemptId="b" onSubmit={receive} />);
    expect(screen.getAllByRole('textbox')[0]).toHaveValue('');
  });

  it('keeps answers for equivalent DTO objects and language changes', () => {
    const receive = vi.fn();
    const { rerender } = render(<FullMockPreviewPractice preview={reading} attemptId="a" onSubmit={receive} />);
    fillFirst('keep me');
    rerender(<FullMockPreviewPractice preview={structuredClone(reading)} attemptId="a" locale="zh" onSubmit={receive} />);
    expect(screen.getAllByRole('textbox')[0]).toHaveValue('keep me');
    expect(screen.getByRole('button', { name: '检查提交' })).toBeVisible();
  });

  it('prevents duplicate callback calls, retains answers on failure, allows retry', async () => {
    let reject!: (error: Error) => void;
    const receive = vi.fn().mockImplementationOnce(() => new Promise<void>((_, no) => { reject = no; })).mockResolvedValue(undefined);
    render(<FullMockPreviewPractice preview={reading} attemptId="a" onSubmit={receive} />);
    fillFirst('retry me'); review();
    fireEvent.click(screen.getByRole('button', { name: 'Submit answers' }));
    fireEvent.click(screen.getByRole('button', { name: 'Submitting…' }));
    expect(receive).toHaveBeenCalledTimes(1);
    await act(async () => { reject(new Error('secret internal details')); });
    expect(screen.getByRole('alert')).toHaveTextContent('Your answers are still here');
    expect(screen.getByRole('alert')).not.toHaveTextContent('secret');
    expect(screen.getAllByRole('textbox')[0]).toHaveValue('retry me');
    review(); await submit();
    expect(receive).toHaveBeenCalledTimes(2);
  });

  it('late completion of an old attempt does not lock a new attempt', async () => {
    let resolve!: () => void;
    const receive = vi.fn(() => new Promise<void>(yes => { resolve = yes; }));
    const { rerender } = render(<FullMockPreviewPractice preview={reading} attemptId="a" onSubmit={receive} />);
    review(); fireEvent.click(screen.getByRole('button', { name: 'Submit answers' }));
    rerender(<FullMockPreviewPractice preview={reading} attemptId="b" onSubmit={receive} />);
    fillFirst('new draft');
    await act(async () => { resolve(); });
    expect(screen.getAllByRole('textbox')[0]).toHaveValue('new draft');
    expect(screen.queryByText('Answers submitted.')).not.toBeInTheDocument();
  });

  it('uses controlled audio without autoplay and individual matching inputs', async () => {
    const receive = vi.fn();
    const { container } = render(<FullMockPreviewPractice preview={listening} attemptId="a" onSubmit={receive} />);
    const audio = container.querySelector('audio')!;
    expect(audio.getAttribute('src')).toBe('/audio/synthetic.wav');
    expect(audio.getAttribute('preload')).toBe('none');
    expect(audio.autoplay).toBe(false);
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'B' } });
    fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: 'A' } });
    review(); await submit();
    expect(receive).toHaveBeenCalledWith({ schema_version: 'full_mock_raw_v2', answers: { 's1:q9': 'B', 's1:q10': 'A' } });
    expect(container.textContent).not.toMatch(/Guide:|Correct:|crate/);
  });

  it('refuses external media and never interprets prompt or option markup as HTML', () => {
    const dto = structuredClone(listening);
    dto.sections[0].audio_url = 'https://unapproved.example/audio.mp3?token=secret';
    dto.sections[0].questions[0].prompt = '<img src=x onerror=alert(1)>';
    const { container } = render(<FullMockPreviewPractice preview={dto} attemptId="a" onSubmit={vi.fn()} />);
    expect(container.querySelector('audio')).toBeNull();
    expect(container.querySelector('img')).toBeNull();
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeVisible();
    expect(screen.getByRole('alert')).toHaveTextContent('Audio is unavailable');
  });

  it('fails closed on duplicate keys, missing sections and legacy versions', () => {
    const duplicate = structuredClone(reading);
    duplicate.sections[0].questions[1].key = duplicate.sections[0].questions[0].key;
    const { rerender } = render(<FullMockPreviewPractice preview={duplicate} attemptId="a" onSubmit={vi.fn()} />);
    expect(screen.getByRole('alert')).toHaveTextContent('incomplete or unsupported');
    const missing = structuredClone(reading); missing.sections.pop();
    rerender(<FullMockPreviewPractice preview={missing} attemptId="a" onSubmit={vi.fn()} />);
    expect(screen.getByRole('alert')).toBeVisible();
    rerender(<FullMockPreviewPractice preview={{ ...reading, schema_version: 'v1' } as unknown as FullMockPreview} attemptId="a" onSubmit={vi.fn()} />);
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });
});
