import { useState, useEffect, useRef, useCallback } from 'react';
import { practiceAPI, progressAPI } from '../../api';
import type {
  AISpeakingPractice, SpeakingGradingResult, SpeakingPronunciationWord, SpeakingInsights,
} from '../../types';

interface AISpeakingViewProps {
  exercise: AISpeakingPractice;
  onBack: () => void;
}

type SpeakingStage = 'cue_card' | 'preparation' | 'recording' | 'processing' | 'results';
type ProcessingStep = 'transcribing' | 'pronunciation' | 'grading';

const PROCESSING_STEPS: { key: ProcessingStep; label: string; icon: string; duration: number }[] = [
  { key: 'transcribing', label: 'Transcribing your speech...', icon: '🎧', duration: 6000 },
  { key: 'pronunciation', label: 'Analyzing response...', icon: '🔍', duration: 3000 },
  { key: 'grading', label: 'Examiner is grading...', icon: '📝', duration: 8000 },
];

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
  const [processingStep, setProcessingStep] = useState(0);
  const [processingElapsed, setProcessingElapsed] = useState(0);
  const [pronLoading, setPronLoading] = useState(false);
  const [pronAnalyzed, setPronAnalyzed] = useState(false);
  const [pronWords, setPronWords] = useState<SpeakingPronunciationWord[]>([]);
  const [pronDiff, setPronDiff] = useState<{ oldPron: number; newPron: number; oldOverall: number; newOverall: number } | null>(null);
  const [speakingAvg, setSpeakingAvg] = useState<SpeakingInsights | null>(null);
  const [azureDetail, setAzureDetail] = useState<{ accuracy: number; fluency: number; prosody: number; composite: number } | null>(null);

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

  // Processing step animation — advance through steps based on elapsed time
  useEffect(() => {
    if (stage !== 'processing') {
      setProcessingStep(0);
      setProcessingElapsed(0);
      return;
    }
    const start = Date.now();
    const interval = setInterval(() => {
      const elapsed = Date.now() - start;
      setProcessingElapsed(elapsed);
      let cumulative = 0;
      for (let i = 0; i < PROCESSING_STEPS.length; i++) {
        cumulative += PROCESSING_STEPS[i].duration;
        if (elapsed < cumulative) { setProcessingStep(i); return; }
      }
      setProcessingStep(PROCESSING_STEPS.length - 1);
    }, 200);
    return () => clearInterval(interval);
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

  const handleAnalyzePronunciation = async () => {
    setPronLoading(true);
    try {
      const res = await practiceAPI.analyzePronunciation(exercise.practice_db_id);
      const data = res.data;
      setPronWords(data.pronunciation_words || []);
      setPronAnalyzed(true);
      setAzureDetail(data.azure_scores || null);
      setPronDiff({
        oldPron: data.old_pronunciation_band,
        newPron: data.pronunciation_band,
        oldOverall: data.old_overall_band,
        newOverall: data.overall_band,
      });
      // Update grading with new pronunciation band + overall
      if (grading && data.pronunciation_band != null) {
        setGrading({
          ...grading,
          examiner_result: {
            ...grading.examiner_result,
            pronunciation: {
              ...grading.examiner_result.pronunciation,
              band: data.pronunciation_band,
              azure_scores: data.azure_scores,
            },
            overall_band: data.overall_band,
          },
          pronunciation_words: data.pronunciation_words,
          has_pronunciation_analysis: true,
        } as any);
      }
    } catch (err: any) {
      console.error('[Speaking] Pronunciation analysis error:', err);
      setError(err?.response?.data?.detail || 'Pronunciation analysis failed.');
    } finally {
      setPronLoading(false);
    }
  };

  const submitRecording = async (blob: Blob) => {
    setStage('processing');
    try {
      const res = await practiceAPI.submitAISpeaking(blob, exercise.practice_db_id);
      console.log('[Speaking] Grading response:', res.status, res.data);
      const result = res.data as SpeakingGradingResult;
      setGrading(result);
      setStage('results');

      // Fetch speaking insights for comparison (fire-and-forget)
      progressAPI.getSpeakingInsights().then(r => setSpeakingAvg(r.data)).catch(() => {});

      // Update progress (fire-and-forget — don't let failures hide grading results)
      const overallBand = result?.examiner_result?.overall_band ?? 0;
      const minutes = Math.min(Math.round(recordTime / 60) + 1, 30);
      progressAPI.updateProgress({
        skill: 'speaking',
        band_score: overallBand,
        correct_answers: 0,
        total_questions: 4,
        study_time_minutes: minutes,
      }).catch(e => console.warn('[Speaking] Progress update failed:', e));
      progressAPI.createSession({
        skill: 'speaking',
        duration_minutes: minutes,
        notes: `Speaking Part 2 (${exercise.meta.domain}) — Band ${overallBand}`,
      }).catch(e => console.warn('[Speaking] Session create failed:', e));
    } catch (err: any) {
      console.error('[Speaking] Submit error:', err?.response?.status, err?.response?.data, err?.message);
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail
        : Array.isArray(detail) ? detail.map((d: any) => d.msg || d).join('; ')
        : `Grading failed: ${err?.message || 'Please try again.'}`;
      setError(msg);
      setStage('cue_card');
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // ─── Render: Cue Card (Part 2 only — cue_card is always present) ───
  const cueCard = exercise.cue_card!;
  if (stage === 'cue_card') {
    return (
      <div className="speaking-container">
        <div className="speaking-cue-card">
          <h2 className="cue-topic">{cueCard.topic_line}</h2>
          <p className="cue-instruction">You should say:</p>
          <ul className="cue-bullets">
            {cueCard.bullets.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
          {cueCard.follow_up && (
            <p className="cue-followup">and explain {cueCard.follow_up}</p>
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
          <h2 className="cue-topic">{cueCard.topic_line}</h2>
          <ul className="cue-bullets">
            {cueCard.bullets.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
          {cueCard.follow_up && (
            <p className="cue-followup">and explain {cueCard.follow_up}</p>
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
    const currentStep = PROCESSING_STEPS[processingStep];
    const totalExpected = PROCESSING_STEPS.reduce((s, p) => s + p.duration, 0);
    const progressPct = Math.min((processingElapsed / totalExpected) * 100, 95);
    return (
      <div className="speaking-container">
        <div className="processing-view">
          <div className="processing-icon">{currentStep.icon}</div>
          <p className="processing-label">{currentStep.label}</p>
          <div className="processing-bar-track">
            <div className="processing-bar-fill" style={{ width: `${progressPct}%` }} />
          </div>
          <div className="processing-steps">
            {PROCESSING_STEPS.map((step, i) => (
              <div key={step.key} className={`processing-step ${i < processingStep ? 'done' : i === processingStep ? 'active' : ''}`}>
                <span className="step-icon">{i < processingStep ? '✓' : step.icon}</span>
                <span className="step-text">{step.label.replace('...', '')}</span>
              </div>
            ))}
          </div>
          <p className="processing-hint">This usually takes 10–20 seconds</p>
        </div>
        <style>{speakingStyles}</style>
      </div>
    );
  }

  // ─── Render: Results ───────────────────────────────────────────────
  const ex = grading?.examiner_result;
  const coaching = grading?.coaching_feedback;

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
              ['Fluency & Coherence', ex.fluency_coherence, 'fluency_coherence'],
              ['Lexical Resource', ex.lexical_resource, 'lexical_resource'],
              ['Grammar Range & Accuracy', ex.grammatical_range_accuracy, 'grammatical_range_accuracy'],
              ['Pronunciation', ex.pronunciation, 'pronunciation'],
            ] as [string, { band: number; evidence: string }, string][]).map(([label, data, name]) => {
              const avgCriterion = speakingAvg && speakingAvg.total_sessions > 1
                ? speakingAvg.criteria.find(c => c.name === name) : null;
              const delta = avgCriterion ? +(data.band - avgCriterion.average).toFixed(1) : null;
              return (
                <div key={label} className="band-card">
                  <div className="band-card-header">
                    <span className="band-card-label">{label}</span>
                    <div style={{ textAlign: 'right' }}>
                      <span className="band-card-score" style={{ color: bandColor(data.band) }}>{data.band}</span>
                      {avgCriterion && (
                        <div className="band-card-avg">
                          <span className="band-avg-text">avg: {avgCriterion.average.toFixed(1)}</span>
                          {delta !== null && delta !== 0 && (
                            <span className="band-delta" style={{ color: delta > 0 ? '#10B981' : '#EF4444' }}>
                              {delta > 0 ? '+' : ''}{delta}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  <p className="band-card-evidence">{data.evidence}</p>
                </div>
              );
            })}
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

      {/* Pronunciation Analysis — Layer 2 (on-demand) */}
      {pronAnalyzed ? (
        <div className="speaking-section">
          <h3>Pronunciation Analysis</h3>

          {/* Score update notification */}
          {pronDiff && (
            <div className="pron-update-banner">
              <div className="pron-update-row">
                <span>Pronunciation</span>
                <span>
                  <span className="pron-old-score">{pronDiff.oldPron}</span>
                  <span className="pron-arrow"> → </span>
                  <span className="pron-new-score" style={{ color: bandColor(pronDiff.newPron) }}>{pronDiff.newPron}</span>
                  {pronDiff.newPron !== pronDiff.oldPron && (
                    <span className={`pron-delta ${pronDiff.newPron > pronDiff.oldPron ? 'up' : 'down'}`}>
                      {pronDiff.newPron > pronDiff.oldPron ? '+' : ''}{pronDiff.newPron - pronDiff.oldPron}
                    </span>
                  )}
                </span>
              </div>
              {pronDiff.newOverall !== pronDiff.oldOverall && (
                <div className="pron-update-row">
                  <span>Overall Band</span>
                  <span>
                    <span className="pron-old-score">{pronDiff.oldOverall}</span>
                    <span className="pron-arrow"> → </span>
                    <span className="pron-new-score" style={{ color: bandColor(pronDiff.newOverall) }}>{pronDiff.newOverall}</span>
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Azure detail scores */}
          {azureDetail && (
            <div className="azure-scores">
              <div className="azure-score-item">
                <span className="azure-label">Accuracy</span>
                <div className="azure-bar-track"><div className="azure-bar-fill" style={{ width: `${azureDetail.accuracy}%`, background: pronColor(azureDetail.accuracy) }} /></div>
                <span className="azure-value">{azureDetail.accuracy}</span>
              </div>
              <div className="azure-score-item">
                <span className="azure-label">Fluency</span>
                <div className="azure-bar-track"><div className="azure-bar-fill" style={{ width: `${azureDetail.fluency}%`, background: pronColor(azureDetail.fluency) }} /></div>
                <span className="azure-value">{azureDetail.fluency}</span>
              </div>
              <div className="azure-score-item">
                <span className="azure-label">Prosody</span>
                <div className="azure-bar-track"><div className="azure-bar-fill" style={{ width: `${azureDetail.prosody}%`, background: pronColor(azureDetail.prosody) }} /></div>
                <span className="azure-value">{azureDetail.prosody}</span>
              </div>
            </div>
          )}

          {/* Mispronounced words */}
          {pronWords.length > 0 && (
            <>
              <h4 style={{ fontSize: '0.9rem', marginTop: 'var(--spacing-md)', marginBottom: 'var(--spacing-xs)' }}>Words to Practice ({pronWords.length})</h4>
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
            </>
          )}
        </div>
      ) : (
        <div className="speaking-section pron-cta">
          <div className="pron-cta-content">
            <span className="pron-cta-icon">🗣️</span>
            <div>
              <h3>Pronunciation Analysis</h3>
              <p className="pron-cta-desc">Get detailed word-by-word pronunciation scoring powered by AI speech analysis. See which words need work and track accuracy, fluency, and prosody.</p>
            </div>
          </div>
          <button
            className="btn btn-primary"
            onClick={handleAnalyzePronunciation}
            disabled={pronLoading}
          >
            {pronLoading ? 'Analyzing... (30-60s)' : 'Analyze My Pronunciation'}
          </button>
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
  .processing-view { display: flex; flex-direction: column; align-items: center; gap: var(--spacing-lg); padding: var(--spacing-2xl) var(--spacing-lg); }
  .processing-icon { font-size: 3rem; animation: processing-bounce 1.5s ease-in-out infinite; }
  @keyframes processing-bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
  .processing-label { font-size: 1.1rem; font-weight: 600; color: var(--color-text-primary); text-align: center; }
  .processing-bar-track { width: 100%; max-width: 300px; height: 6px; background: var(--color-border); border-radius: 3px; overflow: hidden; }
  .processing-bar-fill { height: 100%; background: linear-gradient(90deg, var(--color-primary), #8B5CF6); border-radius: 3px; transition: width 0.3s ease; }
  .processing-steps { display: flex; flex-direction: column; gap: 8px; width: 100%; max-width: 280px; margin-top: var(--spacing-sm); }
  .processing-step { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; color: var(--color-text-secondary); opacity: 0.4; transition: opacity 0.3s; }
  .processing-step.done { opacity: 1; color: #10B981; }
  .processing-step.active { opacity: 1; color: var(--color-text-primary); font-weight: 600; }
  .step-icon { font-size: 1rem; width: 24px; text-align: center; }
  .step-text { flex: 1; }
  .processing-hint { font-size: 0.75rem; color: var(--color-text-secondary); margin-top: var(--spacing-xs); }

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
  .band-card-avg { display: flex; align-items: center; gap: 4px; justify-content: flex-end; margin-top: 2px; }
  .band-avg-text { font-size: 0.7rem; color: var(--color-text-secondary); }
  .band-delta { font-size: 0.7rem; font-weight: 600; }

  /* Sections */
  .speaking-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); margin-bottom: var(--spacing-md); }
  .speaking-section h3 { font-size: 1rem; font-weight: 600; margin-bottom: var(--spacing-sm); color: var(--color-text-primary); }
  .transcript-text { line-height: 1.8; color: var(--color-text-primary); font-size: 0.95rem; }

  /* Pronunciation CTA */
  .pron-cta { text-align: center; }
  .pron-cta-content { display: flex; align-items: flex-start; gap: var(--spacing-md); text-align: left; margin-bottom: var(--spacing-md); }
  .pron-cta-icon { font-size: 2rem; flex-shrink: 0; }
  .pron-cta-content h3 { margin-bottom: 4px; }
  .pron-cta-desc { font-size: 0.85rem; color: var(--color-text-secondary); line-height: 1.5; }

  /* Pronunciation update banner */
  .pron-update-banner { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--spacing-md); margin-bottom: var(--spacing-md); }
  .pron-update-row { display: flex; justify-content: space-between; align-items: center; font-size: 0.9rem; padding: 4px 0; }
  .pron-old-score { color: var(--color-text-secondary); text-decoration: line-through; }
  .pron-arrow { color: var(--color-text-secondary); }
  .pron-new-score { font-weight: 700; font-size: 1.1rem; }
  .pron-delta { font-size: 0.8rem; font-weight: 600; margin-left: 4px; padding: 1px 6px; border-radius: 10px; }
  .pron-delta.up { background: #D1FAE5; color: #059669; }
  .pron-delta.down { background: #FEE2E2; color: #DC2626; }

  /* Azure detail scores */
  .azure-scores { display: flex; flex-direction: column; gap: 8px; margin-bottom: var(--spacing-md); }
  .azure-score-item { display: flex; align-items: center; gap: 8px; }
  .azure-label { font-size: 0.8rem; color: var(--color-text-secondary); width: 65px; flex-shrink: 0; }
  .azure-bar-track { flex: 1; height: 8px; background: var(--color-border); border-radius: 4px; overflow: hidden; }
  .azure-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
  .azure-value { font-size: 0.8rem; font-weight: 600; width: 30px; text-align: right; }

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
