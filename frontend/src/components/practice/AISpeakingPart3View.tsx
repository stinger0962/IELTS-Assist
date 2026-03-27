import { useState, useEffect, useRef, useCallback } from 'react';
import { practiceAPI, progressAPI } from '../../api';
import type { AISpeakingPractice, SpeakingGradingResult, SpeakingInsights } from '../../types';
import { ConfettiBurst, CountUp } from '../Celebrations';

interface Props {
  exercise: AISpeakingPractice;
  onBack: () => void;
}

type Stage = 'intro' | 'interview' | 'processing' | 'results';

function bandColor(band: number): string {
  if (band >= 7) return '#10B981';
  if (band >= 6) return '#F59E0B';
  return '#EF4444';
}

export default function AISpeakingPart3View({ exercise, onBack }: Props) {
  const topics = exercise.topics || [];
  const allQuestions = topics.flatMap((t, ti) =>
    t.questions.map((q, qi) => ({ topic: t.area, question: q, topicIdx: ti, questionIdx: qi }))
  );
  const totalQ = allQuestions.length;

  const [stage, setStage] = useState<Stage>('intro');
  const [currentQ, setCurrentQ] = useState(0);
  const [recordTime, setRecordTime] = useState(0);
  const [grading, setGrading] = useState<SpeakingGradingResult | null>(null);
  const [speakingAvg, setSpeakingAvg] = useState<SpeakingInsights | null>(null);
  const [error, setError] = useState('');

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    };
  }, []);

  // Recording timer
  useEffect(() => {
    if (stage !== 'interview') return;
    timerRef.current = setInterval(() => {
      setRecordTime(t => t + 1);
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [stage, currentQ]);

  const negotiateMimeType = (): string => {
    const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
    for (const t of types) {
      if (MediaRecorder.isTypeSupported(t)) return t;
    }
    return '';
  };

  const startInterview = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Single continuous recording for the entire interview
      // (multiple webm blobs can't be concatenated — Whisper only reads the first container)
      const mimeType = negotiateMimeType();
      const options: MediaRecorderOptions = mimeType ? { mimeType } : {};
      const recorder = new MediaRecorder(stream, options);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.start();
      mediaRecorderRef.current = recorder;

      setStage('interview');
      setCurrentQ(0);
    } catch {
      setError('Microphone access denied. Please allow microphone access and try again.');
    }
  }, []);

  const handleNextQuestion = () => {
    const nextQ = currentQ + 1;
    if (nextQ >= totalQ) {
      // All questions done — stop recording and submit
      if (timerRef.current) clearInterval(timerRef.current);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.onstop = () => {
          if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
          const mimeType = negotiateMimeType() || 'audio/webm';
          const blob = new Blob(chunksRef.current, { type: mimeType });
          console.log('[Part1] Final blob:', blob.size, 'bytes,', chunksRef.current.length, 'chunks');
          submitFinalRecording(blob);
        };
        mediaRecorderRef.current.stop();
      }
    } else {
      setCurrentQ(nextQ);
      setRecordTime(0);
    }
  };

  const submitFinalRecording = async (blob: Blob) => {
    setStage('processing');

    console.log('[Part1] Submitting blob:', blob.size, 'bytes');

    if (blob.size < 5000) {
      setError('No audio was recorded. Please check your microphone and try again.');
      setStage('intro');
      return;
    }

    try {
      const res = await practiceAPI.submitAISpeaking(blob, exercise.practice_db_id);
      const result = res.data as SpeakingGradingResult;
      setGrading(result);
      setStage('results');

      // Fire-and-forget: insights + progress
      progressAPI.getSpeakingInsights().then(r => setSpeakingAvg(r.data)).catch(() => {});
      const overallBand = result?.examiner_result?.overall_band ?? 0;
      progressAPI.updateProgress({
        skill: 'speaking',
        band_score: overallBand,
        correct_answers: 0,
        total_questions: 4,
        study_time_minutes: Math.min(Math.round(totalQ * 0.5) + 1, 30),
      }).catch(() => {});
      progressAPI.createSession({
        skill: 'speaking',
        duration_minutes: Math.min(Math.round(totalQ * 0.5) + 1, 30),
        notes: `Speaking Part 3 Discussion — Band ${overallBand}`,
      }).catch(() => {});
    } catch (err: any) {
      console.error('[Part1] Submit error:', err);
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail
        : Array.isArray(detail) ? detail.map((d: any) => d.msg || d).join('; ')
        : `Grading failed: ${err?.message || 'Please try again.'}`;
      setError(msg);
      setStage('intro');
    }
  };

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;

  // ─── Error ────
  if (error) {
    return (
      <div className="p1-container">
        <div className="p1-error">
          <p>{error}</p>
          <button className="btn btn-primary" onClick={() => { setError(''); setStage('intro'); }}>Try Again</button>
          <button className="btn" onClick={onBack} style={{ marginTop: 8 }}>Back</button>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // ─── Intro ────
  if (stage === 'intro') {
    return (
      <div className="p1-container">
        <div className="p1-intro">
          <h2>Part 3: Discussion</h2>
          <p className="p1-intro-desc">The examiner will ask analytical questions about a topic. Give detailed answers of 30-60 seconds each.</p>
          <div className="p1-topics-preview">
            {topics.map((t, i) => (
              <div key={i} className="p1-topic-chip">{t.area}</div>
            ))}
          </div>
          <p className="p1-intro-count">{totalQ} questions · ~3-4 minutes</p>
          <button className="btn btn-primary btn-lg" onClick={startInterview}>Start Interview</button>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // ─── Interview (multi-turn) ────
  if (stage === 'interview' && currentQ < totalQ) {
    const q = allQuestions[currentQ];
    const isNewTopic = currentQ === 0 || allQuestions[currentQ - 1].topicIdx !== q.topicIdx;

    return (
      <div className="p1-container">
        {/* Progress */}
        <div className="p1-progress">
          <div className="p1-progress-bar">
            <div className="p1-progress-fill" style={{ width: `${((currentQ + 1) / totalQ) * 100}%` }} />
          </div>
          <span className="p1-progress-label">Q{currentQ + 1}/{totalQ}</span>
        </div>

        {/* Topic transition */}
        {isNewTopic && (
          <div className="p1-topic-header">Let's talk about <strong>{q.topic}</strong></div>
        )}

        {/* Question */}
        <div className="p1-question-card">
          <p className="p1-question-text">{q.question}</p>
        </div>

        {/* Recording indicator */}
        <div className="p1-recording">
          <div className="p1-rec-indicator">
            <span className="p1-rec-dot" />
            <span className="p1-rec-label">Recording</span>
            <span className="p1-rec-time">{formatTime(recordTime)}</span>
          </div>
        </div>

        {/* Next button */}
        <button className="p1-next-btn" onClick={handleNextQuestion}>
          {currentQ < totalQ - 1 ? 'Next Question →' : 'Finish Interview'}
        </button>

        <style>{styles}</style>
      </div>
    );
  }

  // ─── Processing ────
  if (stage === 'processing') {
    return (
      <div className="p1-container">
        <div className="p1-processing">
          <div className="p1-processing-icon">📝</div>
          <p className="p1-processing-label">Examiner is grading your interview...</p>
          <div className="p1-processing-bar-track">
            <div className="p1-processing-bar-fill" />
          </div>
          <p className="p1-processing-hint">This usually takes 10-20 seconds</p>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // ─── Results ────
  const ex = grading?.examiner_result;
  const coaching = grading?.coaching_feedback;

  return (
    <div className="p1-container">
      {ex && (
        <>
          <ConfettiBurst />
          <div className="p1-overall">
            <span className="p1-overall-label">Overall Band</span>
            <span className="p1-overall-band" style={{ color: bandColor(ex.overall_band) }}><CountUp value={ex.overall_band} decimals={1} /></span>
            <span className="p1-overall-part">Part 3 Discussion</span>
          </div>

          <div className="p1-band-cards">
            {([
              ['Fluency & Coherence', ex.fluency_coherence, 'fluency_coherence'],
              ['Lexical Resource', ex.lexical_resource, 'lexical_resource'],
              ['Grammar', ex.grammatical_range_accuracy, 'grammatical_range_accuracy'],
              ['Pronunciation', ex.pronunciation, 'pronunciation'],
            ] as [string, { band: number; evidence: string }, string][]).map(([label, data, name]) => {
              const avgC = speakingAvg && speakingAvg.total_sessions > 1
                ? speakingAvg.criteria.find(c => c.name === name) : null;
              const delta = avgC ? +(data.band - avgC.average).toFixed(1) : null;
              return (
                <div key={label} className="p1-band-card">
                  <div className="p1-band-header">
                    <span className="p1-band-label">{label}</span>
                    <div style={{ textAlign: 'right' }}>
                      <span className="p1-band-score" style={{ color: bandColor(data.band) }}>{data.band}</span>
                      {avgC && (
                        <div className="p1-band-avg">
                          <span>avg: {avgC.average.toFixed(1)}</span>
                          {delta !== null && delta !== 0 && (
                            <span style={{ color: delta > 0 ? '#10B981' : '#EF4444', fontWeight: 600, marginLeft: 4 }}>
                              {delta > 0 ? '+' : ''}{delta}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  <p className="p1-band-evidence">{data.evidence}</p>
                </div>
              );
            })}
          </div>
        </>
      )}

      {grading?.transcript && (
        <div className="p1-section">
          <h3>Your Transcript</h3>
          <p className="p1-transcript">{grading.transcript}</p>
        </div>
      )}

      {coaching && (
        <div className="p1-section">
          <h3>Coaching Feedback</h3>
          <p className="p1-coaching-summary">{coaching.summary}</p>
          {coaching.strengths.length > 0 && (
            <>
              <h4 className="p1-coaching-heading" style={{ color: '#10B981' }}>Strengths</h4>
              <ul className="p1-coaching-list">{coaching.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </>
          )}
          {coaching.improvements.length > 0 && (
            <>
              <h4 className="p1-coaching-heading" style={{ color: '#F59E0B' }}>Improvements</h4>
              <ul className="p1-coaching-list">{coaching.improvements.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </>
          )}
        </div>
      )}

      <div className="p1-actions">
        <button className="btn btn-primary btn-lg" onClick={onBack}>Finish</button>
      </div>

      <style>{styles}</style>
    </div>
  );
}

const styles = `
  .p1-container { max-width: 480px; margin: 0 auto; padding: var(--spacing-md); }

  /* Intro */
  .p1-intro { text-align: center; padding: var(--spacing-2xl) 0; }
  .p1-intro h2 { font-size: 1.5rem; margin-bottom: var(--spacing-sm); }
  .p1-intro-desc { color: var(--color-text-secondary); font-size: 0.9rem; margin-bottom: var(--spacing-lg); line-height: 1.5; }
  .p1-topics-preview { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin-bottom: var(--spacing-md); }
  .p1-topic-chip { background: var(--color-primary); color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 500; }
  .p1-intro-count { font-size: 0.8rem; color: var(--color-text-secondary); margin-bottom: var(--spacing-lg); }

  /* Progress bar */
  .p1-progress { display: flex; align-items: center; gap: 8px; margin-bottom: var(--spacing-md); }
  .p1-progress-bar { flex: 1; height: 6px; background: var(--color-border); border-radius: 3px; overflow: hidden; }
  .p1-progress-fill { height: 100%; background: var(--color-primary); border-radius: 3px; transition: width 0.3s ease; }
  .p1-progress-label { font-size: 0.8rem; font-weight: 600; color: var(--color-text-secondary); width: 45px; text-align: right; }

  /* Topic header */
  .p1-topic-header { text-align: center; font-size: 0.9rem; color: var(--color-text-secondary); padding: var(--spacing-sm) 0; margin-bottom: var(--spacing-sm); }

  /* Question card */
  .p1-question-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-xl); margin-bottom: var(--spacing-lg); min-height: 120px; display: flex; align-items: center; justify-content: center; }
  .p1-question-text { font-size: 1.2rem; font-weight: 600; color: var(--color-text-primary); text-align: center; line-height: 1.5; }

  /* Recording */
  .p1-recording { text-align: center; margin-bottom: var(--spacing-lg); }
  .p1-rec-indicator { display: inline-flex; align-items: center; gap: 8px; }
  .p1-rec-dot { width: 10px; height: 10px; border-radius: 50%; background: #EF4444; animation: p1-pulse 1s ease-in-out infinite; }
  @keyframes p1-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
  .p1-rec-label { font-size: 0.85rem; color: #EF4444; font-weight: 600; }
  .p1-rec-time { font-size: 0.85rem; color: var(--color-text-secondary); }

  /* Next button */
  .p1-next-btn { width: 100%; padding: 14px; background: var(--color-primary); color: white; border: none; border-radius: var(--radius-lg); font-size: 1rem; font-weight: 600; cursor: pointer; }
  .p1-next-btn:hover { opacity: 0.9; }

  /* Processing */
  .p1-processing { display: flex; flex-direction: column; align-items: center; gap: var(--spacing-md); padding: var(--spacing-2xl) 0; }
  .p1-processing-icon { font-size: 3rem; animation: p1-bounce 1.5s ease-in-out infinite; }
  @keyframes p1-bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
  .p1-processing-label { font-size: 1rem; font-weight: 600; color: var(--color-text-primary); }
  .p1-processing-bar-track { width: 100%; max-width: 250px; height: 6px; background: var(--color-border); border-radius: 3px; overflow: hidden; }
  .p1-processing-bar-fill { height: 100%; width: 0%; background: linear-gradient(90deg, var(--color-primary), #8B5CF6); border-radius: 3px; animation: p1-progress 15s ease-out forwards; }
  @keyframes p1-progress { to { width: 95%; } }
  .p1-processing-hint { font-size: 0.75rem; color: var(--color-text-secondary); }

  /* Results */
  .p1-overall { text-align: center; margin-bottom: var(--spacing-lg); }
  .p1-overall-label { display: block; font-size: 0.8rem; color: var(--color-text-secondary); }
  .p1-overall-band { display: block; font-size: 3rem; font-weight: 700; }
  .p1-overall-part { display: block; font-size: 0.75rem; color: var(--color-text-secondary); margin-top: 2px; }

  .p1-band-cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--spacing-sm); margin-bottom: var(--spacing-lg); }
  @media (max-width: 400px) { .p1-band-cards { grid-template-columns: 1fr; } }
  .p1-band-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--spacing-sm); }
  .p1-band-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
  .p1-band-label { font-size: 0.75rem; font-weight: 600; color: var(--color-text-primary); }
  .p1-band-score { font-size: 1.3rem; font-weight: 700; }
  .p1-band-avg { font-size: 0.65rem; color: var(--color-text-secondary); text-align: right; }
  .p1-band-evidence { font-size: 0.75rem; color: var(--color-text-secondary); line-height: 1.4; }

  .p1-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-md); margin-bottom: var(--spacing-md); }
  .p1-section h3 { font-size: 0.9rem; font-weight: 600; margin-bottom: var(--spacing-sm); }
  .p1-transcript { font-size: 0.85rem; line-height: 1.7; color: var(--color-text-primary); }
  .p1-coaching-summary { font-size: 0.85rem; color: var(--color-text-primary); line-height: 1.5; margin-bottom: var(--spacing-sm); }
  .p1-coaching-heading { font-size: 0.8rem; font-weight: 600; margin-bottom: 4px; }
  .p1-coaching-list { padding-left: var(--spacing-md); font-size: 0.8rem; line-height: 1.5; margin-bottom: var(--spacing-sm); }

  .p1-actions { text-align: center; margin-top: var(--spacing-md); }
  .p1-error { text-align: center; padding: var(--spacing-2xl) var(--spacing-md); color: #EF4444; }
`;
