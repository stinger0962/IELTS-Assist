import React, { useState, useEffect, useRef } from 'react';
import { Check, X } from 'lucide-react';
import { practiceAPI, progressAPI } from '../../api';
import type {
  AIWritingPractice, WritingGradingResult, WritingAnnotation,
} from '../../types';

const ESSAY_TYPE_LABELS: Record<string, string> = {
  opinion: 'Opinion Essay',
  discussion: 'Discussion Essay',
  problem_solution: 'Problem & Solution',
  advantages_disadvantages: 'Advantages & Disadvantages',
  two_part: 'Two-Part Question',
};

function AIWritingExerciseView({
  exercise,
  onBack,
}: {
  exercise: AIWritingPractice;
  onBack: () => void;
}) {
  const [essay, setEssay] = useState('');
  const [mode, setMode] = useState<'study' | 'exam'>('study');
  const [submitted, setSubmitted] = useState(false);
  const [grading, setGrading] = useState<WritingGradingResult | null>(null);
  const [gradingLoading, setGradingLoading] = useState(false);
  const [gradingError, setGradingError] = useState('');
  const [startTime] = useState(Date.now());
  const [elapsed, setElapsed] = useState(0);
  const [activeAnnotation, setActiveAnnotation] = useState<WritingAnnotation | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const wordCount = essay.trim() ? essay.trim().split(/\s+/).length : 0;
  const EXAM_TIME = 40 * 60; // 40 minutes in seconds
  const remaining = EXAM_TIME - elapsed;

  // Timer
  useEffect(() => {
    timerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [startTime]);

  const formatTime = (secs: number) => {
    const m = Math.floor(Math.abs(secs) / 60);
    const s = Math.abs(secs) % 60;
    return `${secs < 0 ? '-' : ''}${m}:${s.toString().padStart(2, '0')}`;
  };

  const handleSubmit = async () => {
    if (wordCount < 20 || !exercise.practice_db_id) return;
    setGradingLoading(true);
    setGradingError('');
    if (timerRef.current) clearInterval(timerRef.current);
    try {
      const timeSeconds = Math.floor((Date.now() - startTime) / 1000);
      const res = await practiceAPI.submitAIWriting(exercise.practice_db_id, essay, timeSeconds, mode);
      const result = res.data?.grading as WritingGradingResult;
      setGrading(result);
      setSubmitted(true);

      // Update progress
      const overallBand = result?.examiner_result?.overall_band ?? 0;
      const minutes = Math.min(Math.round(timeSeconds / 60), 30);
      await progressAPI.updateProgress({
        skill: 'writing',
        band_score: overallBand,
        correct_answers: 0,
        total_questions: 4,
        study_time_minutes: minutes,
      });
      await progressAPI.createSession({
        skill: 'writing',
        duration_minutes: minutes,
        notes: `Writing Task 2 (${exercise.meta.essay_type}) — Band ${overallBand}`,
      });
    } catch (err: any) {
      setGradingError(err?.response?.data?.detail || 'Grading failed. Please try again.');
    } finally {
      setGradingLoading(false);
    }
  };

  // Render annotated essay with highlights
  const renderAnnotatedEssay = () => {
    if (!grading?.annotations?.length) return <p className="essay-text-plain">{essay}</p>;
    const annotations = [...grading.annotations].sort((a, b) => a.start_char - b.start_char);
    const parts: React.ReactNode[] = [];
    let cursor = 0;
    annotations.forEach((ann, i) => {
      if (ann.start_char > cursor) {
        parts.push(<span key={`t${i}`}>{essay.slice(cursor, ann.start_char)}</span>);
      }
      parts.push(
        <span
          key={`a${i}`}
          className={`annotation-highlight ${ann.severity}`}
          onClick={() => setActiveAnnotation(activeAnnotation === ann ? null : ann)}
          title={`${ann.category}: ${ann.suggestion}`}
        >
          {essay.slice(ann.start_char, ann.end_char)}
        </span>
      );
      cursor = ann.end_char;
    });
    if (cursor < essay.length) parts.push(<span key="end">{essay.slice(cursor)}</span>);
    return <p className="essay-text-annotated">{parts}</p>;
  };

  // Grading loading state
  if (gradingLoading) {
    return (
      <div className="writing-grading-spinner">
        <div className="loading-spinner" />
        <h3>AI examiner is grading your essay...</h3>
        <p>This typically takes 10–20 seconds</p>
        <style>{writingStyles}</style>
      </div>
    );
  }

  // Results view
  if (submitted && grading) {
    const er = grading.examiner_result;
    const cf = grading.coaching_feedback;
    const criteria = [
      { label: 'Task Response', data: er.task_response, key: 'tr' },
      { label: 'Coherence & Cohesion', data: er.coherence_cohesion, key: 'cc' },
      { label: 'Lexical Resource', data: er.lexical_resource, key: 'lr' },
      { label: 'Grammatical Range & Accuracy', data: er.grammatical_range_accuracy, key: 'gra' },
    ];

    return (
      <div className="writing-results">
        <div className="writing-results-header">
          <div className="overall-band-display">
            <span className="overall-band-label">Overall Band</span>
            <span className="overall-band-score">{er.overall_band}</span>
          </div>
          <div className="result-meta">
            <span>{wordCount} words</span>
            <span>{formatTime(Math.floor((Date.now() - startTime) / 1000))}</span>
            {mode === 'study' && <span className="essay-type-badge">{ESSAY_TYPE_LABELS[exercise.meta.essay_type] || exercise.meta.essay_type}</span>}
          </div>
        </div>

        {/* 4 Criteria */}
        <div className="criteria-grid">
          {criteria.map(c => (
            <div key={c.key} className="criterion-card">
              <div className="criterion-header">
                <span className="criterion-label">{c.label}</span>
                <span className="criterion-band">{c.data.band}</span>
              </div>
              <p className="criterion-evidence">{c.data.evidence}</p>
              {c.data.task_completion && (
                <div className="task-completion-flags">
                  {Object.entries(c.data.task_completion).map(([flag, val]) => (
                    <span key={flag} className={`tc-flag ${val ? 'pass' : 'fail'}`}>
                      {val ? <Check size={11} /> : <X size={11} />}
                      {flag.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Coaching Feedback */}
        <div className="coaching-section">
          <p className="coaching-summary">{cf.summary}</p>
          <div className="coaching-columns">
            <div className="coaching-strengths">
              <h4>Strengths</h4>
              <ul>{cf.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </div>
            <div className="coaching-improvements">
              <h4>Areas for Improvement</h4>
              <ul>{cf.improvements.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </div>
          </div>
        </div>

        {/* Annotated Essay */}
        <div className="annotated-essay-section">
          <h4>Your Essay {grading.annotations.length > 0 && <span className="annotation-count">({grading.annotations.length} annotations)</span>}</h4>
          <div className="annotated-essay-body">
            {renderAnnotatedEssay()}
          </div>
          {activeAnnotation && (
            <div className="annotation-tooltip-box">
              <span className={`ann-category ${activeAnnotation.severity}`}>{activeAnnotation.category}</span>
              <span className="ann-suggestion">{activeAnnotation.suggestion}</span>
              <button className="ann-close" onClick={() => setActiveAnnotation(null)}><X size={12} /></button>
            </div>
          )}
        </div>

        <p className="grading-disclaimer">AI-estimated scores. Actual IELTS band may differ.</p>

        <button className="btn btn-primary btn-lg" onClick={onBack} style={{ marginTop: '1rem' }}>
          Finish
        </button>

        <style>{writingStyles}</style>
      </div>
    );
  }

  // Writing state (before submit)
  return (
    <div className="writing-exercise">
      {/* Mode toggle */}
      <div className="writing-mode-toggle">
        <button className={`mode-btn ${mode === 'study' ? 'active' : ''}`} onClick={() => setMode('study')}>Study</button>
        <button className={`mode-btn ${mode === 'exam' ? 'active' : ''}`} onClick={() => setMode('exam')}>Exam Simulation</button>
      </div>

      {/* Prompt card */}
      <div className={`writing-prompt-card ${mode === 'exam' ? 'exam-mode' : ''}`}>
        {mode === 'study' && (
          <span className="essay-type-badge">{ESSAY_TYPE_LABELS[exercise.meta.essay_type] || exercise.meta.essay_type}</span>
        )}
        <p className="prompt-statement">{exercise.prompt.statement}</p>
        <p className="prompt-instruction"><em>{exercise.prompt.instruction}</em></p>
        <p className="prompt-notes">{exercise.prompt.notes}</p>
      </div>

      {/* Textarea */}
      <textarea
        className="essay-textarea"
        value={essay}
        onChange={e => setEssay(e.target.value)}
        placeholder="Write your essay here..."
        rows={18}
      />

      {/* Status bar */}
      <div className="writing-status-bar">
        <span className={`word-counter ${wordCount >= 250 ? 'good' : wordCount >= 200 ? 'warn' : 'low'}`}>
          {wordCount} words
        </span>
        <span className="timer-display">
          {mode === 'exam'
            ? <span className={remaining <= 0 ? 'time-over' : remaining <= 300 ? 'time-warn' : ''}>{formatTime(remaining)}</span>
            : <span>{formatTime(elapsed)}</span>
          }
        </span>
      </div>

      {gradingError && <p className="grading-error">{gradingError}</p>}

      <div className="writing-actions">
        <button
          className="btn btn-primary btn-lg"
          onClick={handleSubmit}
          disabled={wordCount < 20 || gradingLoading}
        >
          Submit for Grading
        </button>
        <p className="grading-disclaimer">Your essay will be graded by AI (GPT-4o)</p>
      </div>

      <style>{writingStyles}</style>
    </div>
  );
}

const writingStyles = `
  .writing-grading-spinner { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 40vh; gap: var(--spacing-md); text-align: center; }
  .writing-grading-spinner h3 { margin: 0; color: var(--color-text-primary); }
  .writing-grading-spinner p { color: var(--color-text-secondary); font-size: 0.875rem; }

  .writing-mode-toggle { display: flex; gap: 4px; margin-bottom: var(--spacing-md); background: var(--color-background); border-radius: var(--radius-md); padding: 3px; border: 1px solid var(--color-border); width: fit-content; }
  .mode-btn { padding: 6px 16px; border: none; background: none; border-radius: var(--radius-sm); cursor: pointer; font-size: 0.8rem; font-weight: 500; color: var(--color-text-secondary); transition: all var(--transition-fast); }
  .mode-btn.active { background: var(--color-primary); color: white; }

  .writing-prompt-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); margin-bottom: var(--spacing-md); }
  .writing-prompt-card.exam-mode { border-left: 4px solid #6B7280; }
  .essay-type-badge { display: inline-block; background: rgba(245,158,11,0.12); color: #D97706; padding: 2px 10px; border-radius: var(--radius-full); font-size: 0.7rem; font-weight: 600; margin-bottom: var(--spacing-sm); text-transform: uppercase; letter-spacing: 0.5px; }
  .prompt-statement { font-size: 1.05rem; line-height: 1.7; color: var(--color-text-primary); margin-bottom: var(--spacing-sm); }
  .prompt-instruction { font-size: 0.95rem; color: var(--color-text-primary); font-weight: 500; margin-bottom: var(--spacing-sm); }
  .prompt-notes { font-size: 0.8rem; color: var(--color-text-secondary); }

  .essay-textarea { width: 100%; min-height: 400px; padding: var(--spacing-lg); border: 1px solid var(--color-border); border-radius: var(--radius-lg); font-family: inherit; font-size: 1rem; line-height: 1.8; resize: vertical; background: var(--color-surface); color: var(--color-text-primary); }
  .essay-textarea:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 2px rgba(79,70,229,0.1); }

  .writing-status-bar { display: flex; justify-content: space-between; align-items: center; padding: var(--spacing-sm) 0; }
  .word-counter { font-size: 0.85rem; font-weight: 600; }
  .word-counter.good { color: var(--color-success); }
  .word-counter.warn { color: #D97706; }
  .word-counter.low { color: var(--color-text-secondary); }
  .timer-display { font-size: 0.85rem; font-weight: 500; color: var(--color-text-secondary); font-variant-numeric: tabular-nums; }
  .time-warn { color: #D97706 !important; }
  .time-over { color: var(--color-error) !important; font-weight: 700; }

  .grading-error { color: var(--color-error); font-size: 0.875rem; margin: var(--spacing-sm) 0; }

  .writing-actions { display: flex; flex-direction: column; align-items: center; gap: var(--spacing-sm); margin-top: var(--spacing-md); }
  .grading-disclaimer { font-size: 0.75rem; color: var(--color-text-secondary); }

  /* Results */
  .writing-results { max-width: 800px; margin: 0 auto; }
  .writing-results-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--spacing-lg); padding: var(--spacing-lg); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); }
  .overall-band-display { display: flex; flex-direction: column; align-items: center; }
  .overall-band-label { font-size: 0.75rem; color: var(--color-text-secondary); text-transform: uppercase; letter-spacing: 1px; }
  .overall-band-score { font-size: 3rem; font-weight: 800; color: var(--color-primary); line-height: 1; }
  .result-meta { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; font-size: 0.8rem; color: var(--color-text-secondary); }

  .criteria-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-md); margin-bottom: var(--spacing-lg); }
  @media (max-width: 640px) { .criteria-grid { grid-template-columns: 1fr; } }
  .criterion-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-md); }
  .criterion-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--spacing-sm); }
  .criterion-label { font-size: 0.8rem; font-weight: 600; color: var(--color-text-primary); }
  .criterion-band { font-size: 1.5rem; font-weight: 800; color: var(--color-primary); }
  .criterion-evidence { font-size: 0.8rem; line-height: 1.5; color: var(--color-text-secondary); }

  .task-completion-flags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: var(--spacing-sm); }
  .tc-flag { display: inline-flex; align-items: center; gap: 3px; font-size: 0.7rem; padding: 2px 6px; border-radius: var(--radius-sm); }
  .tc-flag.pass { background: rgba(16,185,129,0.1); color: var(--color-success); }
  .tc-flag.fail { background: rgba(239,68,68,0.1); color: var(--color-error); }

  .coaching-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); margin-bottom: var(--spacing-lg); }
  .coaching-summary { font-size: 0.95rem; line-height: 1.6; color: var(--color-text-primary); margin-bottom: var(--spacing-md); }
  .coaching-columns { display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-lg); }
  @media (max-width: 640px) { .coaching-columns { grid-template-columns: 1fr; } }
  .coaching-strengths h4 { color: var(--color-success); font-size: 0.85rem; margin-bottom: var(--spacing-xs); }
  .coaching-improvements h4 { color: #D97706; font-size: 0.85rem; margin-bottom: var(--spacing-xs); }
  .coaching-strengths ul, .coaching-improvements ul { list-style: none; padding: 0; margin: 0; }
  .coaching-strengths li, .coaching-improvements li { font-size: 0.825rem; line-height: 1.5; color: var(--color-text-secondary); padding: 3px 0; }
  .coaching-strengths li::before { content: '+ '; color: var(--color-success); font-weight: 700; }
  .coaching-improvements li::before { content: '- '; color: #D97706; font-weight: 700; }

  .annotated-essay-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); margin-bottom: var(--spacing-md); }
  .annotated-essay-section h4 { margin-bottom: var(--spacing-md); font-size: 0.9rem; }
  .annotation-count { font-weight: 400; color: var(--color-text-secondary); font-size: 0.8rem; }
  .annotated-essay-body { line-height: 1.8; font-size: 0.95rem; color: var(--color-text-primary); white-space: pre-wrap; }
  .essay-text-plain { line-height: 1.8; white-space: pre-wrap; }
  .essay-text-annotated { line-height: 1.8; white-space: pre-wrap; }

  .annotation-highlight { cursor: pointer; border-radius: 2px; padding: 0 1px; }
  .annotation-highlight.major { background: rgba(239,68,68,0.12); border-bottom: 2px solid var(--color-error); }
  .annotation-highlight.minor { background: rgba(245,158,11,0.12); border-bottom: 2px solid #D97706; }

  .annotation-tooltip-box { display: flex; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-sm) var(--spacing-md); background: var(--color-background); border: 1px solid var(--color-border); border-radius: var(--radius-md); margin-top: var(--spacing-sm); font-size: 0.825rem; }
  .ann-category { font-weight: 600; text-transform: uppercase; font-size: 0.7rem; padding: 2px 6px; border-radius: var(--radius-sm); }
  .ann-category.major { background: rgba(239,68,68,0.1); color: var(--color-error); }
  .ann-category.minor { background: rgba(245,158,11,0.1); color: #D97706; }
  .ann-suggestion { flex: 1; color: var(--color-text-secondary); }
  .ann-close { background: none; border: none; cursor: pointer; color: var(--color-text-secondary); padding: 2px; }
`;

export default AIWritingExerciseView;
