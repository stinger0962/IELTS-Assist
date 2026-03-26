import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ChevronLeft } from 'lucide-react';
import { progressAPI } from '../api';
import type { SpeakingInsights, AccuracyInsights, UserProgress } from '../types';

function bandColor(band: number): string {
  if (band >= 7) return '#10B981';
  if (band >= 6) return '#F59E0B';
  return '#EF4444';
}

function accuracyColor(pct: number): string {
  if (pct >= 80) return '#10B981';
  if (pct >= 60) return '#F59E0B';
  return '#EF4444';
}

function trendArrow(trend: string): { symbol: string; color: string } {
  switch (trend) {
    case 'improving': return { symbol: '↑', color: '#10B981' };
    case 'declining': return { symbol: '↓', color: '#EF4444' };
    case 'stable': return { symbol: '→', color: '#888' };
    default: return { symbol: '—', color: '#888' };
  }
}

type SkillType = 'speaking' | 'writing' | 'reading' | 'listening' | 'grammar';
const CRITERION_SKILLS: SkillType[] = ['speaking', 'writing'];
const ACCURACY_SKILLS: SkillType[] = ['reading', 'listening', 'grammar'];

const CRITERION_DESCRIPTIONS: Record<string, string> = {
  // Speaking
  fluency_coherence: 'Speak smoothly with logical flow',
  lexical_resource: 'Use varied, precise vocabulary',
  grammatical_range_accuracy: 'Use complex structures accurately',
  pronunciation: 'Clear pronunciation and natural intonation',
  // Writing
  task_response: 'Address all parts of the question',
  coherence_cohesion: 'Organize ideas with clear paragraphing',
};

const QUESTION_TYPE_LABELS: Record<string, string> = {
  mcq: 'Multiple Choice',
  true_false_not_given: 'True / False / Not Given',
  completion: 'Completion',
  matching: 'Matching',
  yes_no_not_given: 'Yes / No / Not Given',
};

export default function SkillProgress() {
  const { skill } = useParams<{ skill: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [criterionInsights, setCriterionInsights] = useState<SpeakingInsights | null>(null);
  const [accuracyInsights, setAccuracyInsights] = useState<AccuracyInsights | null>(null);
  const [basicProgress, setBasicProgress] = useState<UserProgress | null>(null);
  const [loading, setLoading] = useState(true);

  const skillName = t(`skills.${skill}` as any) || skill || '';
  const isCriterionSkill = CRITERION_SKILLS.includes(skill as SkillType);
  const isAccuracySkill = ACCURACY_SKILLS.includes(skill as SkillType);

  useEffect(() => {
    loadData();
  }, [skill]);

  const loadData = async () => {
    setLoading(true);
    setCriterionInsights(null);
    setAccuracyInsights(null);
    try {
      const progressRes = await progressAPI.getProgress();
      const skillProgress = progressRes.data?.find((p: UserProgress) => p.skill === skill);
      if (skillProgress) setBasicProgress(skillProgress);

      if (skill === 'speaking') {
        const res = await progressAPI.getSpeakingInsights();
        setCriterionInsights(res.data);
      } else if (skill === 'writing') {
        const res = await progressAPI.getWritingInsights();
        setCriterionInsights(res.data);
      } else if (isAccuracySkill) {
        const res = await progressAPI.getAccuracyInsights(skill!);
        setAccuracyInsights(res.data);
      }
    } catch (e) {
      console.error('Failed to load progress:', e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="sp-container">
        <div className="sp-loading"><div className="loading-spinner" /></div>
        <style>{styles}</style>
      </div>
    );
  }

  // Empty state
  if (!basicProgress && !criterionInsights && !accuracyInsights) {
    return (
      <div className="sp-container">
        <div className="sp-header">
          <button className="sp-back" onClick={() => navigate('/')}><ChevronLeft size={16} /> Back</button>
          <h1 className="sp-title">{skillName} Progress</h1>
        </div>
        <div className="sp-empty">
          <p>No practice data yet</p>
          <button className="btn btn-primary" onClick={() => navigate('/practice')}>Start Practicing</button>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  // ─── Criterion-based view (speaking, writing) ────
  if (isCriterionSkill && criterionInsights && criterionInsights.total_sessions > 0) {
    return (
      <div className="sp-container">
        <div className="sp-header">
          <button className="sp-back" onClick={() => navigate('/')}><ChevronLeft size={16} /> Back</button>
          <h1 className="sp-title">{skillName} Progress</h1>
        </div>

        <div className="sp-summary">
          <div className="sp-stat">
            <span className="sp-stat-value" style={{ color: 'var(--color-primary)' }}>
              {criterionInsights.overall_average?.toFixed(1)}
            </span>
            <span className="sp-stat-label">Avg Band</span>
          </div>
          <div className="sp-stat">
            <span className="sp-stat-value" style={{ color: '#10B981' }}>
              {criterionInsights.best_session_band?.toFixed(1)}
            </span>
            <span className="sp-stat-label">Best</span>
          </div>
          <div className="sp-stat">
            <span className="sp-stat-value">{criterionInsights.total_sessions}</span>
            <span className="sp-stat-label">Sessions</span>
          </div>
        </div>

        <div className="sp-section">
          <h2 className="sp-section-title">Criterion Breakdown</h2>
          {criterionInsights.criteria.map((c) => {
            const barPct = Math.min((c.average / 9) * 100, 100);
            const ta = trendArrow(c.trend);
            const desc = CRITERION_DESCRIPTIONS[c.name];
            return (
              <div key={c.name} className="sp-criterion-row">
                <div className="sp-criterion">
                  <span className="sp-criterion-label">{c.label}</span>
                  <div className="sp-bar-track">
                    <div className="sp-bar-fill" style={{ width: `${barPct}%`, background: bandColor(c.average) }} />
                  </div>
                  <span className="sp-criterion-band">{c.average.toFixed(1)}</span>
                  <span className="sp-trend" style={{ color: ta.color }}>{ta.symbol}</span>
                </div>
                {desc && <div className="sp-criterion-desc">{desc}</div>}
              </div>
            );
          })}
        </div>

        {criterionInsights.weakest_criterion && (
          <div className="sp-focus">
            <div className="sp-focus-title">Focus Area: {criterionInsights.weakest_criterion}</div>
            {criterionInsights.weakest_recommendation && (
              <div className="sp-focus-rec">{criterionInsights.weakest_recommendation}</div>
            )}
          </div>
        )}

        {criterionInsights.recent_sessions.length > 0 && (
          <div className="sp-section">
            <h2 className="sp-section-title">Recent Sessions</h2>
            {criterionInsights.recent_sessions.map((s, i) => (
              <div key={i} className="sp-session">
                <span className="sp-session-date">
                  {new Date(s.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                </span>
                <span className="sp-session-band" style={{ color: bandColor(s.overall_band) }}>
                  {s.overall_band}
                </span>
                <span className="sp-session-topic">{s.topic || '—'}</span>
              </div>
            ))}
          </div>
        )}

        <button className="sp-cta" onClick={() => navigate('/practice')}>Practice {skillName}</button>
        <style>{styles}</style>
      </div>
    );
  }

  // ─── Accuracy-based view (reading, listening, grammar) ────
  if (isAccuracySkill && accuracyInsights && accuracyInsights.total_sessions > 0) {
    const ta = trendArrow(accuracyInsights.accuracy_trend);
    return (
      <div className="sp-container">
        <div className="sp-header">
          <button className="sp-back" onClick={() => navigate('/')}><ChevronLeft size={16} /> Back</button>
          <h1 className="sp-title">{skillName} Progress</h1>
        </div>

        <div className="sp-summary">
          <div className="sp-stat">
            <span className="sp-stat-value" style={{ color: accuracyColor(accuracyInsights.overall_accuracy || 0) }}>
              {accuracyInsights.overall_accuracy?.toFixed(0)}%
            </span>
            <span className="sp-stat-label">
              Accuracy <span style={{ color: ta.color, fontWeight: 700 }}>{ta.symbol}</span>
            </span>
          </div>
          {accuracyInsights.overall_average_band && (
            <div className="sp-stat">
              <span className="sp-stat-value" style={{ color: bandColor(accuracyInsights.overall_average_band) }}>
                {accuracyInsights.overall_average_band.toFixed(1)}
              </span>
              <span className="sp-stat-label">Avg Band</span>
            </div>
          )}
          <div className="sp-stat">
            <span className="sp-stat-value">{accuracyInsights.total_sessions}</span>
            <span className="sp-stat-label">Sessions</span>
          </div>
        </div>

        <div className="sp-section">
          <h2 className="sp-section-title">Overall Stats</h2>
          <div className="sp-accuracy-grid">
            <div className="sp-accuracy-item">
              <span className="sp-accuracy-val">{accuracyInsights.total_correct}</span>
              <span className="sp-accuracy-label">Correct</span>
            </div>
            <div className="sp-accuracy-item">
              <span className="sp-accuracy-val">{accuracyInsights.total_questions_answered}</span>
              <span className="sp-accuracy-label">Total Qs</span>
            </div>
            <div className="sp-accuracy-item">
              <span className="sp-accuracy-val" style={{ color: '#10B981' }}>{accuracyInsights.best_accuracy?.toFixed(0)}%</span>
              <span className="sp-accuracy-label">Best</span>
            </div>
            <div className="sp-accuracy-item">
              <span className="sp-accuracy-val" style={{ color: '#EF4444' }}>{accuracyInsights.worst_accuracy?.toFixed(0)}%</span>
              <span className="sp-accuracy-label">Worst</span>
            </div>
          </div>
        </div>

        {accuracyInsights.question_type_breakdown && accuracyInsights.question_type_breakdown.length > 0 && (
          <div className="sp-section">
            <h2 className="sp-section-title">Accuracy by Question Type</h2>
            {accuracyInsights.question_type_breakdown.map((qt) => {
              const barPct = Math.min(qt.accuracy, 100);
              return (
                <div key={qt.type} className="sp-criterion-row">
                  <div className="sp-criterion">
                    <span className="sp-criterion-label sp-qt-label">{QUESTION_TYPE_LABELS[qt.type] || qt.type}</span>
                    <div className="sp-bar-track">
                      <div className="sp-bar-fill" style={{ width: `${barPct}%`, background: accuracyColor(qt.accuracy) }} />
                    </div>
                    <span className="sp-criterion-band">{qt.accuracy.toFixed(0)}%</span>
                  </div>
                  <div className="sp-criterion-desc">{qt.correct}/{qt.total} correct</div>
                </div>
              );
            })}
          </div>
        )}

        {accuracyInsights.recent_sessions.length > 0 && (
          <div className="sp-section">
            <h2 className="sp-section-title">Recent Sessions</h2>
            {accuracyInsights.recent_sessions.map((s, i) => (
              <div key={i} className="sp-session">
                <span className="sp-session-date">
                  {new Date(s.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                </span>
                <span className="sp-session-band" style={{ color: accuracyColor(s.accuracy) }}>
                  {s.accuracy.toFixed(0)}%
                </span>
                <span className="sp-session-topic">{s.topic || '—'}</span>
                <span className="sp-session-detail">{s.correct}/{s.total_questions}</span>
              </div>
            ))}
          </div>
        )}

        <button className="sp-cta" onClick={() => navigate('/practice')}>Practice {skillName}</button>
        <style>{styles}</style>
      </div>
    );
  }

  // ─── Fallback (0 sessions for any skill) ────
  return (
    <div className="sp-container">
      <div className="sp-header">
        <button className="sp-back" onClick={() => navigate('/')}><ChevronLeft size={16} /> Back</button>
        <h1 className="sp-title">{skillName} Progress</h1>
      </div>

      <div className="sp-summary">
        <div className="sp-stat">
          <span className="sp-stat-value" style={{ color: 'var(--color-primary)' }}>
            {basicProgress?.band_score.toFixed(1) || '0.0'}
          </span>
          <span className="sp-stat-label">Band</span>
        </div>
        <div className="sp-stat">
          <span className="sp-stat-value">{basicProgress?.total_exercises || 0}</span>
          <span className="sp-stat-label">Exercises</span>
        </div>
        <div className="sp-stat">
          <span className="sp-stat-value">{basicProgress?.study_time_minutes || 0}</span>
          <span className="sp-stat-label">Minutes</span>
        </div>
      </div>

      <div className="sp-empty-inline">Complete a {skillName.toLowerCase()} exercise to see detailed insights</div>

      <button className="sp-cta" onClick={() => navigate('/practice')}>Practice {skillName}</button>
      <style>{styles}</style>
    </div>
  );
}

const styles = `
  .sp-container { max-width: 480px; margin: 0 auto; padding: 0 var(--spacing-md) var(--spacing-lg); }

  .sp-header { display: flex; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-md) 0; }
  .sp-back { display: flex; align-items: center; gap: 2px; background: none; border: none; color: var(--color-primary); font-size: 14px; cursor: pointer; padding: 0; }
  .sp-title { font-size: 1.25rem; font-weight: 700; flex: 1; }

  .sp-summary { display: flex; justify-content: space-around; padding: var(--spacing-lg) 0; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); margin-bottom: var(--spacing-md); }
  .sp-stat { text-align: center; }
  .sp-stat-value { display: block; font-size: 2rem; font-weight: 700; }
  .sp-stat-label { font-size: 0.75rem; color: var(--color-text-secondary); }

  .sp-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-md); margin-bottom: var(--spacing-md); }
  .sp-section-title { font-size: 0.9rem; font-weight: 600; margin-bottom: var(--spacing-sm); color: var(--color-text-primary); }

  .sp-criterion-row { margin-bottom: 12px; }
  .sp-criterion-row:last-child { margin-bottom: 0; }
  .sp-criterion { display: flex; align-items: center; gap: 8px; }
  .sp-criterion-desc { font-size: 0.7rem; color: var(--color-text-secondary); margin-top: 2px; padding-left: 0; }
  .sp-criterion-label { font-size: 0.75rem; color: var(--color-text-secondary); width: 36px; flex-shrink: 0; font-weight: 600; }
  .sp-qt-label { width: auto; min-width: 60px; max-width: 120px; font-size: 0.7rem; }
  .sp-bar-track { flex: 1; height: 10px; background: var(--color-border); border-radius: 5px; overflow: hidden; }
  .sp-bar-fill { height: 100%; border-radius: 5px; transition: width 0.4s ease; }
  .sp-criterion-band { font-size: 0.85rem; font-weight: 700; width: 28px; text-align: right; }
  .sp-trend { font-size: 1rem; font-weight: 700; width: 16px; text-align: center; }

  .sp-focus { border: 1px solid #F59E0B; border-radius: var(--radius-lg); padding: var(--spacing-sm) var(--spacing-md); background: #FFFBEB; margin-bottom: var(--spacing-md); }
  [data-theme="dark"] .sp-focus { background: #78350F22; }
  .sp-focus-title { font-size: 0.85rem; font-weight: 600; color: #92400E; }
  [data-theme="dark"] .sp-focus-title { color: #FCD34D; }
  .sp-focus-rec { font-size: 0.8rem; color: #92400E; margin-top: 4px; }
  [data-theme="dark"] .sp-focus-rec { color: #FCD34D; }

  .sp-session { display: flex; align-items: center; gap: var(--spacing-sm); padding: 6px 0; border-bottom: 1px solid var(--color-border); }
  .sp-session:last-child { border-bottom: none; }
  .sp-session-date { font-size: 0.8rem; color: var(--color-text-secondary); width: 55px; flex-shrink: 0; }
  .sp-session-band { font-size: 0.9rem; font-weight: 700; width: 36px; }
  .sp-session-topic { font-size: 0.8rem; color: var(--color-text-secondary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sp-session-detail { font-size: 0.75rem; color: var(--color-text-secondary); flex-shrink: 0; }

  .sp-accuracy-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--spacing-sm); }
  .sp-accuracy-item { text-align: center; }
  .sp-accuracy-val { display: block; font-size: 1.2rem; font-weight: 700; color: var(--color-text-primary); }
  .sp-accuracy-label { font-size: 0.7rem; color: var(--color-text-secondary); }

  .sp-cta { width: 100%; padding: 12px; background: var(--color-primary); color: white; border: none; border-radius: var(--radius-lg); font-size: 1rem; font-weight: 600; cursor: pointer; margin-top: var(--spacing-sm); }
  .sp-cta:hover { opacity: 0.9; }

  .sp-empty { text-align: center; padding: var(--spacing-2xl) var(--spacing-md); color: var(--color-text-secondary); }
  .sp-empty p { margin-bottom: var(--spacing-md); }
  .sp-empty-inline { text-align: center; padding: var(--spacing-lg); color: var(--color-text-secondary); font-size: 0.9rem; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); margin-bottom: var(--spacing-md); }

  .sp-loading { display: flex; justify-content: center; padding: var(--spacing-2xl); }
  .loading-spinner { width: 40px; height: 40px; border: 3px solid var(--color-border); border-top-color: var(--color-primary); border-radius: 50%; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
`;
