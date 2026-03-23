import { useState, useEffect, useRef, useCallback } from 'react';
import { practiceAPI, progressAPI } from '../../api';
import type {
  AISpeakingPractice, SpeakingGradingResult, SpeakingPronunciationWord,
} from '../../types';

interface AISpeakingViewProps {
  exercise: AISpeakingPractice;
  onBack: () => void;
}

type SpeakingStage = 'cue_card' | 'preparation' | 'recording' | 'processing' | 'results';

function negotiateMimeType(): string {
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/ogg;codecs=opus',
    'audio/ogg',
  ];
  for (const t of types) {
    if (MediaRecorder.isTypeSupported(t)) return t;
  }
  return '';
}

function bandColor(band: number): string {
  if (band >= 7) return '#10B981';
  if (band >= 6) return '#F59E0B';
  return '#EF4444';
}

function pronColor(score: number): string {
  if (score >= 80) return '#10B981';
  if (score >= 60) return '#F59E0B';
  return '#EF4444';
}

export default function AISpeakingExerciseView({ exercise, onBack }: AISpeakingViewProps) {
  const [stage, setStage] = useState<SpeakingStage>('cue_card');
  const [prepTime, setPrepTime] = useState(60);
  const [recordTime, setRecordTime] = useState(0);
  const [grading, setGrading] = useState<SpeakingGradingResult | null>(null);
  const [error, setError] = useState('');

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const prepTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const recTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (prepTimerRef.current) clearInterval(prepTimerRef.current);
      if (recTimerRef.current) clearInterval(recTimerRef.current);
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    };
  }, []);

  // Preparation countdown
  useEffect(() => {
    if (stage !== 'preparation') return;
    setPrepTime(60);
    prepTimerRef.current = setInterval(() => {
      setPrepTime(prev => {
        if (prev <= 1) {
          if (prepTimerRef.current) clearInterval(prepTimerRef.current);
          startRecording();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => { if (prepTimerRef.current) clearInterval(prepTimerRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  // Recording timer (max 2 minutes)
  useEffect(() => {
    if (stage !== 'recording') return;
    setRecordTime(0);
    recTimerRef.current = setInterval(() => {
      setRecordTime(prev => {
        if (prev >= 119) {
          stopRecording();
          return 120;
        }
        return prev + 1;
      });
    }, 1000);
    return () => { if (recTimerRef.current) clearInterval(recTimerRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  const startRecording = useCallback(async () => {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = negotiateMimeType();
      const options: MediaRecorderOptions = mimeType ? { mimeType } : {};
      const recorder = new MediaRecorder(stream, options);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.onstop = () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunksRef.current, { type: mimeType || 'audio/webm' });
        console.log('[Speaking] Recording stopped, blob size:', blob.size, 'chunks:', chunksRef.current.length);
        if (blob.size < 1000) {
          setError('No audio was recorded. Please check your microphone and try again.');
          setStage('cue_card');
          return;
        }
        submitRecording(blob);
      };
      // No timeslice — collect entire recording as one blob on stop
      // Using timeslice (e.g. start(250)) causes race conditions where
      // onstop fires before the final ondataavailable completes
      recorder.start();
      mediaRecorderRef.current = recorder;
      setStage('recording');
    } catch {
      setError('Microphone access denied. Please allow microphone access and try again.');
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (recTimerRef.current) clearInterval(recTimerRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const submitRecording = async (blob: Blob) => {
    setStage('processing');
    try {
      const res = await practiceAPI.submitAISpeaking(blob, exercise.practice_db_id);
      const result = res.data as SpeakingGradingResult;
      setGrading(result);
      setStage('results');

      // Update progress
      const overallBand = result?.examiner_result?.overall_band ?? 0;
      const minutes = Math.min(Math.round(recordTime / 60) + 1, 30);
      await progressAPI.updateProgress({
        skill: 'speaking',
        band_score: overallBand,
        correct_answers: 0,
        total_questions: 4,
        study_time_minutes: minutes,
      });
      await progressAPI.createSession({
        skill: 'speaking',
        duration_minutes: minutes,
        notes: `Speaking Part 2 (${exercise.meta.domain}) — Band ${overallBand}`,
      });
    } catch (err: any) {
      console.error('[Speaking] Submit error:', err?.response?.status, err?.response?.data);
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail
        : Array.isArray(detail) ? detail.map((d: any) => d.msg || d).join('; ')
        : 'Grading failed. Please try again.';
      setError(msg);
      setStage('cue_card');
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // ─── Render: Cue Card ──────────────────────────────────────────────
  if (stage === 'cue_card') {
    return (
      <div className="speaking-container">
        <div className="speaking-cue-card">
          <h2 className="cue-topic">{exercise.cue_card.topic_line}</h2>
          <p className="cue-instruction">You should say:</p>
          <ul className="cue-bullets">
            {exercise.cue_card.bullets.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
          {exercise.cue_card.follow_up && (
            <p className="cue-followup">and explain {exercise.cue_card.follow_up}</p>
          )}
        </div>
        {error && <p className="speaking-error">{error}</p>}
        <div className="speaking-actions">
          <button className="btn btn-primary btn-lg" onClick={() => setStage('preparation')}>
            Start
          </button>
        </div>
        <style>{speakingStyles}</style>
      </div>
    );
  }

  // ─── Render: Preparation ───────────────────────────────────────────
  if (stage === 'preparation') {
    return (
      <div className="speaking-container">
        <div className="speaking-cue-card">
          <h2 className="cue-topic">{exercise.cue_card.topic_line}</h2>
          <ul className="cue-bullets">
            {exercise.cue_card.bullets.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
          {exercise.cue_card.follow_up && (
            <p className="cue-followup">and explain {exercise.cue_card.follow_up}</p>
          )}
        </div>
        <div className="prep-timer">
          <div className="prep-label">Preparation Time</div>
          <div className="prep-countdown">{prepTime}</div>
          <div className="prep-seconds">seconds remaining</div>
        </div>
        <div className="speaking-actions">
          <button className="btn btn-primary btn-lg" onClick={() => {
            if (prepTimerRef.current) clearInterval(prepTimerRef.current);
            startRecording();
          }}>
            Start Speaking Now
          </button>
        </div>
        <style>{speakingStyles}</style>
      </div>
    );
  }

  // ─── Render: Recording ─────────────────────────────────────────────
  if (stage === 'recording') {
    return (
      <div className="speaking-container">
        <div className="recording-indicator">
          <span className="rec-dot" />
          <span className="rec-label">Recording</span>
        </div>
        <div className="rec-timer">{formatTime(recordTime)}</div>
        <div className="rec-max">Max 2:00</div>
        <div className="speaking-actions">
          <button className="btn btn-lg" style={{ background: '#EF4444', color: '#fff', border: 'none' }} onClick={stopRecording}>
            Stop Recording
          </button>
        </div>
        <style>{speakingStyles}</style>
      </div>
    );
  }

  // ─── Render: Processing ────────────────────────────────────────────
  if (stage === 'processing') {
    return (
      <div className="speaking-container">
        <div className="processing-view">
          <div className="loading-spinner" />
          <p className="processing-text">Examiner is reviewing your response...</p>
        </div>
        <style>{speakingStyles}</style>
      </div>
    );
  }

  // ─── Render: Results ───────────────────────────────────────────────
  const ex = grading?.examiner_result;
  const coaching = grading?.coaching_feedback;
  const pronWords = grading?.pronunciation_words;

  return (
    <div className="speaking-container">
      {ex && (
        <>
          <div className="speaking-overall">
            <span className="overall-label">Overall Band</span>
            <span className="overall-band" style={{ color: bandColor(ex.overall_band) }}>
              {ex.overall_band}
            </span>
          </div>

          <div className="band-cards">
            {([
              ['Fluency & Coherence', ex.fluency_coherence],
              ['Lexical Resource', ex.lexical_resource],
              ['Grammar Range & Accuracy', ex.grammatical_range_accuracy],
              ['Pronunciation', ex.pronunciation],
            ] as [string, { band: number; evidence: string }][]).map(([label, data]) => (
              <div key={label} className="band-card">
                <div className="band-card-header">
                  <span className="band-card-label">{label}</span>
                  <span className="band-card-score" style={{ color: bandColor(data.band) }}>{data.band}</span>
                </div>
                <p className="band-card-evidence">{data.evidence}</p>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Transcript */}
      {grading?.transcript && (
        <div className="speaking-section">
          <h3>Your Transcript</h3>
          <p className="transcript-text">{grading.transcript}</p>
        </div>
      )}

      {/* Pronunciation Words */}
      {pronWords && pronWords.length > 0 && (
        <div className="speaking-section">
          <h3>Pronunciation Details</h3>
          <div className="pron-legend">
            <span><span className="pron-dot" style={{ background: '#10B981' }} /> Good (80+)</span>
            <span><span className="pron-dot" style={{ background: '#F59E0B' }} /> Fair (60-79)</span>
            <span><span className="pron-dot" style={{ background: '#EF4444' }} /> Needs Work (&lt;60)</span>
          </div>
          <div className="pron-words">
            {pronWords.map((w: SpeakingPronunciationWord, i: number) => (
              <span
                key={i}
                className="pron-word"
                style={{ color: pronColor(w.accuracy_score), borderColor: pronColor(w.accuracy_score) }}
                title={`${w.accuracy_score}% — ${w.error_type || 'OK'}`}
              >
                {w.word}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Coaching Feedback */}
      {coaching && (
        <div className="speaking-section">
          <h3>Coaching Feedback</h3>
          <p className="coaching-summary">{coaching.summary}</p>
          {coaching.strengths.length > 0 && (
            <>
              <h4 className="coaching-heading strengths">Strengths</h4>
              <ul className="coaching-list">
                {coaching.strengths.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </>
          )}
          {coaching.improvements.length > 0 && (
            <>
              <h4 className="coaching-heading improvements">Areas for Improvement</h4>
              <ul className="coaching-list">
                {coaching.improvements.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </>
          )}
        </div>
      )}

      {error && <p className="speaking-error">{error}</p>}

      <div className="speaking-actions">
        <button className="btn btn-primary btn-lg" onClick={onBack}>Finish</button>
      </div>
      <style>{speakingStyles}</style>
    </div>
  );
}

const speakingStyles = `
  .speaking-container { max-width: 720px; margin: 0 auto; padding: var(--spacing-lg) 0; }

  /* Cue Card */
  .speaking-cue-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-xl); margin-bottom: var(--spacing-lg); }
  .cue-topic { font-size: 1.25rem; font-weight: 600; color: var(--color-text-primary); margin-bottom: var(--spacing-md); }
  .cue-instruction { font-size: 0.875rem; color: var(--color-text-secondary); margin-bottom: var(--spacing-sm); }
  .cue-bullets { padding-left: var(--spacing-lg); margin-bottom: var(--spacing-md); }
  .cue-bullets li { margin-bottom: var(--spacing-xs); line-height: 1.6; color: var(--color-text-primary); }
  .cue-followup { font-style: italic; color: var(--color-text-secondary); }

  /* Prep Timer */
  .prep-timer { text-align: center; margin-bottom: var(--spacing-lg); }
  .prep-label { font-size: 0.875rem; color: var(--color-text-secondary); margin-bottom: var(--spacing-xs); }
  .prep-countdown { font-size: 4rem; font-weight: 700; color: var(--color-primary); line-height: 1; }
  .prep-seconds { font-size: 0.75rem; color: var(--color-text-secondary); margin-top: var(--spacing-xs); }

  /* Recording */
  .recording-indicator { display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: var(--spacing-md); }
  .rec-dot { width: 12px; height: 12px; border-radius: 50%; background: #EF4444; animation: rec-pulse 1s ease-in-out infinite; }
  @keyframes rec-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
  .rec-label { font-size: 1rem; font-weight: 600; color: #EF4444; }
  .rec-timer { text-align: center; font-size: 3rem; font-weight: 700; color: var(--color-text-primary); margin-bottom: var(--spacing-xs); }
  .rec-max { text-align: center; font-size: 0.75rem; color: var(--color-text-secondary); margin-bottom: var(--spacing-lg); }

  /* Processing */
  .processing-view { display: flex; flex-direction: column; align-items: center; gap: var(--spacing-md); padding: var(--spacing-2xl) 0; }
  .processing-text { font-size: 1rem; color: var(--color-text-secondary); }
  .loading-spinner { width: 40px; height: 40px; border: 3px solid var(--color-border); border-top-color: var(--color-primary); border-radius: 50%; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Actions */
  .speaking-actions { display: flex; justify-content: center; margin-top: var(--spacing-lg); }

  /* Error */
  .speaking-error { color: #EF4444; text-align: center; font-size: 0.875rem; margin-top: var(--spacing-sm); }

  /* Results */
  .speaking-overall { text-align: center; margin-bottom: var(--spacing-lg); }
  .overall-label { display: block; font-size: 0.875rem; color: var(--color-text-secondary); margin-bottom: 4px; }
  .overall-band { font-size: 3rem; font-weight: 700; }

  .band-cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--spacing-md); margin-bottom: var(--spacing-lg); }
  @media (max-width: 600px) { .band-cards { grid-template-columns: 1fr; } }
  .band-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--spacing-md); }
  .band-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--spacing-xs); }
  .band-card-label { font-size: 0.8rem; font-weight: 600; color: var(--color-text-primary); }
  .band-card-score { font-size: 1.5rem; font-weight: 700; }
  .band-card-evidence { font-size: 0.8rem; color: var(--color-text-secondary); line-height: 1.5; }

  /* Sections */
  .speaking-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); margin-bottom: var(--spacing-md); }
  .speaking-section h3 { font-size: 1rem; font-weight: 600; margin-bottom: var(--spacing-sm); color: var(--color-text-primary); }
  .transcript-text { line-height: 1.8; color: var(--color-text-primary); font-size: 0.95rem; }

  /* Pronunciation */
  .pron-legend { display: flex; gap: var(--spacing-md); font-size: 0.75rem; color: var(--color-text-secondary); margin-bottom: var(--spacing-sm); flex-wrap: wrap; }
  .pron-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }
  .pron-words { display: flex; flex-wrap: wrap; gap: 6px; }
  .pron-word { display: inline-block; padding: 2px 6px; border: 1px solid; border-radius: var(--radius-sm); font-size: 0.85rem; font-weight: 500; cursor: default; }

  /* Coaching */
  .coaching-summary { font-size: 0.9rem; color: var(--color-text-primary); line-height: 1.6; margin-bottom: var(--spacing-sm); }
  .coaching-heading { font-size: 0.85rem; font-weight: 600; margin-bottom: var(--spacing-xs); }
  .coaching-heading.strengths { color: #10B981; }
  .coaching-heading.improvements { color: #F59E0B; }
  .coaching-list { padding-left: var(--spacing-lg); font-size: 0.85rem; color: var(--color-text-primary); line-height: 1.6; margin-bottom: var(--spacing-sm); }
`;
