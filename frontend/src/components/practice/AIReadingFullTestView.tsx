import { useState, useEffect, useRef } from 'react';
import { Check, X, Clock } from 'lucide-react';
import { practiceAPI, progressAPI } from '../../api';
import { completionMatch } from '../../utils/completionMatch';
import type { ReadingExamResult } from '../../types';
import { ConfettiBurst, CountUp } from '../Celebrations';

interface Props {
  exercise: any; // AIReadingPractice with sections
  onBack: () => void;
}

type Stage = 'intro' | 'exam' | 'confirm' | 'processing' | 'results';

function bandColor(b: number) { return b >= 7 ? '#10B981' : b >= 6 ? '#F59E0B' : '#EF4444'; }
function accColor(p: number) { return p >= 80 ? '#10B981' : p >= 60 ? '#F59E0B' : '#EF4444'; }

const QT_LABELS: Record<string, string> = {
  true_false_not_given: 'True / False / Not Given',
  yes_no_not_given: 'Yes / No / Not Given',
  multiple_choice: 'Multiple Choice',
  sentence_completion: 'Sentence Completion',
  summary_completion: 'Summary Completion',
  matching_headings: 'Matching Headings',
  matching_information: 'Matching Information',
  short_answer: 'Short Answer',
};

export default function AIReadingFullTestView({ exercise, onBack }: Props) {
  const sections = exercise.sections || [];
  const totalQ = exercise.meta?.total_questions || sections.reduce((n: number, s: any) => n + (s.question_count || 0), 0);
  const timeLimit = (exercise.meta?.time_limit_minutes || 60) * 60;

  const [stage, setStage] = useState<Stage>('intro');
  const [activeSection, setActiveSection] = useState(0);
  const [timer, setTimer] = useState(timeLimit);
  const [result, setResult] = useState<ReadingExamResult | null>(null);
  const [error, setError] = useState('');
  const [showExplanations, setShowExplanations] = useState<number | null>(null);

  // Answers: { 0: { "q_0_0": "TRUE" }, 1: { ... }, 2: { ... } }
  const answersRef = useRef<Record<number, Record<string, string>>>({});
  const [, forceUpdate] = useState(0); // trigger re-render when answers change
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef(0);

  // Timer
  useEffect(() => {
    if (stage !== 'exam') return;
    startTimeRef.current = Date.now();
    timerRef.current = setInterval(() => {
      setTimer(t => {
        if (t <= 1) {
          clearInterval(timerRef.current!);
          handleSubmit();
          return 0;
        }
        if (t === 300) { /* 5 min warning — could add visual indicator */ }
        return t - 1;
      });
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [stage]);

  const setAnswer = (sectionIdx: number, key: string, value: string) => {
    if (!answersRef.current[sectionIdx]) answersRef.current[sectionIdx] = {};
    answersRef.current[sectionIdx][key] = value;
    forceUpdate(n => n + 1);
  };

  const getAnswer = (sectionIdx: number, key: string) => {
    return answersRef.current[sectionIdx]?.[key] || '';
  };

  const countAnswered = () => {
    let count = 0;
    for (const sec of Object.values(answersRef.current)) {
      count += Object.values(sec).filter(v => v.trim() !== '').length;
    }
    return count;
  };

  const handleSubmit = async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    const timeTaken = Math.round((Date.now() - startTimeRef.current) / 1000);
    setStage('processing');

    const submissionSections = sections.map((s: any, i: number) => ({
      section_number: s.section_number,
      answers: answersRef.current[i] || {},
    }));

    try {
      const res = await practiceAPI.submitReadingExam(
        exercise.practice_db_id,
        submissionSections,
        timeTaken,
      );
      setResult(res.data);
      setStage('results');

      // Fire-and-forget progress update
      const band = res.data?.overall?.band || 0;
      progressAPI.updateProgress({
        skill: 'reading',
        band_score: band,
        correct_answers: res.data?.overall?.correct || 0,
        total_questions: res.data?.overall?.total || 0,
        study_time_minutes: Math.min(Math.round(timeTaken / 60), 60),
      }).catch(() => {});
      progressAPI.createSession({
        skill: 'reading',
        duration_minutes: Math.min(Math.round(timeTaken / 60), 60),
        notes: `Full Reading Test — Band ${band}`,
      }).catch(() => {});
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Submission failed. Please try again.');
      setStage('exam');
    }
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  // ─── Error ────
  if (error) {
    return (
      <div className="rft-container">
        <div className="rft-error">
          <p>{error}</p>
          <button className="btn btn-primary" onClick={() => setError('')}>Back to Exam</button>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // ─── Intro ────
  if (stage === 'intro') {
    return (
      <div className="rft-container">
        <div className="rft-intro">
          <h2>Full Reading Test</h2>
          <p className="rft-intro-desc">
            You are about to start a complete IELTS Reading exam. This will take up to <strong>60 minutes</strong>.
          </p>
          <div className="rft-sections-preview">
            {sections.map((s: any, i: number) => (
              <div key={i} className="rft-preview-item">
                <span className="rft-preview-badge">Section {s.section_number}</span>
                <span>{s.meta?.topic || `Section ${i + 1}`}</span>
                <span className="rft-preview-q">{s.question_count}q</span>
              </div>
            ))}
          </div>
          <p className="rft-intro-total">{totalQ} questions · 60 minutes</p>
          <button className="btn btn-primary btn-lg" onClick={() => setStage('exam')}>Start Exam</button>
          <button className="btn" onClick={onBack} style={{ marginTop: 8 }}>Cancel</button>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // ─── Confirm submit ────
  if (stage === 'confirm') {
    const answered = countAnswered();
    return (
      <div className="rft-container">
        <div className="rft-confirm">
          <h3>Submit Exam?</h3>
          <p>You have answered <strong>{answered} / {totalQ}</strong> questions.</p>
          {answered < totalQ && <p className="rft-confirm-warn">You have {totalQ - answered} unanswered questions!</p>}
          <div className="rft-confirm-btns">
            <button className="btn btn-primary" onClick={handleSubmit}>Submit</button>
            <button className="btn" onClick={() => setStage('exam')}>Go Back</button>
          </div>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // ─── Processing ────
  if (stage === 'processing') {
    return (
      <div className="rft-container">
        <div className="rft-processing">
          <div className="rft-processing-icon">📝</div>
          <p>Scoring your exam...</p>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // ─── Results ────
  if (stage === 'results' && result) {
    return (
      <div className="rft-container">
        <ConfettiBurst />
        <div className="rft-results-overall">
          <span className="rft-results-label">Overall Band</span>
          <span className="rft-results-band" style={{ color: bandColor(result.overall.band) }}>
            <CountUp value={result.overall.band} decimals={1} />
          </span>
          <span className="rft-results-score">{result.overall.correct} / {result.overall.total} correct</span>
          <span className="rft-results-time">{formatTime(result.time_taken_seconds)} elapsed</span>
        </div>

        {/* Per-section breakdown */}
        <div className="rft-section-cards">
          {result.sections.map((s) => (
            <div key={s.section} className="rft-section-card">
              <span className="rft-sc-label">Section {s.section}</span>
              <span className="rft-sc-score" style={{ color: accColor(s.accuracy) }}>{s.correct}/{s.total}</span>
              <span className="rft-sc-pct">{s.accuracy.toFixed(0)}%</span>
            </div>
          ))}
        </div>

        {/* Question type breakdown */}
        {result.question_types.length > 0 && (
          <div className="rft-qt-section">
            <h3>By Question Type</h3>
            {result.question_types.map((qt) => (
              <div key={qt.type} className="rft-qt-row">
                <span className="rft-qt-name">{QT_LABELS[qt.type] || qt.type.replace(/_/g, ' ')}</span>
                <span className="rft-qt-score">{qt.correct}/{qt.total}</span>
                <span className="rft-qt-pct" style={{ color: accColor(qt.accuracy) }}>{qt.accuracy.toFixed(0)}%</span>
              </div>
            ))}
          </div>
        )}

        {/* Review — tabbed sections, not scroll-forever */}
        <div className="rft-review">
          <h3>Review Answers</h3>
          <div className="rft-review-tabs">
            {sections.map((s: any, si: number) => (
              <button
                key={si}
                className={`rft-review-tab ${showExplanations === si ? 'active' : ''}`}
                onClick={() => setShowExplanations(showExplanations === si ? null : si)}
              >
                S{s.section_number}
              </button>
            ))}
          </div>
          {showExplanations !== null && sections[showExplanations] && (() => {
            const s = sections[showExplanations];
            const passageText = typeof s.passage === 'string' ? s.passage : s.passage?.content || '';
            return (
              <div className="rft-review-content">
                {/* Collapsible passage */}
                <details className="rft-review-passage-details">
                  <summary>View Passage: {s.meta?.topic}</summary>
                  <div className="rft-review-passage-text reading-passage">{passageText}</div>
                </details>
                {/* Questions with answers */}
                <div className="rft-answers-list">
                  {renderSectionReview(s, showExplanations)}
                </div>
              </div>
            );
          })()}
        </div>

        <button className="btn btn-primary btn-lg" onClick={onBack} style={{ width: '100%', marginTop: 16 }}>Finish</button>
        <style>{styles}</style>
      </div>
    );
  }

  // ─── Exam ────
  const section = sections[activeSection];
  const groups = section?.questions?.groups || [];

  // Count paragraphs for matching_information dropdown options
  const passageTextForParaCount = typeof section.passage === 'string' ? section.passage : section.passage?.content || '';
  const paragraphCount = passageTextForParaCount.split(/\n\n+/).filter((p: string) => p.trim()).length;
  const paragraphLetters = Array.from({ length: paragraphCount }, (_, i) => String.fromCharCode(65 + i));

  function renderSectionReview(sec: any, secIdx: number) {
    const grps = sec?.questions?.groups || [];
    return grps.map((group: any, gi: number) => {
      const gtype = group.type;
      const items = group.items || [];
      const answers = group.answers || [];
      return (
        <div key={gi} className="rft-review-group">
          <h4>{QT_LABELS[gtype] || gtype.replace(/_/g, ' ')}</h4>
          {(gtype === 'true_false_not_given' || gtype === 'yes_no_not_given') && items.map((item: any, qi: number) => {
            const key = `q_${gi}_${qi}`;
            const userAns = answersRef.current[secIdx]?.[key] || '';
            const correctAns = answers[qi] || item.answer || '';
            const isCorrect = userAns.trim().toUpperCase() === correctAns.trim().toUpperCase();
            return (
              <div key={qi} className={`rft-review-item ${isCorrect ? 'review-correct' : 'review-wrong'}`}>
                <span className="rft-review-q">{item.question_number || qi + 1}. {item.statement}</span>
                <span>Your answer: <strong>{userAns || '—'}</strong> {isCorrect ? <Check size={14} color="#10B981" /> : <><X size={14} color="#EF4444" /> Correct: <strong>{correctAns}</strong></>}</span>
                {item.explanation && <p className="rft-review-explain">{item.explanation}</p>}
              </div>
            );
          })}
          {gtype === 'multiple_choice' && items.map((item: any, qi: number) => {
            const key = `q_${gi}_${item.question_number || qi}`;
            const userAns = answersRef.current[secIdx]?.[key] || '';
            const correctAns = item.answer || '';
            const isCorrect = userAns === correctAns;
            return (
              <div key={qi} className={`rft-review-item ${isCorrect ? 'review-correct' : 'review-wrong'}`}>
                <span className="rft-review-q">{item.question_number || qi + 1}. {item.question}</span>
                <span>Your answer: <strong>{userAns || '—'}</strong> {isCorrect ? <Check size={14} color="#10B981" /> : <><X size={14} color="#EF4444" /> Correct: <strong>{correctAns}</strong></>}</span>
                {item.explanation && <p className="rft-review-explain">{item.explanation}</p>}
              </div>
            );
          })}
          {(gtype === 'sentence_completion' || gtype === 'summary_completion' || gtype === 'short_answer') && items.map((item: any, qi: number) => {
            const key = `q_${gi}_${qi}`;
            const userAns = answersRef.current[secIdx]?.[key] || '';
            const correctAns = answers[qi] || item.answer || '';
            const isCorrect = completionMatch(userAns, correctAns);
            return (
              <div key={qi} className={`rft-review-item ${isCorrect ? 'review-correct' : 'review-wrong'}`}>
                <span className="rft-review-q">{item.question_number || qi + 1}. {typeof item === 'string' ? item : item.text || item.sentence || item.question || item.statement || ''}</span>
                <span>Your answer: <strong>{userAns || '—'}</strong> {isCorrect ? <Check size={14} color="#10B981" /> : <><X size={14} color="#EF4444" /> Correct: <strong>{correctAns}</strong></>}</span>
              </div>
            );
          })}
          {gtype === 'matching_headings' && (() => {
            const headingsData = items as any;
            const paras = headingsData.paragraphs || [];
            const matchAnswers = group.answers || [];
            return paras.map((para: any, qi: number) => {
              const key = `mh_${gi}_${para.number}`;
              const userAns = answersRef.current[secIdx]?.[key] || '';
              const correctAns = matchAnswers.find((a: any) => a.paragraph_number === para.number)?.answer || '';
              const isCorrect = userAns === correctAns;
              return (
                <div key={qi} className={`rft-review-item ${isCorrect ? 'review-correct' : 'review-wrong'}`}>
                  <span className="rft-review-q">Paragraph {para.number}: {para.title}</span>
                  <span>Your answer: <strong>{userAns || '—'}</strong> {isCorrect ? <Check size={14} color="#10B981" /> : <><X size={14} color="#EF4444" /> Correct: <strong>{correctAns}</strong></>}</span>
                </div>
              );
            });
          })()}
        </div>
      );
    });
  }

  return (
    <div className="rft-container">
      {/* Top bar: section tabs + timer */}
      <div className="rft-topbar">
        <div className="rft-tabs">
          {sections.map((s: any, i: number) => {
            const answered = Object.values(answersRef.current[i] || {}).filter(v => (v as string).trim() !== '').length;
            return (
              <button
                key={i}
                className={`rft-tab ${activeSection === i ? 'active' : ''}`}
                onClick={() => { setActiveSection(i); window.scrollTo(0, 0); }}
              >
                <span>S{s.section_number}</span>
                <span className="rft-tab-count">{answered}/{s.question_count}</span>
              </button>
            );
          })}
        </div>
        <div className={`rft-timer ${timer <= 300 ? 'timer-warn' : ''}`}>
          <Clock size={14} />
          <span>{formatTime(timer)}</span>
        </div>
      </div>

      {/* Passage — label paragraphs A, B, C... if matching_information exists */}
      {(() => {
        const passageText = typeof section.passage === 'string' ? section.passage : section.passage?.content || '';
        const hasMatchingInfo = groups.some((g: any) => g.type === 'matching_information');
        const paragraphs = passageText.split(/\n\n+/).filter((p: string) => p.trim());
        return (
          <div className="rft-passage">
            <h3>{typeof section.passage === 'object' ? section.passage?.title : section.meta?.topic}</h3>
            {hasMatchingInfo ? (
              <div className="rft-passage-text reading-passage">
                {paragraphs.map((para: string, pi: number) => (
                  <p key={pi} className="rft-labeled-para">
                    <span className="rft-para-label">{String.fromCharCode(65 + pi)}</span>
                    {para}
                  </p>
                ))}
              </div>
            ) : (
              <div className="rft-passage-text reading-passage">{passageText}</div>
            )}
          </div>
        );
      })()}

      {/* Questions — exam mode (no instant feedback) */}
      <div className="rft-questions">
        <h3>Questions — Section {section.section_number}</h3>
        {groups.map((group: any, gi: number) => {
          const gtype = group.type;
          const items = group.items || [];
          const typeLabel = QT_LABELS[gtype] || gtype.replace(/_/g, ' ');
          const opts = gtype === 'true_false_not_given' ? ['TRUE', 'FALSE', 'NOT GIVEN']
            : gtype === 'yes_no_not_given' ? ['YES', 'NO', 'NOT GIVEN']
            : null;

          return (
            <div key={gi} className="rft-group">
              <div className="rft-group-header">{typeLabel}</div>
              {group.instructions && <p className="rft-group-instructions">{group.instructions}</p>}

              {/* T/F/NG or Y/N/NG */}
              {opts && items.map((item: any, qi: number) => {
                const key = `q_${gi}_${qi}`;
                const userAns = getAnswer(activeSection, key);
                return (
                  <div key={qi} className="rft-tfng-row">
                    <div className="rft-tfng-statement">
                      <span className="rft-qnum">{item.question_number || qi + 1}.</span>
                      <span>{item.statement}</span>
                    </div>
                    <div className="rft-tfng-btns">
                      {opts.map(opt => (
                        <button
                          key={opt}
                          className={`rft-tfng-btn ${userAns === opt ? 'selected' : ''}`}
                          onClick={() => setAnswer(activeSection, key, opt)}
                        >
                          {opt === 'NOT GIVEN' ? 'NG' : opt.charAt(0)}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}

              {/* MCQ */}
              {gtype === 'multiple_choice' && items.map((item: any, qi: number) => {
                const key = `q_${gi}_${item.question_number || qi}`;
                const userAns = getAnswer(activeSection, key);
                const itemOpts = item.options || {};
                return (
                  <div key={qi} className="rft-mcq">
                    <p className="rft-mcq-q"><span className="rft-qnum">{item.question_number || qi + 1}.</span> {item.question}</p>
                    <div className="rft-mcq-opts">
                      {Object.entries(itemOpts).map(([letter, text]) => (
                        <button
                          key={letter}
                          className={`option ${userAns === letter ? 'selected' : ''}`}
                          onClick={() => setAnswer(activeSection, key, letter)}
                        >
                          <span className="option-letter">{letter}</span>
                          <span className="option-text">{text as string}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}

              {/* Completion types: sentence, summary, short answer */}
              {(gtype === 'sentence_completion' || gtype === 'summary_completion' || gtype === 'short_answer') && items.map((item: any, qi: number) => {
                const key = `q_${gi}_${qi}`;
                const userAns = getAnswer(activeSection, key);
                const qText = typeof item === 'string' ? item : (item.text || item.sentence || item.question || item.statement || '');
                const hint = item.explanation ? item.explanation.split('.')[0] : '';
                return (
                  <div key={qi} className="rft-completion">
                    <p>
                      <span className="rft-qnum">{item.question_number || qi + 1}.</span>{' '}
                      {qText || (hint ? `Based on the passage: ${hint}` : `Complete with information from the passage`)}
                      {!qText && item.word_limit && <span className="rft-word-limit"> (max {item.word_limit} words)</span>}
                    </p>
                    <input
                      type="text"
                      className="form-input"
                      placeholder={`Answer (max ${item.word_limit || 3} words)`}
                      value={userAns}
                      onChange={e => setAnswer(activeSection, key, e.target.value)}
                    />
                  </div>
                );
              })}

              {/* Matching headings */}
              {gtype === 'matching_headings' && (() => {
                const headingsData = items as any;
                const headings = headingsData.headings || [];
                const paras = headingsData.paragraphs || [];
                return (
                  <div>
                    <div className="rft-headings-bank">
                      {headings.map((h: any) => (
                        <div key={h.id} className="rft-heading-entry"><strong>{h.id}.</strong> {h.text}</div>
                      ))}
                    </div>
                    {paras.map((para: any) => {
                      const key = `mh_${gi}_${para.number}`;
                      const userAns = getAnswer(activeSection, key);
                      return (
                        <div key={para.number} className="rft-match-row">
                          <span>Paragraph {para.number}: <em>{para.title}</em></span>
                          <select value={userAns} onChange={e => setAnswer(activeSection, key, e.target.value)}>
                            <option value="">Select...</option>
                            {headings.map((h: any) => <option key={h.id} value={h.id}>{h.id}</option>)}
                          </select>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}

              {/* Matching information */}
              {gtype === 'matching_information' && (
                <>
                  <p className="rft-group-instructions">Which paragraph contains the following information? Write the correct letter (A, B, C, D...)</p>
                  {items.map((item: any, qi: number) => {
                    const key = `q_${gi}_${qi}`;
                    const userAns = getAnswer(activeSection, key);
                    return (
                      <div key={qi} className="rft-match-row">
                        <span><span className="rft-qnum">{item.question_number || qi + 1}.</span> {item.statement || item.question || ''}</span>
                        <select
                          value={userAns}
                          onChange={e => setAnswer(activeSection, key, e.target.value)}
                          style={{ flexShrink: 0 }}
                        >
                          <option value="">Select</option>
                          {paragraphLetters.map(letter => (
                            <option key={letter} value={letter}>{letter}</option>
                          ))}
                        </select>
                      </div>
                    );
                  })}
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Navigation */}
      <div className="rft-nav">
        {activeSection > 0 && (
          <button className="btn" onClick={() => { setActiveSection(activeSection - 1); window.scrollTo(0, 0); }}>Previous Section</button>
        )}
        {activeSection < sections.length - 1 ? (
          <button className="btn btn-primary" onClick={() => { setActiveSection(activeSection + 1); window.scrollTo(0, 0); }}>Next Section</button>
        ) : (
          <button className="btn btn-primary" onClick={() => setStage('confirm')}>Submit Exam</button>
        )}
      </div>

      <style>{styles}</style>
    </div>
  );
}

const styles = `
  .rft-container { max-width: 700px; margin: 0 auto; padding: var(--spacing-md); }

  /* Intro */
  .rft-intro { text-align: center; padding: var(--spacing-xl) 0; }
  .rft-intro h2 { margin-bottom: var(--spacing-sm); }
  .rft-intro-desc { color: var(--color-text-secondary); font-size: 0.9rem; margin-bottom: var(--spacing-lg); line-height: 1.5; }
  .rft-sections-preview { text-align: left; margin-bottom: var(--spacing-lg); }
  .rft-preview-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; font-size: 0.85rem; border-bottom: 1px solid var(--color-border); }
  .rft-preview-badge { background: var(--color-primary); color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: 600; white-space: nowrap; }
  .rft-preview-q { margin-left: auto; color: var(--color-text-secondary); font-size: 0.8rem; }
  .rft-intro-total { font-size: 0.8rem; color: var(--color-text-secondary); margin-bottom: var(--spacing-lg); }

  /* Top bar */
  .rft-topbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--spacing-md); position: sticky; top: 0; background: var(--color-background); z-index: 10; padding: 8px 0; border-bottom: 1px solid var(--color-border); }
  .rft-tabs { display: flex; gap: 4px; }
  .rft-tab { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 6px 12px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); font-size: 0.8rem; font-weight: 600; cursor: pointer; color: var(--color-text-secondary); }
  .rft-tab.active { border-color: var(--color-primary); color: var(--color-primary); background: rgba(79,70,229,0.08); }
  .rft-tab-count { font-size: 0.65rem; font-weight: 400; }
  .rft-timer { display: flex; align-items: center; gap: 4px; font-size: 0.9rem; font-weight: 700; color: var(--color-text-primary); }
  .rft-timer.timer-warn { color: #EF4444; animation: pulse 1s infinite; }

  /* Passage */
  .rft-passage { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); margin-bottom: var(--spacing-md); }
  .rft-passage h3 { margin-bottom: var(--spacing-md); }
  .rft-passage-text { line-height: 1.9; white-space: pre-line; }

  /* Questions */
  .rft-questions { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); margin-bottom: var(--spacing-md); }
  .rft-questions h3 { margin-bottom: var(--spacing-md); }
  .rft-group { margin-bottom: var(--spacing-lg); border-bottom: 1px solid var(--color-border); padding-bottom: var(--spacing-md); }
  .rft-group:last-child { margin-bottom: 0; border-bottom: none; }
  .rft-group-header { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-primary); margin-bottom: var(--spacing-sm); padding: 4px 8px; background: rgba(79,70,229,0.06); border-radius: var(--radius-sm); display: inline-block; }
  .rft-group-instructions { font-size: 0.85rem; color: var(--color-text-secondary); font-style: italic; margin-bottom: var(--spacing-sm); }
  .rft-qnum { font-weight: 700; color: var(--color-primary); margin-right: 4px; }

  /* T/F/NG */
  .rft-tfng-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--color-border); }
  .rft-tfng-statement { flex: 1; font-size: 0.9rem; }
  .rft-tfng-btns { display: flex; gap: 4px; flex-shrink: 0; }
  .rft-tfng-btn { padding: 4px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-background); color: var(--color-text-primary); cursor: pointer; font-size: 0.8rem; font-weight: 600; }
  .rft-tfng-btn.selected { background: var(--color-primary); color: white; border-color: var(--color-primary); }

  /* MCQ */
  .rft-mcq { margin-bottom: var(--spacing-md); }
  .rft-mcq-q { font-size: 0.95rem; margin-bottom: var(--spacing-sm); }
  .rft-mcq-opts { display: flex; flex-direction: column; gap: 6px; }

  /* Completion */
  .rft-completion { margin-bottom: var(--spacing-sm); }
  .rft-completion p { font-size: 0.9rem; margin-bottom: 4px; }
  .rft-completion input { max-width: 300px; }

  /* Matching headings */
  .rft-headings-bank { background: var(--color-background); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--spacing-sm); margin-bottom: var(--spacing-sm); }
  .rft-heading-entry { font-size: 0.85rem; padding: 2px 0; }
  .rft-match-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--color-border); font-size: 0.85rem; gap: 8px; }
  .rft-match-row select { padding: 4px 8px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-background); color: var(--color-text-primary); }

  /* Nav */
  .rft-nav { display: flex; justify-content: space-between; gap: var(--spacing-sm); }

  /* Confirm */
  .rft-confirm { text-align: center; padding: var(--spacing-2xl) var(--spacing-md); }
  .rft-confirm h3 { margin-bottom: var(--spacing-sm); }
  .rft-confirm-warn { color: #F59E0B; font-weight: 600; margin-top: var(--spacing-sm); }
  .rft-confirm-btns { display: flex; gap: var(--spacing-sm); justify-content: center; margin-top: var(--spacing-lg); }

  /* Processing */
  .rft-processing { text-align: center; padding: var(--spacing-2xl); }
  .rft-processing-icon { font-size: 3rem; margin-bottom: var(--spacing-md); }

  /* Results */
  .rft-results-overall { text-align: center; margin-bottom: var(--spacing-lg); }
  .rft-results-label { display: block; font-size: 0.8rem; color: var(--color-text-secondary); }
  .rft-results-band { display: block; font-size: 3rem; font-weight: 700; }
  .rft-results-score { display: block; font-size: 0.9rem; color: var(--color-text-secondary); }
  .rft-results-time { display: block; font-size: 0.8rem; color: var(--color-text-secondary); margin-top: 2px; }

  .rft-section-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--spacing-sm); margin-bottom: var(--spacing-md); }
  .rft-section-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--spacing-sm); text-align: center; }
  .rft-sc-label { display: block; font-size: 0.7rem; color: var(--color-text-secondary); }
  .rft-sc-score { display: block; font-size: 1.1rem; font-weight: 700; }
  .rft-sc-pct { font-size: 0.75rem; }

  .rft-qt-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-md); margin-bottom: var(--spacing-md); }
  .rft-qt-section h3 { font-size: 0.9rem; margin-bottom: var(--spacing-sm); }
  .rft-qt-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 0.82rem; }
  .rft-qt-name { flex: 1; color: var(--color-text-secondary); }
  .rft-qt-score { font-weight: 600; }
  .rft-qt-pct { font-weight: 700; width: 36px; text-align: right; }

  /* Labeled paragraphs for matching information */
  .rft-labeled-para { margin-bottom: var(--spacing-md); }
  .rft-para-label { float: left; width: 22px; height: 22px; border-radius: 50%; background: var(--color-primary); color: white; display: inline-flex; align-items: center; justify-content: center; font-size: 0.7rem; font-weight: 700; margin-right: 6px; margin-top: 2px; line-height: 22px; }

  /* Review section — tabbed, not scroll-forever */
  .rft-review { margin-bottom: var(--spacing-md); }
  .rft-review h3 { font-size: 0.9rem; margin-bottom: var(--spacing-sm); }
  .rft-review-tabs { display: flex; gap: 6px; margin-bottom: var(--spacing-md); }
  .rft-review-tab { padding: 8px 16px; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); font-size: 0.85rem; font-weight: 600; cursor: pointer; color: var(--color-text-secondary); flex: 1; text-align: center; }
  .rft-review-tab.active { background: var(--color-primary); color: white; border-color: var(--color-primary); }
  .rft-review-content { }
  .rft-review-passage-details { margin-bottom: var(--spacing-md); }
  .rft-review-passage-details summary { font-size: 0.85rem; font-weight: 600; color: var(--color-primary); cursor: pointer; padding: var(--spacing-sm); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); }
  .rft-review-passage-details[open] summary { border-radius: var(--radius-md) var(--radius-md) 0 0; }
  .rft-review-passage-text { font-size: 0.85rem; line-height: 1.8; white-space: pre-line; padding: var(--spacing-md); background: var(--color-surface); border: 1px solid var(--color-border); border-top: none; border-radius: 0 0 var(--radius-md) var(--radius-md); max-height: 300px; overflow-y: auto; }
  .rft-expand-btn { width: 100%; text-align: left; padding: 10px var(--spacing-md); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); cursor: pointer; font-size: 0.85rem; font-weight: 600; color: var(--color-text-primary); margin-bottom: 4px; }
  .rft-answers-list { padding: var(--spacing-sm); }
  .rft-review-group { margin-bottom: var(--spacing-lg); }
  .rft-review-group h4 { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-primary); margin-bottom: var(--spacing-sm); padding: 4px 8px; background: rgba(79,70,229,0.06); border-radius: var(--radius-sm); display: inline-block; }
  .rft-review-item { padding: var(--spacing-sm) var(--spacing-md); border-radius: var(--radius-md); margin-bottom: var(--spacing-sm); font-size: 0.88rem; border-left: 3px solid transparent; }
  .rft-review-item.review-correct { background: rgba(16,185,129,0.06); border-left-color: #10B981; }
  .rft-review-item.review-wrong { background: rgba(239,68,68,0.06); border-left-color: #EF4444; }
  .rft-review-q { display: block; font-weight: 600; margin-bottom: 4px; line-height: 1.5; }
  .rft-review-explain { font-size: 0.82rem; color: var(--color-text-secondary); margin-top: 6px; font-style: italic; line-height: 1.5; padding: 6px 8px; background: var(--color-background); border-radius: var(--radius-sm); }
  .rft-word-limit { font-size: 0.75rem; color: var(--color-text-secondary); font-style: italic; }

  .rft-error { text-align: center; padding: var(--spacing-2xl); color: #EF4444; }

  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
`;
