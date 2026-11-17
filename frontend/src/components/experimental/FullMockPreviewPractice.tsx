import { useId, useRef, useState } from 'react';

export interface PreviewQuestion {
  key: string;
  type: 'completion' | 'sentence_completion' | 'short_answer' | 'multiple_choice'
    | 'matching' | 'matching_headings' | 'true_false_not_given' | 'yes_no_not_given';
  prompt: string;
  options?: Array<{ id: string; text: string }>;
  word_limit?: number;
}
export interface FullMockPreview {
  schema_version: 'full_mock_active_preview_v2';
  skill: 'reading' | 'listening';
  total_questions: 40;
  sections: Array<{ section_number: number; passage?: string; audio_url?: string; questions: PreviewQuestion[] }>;
}
export interface RawMockSubmission {
  schema_version: 'full_mock_raw_v2';
  answers: Record<string, string>;
}
interface Props {
  preview: FullMockPreview;
  attemptId: string;
  locale?: 'en' | 'zh';
  onSubmit: (submission: RawMockSubmission) => void | Promise<void>;
}
const copy = {
  en: {
    title: 'Practice preview', notice: 'Experimental practice. No IELTS band estimate.',
    section: 'Section', previous: 'Previous section', next: 'Next section',
    choose: 'Choose an answer', review: 'Review submission', cancel: 'Keep editing',
    send: 'Submit answers', sending: 'Submitting…', submitted: 'Answers submitted.',
    error: 'Submission did not finish. Your answers are still here. Try again.',
    incomplete: 'Unanswered questions earn zero marks. Submit this attempt?',
    answered: 'answered', audio: 'Section audio', unavailable: 'Audio is unavailable for this preview.',
    limit: 'Maximum words', invalid: 'This preview is incomplete or unsupported.',
  },
  zh: {
    title: '练习预览', notice: '实验性练习，不提供雅思分数估计。',
    section: '部分', previous: '上一部分', next: '下一部分',
    choose: '请选择答案', review: '检查提交', cancel: '继续编辑',
    send: '提交答案', sending: '正在提交…', submitted: '答案已提交。',
    error: '提交未完成，答案仍已保留，请重试。',
    incomplete: '未作答的题目计零分。确认提交本次练习？',
    answered: '题已作答', audio: '本部分音频', unavailable: '此预览的音频不可用。',
    limit: '最多词数', invalid: '此预览不完整或暂不支持。',
  },
};
const safeAudio = (value: string | undefined) =>
  typeof value === 'string' && /^\/audio\/(?:[A-Za-z0-9_-]+\/)*[A-Za-z0-9_-]+\.(?:wav|mp3|ogg|m4a)$/.test(value);

// This is a typed, experimental DTO boundary, not an inventory admission check.
// Require complete audit identities, never make up IDs or fall back to v1 data.
function usable(preview: FullMockPreview): boolean {
  if (!preview || preview.schema_version !== 'full_mock_active_preview_v2'
      || !['reading', 'listening'].includes(preview.skill) || preview.total_questions !== 40
      || !Array.isArray(preview.sections)
      || preview.sections.length !== (preview.skill === 'reading' ? 3 : 4)) return false;
  const keys = new Set<string>();
  let count = 0;
  const choices = new Set(['multiple_choice', 'matching', 'matching_headings', 'true_false_not_given', 'yes_no_not_given']);
  const text = new Set(['completion', 'sentence_completion', 'short_answer']);
  for (const [index, section] of preview.sections.entries()) {
    if (!section || section.section_number !== index + 1 || !Array.isArray(section.questions)
        || !section.questions.length || (preview.skill === 'listening' && section.questions.length !== 10)
        || (preview.skill === 'reading' && (typeof section.passage !== 'string' || !section.passage.trim()))) return false;
    for (const question of section.questions) {
      if (!question || typeof question.key !== 'string' || !question.key.startsWith(`s${index + 1}:`)
          || !/^s[1-4]:(?:q(?:[1-9]|[1-3]\d|40)|heading\d+:(?:[1-9]|[1-3]\d|40))$/.test(question.key)
          || keys.has(question.key) || typeof question.prompt !== 'string' || !question.prompt.trim()
          || (!choices.has(question.type) && !text.has(question.type))) return false;
      if (choices.has(question.type) && (!Array.isArray(question.options) || question.options.length < 2
          || question.options.some(o => !o || typeof o.id !== 'string' || !o.id || typeof o.text !== 'string' || !o.text.trim())
          || new Set(question.options.map(o => o.id)).size !== question.options.length)) return false;
      if (text.has(question.type) && question.options !== undefined) return false;
      if (question.word_limit !== undefined && (!Number.isInteger(question.word_limit)
          || question.word_limit < 1 || question.word_limit > 100)) return false;
      keys.add(question.key);
      count++;
    }
  }
  return count === 40;
}

export default function FullMockPreviewPractice(props: Props) {
  const labels = copy[props.locale ?? 'en'];
  if (!props.attemptId || !usable(props.preview)) return <p role="alert">{labels.invalid}</p>;
  // Deliberately remount on a different attempt OR changed content, but not on
  // a locale change or an equivalent object rebuilt by the caller. Late promises
  // belong to the unmounted session and cannot lock/clear the new attempt.
  return <PracticeSession key={JSON.stringify([props.attemptId, props.preview])} {...props} />;
}

function PracticeSession({ preview, locale = 'en', onSubmit }: Props) {
  const labels = copy[locale];
  const prefix = useId();
  const [sectionIndex, setSectionIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [confirm, setConfirm] = useState(false);
  const [status, setStatus] = useState<'editing' | 'sending' | 'submitted' | 'error'>('editing');
  const locked = useRef(false);
  const section = preview.sections[sectionIndex];
  const answered = Object.values(answers).filter(answer => answer.trim()).length;
  const disabled = status === 'sending' || status === 'submitted';
  async function submit() {
    if (locked.current) return;
    locked.current = true;
    setStatus('sending');
    try {
      await onSubmit({ schema_version: 'full_mock_raw_v2', answers: { ...answers } });
      setStatus('submitted');
      setConfirm(false);
    } catch {
      locked.current = false;
      setStatus('error');
      setConfirm(false);
    }
  }
  return (
    <section className="experimental-mock-preview" aria-label={labels.title}>
      <h2>{labels.title}</h2>
      <p>{labels.notice}</p>
      <p role="status" aria-live="polite">{answered}/40 {labels.answered}</p>
      <h3>{labels.section} {section.section_number}/{preview.sections.length}</h3>
      {preview.skill === 'reading'
        ? <div className="experimental-mock-passage">{section.passage}</div>
        : safeAudio(section.audio_url)
          ? <audio key={`${section.section_number}:${section.audio_url}`} controls preload="none" src={section.audio_url} aria-label={labels.audio} />
          : <p role="alert">{labels.unavailable}</p>}
      <fieldset disabled={disabled || confirm}>
        {section.questions.map((question, index) => {
          const id = `${prefix}-question-${index}`;
          return (
            <div className="experimental-mock-question" key={question.key}>
              <label htmlFor={id}>{question.prompt}</label>
              {question.options
                ? <select id={id} value={answers[question.key] ?? ''}
                    onChange={event => setAnswers(current => ({ ...current, [question.key]: event.target.value }))}>
                    <option value="">{labels.choose}</option>
                    {question.options.map(option => <option key={option.id} value={option.id}>{option.text}</option>)}
                  </select>
                : <input id={id} type="text" value={answers[question.key] ?? ''} autoComplete="off"
                    onChange={event => setAnswers(current => ({ ...current, [question.key]: event.target.value }))} />}
              {question.word_limit !== undefined && <small>{labels.limit}: {question.word_limit}</small>}
            </div>
          );
        })}
      </fieldset>
      <nav aria-label={labels.section}>
        <button className="btn" type="button" disabled={disabled || confirm || sectionIndex === 0}
          onClick={() => setSectionIndex(index => index - 1)}>{labels.previous}</button>
        <button className="btn" type="button" disabled={disabled || confirm || sectionIndex === preview.sections.length - 1}
          onClick={() => setSectionIndex(index => index + 1)}>{labels.next}</button>
      </nav>
      {status === 'error' && <p role="alert">{labels.error}</p>}
      {status === 'submitted' ? <p role="status">{labels.submitted}</p> : confirm ? (
        <div role="group" aria-label={labels.review}>
          <p>{labels.incomplete}</p>
          <button className="btn btn-primary" type="button" disabled={disabled} onClick={submit}>
            {status === 'sending' ? labels.sending : labels.send}
          </button>
          <button className="btn" type="button" disabled={disabled} onClick={() => setConfirm(false)}>{labels.cancel}</button>
        </div>
      ) : <button className="btn btn-primary" type="button" onClick={() => setConfirm(true)}>{labels.review}</button>}
      <style>{`
        .experimental-mock-preview { max-width: 52rem; margin: 0 auto; padding: 16px; color: var(--color-text); overflow-wrap: anywhere; }
        .experimental-mock-preview fieldset { border: 0; padding: 0; min-width: 0; }
        .experimental-mock-passage { white-space: pre-wrap; line-height: 1.7; padding: 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); }
        .experimental-mock-preview audio { width: 100%; margin-bottom: 16px; }
        .experimental-mock-question { display: grid; gap: 8px; margin: 20px 0; }
        .experimental-mock-question label { line-height: 1.5; }
        .experimental-mock-question input, .experimental-mock-question select { box-sizing: border-box; width: 100%; min-width: 0; min-height: 44px; font: inherit; padding: 10px; border: 1px solid var(--color-border); border-radius: 8px; background: var(--color-surface); color: inherit; }
        .experimental-mock-preview nav, .experimental-mock-preview [role="group"] { display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0; }
        .experimental-mock-preview [role="group"] p { flex-basis: 100%; }
        .experimental-mock-preview button { min-height: 44px; }
      `}</style>
    </section>
  );
}
