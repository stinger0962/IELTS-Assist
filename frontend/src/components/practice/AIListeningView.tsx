import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, X, Play, Pause, RotateCcw, FileText } from 'lucide-react';
import { practiceAPI, progressAPI, mistakesAPI } from '../../api';
import { completionMatch } from '../../utils/completionMatch';
import type { AIListeningPractice, AIListeningMatchingBlock } from '../../types';

function AIListeningExerciseView({
  exercise,
  onComplete,
}: {
  exercise: AIListeningPractice;
  onComplete: (correct: number, total: number) => void;
}) {
  const { t } = useTranslation();
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [submitted, setSubmitted] = useState(false);
  const [score, setScore] = useState<{ correct: number; total: number } | null>(null);
  const [startTime] = useState(Date.now());
  const [explanations, setExplanations] = useState<Record<string, string>>({});
  const [explanationsLoading, setExplanationsLoading] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);
  const transcriptLineRefs = useRef<(HTMLParagraphElement | null)[]>([]);

  // Answer state: keyed by "comp_0", "mc_0", etc.
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const completionQs = exercise.questions.completion ?? [];
  const mcqQs = exercise.questions.multiple_choice ?? [];
  const matchingBlocks = exercise.questions.matching ?? [];
  const matchingStemCount = matchingBlocks.reduce((sum, m) => sum + m.stems.length, 0);
  const totalQuestions = completionQs.length + mcqQs.length + matchingStemCount;

  // Audio URL — prepend VPS base if it's a relative path
  const audioUrl = exercise.meta.audio_url?.startsWith('http')
    ? exercise.meta.audio_url
    : exercise.meta.audio_url; // relative URL served by nginx

  // Audio controls
  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) { audio.pause(); } else { audio.play(); }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) setCurrentTime(audioRef.current.currentTime);
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) setDuration(audioRef.current.duration);
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (audioRef.current) { audioRef.current.currentTime = time; setCurrentTime(time); }
  };

  const changeSpeed = () => {
    const speeds = [0.75, 1, 1.25];
    const next = speeds[(speeds.indexOf(playbackRate) + 1) % speeds.length];
    setPlaybackRate(next);
    if (audioRef.current) audioRef.current.playbackRate = next;
  };

  const replay = () => {
    if (audioRef.current) { audioRef.current.currentTime = 0; audioRef.current.play(); }
  };

  // Auto-scroll to active transcript line
  const activeLineIdx = (() => {
    const ts = exercise.line_timestamps;
    if (!ts || ts.length === 0 || !isPlaying) return -1;
    return ts.reduce((acc, t) => (currentTime >= t.start ? t.line_index : acc), -1);
  })();
  useEffect(() => {
    if (activeLineIdx >= 0 && showTranscript) {
      const el = transcriptLineRefs.current[activeLineIdx];
      if (el) {
        const container = el.closest('.transcript-content') as HTMLElement | null;
        if (container) {
          const elTop = el.offsetTop - container.offsetTop;
          const target = elTop - container.clientHeight / 2 + el.clientHeight / 2;
          container.scrollTo({ top: target, behavior: 'smooth' });
        }
      }
    }
  }, [activeLineIdx, showTranscript]);

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const setAnswer = (key: string, value: string) => {
    setAnswers(prev => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async () => {
    let correct = 0;
    type WrongEntry = { key: string; question_type: string; question: string; user_answer: string; correct_answer: string };
    const wrongAnswers: WrongEntry[] = [];

    // Score completion questions (accept both number words and digits)
    completionQs.forEach((q, i) => {
      const key = `comp_${i}`;
      const userAns = (answers[key] ?? '').trim();
      const correctAns = q.answer.trim();
      if (completionMatch(userAns, correctAns)) {
        correct++;
      } else {
        wrongAnswers.push({ key, question_type: 'completion', question: q.text, user_answer: userAns || '(unanswered)', correct_answer: correctAns });
        mistakesAPI.create({
          skill: 'listening', question: q.text,
          user_answer: userAns || '(unanswered)', correct_answer: correctAns,
          mistake_type: 'completion',
        }).catch(() => {});
      }
    });

    // Score MCQ questions
    mcqQs.forEach((q, i) => {
      const key = `mc_${i}`;
      const userAns = (answers[key] ?? '').trim().toUpperCase();
      if (userAns === q.answer) {
        correct++;
      } else {
        const userLabel = userAns ? `${userAns}. ${q.options[userAns] ?? ''}` : '(unanswered)';
        const correctLabel = `${q.answer}. ${q.options[q.answer] ?? ''}`;
        wrongAnswers.push({ key, question_type: 'MCQ', question: q.question, user_answer: userLabel, correct_answer: correctLabel });
        mistakesAPI.create({
          skill: 'listening', question: q.question,
          user_answer: userLabel, correct_answer: correctLabel,
          mistake_type: 'multiple_choice',
        }).catch(() => {});
      }
    });

    // Score matching questions
    matchingBlocks.forEach((block, bIdx) => {
      block.stems.forEach(stem => {
        const key = `match_${bIdx}_${stem.question_number}`;
        const userAns = (answers[key] ?? '').trim().toUpperCase();
        const correctAns = (block.answers[String(stem.question_number)] ?? '').trim().toUpperCase();
        if (userAns && userAns === correctAns) {
          correct++;
        } else {
          const correctOption = block.options.find(o => o.startsWith(correctAns)) ?? correctAns;
          const userOption = userAns ? (block.options.find(o => o.startsWith(userAns)) ?? userAns) : '(unanswered)';
          wrongAnswers.push({ key, question_type: 'matching', question: `${block.instruction}: ${stem.text}`, user_answer: userOption, correct_answer: correctOption });
          mistakesAPI.create({
            skill: 'listening', question: `${block.instruction}: ${stem.text}`,
            user_answer: userOption, correct_answer: correctOption,
            mistake_type: 'matching',
          }).catch(() => {});
        }
      });
    });

    setScore({ correct, total: totalQuestions });
    setSubmitted(true);

    // Submit to backend
    if (exercise.practice_db_id) {
      const band = Math.round((3.5 + (correct / totalQuestions) * 4.5) * 2) / 2;
      practiceAPI.submitAIListening(
        exercise.practice_db_id, JSON.stringify(answers),
        band, correct, totalQuestions,
      ).catch(() => {});

      const studyMinutes = Math.max(1, Math.min(30, Math.round((Date.now() - startTime) / 60000)));
      progressAPI.updateProgress({
        skill: 'listening', correct_answers: correct,
        total_questions: totalQuestions, study_time_minutes: studyMinutes,
        band_score: band,
      }).catch(() => {});
      progressAPI.createSession({ skill: 'listening', duration_minutes: studyMinutes }).catch(() => {});
    }

    // Fetch explanations for wrong answers
    if (wrongAnswers.length > 0) {
      setExplanationsLoading(true);
      practiceAPI.explainMistakes(exercise.transcript, wrongAnswers)
        .then(res => {
          const map: Record<string, string> = {};
          for (const item of (res.data.explanations ?? [])) map[item.key] = item.explanation;
          setExplanations(map);
        })
        .catch(() => {})
        .finally(() => setExplanationsLoading(false));
    }
  };

  // Merge all questions into a single list sorted by question_number for display
  const allQuestions: { type: 'completion' | 'mcq' | 'matching'; q: any; idx: number; num: number; blockIdx?: number }[] = [
    ...completionQs.map((q, i) => ({ type: 'completion' as const, q, idx: i, num: q.question_number })),
    ...mcqQs.map((q, i) => ({ type: 'mcq' as const, q, idx: i, num: q.question_number })),
    ...matchingBlocks.flatMap((block, bIdx) =>
      block.stems.map(stem => ({ type: 'matching' as const, q: { ...stem, block }, idx: bIdx, num: stem.question_number, blockIdx: bIdx }))
    ),
  ].sort((a, b) => a.num - b.num);

  return (
    <div className="ai-listening-view">
      {/* Audio Player */}
      <div className="audio-player">
        <audio
          ref={audioRef}
          src={audioUrl}
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={() => setIsPlaying(false)}
        />
        <div className="player-controls">
          <button className="player-btn" onClick={togglePlay} title={isPlaying ? 'Pause' : 'Play'}>
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
          <button className="player-btn speed-btn" onClick={changeSpeed} title="Change speed">
            {playbackRate}x
          </button>
          <button className="player-btn" onClick={replay} title="Replay from start">
            <RotateCcw size={16} />
          </button>
        </div>
        <div className="player-info">
          <span className="format-badge">{exercise.meta.format}</span>
          <span className="topic-label">{exercise.meta.topic}</span>
        </div>
      </div>

      {/* Transcript (after submit) — lyrics mode with time-synced highlighting */}
      {submitted && (() => {
        const timestamps = exercise.line_timestamps;
        const hasLyrics = timestamps && timestamps.length > 0;
        // Sentence-level timestamps include "text" field (monologues)
        const hasSentenceText = hasLyrics && !!timestamps[0].text;
        // Find active line: last line whose start <= currentTime
        const activeIdx = hasLyrics
          ? timestamps.reduce((acc, t) => (currentTime >= t.start ? t.line_index : acc), -1)
          : -1;

        // Build display lines: use timestamp texts for monologues, transcript lines for dialogues
        const displayLines = hasSentenceText
          ? timestamps.map(t => t.text!)
          : exercise.transcript.split('\n').filter(Boolean);

        return (
          <div className="transcript-section">
            <button className="transcript-toggle" onClick={() => setShowTranscript(!showTranscript)}>
              <FileText size={16} />
              {showTranscript ? 'Hide Transcript' : 'Show Transcript'}
            </button>
            {showTranscript && (
              <div className="transcript-content">
                {displayLines.map((line, i) => {
                  const isActive = hasLyrics && i === activeIdx && isPlaying;
                  const colonIdx = line.indexOf(':');
                  const hasSpeaker = !hasSentenceText && colonIdx > 0 && colonIdx < 30;
                  return (
                    <p
                      key={i}
                      ref={el => { transcriptLineRefs.current[i] = el; }}
                      className={`transcript-line ${hasLyrics ? 'transcript-clickable' : ''} ${isActive ? 'transcript-line-active' : ''}`}
                      onClick={() => {
                        if (hasLyrics && timestamps[i] && audioRef.current) {
                          audioRef.current.currentTime = timestamps[i].start;
                          setCurrentTime(timestamps[i].start);
                        }
                      }}
                    >
                      {hasSpeaker ? (
                        <><span className="transcript-speaker">{line.slice(0, colonIdx)}:</span> {line.slice(colonIdx + 1).trim()}</>
                      ) : line}
                    </p>
                  );
                })}
              </div>
            )}
          </div>
        );
      })()}

      {/* Questions */}
      <div className="listening-questions">
        <h3>Questions (1–{totalQuestions})</h3>
        {allQuestions.map((item, allIdx) => {
          if (item.type === 'completion') {
            const q = item.q;
            const key = `comp_${item.idx}`;
            const userAns = (answers[key] ?? '').trim();
            const matches = completionMatch(userAns, q.answer);
            const isCorrect = submitted && matches;
            const isWrong = submitted && !matches;
            // Show group_title header for form/table/note subtypes (first in group)
            const groupTitle = q.group_title;
            const subtype = q.subtype || 'sentence';
            const prevItem = allIdx > 0 ? allQuestions[allIdx - 1] : null;
            const showGroupTitle = groupTitle && (
              !prevItem || prevItem.type !== 'completion' || prevItem.q.group_title !== groupTitle
            );
            return (
              <React.Fragment key={key}>
                {showGroupTitle && (
                  <div className={`completion-group-header completion-group-${subtype}`}>
                    {groupTitle}
                  </div>
                )}
                <div className={`question-block ${subtype !== 'sentence' ? `qb-${subtype}` : ''} ${isCorrect ? 'q-correct' : ''} ${isWrong ? 'q-wrong' : ''}`}>
                  <div className="q-number">{q.question_number}</div>
                  <div className="q-body">
                    <p className="q-text">{q.text}</p>
                    <input
                      className={`completion-input ${isCorrect ? 'input-correct' : ''} ${isWrong ? 'input-wrong' : ''}`}
                      type="text"
                      placeholder="Type your answer…"
                      value={answers[key] ?? ''}
                      onChange={e => setAnswer(key, e.target.value)}
                      disabled={submitted}
                    />
                    {isWrong && <span className="correct-label">Correct: {q.answer}</span>}
                    {isWrong && (
                      explanations[key]
                        ? <p className="answer-explanation">{explanations[key]}</p>
                        : explanationsLoading
                          ? <p className="explanation-loading">Explaining…</p>
                          : null
                    )}
                  </div>
                  {submitted && (isCorrect
                    ? <Check size={18} className="q-icon correct" />
                    : <X size={18} className="q-icon incorrect" />)}
                </div>
              </React.Fragment>
            );
          } else if (item.type === 'mcq') {
            const q = item.q;
            const key = `mc_${item.idx}`;
            const userAns = (answers[key] ?? '').trim().toUpperCase();
            const optionKeys = Object.keys(q.options);
            return (
              <div key={key} className={`question-block ${submitted && userAns === q.answer ? 'q-correct' : ''} ${submitted && userAns !== q.answer ? 'q-wrong' : ''}`}>
                <div className="q-number">{q.question_number}</div>
                <div className="q-body">
                  <p className="q-text">{q.question}</p>
                  <div className="mcq-options">
                    {optionKeys.map(letter => {
                      const selected = userAns === letter;
                      const isCorrectOption = submitted && letter === q.answer;
                      const isWrongSelection = submitted && selected && letter !== q.answer;
                      return (
                        <button
                          key={letter}
                          className={`option ${selected && !submitted ? 'selected' : ''} ${isCorrectOption ? 'correct' : ''} ${isWrongSelection ? 'incorrect' : ''}`}
                          onClick={() => !submitted && setAnswer(key, letter)}
                          disabled={submitted}
                        >
                          <span className="option-letter">{letter}</span>
                          <span className="option-text">{q.options[letter]}</span>
                          {isCorrectOption && <Check size={16} className="result-icon correct" />}
                          {isWrongSelection && <X size={16} className="result-icon incorrect" />}
                        </button>
                      );
                    })}
                  </div>
                  {submitted && userAns !== q.answer && (
                    explanations[key]
                      ? <p className="answer-explanation">{explanations[key]}</p>
                      : explanationsLoading
                        ? <p className="explanation-loading">Explaining…</p>
                        : null
                  )}
                </div>
              </div>
            );
          } else {
            // Matching question
            const stem = item.q;
            const block = stem.block as AIListeningMatchingBlock;
            const bIdx = item.blockIdx!;
            const key = `match_${bIdx}_${stem.question_number}`;
            const userAns = (answers[key] ?? '').trim().toUpperCase();
            const correctAns = (block.answers[String(stem.question_number)] ?? '').trim().toUpperCase();
            const isCorrect = submitted && userAns === correctAns;
            const isWrong = submitted && userAns !== correctAns;
            // Show instruction header for the first stem in a block
            const isFirstInBlock = stem.question_number === block.question_number_start;
            return (
              <React.Fragment key={key}>
                {isFirstInBlock && (
                  <div className="matching-instruction">
                    <p>{block.instruction}</p>
                    <div className="matching-options-pool">
                      {block.options.map((opt, oi) => (
                        <span key={oi} className="matching-option-tag">{opt}</span>
                      ))}
                    </div>
                  </div>
                )}
                <div className={`question-block ${isCorrect ? 'q-correct' : ''} ${isWrong ? 'q-wrong' : ''}`}>
                  <div className="q-number">{stem.question_number}</div>
                  <div className="q-body">
                    <p className="q-text">{stem.text}</p>
                    <select
                      className={`matching-select ${isCorrect ? 'input-correct' : ''} ${isWrong ? 'input-wrong' : ''}`}
                      value={answers[key] ?? ''}
                      onChange={e => setAnswer(key, e.target.value)}
                      disabled={submitted}
                    >
                      <option value="">— Select —</option>
                      {block.options.map((opt, oi) => {
                        const letter = opt.split('.')[0]?.trim() || opt.charAt(0);
                        return <option key={oi} value={letter}>{opt}</option>;
                      })}
                    </select>
                    {isWrong && <span className="correct-label">Correct: {block.options.find(o => o.startsWith(correctAns)) ?? correctAns}</span>}
                    {isWrong && (
                      explanations[key]
                        ? <p className="answer-explanation">{explanations[key]}</p>
                        : explanationsLoading
                          ? <p className="explanation-loading">Explaining…</p>
                          : null
                    )}
                  </div>
                  {submitted && (isCorrect
                    ? <Check size={18} className="q-icon correct" />
                    : <X size={18} className="q-icon incorrect" />)}
                </div>
              </React.Fragment>
            );
          }
        })}

        {!submitted ? (
          <div className="submit-row">
            <button className="btn btn-primary" onClick={handleSubmit}>
              {t('practice.submit')}
            </button>
          </div>
        ) : (
          <div className="ai-result-summary">
            <div className="ai-score">
              <span className="score-big">{score?.correct}/{score?.total}</span>
              <span className="score-sub">correct</span>
            </div>
            <button className="btn btn-primary" onClick={() => onComplete(score!.correct, score!.total)}>
              Finish
            </button>
          </div>
        )}
      </div>

      <style>{`
        .ai-listening-view { max-width: 800px; margin: 0 auto; }
        .audio-player { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); margin-bottom: var(--spacing-lg); }
        .player-controls { display: flex; align-items: center; gap: var(--spacing-sm); }
        .player-btn { background: none; border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; color: var(--color-text-primary); transition: all var(--transition-fast); }
        .player-btn:hover { border-color: var(--color-primary); color: var(--color-primary); }
        .speed-btn { font-size: 0.75rem; font-weight: 700; min-width: 40px; padding: 6px 8px; }
        .player-time { font-size: 0.75rem; color: var(--color-text-secondary); font-variant-numeric: tabular-nums; min-width: 36px; text-align: center; }
        .player-progress { flex: 1; height: 4px; accent-color: var(--color-primary); cursor: pointer; }
        .player-info { display: flex; align-items: center; gap: var(--spacing-sm); margin-top: var(--spacing-sm); }
        .format-badge { background: rgba(16,185,129,0.12); color: #10B981; padding: 2px 8px; border-radius: var(--radius-full); font-size: 0.7rem; font-weight: 700; text-transform: capitalize; }
        .topic-label { font-size: 0.85rem; color: var(--color-text-secondary); }

        .listening-questions { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); }
        .listening-questions h3 { margin-bottom: var(--spacing-md); font-size: 1rem; }
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
        .completion-group-header + .question-block { border-top-left-radius: 0; border-top-right-radius: 0; }
        .qb-form .q-text, .qb-note .q-text { font-family: var(--font-mono, monospace); font-size: 0.85rem; }
        .qb-note .q-text { padding-left: 8px; border-left: 2px solid var(--color-primary); }
        .qb-table .q-text { font-size: 0.85rem; color: var(--color-text-secondary); }

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

        .transcript-section { margin-bottom: var(--spacing-lg); }
        .transcript-toggle { display: inline-flex; align-items: center; gap: 6px; background: none; border: 1px solid var(--color-border); color: var(--color-text-secondary); padding: 6px 14px; border-radius: var(--radius-md); font-size: 0.85rem; font-weight: 500; cursor: pointer; transition: all var(--transition-fast); }
        .transcript-toggle:hover { border-color: var(--color-primary); color: var(--color-primary); }
        .transcript-content { margin-top: var(--spacing-sm); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-md); max-height: 300px; overflow-y: auto; }
        .transcript-line { font-size: 0.875rem; line-height: 1.7; color: var(--color-text-primary); margin-bottom: var(--spacing-xs); padding: 2px 6px; border-radius: var(--radius-sm); transition: background 0.2s, opacity 0.2s; }
        .transcript-clickable { cursor: pointer; }
        .transcript-clickable:hover { background: var(--color-border); }
        .transcript-line-active { background: color-mix(in srgb, var(--color-primary) 12%, transparent); font-weight: 500; }
        .transcript-speaker { font-weight: 600; color: var(--color-primary); }

        .submit-row { display: flex; justify-content: center; margin-top: var(--spacing-lg); }
        .ai-result-summary { display: flex; align-items: center; justify-content: center; gap: var(--spacing-lg); margin-top: var(--spacing-lg); padding: var(--spacing-md); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); }
        .ai-score { display: flex; flex-direction: column; align-items: center; }
        .score-big { font-size: 1.5rem; font-weight: 700; color: var(--color-primary); }
        .score-sub { font-size: 0.75rem; color: var(--color-text-secondary); }
        .answer-explanation { font-size: 0.8rem; color: var(--color-text-secondary); font-style: italic; margin-top: var(--spacing-xs); line-height: 1.5; border-left: 2px solid var(--color-primary); padding-left: var(--spacing-sm); }
        .explanation-loading { font-size: 0.75rem; color: var(--color-text-secondary); font-style: italic; margin-top: var(--spacing-xs); opacity: 0.7; }
      `}</style>
    </div>
  );
}

export default AIListeningExerciseView;
