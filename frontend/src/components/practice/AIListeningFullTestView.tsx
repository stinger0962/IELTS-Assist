import { useState, useEffect, useRef, useCallback } from 'react';
import { Check, X, Play, Pause, RotateCcw } from 'lucide-react';
import { practiceAPI, progressAPI } from '../../api';
import { completionMatch } from '../../utils/completionMatch';
import type { ReadingExamResult } from '../../types';
import { ConfettiBurst, CountUp } from '../Celebrations';
import { useVocabSelection } from '../../hooks/useVocabSelection';

interface Props {
  exercise: any;
  onBack: () => void;
  initialResult?: any;
  initialAnswers?: any[];
}

type Stage = 'intro' | 'section_prep' | 'section_play' | 'review' | 'confirm' | 'processing' | 'results';

function bandColor(b: number) { return b >= 7 ? '#10B981' : b >= 6 ? '#F59E0B' : '#EF4444'; }
function accColor(p: number) { return p >= 80 ? '#10B981' : p >= 60 ? '#F59E0B' : '#EF4444'; }

const QT_LABELS: Record<string, string> = {
  completion: 'Completion',
  form_completion: 'Form Completion',
  note_completion: 'Note Completion',
  sentence_completion: 'Sentence Completion',
  summary_completion: 'Summary Completion',
  multiple_choice: 'Multiple Choice',
  matching: 'Matching',
};

export default function AIListeningFullTestView({ exercise, onBack, initialResult, initialAnswers }: Props) {
  const sections = exercise.sections || [];
  const totalQ = exercise.meta?.total_questions || sections.reduce((n: number, s: any) => n + (s.question_count || 0), 0);

  const isReviewMode = !!initialResult;
  const [stage, setStage] = useState<Stage>(isReviewMode ? 'results' : 'intro');
  const [currentSection, setCurrentSection] = useState(0);
  const [result, setResult] = useState<ReadingExamResult | null>(initialResult || null);
  const [error, setError] = useState('');
  const [reviewSection, setReviewSection] = useState<number | null>(null);
  const [reviewTab, setReviewTab] = useState<'transcript' | 'questions'>('transcript');

  // Timers
  const [prepCountdown, setPrepCountdown] = useState(30);
  const [postCountdown, setPostCountdown] = useState(30);
  const [audioEnded, setAudioEnded] = useState(false);
  const prepTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const postTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef(0);

  // Audio
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // Vocab selection (review mode only)
  const vocabEnabled = reviewSection !== null && reviewTab === 'transcript';
  const vocab = useVocabSelection({ enabled: vocabEnabled, skill: 'listening' });

  // Answers: { 0: { "q_0_0": "answer" }, 1: { ... }, ... }
  const answersRef = useRef<Record<number, Record<string, string>>>(
    initialAnswers ? initialAnswers.reduce((acc: any, sec: any) => {
      acc[(sec.section_number || 1) - 1] = sec.answers || {};
      return acc;
    }, {} as Record<number, Record<string, string>>) : {}
  );
  const [, forceUpdate] = useState(0);

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

  // Advance to next section or review stage
  const advanceSection = useCallback(() => {
    // Clean up audio
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
    setAudioEnded(false);

    if (currentSection < sections.length - 1) {
      setCurrentSection(prev => prev + 1);
      setPrepCountdown(30);
      setStage('section_prep');
    } else {
      setStage('review');
    }
  }, [currentSection, sections.length]);

  // Prep countdown
  useEffect(() => {
    if (stage !== 'section_prep') return;
    setPrepCountdown(30);
    prepTimerRef.current = setInterval(() => {
      setPrepCountdown(prev => {
        if (prev <= 1) {
          clearInterval(prepTimerRef.current!);
          setStage('section_play');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => { if (prepTimerRef.current) clearInterval(prepTimerRef.current); };
  }, [stage, currentSection]);

  // Auto-play audio when entering section_play
  useEffect(() => {
    if (stage !== 'section_play') return;
    setAudioEnded(false);
    const audio = audioRef.current;
    if (audio) {
      audio.currentTime = 0;
      audio.play().catch(() => {});
    }
  }, [stage, currentSection]);

  // Post-audio countdown
  useEffect(() => {
    if (!audioEnded || stage !== 'section_play') return;
    setPostCountdown(30);
    postTimerRef.current = setInterval(() => {
      setPostCountdown(prev => {
        if (prev <= 1) {
          clearInterval(postTimerRef.current!);
          advanceSection();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => { if (postTimerRef.current) clearInterval(postTimerRef.current); };
  }, [audioEnded, stage, advanceSection]);

  // Audio event handlers
  const handleTimeUpdate = () => {
    if (audioRef.current) setCurrentTime(audioRef.current.currentTime);
  };
  const handleLoadedMetadata = () => {
    if (audioRef.current) setDuration(audioRef.current.duration);
  };
  const handleAudioEnded = () => {
    setIsPlaying(false);
    setAudioEnded(true);
  };
  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (audioRef.current) { audioRef.current.currentTime = time; setCurrentTime(time); }
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const handleStartExam = () => {
    startTimeRef.current = Date.now();
    setPrepCountdown(30);
    setCurrentSection(0);
    setStage('section_prep');
  };

  const handleSubmit = async () => {
    const timeTaken = Math.round((Date.now() - startTimeRef.current) / 1000);
    setStage('processing');

    const submissionSections = sections.map((s: any, i: number) => ({
      section_number: s.section_number,
      answers: answersRef.current[i] || {},
    }));

    try {
      const res = await practiceAPI.submitListeningExam(
        exercise.practice_db_id,
        submissionSections,
        timeTaken,
      );
      setResult(res.data);
      setStage('results');

      const band = res.data?.overall?.band || 0;
      progressAPI.updateProgress({
        skill: 'listening',
        band_score: band,
        correct_answers: res.data?.overall?.correct || 0,
        total_questions: res.data?.overall?.total || 0,
        study_time_minutes: Math.min(Math.round(timeTaken / 60), 30),
      }).catch(() => {});
      progressAPI.createSession({
        skill: 'listening',
        duration_minutes: Math.min(Math.round(timeTaken / 60), 30),
        notes: `Full Listening Test — Band ${band}`,
      }).catch(() => {});
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Submission failed. Please try again.');
      setStage('review');
    }
  };

  // Get audio URL for current section
  const getAudioUrl = (sectionIdx: number) => {
    const sec = sections[sectionIdx];
    return sec?.audio_url || sec?.meta?.audio_url || '';
  };

  // Convert flat listening format {completion:[], multiple_choice:[], matching:[]} to groups format
  function toGroups(questions: any): any[] {
    if (!questions) return [];
    if (questions.groups) return questions.groups;
    // Flat format — convert to groups
    const groups: any[] = [];
    if (questions.completion?.length > 0) {
      groups.push({ type: 'completion', items: questions.completion.map((item: any) => typeof item === 'string' ? { text: '', answer: item } : item) });
    }
    if (questions.multiple_choice?.length > 0) {
      groups.push({ type: 'multiple_choice', items: questions.multiple_choice });
    }
    if (questions.matching?.length > 0) {
      groups.push({ type: 'matching', items: questions.matching });
    }
    return groups;
  }

  // Render questions for a section
  function renderQuestions(sec: any, secIdx: number, disabled: boolean, showResults: boolean) {
    const groups = toGroups(sec?.questions);
    let globalQNum = 0; // track question numbers across groups

    return groups.map((group: any, gi: number) => {
      const gtype = group.type;
      const items = group.items || [];
      const answers = group.answers || [];
      const typeLabel = QT_LABELS[gtype] || gtype.replace(/_/g, ' ');
      const isCompletionType = ['completion', 'form_completion', 'note_completion', 'sentence_completion', 'summary_completion'].includes(gtype);

      return (
        <div key={gi} className="lt-group">
          <div className="rft-group-header">{typeLabel}</div>
          {group.instructions && <p className="rft-group-instructions">{group.instructions}</p>}
          {group.group_title && <div className="completion-group-header">{group.group_title}</div>}

          {isCompletionType && items.map((item: any, qi: number) => {
            const key = `q_${gi}_${qi}`;
            const userAns = getAnswer(secIdx, key);
            const correctAns = answers[qi] || item.answer || '';
            const isCorrect = showResults && completionMatch(userAns, correctAns);
            const isWrong = showResults && !completionMatch(userAns, correctAns);
            globalQNum++;
            return (
              <div key={qi} className={`question-block ${isCorrect ? 'q-correct' : ''} ${isWrong ? 'q-wrong' : ''}`}>
                <div className="q-number">{item.question_number || globalQNum}</div>
                <div className="q-body">
                  <p className="q-text">{item.text || item.sentence || ''}</p>
                  <input
                    className={`completion-input ${isCorrect ? 'input-correct' : ''} ${isWrong ? 'input-wrong' : ''}`}
                    type="text"
                    placeholder="Type your answer..."
                    value={userAns}
                    onChange={e => setAnswer(secIdx, key, e.target.value)}
                    disabled={disabled}
                  />
                  {isWrong && <span className="correct-label">Correct: {correctAns}</span>}
                </div>
                {showResults && (isCorrect
                  ? <Check size={18} className="q-icon correct" />
                  : <X size={18} className="q-icon incorrect" />)}
              </div>
            );
          })}

          {gtype === 'multiple_choice' && items.map((item: any, qi: number) => {
            const key = `q_${gi}_${qi}`;
            const userAns = getAnswer(secIdx, key);
            const correctAns = item.answer || '';
            const isCorrect = showResults && userAns === correctAns;
            const isWrong = showResults && userAns !== correctAns;
            const itemOpts = item.options || {};
            globalQNum++;
            return (
              <div key={qi} className={`question-block ${isCorrect ? 'q-correct' : ''} ${isWrong ? 'q-wrong' : ''}`}>
                <div className="q-number">{item.question_number || globalQNum}</div>
                <div className="q-body">
                  <p className="q-text">{item.question}</p>
                  <div className="mcq-options">
                    {Object.entries(itemOpts).map(([letter, text]) => {
                      const selected = userAns === letter;
                      const isCorrectOpt = showResults && letter === correctAns;
                      const isWrongSel = showResults && selected && letter !== correctAns;
                      return (
                        <button
                          key={letter}
                          className={`option ${selected && !showResults ? 'selected' : ''} ${isCorrectOpt ? 'correct' : ''} ${isWrongSel ? 'incorrect' : ''}`}
                          onClick={() => !disabled && setAnswer(secIdx, key, letter)}
                          disabled={disabled}
                        >
                          <span className="option-letter">{letter}</span>
                          <span className="option-text">{text as string}</span>
                          {isCorrectOpt && <Check size={16} className="result-icon correct" />}
                          {isWrongSel && <X size={16} className="result-icon incorrect" />}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })}

          {gtype === 'matching' && (() => {
            const options = group.options || [];
            const matchAnswers = group.answers || {};
            return items.map((stem: any, qi: number) => {
              const key = `q_${gi}_${qi}`;
              const userAns = getAnswer(secIdx, key).toUpperCase();
              const correctAns = (typeof matchAnswers === 'object' && !Array.isArray(matchAnswers))
                ? (matchAnswers[String(stem.question_number)] || '').toUpperCase()
                : '';
              const isCorrect = showResults && userAns === correctAns && userAns !== '';
              const isWrong = showResults && userAns !== correctAns;
              globalQNum++;
              const isFirst = qi === 0;
              return (
                <div key={qi}>
                  {isFirst && (
                    <div className="matching-instruction">
                      <p>{group.instruction || group.instructions || 'Match the items below.'}</p>
                      <div className="matching-options-pool">
                        {options.map((opt: string, oi: number) => (
                          <span key={oi} className="matching-option-tag">{opt}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className={`question-block ${isCorrect ? 'q-correct' : ''} ${isWrong ? 'q-wrong' : ''}`}>
                    <div className="q-number">{stem.question_number || globalQNum}</div>
                    <div className="q-body">
                      <p className="q-text">{stem.text}</p>
                      <select
                        className={`matching-select ${isCorrect ? 'input-correct' : ''} ${isWrong ? 'input-wrong' : ''}`}
                        value={getAnswer(secIdx, key)}
                        onChange={e => setAnswer(secIdx, key, e.target.value)}
                        disabled={disabled}
                      >
                        <option value="">-- Select --</option>
                        {options.map((opt: string, oi: number) => {
                          const letter = opt.split('.')[0]?.trim() || opt.charAt(0);
                          return <option key={oi} value={letter}>{opt}</option>;
                        })}
                      </select>
                      {isWrong && <span className="correct-label">Correct: {options.find((o: string) => o.startsWith(correctAns)) ?? correctAns}</span>}
                    </div>
                    {showResults && (isCorrect
                      ? <Check size={18} className="q-icon correct" />
                      : <X size={18} className="q-icon incorrect" />)}
                  </div>
                </div>
              );
            });
          })()}
        </div>
      );
    });
  }

  // ── Error ──
  if (error) {
    return (
      <div className="rft-container">
        <div className="rft-error">
          <p>{error}</p>
          <button className="btn btn-primary" onClick={() => setError('')}>Back</button>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // ── Intro ──
  if (stage === 'intro') {
    return (
      <div className="rft-container">
        <button className="rft-back-to-practice" onClick={onBack}>← Back</button>
        <div className="rft-intro">
          <h2>Full Listening Test</h2>
          <p className="rft-intro-desc">
            You are about to start a complete IELTS Listening exam with <strong>4 sections</strong> and approximately <strong>30 minutes</strong> of audio. There are <strong>{totalQ} questions</strong> in total.
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
          <p className="rft-intro-total">{totalQ} questions · ~30 minutes</p>
          <button className="btn btn-primary btn-lg" onClick={handleStartExam}>Start Exam</button>
          <button className="btn" onClick={onBack} style={{ marginTop: 8 }}>Cancel</button>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // ── Section Prep ──
  if (stage === 'section_prep') {
    const sec = sections[currentSection];
    return (
      <div className="rft-container">
        <div className="lt-section-header">
          <span className="lt-section-badge">Section {sec.section_number}</span>
          <span className="lt-section-topic">{sec.meta?.topic || `Section ${currentSection + 1}`}</span>
        </div>
        <div className="lt-prep-area">
          <p className="lt-prep-label">Read the questions before the audio begins</p>
          <div className="lt-prep-countdown">{prepCountdown}</div>
          <button className="btn btn-primary" onClick={() => {
            if (prepTimerRef.current) clearInterval(prepTimerRef.current);
            setStage('section_play');
          }}>
            Start Audio Now
          </button>
        </div>
        <div className="listening-questions">
          <h3>Questions — Section {sec.section_number}</h3>
          {renderQuestions(sec, currentSection, false, false)}
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // ── Section Play ──
  if (stage === 'section_play') {
    const sec = sections[currentSection];
    const audioUrl = getAudioUrl(currentSection);
    return (
      <div className="rft-container">
        <div className="lt-section-header">
          <span className="lt-section-badge">Section {sec.section_number}</span>
          <span className="lt-section-topic">{sec.meta?.topic || `Section ${currentSection + 1}`}</span>
        </div>

        {/* Audio player */}
        <div className="audio-player">
          <audio
            ref={audioRef}
            src={audioUrl}
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onEnded={handleAudioEnded}
          />
          <div className="player-controls">
            <button className="player-btn" onClick={() => {
              const audio = audioRef.current;
              if (!audio) return;
              if (isPlaying) audio.pause(); else audio.play();
            }}>
              {isPlaying ? <Pause size={20} /> : <Play size={20} />}
            </button>
            <span className="player-time">{formatTime(currentTime)}</span>
            <input
              className="player-progress"
              type="range"
              min={0}
              max={duration || 0}
              step={0.1}
              value={currentTime}
              onChange={handleSeek}
            />
            <span className="player-time">{formatTime(duration)}</span>
            <button className="player-btn" onClick={() => {
              if (audioRef.current) { audioRef.current.currentTime = 0; audioRef.current.play(); }
            }}>
              <RotateCcw size={16} />
            </button>
          </div>
        </div>

        {/* Audio status */}
        <div className="lt-audio-status">
          {!audioEnded ? (
            <span className="lt-status-playing">Playing Section {sec.section_number}...</span>
          ) : (
            <span className="lt-status-ended">Audio ended — finalize your answers ({postCountdown}s)</span>
          )}
        </div>

        {/* Questions */}
        <div className="listening-questions">
          <h3>Questions — Section {sec.section_number}</h3>
          {renderQuestions(sec, currentSection, false, false)}
        </div>

        {audioEnded && (
          <div className="lt-advance-row">
            <button className="btn btn-primary" onClick={() => {
              if (postTimerRef.current) clearInterval(postTimerRef.current);
              advanceSection();
            }}>
              {currentSection < sections.length - 1 ? 'Next Section' : 'Review Answers'}
            </button>
          </div>
        )}

        <style>{styles}</style>
      </div>
    );
  }

  // ── Review (pre-submit) ──
  if (stage === 'review') {
    const answered = countAnswered();
    return (
      <div className="rft-container">
        <h2 style={{ textAlign: 'center', marginBottom: 16 }}>Review Your Answers</h2>
        <p style={{ textAlign: 'center', color: 'var(--color-text-secondary)', marginBottom: 16 }}>
          {answered} / {totalQ} questions answered
        </p>
        {sections.map((sec: any, si: number) => (
          <div key={si} className="lt-review-section">
            <h3 className="lt-review-section-title">Section {sec.section_number}: {sec.meta?.topic || ''}</h3>
            <div className="listening-questions">
              {renderQuestions(sec, si, false, false)}
            </div>
          </div>
        ))}
        <div className="rft-nav">
          <button className="btn" onClick={() => {
            setCurrentSection(0);
            setPrepCountdown(30);
            setStage('section_prep');
          }}>Restart Audio</button>
          <button className="btn btn-primary" onClick={() => setStage('confirm')}>Submit Exam</button>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // ── Confirm ──
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
            <button className="btn" onClick={() => setStage('review')}>Go Back</button>
          </div>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // ── Processing ──
  if (stage === 'processing') {
    return (
      <div className="rft-container">
        <div className="rft-processing">
          <div className="rft-processing-icon">🎧</div>
          <p>Scoring your exam...</p>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // ── Results ──
  if (stage === 'results' && result) {
    // Review mode for a specific section
    if (reviewSection !== null && sections[reviewSection]) {
      const rs = sections[reviewSection];
      const rsResult = result.sections.find((s) => s.section === rs.section_number);
      const transcript = rs.transcript || rs.meta?.transcript || '';

      return (
        <div className="rft-container">
          {/* Sticky top bar */}
          <div className="rft-review-topbar">
            <button className="rft-review-back" onClick={() => { setReviewSection(null); setReviewTab('transcript'); window.scrollTo(0, 0); }}>← Results</button>
            <span className="rft-review-title">{rs.meta?.topic}</span>
            <span className="rft-review-badge">{rsResult ? `${rsResult.correct}/${rsResult.total}` : ''}</span>
          </div>
          {/* Section switcher */}
          <div className="rft-review-section-tabs">
            {sections.map((s: any, i: number) => {
              const sr = result.sections.find((r) => r.section === s.section_number);
              return (
                <button key={i} className={reviewSection === i ? 'active' : ''} onClick={() => { setReviewSection(i); setReviewTab('transcript'); window.scrollTo(0, 0); }}>
                  S{s.section_number} · {sr ? `${sr.correct}/${sr.total}` : ''}
                </button>
              );
            })}
          </div>
          {/* Transcript / Questions toggle */}
          <div className="rft-review-toggle">
            <button className={reviewTab === 'transcript' ? 'active' : ''} onClick={() => setReviewTab('transcript')}>Transcript</button>
            <button className={reviewTab === 'questions' ? 'active' : ''} onClick={() => setReviewTab('questions')}>Questions</button>
          </div>

          {/* Vocab popup + modal */}
          {vocab.popupPos && !vocab.showModal && (
            <div className="vocab-popup" style={{ left: vocab.popupPos.x, top: vocab.popupPos.y + 10 }}
              onMouseDown={e => { e.preventDefault(); vocab.openModal(vocab.word); }}
              onTouchEnd={e => { e.preventDefault(); vocab.openModal(vocab.word); }}>
              + Add to Vocab
            </div>
          )}
          {vocab.showModal && (
            <div className="vocab-modal-overlay" onClick={vocab.closeModal}>
              <div className="vocab-modal" onClick={e => e.stopPropagation()}>
                <h4>Add to Vocabulary</h4>
                <label className="vocab-label">Word</label>
                <input className="vocab-input" value={vocab.word} onChange={e => vocab.setWord(e.target.value)} />
                <label className="vocab-label">Definition{vocab.defLoading && <span className="vocab-loading-hint"> · Looking up...</span>}</label>
                <textarea className="vocab-textarea" placeholder={vocab.defLoading ? 'Looking up...' : 'Enter definition...'} value={vocab.def} onChange={e => vocab.setDef(e.target.value)} rows={3} />
                {vocab.duplicate && <p className="vocab-duplicate-msg">Already in your deck</p>}
                <div className="vocab-modal-actions">
                  <button className="btn btn-secondary" onClick={vocab.closeModal}>Cancel</button>
                  <button className="btn btn-primary" onClick={vocab.save} disabled={vocab.saving || vocab.defLoading || !vocab.def.trim()}>
                    {vocab.saving ? 'Saving...' : 'Save'}
                  </button>
                </div>
              </div>
            </div>
          )}
          {vocab.saved && <div className="vocab-toast">Added to vocabulary!</div>}

          {/* Transcript tab */}
          {reviewTab === 'transcript' && (
            <div className="rft-review-passage">
              <h3>{rs.meta?.topic}</h3>
              {transcript ? transcript.split('\n').filter((l: string) => l.trim()).map((line: string, li: number) => {
                const colonIdx = line.indexOf(':');
                const hasSpeaker = colonIdx > 0 && colonIdx < 30;
                return (
                  <p key={li} className="transcript-line">
                    {hasSpeaker ? (
                      <><span className="transcript-speaker">{line.slice(0, colonIdx)}:</span> {line.slice(colonIdx + 1).trim()}</>
                    ) : line}
                  </p>
                );
              }) : <p style={{ color: 'var(--color-text-secondary)', fontStyle: 'italic' }}>No transcript available.</p>}
            </div>
          )}

          {/* Questions tab */}
          {reviewTab === 'questions' && (
            <div className="rft-review-questions">
              {renderQuestions(rs, reviewSection, true, true)}
            </div>
          )}
          <style>{styles}</style>
        </div>
      );
    }

    // Results summary page
    return (
      <div className="rft-container">
        <button className="rft-back-to-practice" onClick={onBack}>← Back to Practice</button>
        <ConfettiBurst />
        <div className="rft-results-overall">
          <span className="rft-results-label">Overall Band</span>
          <span className="rft-results-band" style={{ color: bandColor(result.overall.band) }}>
            <CountUp value={result.overall.band} decimals={1} />
          </span>
          <span className="rft-results-score">{result.overall.correct} / {result.overall.total} correct</span>
          <span className="rft-results-time">{formatTime(result.time_taken_seconds)} elapsed</span>
        </div>

        {/* Clickable section cards */}
        <div className="rft-section-cards">
          {result.sections.map((s, si) => (
            <div key={s.section} className="rft-section-card rft-section-card-clickable" onClick={() => { setReviewSection(si); setReviewTab('transcript'); window.scrollTo(0, 0); }}>
              <span className="rft-sc-label">Section {s.section}</span>
              <span className="rft-sc-score" style={{ color: accColor(s.accuracy) }}>{s.correct}/{s.total}</span>
              <span className="rft-sc-pct">{s.accuracy.toFixed(0)}%</span>
              <span className="rft-sc-review">Review →</span>
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

        <button className="btn btn-primary btn-lg" onClick={onBack} style={{ width: '100%', marginTop: 16 }}>Finish</button>
        <style>{styles}</style>
      </div>
    );
  }

  // Fallback
  return (
    <div className="rft-container">
      <p>Loading...</p>
      <style>{styles}</style>
    </div>
  );
}

const styles = `
  .rft-container { max-width: 700px; margin: 0 auto; padding: var(--spacing-md); }
  .rft-back-to-practice { background: none; border: none; font-size: 0.85rem; font-weight: 600; color: var(--color-primary); cursor: pointer; padding: 8px 0; margin-bottom: 8px; display: block; }

  /* Intro */
  .rft-intro { text-align: center; padding: var(--spacing-xl) 0; }
  .rft-intro h2 { margin-bottom: var(--spacing-sm); }
  .rft-intro-desc { color: var(--color-text-secondary); font-size: 0.9rem; margin-bottom: var(--spacing-lg); line-height: 1.5; }
  .rft-sections-preview { text-align: left; margin-bottom: var(--spacing-lg); }
  .rft-preview-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; font-size: 0.85rem; border-bottom: 1px solid var(--color-border); }
  .rft-preview-badge { background: var(--color-primary); color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: 600; white-space: nowrap; }
  .rft-preview-q { margin-left: auto; color: var(--color-text-secondary); font-size: 0.8rem; }
  .rft-intro-total { font-size: 0.8rem; color: var(--color-text-secondary); margin-bottom: var(--spacing-lg); }

  /* Section header */
  .lt-section-header { display: flex; align-items: center; gap: 8px; margin-bottom: var(--spacing-md); padding: 12px 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); }
  .lt-section-badge { background: var(--color-primary); color: white; padding: 3px 10px; border-radius: 10px; font-size: 0.75rem; font-weight: 700; white-space: nowrap; }
  .lt-section-topic { font-size: 0.9rem; font-weight: 600; color: var(--color-text-primary); }

  /* Prep area */
  .lt-prep-area { text-align: center; padding: var(--spacing-lg); margin-bottom: var(--spacing-md); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); }
  .lt-prep-label { font-size: 0.9rem; color: var(--color-text-secondary); margin-bottom: var(--spacing-sm); }
  .lt-prep-countdown { font-size: 4rem; font-weight: 700; color: var(--color-primary); margin: var(--spacing-md) 0; font-variant-numeric: tabular-nums; line-height: 1; }

  /* Audio player */
  .audio-player { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); margin-bottom: var(--spacing-sm); }
  .player-controls { display: flex; align-items: center; gap: var(--spacing-sm); }
  .player-btn { background: none; border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; color: var(--color-text-primary); transition: all var(--transition-fast); }
  .player-btn:hover { border-color: var(--color-primary); color: var(--color-primary); }
  .player-time { font-size: 0.75rem; color: var(--color-text-secondary); font-variant-numeric: tabular-nums; min-width: 36px; text-align: center; }
  .player-progress { flex: 1; height: 4px; accent-color: var(--color-primary); cursor: pointer; }

  /* Audio status */
  .lt-audio-status { text-align: center; padding: 8px; margin-bottom: var(--spacing-md); font-size: 0.85rem; font-weight: 600; }
  .lt-status-playing { color: var(--color-primary); }
  .lt-status-ended { color: #F59E0B; }

  /* Advance button row */
  .lt-advance-row { display: flex; justify-content: center; margin-top: var(--spacing-lg); }

  /* Questions (reused from listening view) */
  .listening-questions { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); margin-bottom: var(--spacing-md); }
  .listening-questions h3 { margin-bottom: var(--spacing-md); font-size: 1rem; }
  .lt-group { margin-bottom: var(--spacing-lg); border-bottom: 1px solid var(--color-border); padding-bottom: var(--spacing-md); }
  .lt-group:last-child { margin-bottom: 0; border-bottom: none; }
  .question-block { display: flex; align-items: flex-start; gap: var(--spacing-sm); padding: var(--spacing-md); border-radius: var(--radius-md); margin-bottom: var(--spacing-sm); border: 1px solid var(--color-border); background: var(--color-background); }
  .question-block.q-correct { border-color: var(--color-success); background: rgba(16,185,129,0.05); }
  .question-block.q-wrong { border-color: var(--color-error); background: rgba(239,68,68,0.05); }
  .q-number { width: 28px; height: 28px; border-radius: 50%; background: var(--color-primary); color: white; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; flex-shrink: 0; margin-top: 2px; }
  .q-body { flex: 1; min-width: 0; }
  .q-text { font-size: 0.9rem; color: var(--color-text-primary); margin-bottom: var(--spacing-sm); line-height: 1.5; }
  .q-icon { flex-shrink: 0; margin-top: 4px; }
  .q-icon.correct { color: var(--color-success); }
  .q-icon.incorrect { color: var(--color-error); }

  .completion-input { width: 100%; max-width: 300px; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text-primary); font-size: 0.875rem; }
  .completion-input:focus { outline: none; border-color: var(--color-primary); }
  .completion-input.input-correct { border-color: var(--color-success); background: rgba(16,185,129,0.08); }
  .completion-input.input-wrong { border-color: var(--color-error); background: rgba(239,68,68,0.08); }
  .completion-input:disabled { opacity: 0.8; cursor: default; }
  .correct-label { display: block; font-size: 0.8rem; color: var(--color-success); margin-top: 4px; font-weight: 600; }

  .completion-group-header { background: var(--color-primary); color: white; padding: 8px 14px; border-radius: var(--radius-md) var(--radius-md) 0 0; font-size: 0.85rem; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 0; }

  .mcq-options { display: flex; flex-direction: column; gap: var(--spacing-xs); }

  .matching-instruction { background: var(--color-surface); border: 1px solid var(--color-primary); border-radius: var(--radius-md); padding: var(--spacing-md); margin-bottom: var(--spacing-sm); }
  .matching-instruction p { font-size: 0.9rem; font-weight: 600; color: var(--color-text-primary); margin-bottom: var(--spacing-xs); }
  .matching-options-pool { display: flex; flex-wrap: wrap; gap: 6px; }
  .matching-option-tag { background: rgba(79,70,229,0.08); color: var(--color-primary); padding: 3px 10px; border-radius: var(--radius-full); font-size: 0.8rem; font-weight: 500; border: 1px solid rgba(79,70,229,0.2); }
  .matching-select { width: 100%; max-width: 300px; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text-primary); font-size: 0.875rem; cursor: pointer; }
  .matching-select:focus { outline: none; border-color: var(--color-primary); }
  .matching-select.input-correct { border-color: var(--color-success); background: rgba(16,185,129,0.08); }
  .matching-select.input-wrong { border-color: var(--color-error); background: rgba(239,68,68,0.08); }
  .matching-select:disabled { opacity: 0.8; cursor: default; }

  /* Review section */
  .lt-review-section { margin-bottom: var(--spacing-lg); }
  .lt-review-section-title { font-size: 0.95rem; font-weight: 600; margin-bottom: var(--spacing-sm); color: var(--color-text-primary); }

  /* Transcript lines in review */
  .transcript-line { font-size: 0.875rem; line-height: 1.7; color: var(--color-text-primary); margin-bottom: var(--spacing-xs); padding: 2px 6px; border-radius: var(--radius-sm); }
  .transcript-speaker { font-weight: 600; color: var(--color-primary); }

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

  .rft-section-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--spacing-sm); margin-bottom: var(--spacing-md); }
  .rft-section-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--spacing-sm); text-align: center; }
  .rft-section-card-clickable { cursor: pointer; transition: all 0.2s; }
  .rft-section-card-clickable:hover { border-color: var(--color-primary); box-shadow: 0 2px 8px rgba(79,70,229,0.12); transform: translateY(-1px); }
  .rft-section-card-clickable:active { transform: scale(0.97); }
  .rft-sc-label { display: block; font-size: 0.7rem; color: var(--color-text-secondary); text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }
  .rft-sc-score { display: block; font-size: 1.3rem; font-weight: 700; margin: 4px 0; }
  .rft-sc-pct { font-size: 0.75rem; display: block; }
  .rft-sc-review { display: inline-flex; align-items: center; gap: 4px; font-size: 0.7rem; font-weight: 600; color: var(--color-primary); margin-top: 6px; padding: 3px 10px; background: rgba(79,70,229,0.08); border-radius: 20px; }

  /* Review Mode */
  .rft-review-topbar { display: flex; align-items: center; gap: 8px; padding: 12px 16px; background: var(--color-surface); border-bottom: 1px solid var(--color-border); position: sticky; top: 0; z-index: 10; }
  .rft-review-back { background: none; border: none; font-size: 0.85rem; font-weight: 600; color: var(--color-primary); cursor: pointer; padding: 4px 0; white-space: nowrap; }
  .rft-review-title { font-size: 0.8rem; font-weight: 600; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .rft-review-badge { font-size: 0.75rem; font-weight: 600; color: var(--color-primary); background: rgba(79,70,229,0.08); padding: 3px 10px; border-radius: 20px; white-space: nowrap; }
  .rft-review-section-tabs { display: flex; gap: 4px; padding: 8px 16px; background: var(--color-background); border-bottom: 1px solid var(--color-border); }
  .rft-review-section-tabs button { flex: 1; padding: 8px; border: 1px solid var(--color-border); background: var(--color-surface); border-radius: 8px; font-size: 0.75rem; font-weight: 600; cursor: pointer; transition: all 0.15s; color: var(--color-text-secondary); }
  .rft-review-section-tabs button.active { background: var(--color-primary); color: white; border-color: var(--color-primary); }
  .rft-review-toggle { display: flex; margin: 12px 16px; background: var(--color-background); border-radius: 8px; padding: 3px; }
  .rft-review-toggle button { flex: 1; padding: 8px; border: none; background: transparent; border-radius: 6px; font-size: 0.85rem; font-weight: 600; cursor: pointer; color: var(--color-text-secondary); transition: all 0.2s; }
  .rft-review-toggle button.active { background: var(--color-primary); color: white; box-shadow: 0 1px 3px rgba(79,70,229,0.3); }
  .rft-review-passage { padding: 16px; }
  .rft-review-passage h3 { font-size: 1.1rem; font-weight: 600; margin-bottom: 12px; }
  .rft-review-questions { padding: 16px; }

  .rft-qt-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-md); margin-bottom: var(--spacing-md); }
  .rft-qt-section h3 { font-size: 0.9rem; margin-bottom: var(--spacing-sm); }
  .rft-qt-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 0.82rem; }
  .rft-qt-name { flex: 1; color: var(--color-text-secondary); }
  .rft-qt-score { font-weight: 600; }
  .rft-qt-pct { font-weight: 700; width: 36px; text-align: right; }

  .rft-group-header { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-primary); margin-bottom: var(--spacing-sm); padding: 4px 8px; background: rgba(79,70,229,0.06); border-radius: var(--radius-sm); display: inline-block; }
  .rft-group-instructions { font-size: 0.85rem; color: var(--color-text-secondary); font-style: italic; margin-bottom: var(--spacing-sm); }

  .rft-nav { display: flex; justify-content: space-between; gap: var(--spacing-sm); }

  .rft-error { text-align: center; padding: var(--spacing-2xl); color: #EF4444; }

  @media (max-width: 480px) {
    .rft-section-cards { grid-template-columns: repeat(2, 1fr); }
  }

  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
`;
