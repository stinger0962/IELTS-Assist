import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import {
  Flame,
  Clock,
  Target,
  BookOpen,
  AlertCircle,
  GraduationCap,
  TrendingUp
} from 'lucide-react';
import { useAppStore } from '../store';
import { progressAPI, goalsAPI } from '../api';
import type { GoalTodayProgressItem, ProgressStats, StudySession, Goal, UserProgress, SpeakingInsights } from '../types';

function ProgressRing({ progress, size = 80, strokeWidth = 8 }: { progress: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (progress / 100) * circumference;

  return (
    <svg width={size} height={size} className="progress-ring">
      <circle
        stroke="var(--color-border)"
        fill="transparent"
        strokeWidth={strokeWidth}
        r={radius}
        cx={size / 2}
        cy={size / 2}
      />
      <circle
        className="progress-ring-circle"
        stroke="var(--color-primary)"
        fill="transparent"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        r={radius}
        cx={size / 2}
        cy={size / 2}
        style={{
          strokeDasharray: circumference,
          strokeDashoffset: offset,
        }}
      />
    </svg>
  );
}

function StatCard({ icon: Icon, label, value, subValue, color }: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  subValue?: string;
  color: string;
}) {
  return (
    <div className="stat-card">
      <div className="stat-icon" style={{ background: `${color}20`, color }}>
        <Icon size={24} />
      </div>
      <div className="stat-info">
        <span className="stat-value">{value}</span>
        <span className="stat-label">{label}</span>
        {subValue && <span className="stat-sub">{subValue}</span>}
      </div>
    </div>
  );
}

function SkillCard({ progress, skillName, goalProgress, onClick, isExpanded }: {
  progress: UserProgress;
  skillName: string;
  goalProgress?: GoalTodayProgressItem;
  onClick?: () => void;
  isExpanded?: boolean;
}) {
  const hasGoal = goalProgress && goalProgress.target > 0;
  const ringPct = hasGoal
    ? Math.min(100, Math.round((goalProgress.actual / goalProgress.target) * 100))
    : progress.total_exercises > 0
      ? Math.round((progress.correct_answers / progress.total_exercises) * 100)
      : 0;
  const ringLabel = hasGoal
    ? `${goalProgress.actual}/${goalProgress.target}`
    : `${ringPct}%`;

  return (
    <div className={`skill-card${onClick ? ' skill-card-clickable' : ''}${isExpanded ? ' skill-card-expanded' : ''}`} onClick={onClick} style={onClick ? { cursor: 'pointer' } : undefined}>
      <div className="skill-header">
        <span className="skill-name">{skillName}{onClick ? (isExpanded ? ' ▾' : ' ▸') : ''}</span>
        <span className="skill-band">{progress.band_score.toFixed(1)}</span>
      </div>
      <div className="skill-progress">
        <div className="ring-wrapper">
          <ProgressRing progress={ringPct} size={60} strokeWidth={6} />
          <span className="ring-sub">{hasGoal ? 'today' : 'accuracy'}</span>
        </div>
        <div className="skill-stats">
          <div className="skill-stat">
            <span className="skill-stat-value">{progress.total_exercises}</span>
            <span className="skill-stat-label">Exercises</span>
          </div>
          <div className="skill-stat">
            <span className="skill-stat-value">{progress.study_time_minutes}</span>
            <span className="skill-stat-label">Min</span>
          </div>
          {hasGoal && (
            <div className="skill-stat">
              <span className="skill-stat-value" style={{ color: 'var(--color-primary)', fontSize: '0.875rem' }}>{ringLabel}</span>
              <span className="skill-stat-label">min</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, setStats } = useAppStore();
  const [stats, setLocalStats] = useState<ProgressStats | null>(null);
  const [sessions, setSessions] = useState<StudySession[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [todayProgress, setTodayProgress] = useState<GoalTodayProgressItem[]>([]);
  const [speakingInsights, setSpeakingInsights] = useState<SpeakingInsights | null>(null);
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [statsRes, sessionsRes, goalsRes, progressRes, speakingRes] = await Promise.all([
        progressAPI.getStats(),
        progressAPI.getSessions(5),
        goalsAPI.getAll(false, 5),
        goalsAPI.getTodayProgress(),
        progressAPI.getSpeakingInsights().catch(() => null),
      ]);
      setLocalStats(statsRes.data);
      setStats(statsRes.data);
      setSessions(sessionsRes.data);
      setGoals(goalsRes.data);
      setTodayProgress(progressRes.data);
      if (speakingRes) setSpeakingInsights(speakingRes.data);
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getSkillName = (skill: string) => {
    const key = `skills.${skill}` as const;
    return t(key);
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner" />
        <p>{t('common.loading')}</p>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <header className="page-header">
        <h1>{t('dashboard.welcome')} {user?.full_name || user?.username || ''}!</h1>
      </header>

      {/* Stats Overview */}
      <div className="stats-grid">
        <StatCard
          icon={Flame}
          label={t('dashboard.studyStreak')}
          value={stats?.streak_days || 0}
          subValue={t('dashboard.days')}
          color="#F59E0B"
        />
        <StatCard
          icon={Clock}
          label={t('dashboard.totalStudyTime')}
          value={Math.round((stats?.total_study_time || 0) / 60)}
          subValue={t('dashboard.hours')}
          color="#4F46E5"
        />
        <StatCard
          icon={Target}
          label={t('dashboard.avgBand')}
          value={stats?.average_band.toFixed(1) || '0.0'}
          subValue={`/ ${user?.target_band || 7.0}`}
          color="#10B981"
        />
        <StatCard
          icon={TrendingUp}
          label={t('skills.exercises')}
          value={stats?.total_exercises || 0}
          color="#EF4444"
        />
      </div>

      {/* Skills Progress */}
      <section className="section">
        <h2>{t('skills.progress')}</h2>
        <div className="skills-grid">
          {stats?.progress.map((p) => (
            <SkillCard
              key={p.id}
              progress={p}
              skillName={getSkillName(p.skill)}
              goalProgress={todayProgress.find(tp => tp.skill === p.skill && tp.goal_type === 'daily_minutes')}
              onClick={p.skill === 'speaking' ? () => setExpandedSkill(expandedSkill === 'speaking' ? null : 'speaking') : undefined}
              isExpanded={p.skill === 'speaking' && expandedSkill === 'speaking'}
            />
          ))}
        </div>
        {expandedSkill === 'speaking' && speakingInsights && (
          <div className="speaking-insights-panel">
            {speakingInsights.total_sessions === 0 ? (
              <p className="speaking-insights-empty">Complete a speaking exercise to see progress insights</p>
            ) : (
              <>
                {/* Criterion bars */}
                <div className="si-criteria">
                  {speakingInsights.criteria.map((c) => {
                    const barPct = Math.min((c.average / 9) * 100, 100);
                    const barClr = c.average >= 7 ? '#10B981' : c.average >= 6 ? '#F59E0B' : '#EF4444';
                    const trendArrow = c.trend === 'improving' ? '\u2191' : c.trend === 'declining' ? '\u2193' : c.trend === 'stable' ? '\u2192' : '\u2014';
                    const trendColor = c.trend === 'improving' ? '#10B981' : c.trend === 'declining' ? '#EF4444' : 'var(--color-text-secondary)';
                    return (
                      <div key={c.name} className="si-criterion-row">
                        <span className="si-criterion-label">{c.label}</span>
                        <div className="si-bar-track">
                          <div className="si-bar-fill" style={{ width: `${barPct}%`, background: barClr }} />
                        </div>
                        <span className="si-criterion-band">{c.average.toFixed(1)}</span>
                        <span className="si-trend" style={{ color: trendColor }}>{trendArrow}</span>
                      </div>
                    );
                  })}
                </div>

                {/* Weakest area callout */}
                {speakingInsights.weakest_criterion && (
                  <div className="si-weakest">
                    <strong>Weakest area: {speakingInsights.weakest_criterion}</strong>
                    {speakingInsights.weakest_recommendation && (
                      <p className="si-weakest-rec">{speakingInsights.weakest_recommendation}</p>
                    )}
                  </div>
                )}

                {/* Recent sessions */}
                {speakingInsights.recent_sessions.length > 0 && (
                  <div className="si-recent">
                    <h4 className="si-recent-title">Recent Sessions</h4>
                    {speakingInsights.recent_sessions.slice(0, 5).map((s, i) => (
                      <div key={i} className="si-session-row">
                        <span className="si-session-date">{new Date(s.date).toLocaleDateString()}</span>
                        <span className="si-session-band" style={{ color: s.overall_band >= 7 ? '#10B981' : s.overall_band >= 6 ? '#F59E0B' : '#EF4444' }}>
                          {s.overall_band}
                        </span>
                        {s.topic && <span className="si-session-topic">{s.topic}</span>}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </section>

      {/* Quick Actions */}
      <section className="section">
        <h2>{t('dashboard.quickActions')}</h2>
        <div className="quick-actions">
          <button className="action-card" onClick={() => navigate('/practice')}>
            <BookOpen size={24} />
            <span>{t('dashboard.startPractice')}</span>
          </button>
          <button className="action-card" onClick={() => navigate('/mistakes')}>
            <AlertCircle size={24} />
            <span>{t('dashboard.reviewMistakes')}</span>
          </button>
          <button className="action-card" onClick={() => navigate('/topics')}>
            <GraduationCap size={24} />
            <span>{t('dashboard.reviewTopics')}</span>
          </button>
        </div>
      </section>

      <div className="dashboard-grid">
        {/* Recent Activity */}
        <section className="section">
          <h2>{t('dashboard.recentActivity')}</h2>
          <div className="card">
            {sessions.length > 0 ? (
              <div className="activity-list">
                {sessions.map((session) => (
                  <div key={session.id} className="activity-item">
                    <div className="activity-icon">
                      <Clock size={16} />
                    </div>
                    <div className="activity-info">
                      <span className="activity-title">
                        {session.skill ? getSkillName(session.skill) : 'Study Session'}
                      </span>
                      <span className="activity-time">
                        {new Date(session.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <span className="activity-duration">{session.duration_minutes} min</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-state">{t('dashboard.noActivity')}</p>
            )}
          </div>
        </section>

        {/* Active Goals */}
        <section className="section">
          <h2>{t('goals.active')}</h2>
          <div className="card">
            {goals.length > 0 ? (
              <div className="goals-list">
                {goals.map((goal) => {
                  const prog = todayProgress.find(p => p.goal_id === goal.id);
                  const pct = prog && prog.target > 0
                    ? Math.min(100, Math.round((prog.actual / prog.target) * 100))
                    : null;
                  return (
                    <div key={goal.id} className="goal-item">
                      <Target size={16} />
                      <div className="goal-item-content">
                        <span className="goal-title">{goal.title}</span>
                        {pct !== null && (
                          <div className="goal-mini-progress">
                            <div className="goal-mini-track">
                              <div className="goal-mini-fill" style={{ width: `${pct}%` }} />
                            </div>
                            <span className="goal-mini-label">
                              {prog!.goal_type === 'weekly_exercises'
                                ? `${prog!.actual}/${prog!.target} this week`
                                : `${prog!.actual}/${prog!.target} min today`}
                            </span>
                          </div>
                        )}
                      </div>
                      {goal.target_date && (
                        <span className="goal-date">
                          {new Date(goal.target_date).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="empty-state">{t('goals.noGoals')}</p>
            )}
          </div>
        </section>
      </div>

      <style>{`
        .dashboard {
          max-width: 1200px;
          margin: 0 auto;
          overflow-x: hidden;
          width: 100%;
          box-sizing: border-box;
        }

        .page-header {
          margin-bottom: var(--spacing-lg);
        }

        .page-header h1 {
          font-size: 1.75rem;
        }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: var(--spacing-md);
          margin-bottom: var(--spacing-xl);
        }

        @media (max-width: 1024px) {
          .stats-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 480px) {
          .stats-grid {
            grid-template-columns: 1fr 1fr;
            gap: var(--spacing-sm);
          }
          .stat-card {
            padding: var(--spacing-sm);
            gap: var(--spacing-sm);
          }
          .stat-icon {
            width: 36px;
            height: 36px;
          }
          .stat-value {
            font-size: 1.25rem;
          }
        }

        .stat-card {
          display: flex;
          align-items: center;
          gap: var(--spacing-md);
          padding: var(--spacing-md);
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
        }

        .stat-icon {
          width: 48px;
          height: 48px;
          border-radius: var(--radius-md);
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .stat-info {
          display: flex;
          flex-direction: column;
        }

        .stat-value {
          font-size: 1.5rem;
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .stat-label {
          font-size: 0.875rem;
          color: var(--color-text-secondary);
        }

        .stat-sub {
          font-size: 0.75rem;
          color: var(--color-text-secondary);
        }

        .section {
          margin-bottom: var(--spacing-xl);
        }

        .section h2 {
          margin-bottom: var(--spacing-md);
        }

        .skills-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: var(--spacing-md);
        }

        @media (max-width: 1024px) {
          .skills-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 480px) {
          .skills-grid {
            grid-template-columns: 1fr 1fr;
            gap: var(--spacing-sm);
          }
          .skill-card {
            padding: var(--spacing-sm);
            overflow: hidden;
          }
          .skill-progress {
            flex-wrap: wrap;
            gap: var(--spacing-xs);
          }
          .skill-stats {
            flex-wrap: wrap;
            gap: var(--spacing-xs);
          }
          .skill-stat-value {
            font-size: 0.95rem;
          }
          .skill-stat-label {
            font-size: 0.65rem;
          }
          .skill-band {
            font-size: 1rem;
          }
        }

        .skill-card {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: var(--spacing-md);
          min-width: 0;
          overflow: hidden;
        }

        .skill-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: var(--spacing-md);
        }

        .skill-name {
          font-weight: 600;
        }

        .skill-band {
          font-size: 1.25rem;
          font-weight: 700;
          color: var(--color-primary);
        }

        .skill-progress {
          display: flex;
          align-items: center;
          gap: var(--spacing-md);
        }

        .skill-stats {
          display: flex;
          gap: var(--spacing-md);
          min-width: 0;
          flex: 1;
        }

        .skill-stat {
          display: flex;
          flex-direction: column;
        }

        .skill-stat-value {
          font-weight: 600;
          font-size: 1.125rem;
        }

        .skill-stat-label {
          font-size: 0.75rem;
          color: var(--color-text-secondary);
        }

        .quick-actions {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: var(--spacing-md);
        }

        @media (max-width: 768px) {
          .quick-actions {
            grid-template-columns: 1fr;
          }
        }

        .action-card {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--spacing-sm);
          padding: var(--spacing-lg);
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          cursor: pointer;
          transition: all var(--transition-fast);
          color: var(--color-text-primary);
          font-size: 1rem;
        }

        .action-card:hover {
          border-color: var(--color-primary);
          background: var(--color-background);
        }

        .action-card svg {
          color: var(--color-primary);
        }

        .dashboard-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: var(--spacing-md);
        }

        @media (max-width: 768px) {
          .dashboard-grid {
            grid-template-columns: 1fr;
          }
        }

        .activity-list,
        .goals-list {
          display: flex;
          flex-direction: column;
          gap: var(--spacing-sm);
        }

        .activity-item {
          display: flex;
          align-items: center;
          gap: var(--spacing-sm);
          padding: var(--spacing-sm);
          border-radius: var(--radius-md);
          background: var(--color-background);
        }

        .activity-icon {
          width: 32px;
          height: 32px;
          border-radius: var(--radius-md);
          background: var(--color-primary);
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .activity-info {
          flex: 1;
          min-width: 0;
          display: flex;
          flex-direction: column;
        }

        .activity-title {
          font-weight: 500;
          font-size: 0.875rem;
        }

        .activity-time {
          font-size: 0.75rem;
          color: var(--color-text-secondary);
        }

        .activity-duration {
          font-size: 0.875rem;
          color: var(--color-primary);
          font-weight: 500;
          white-space: nowrap;
          flex-shrink: 0;
        }

        .goal-item {
          display: flex;
          align-items: flex-start;
          gap: var(--spacing-sm);
          padding: var(--spacing-sm);
          border-radius: var(--radius-md);
          background: var(--color-background);
          color: var(--color-text-primary);
        }

        .goal-item svg {
          color: var(--color-accent);
          margin-top: 2px;
          flex-shrink: 0;
        }

        .goal-item-content {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .goal-title {
          font-weight: 500;
          font-size: 0.875rem;
        }

        .goal-mini-progress {
          display: flex;
          align-items: center;
          gap: var(--spacing-xs);
        }

        .goal-mini-track {
          flex: 1;
          height: 4px;
          background: var(--color-border);
          border-radius: 2px;
          overflow: hidden;
        }

        .goal-mini-fill {
          height: 100%;
          background: var(--color-primary);
          border-radius: 2px;
        }

        .goal-mini-label {
          font-size: 0.7rem;
          color: var(--color-text-secondary);
          white-space: nowrap;
        }

        .goal-date {
          font-size: 0.75rem;
          color: var(--color-text-secondary);
          white-space: nowrap;
        }

        .ring-wrapper {
          position: relative;
          display: inline-flex;
          align-items: center;
          justify-content: center;
        }

        .ring-sub {
          position: absolute;
          bottom: -14px;
          font-size: 0.6rem;
          color: var(--color-text-secondary);
          white-space: nowrap;
        }

        .skill-card-clickable:hover {
          border-color: var(--color-primary);
        }
        .skill-card-expanded {
          border-color: var(--color-primary);
        }

        .speaking-insights-panel {
          grid-column: 1 / -1;
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: var(--spacing-md);
          margin-top: var(--spacing-sm);
        }
        .speaking-insights-empty {
          text-align: center;
          color: var(--color-text-secondary);
          padding: var(--spacing-md);
        }
        .si-criteria {
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-bottom: var(--spacing-md);
        }
        .si-criterion-row {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .si-criterion-label {
          font-size: 0.8rem;
          color: var(--color-text-secondary);
          width: 140px;
          flex-shrink: 0;
        }
        @media (max-width: 480px) {
          .si-criterion-label { width: 80px; font-size: 0.7rem; }
        }
        .si-bar-track {
          flex: 1;
          height: 10px;
          background: var(--color-border);
          border-radius: 5px;
          overflow: hidden;
        }
        .si-bar-fill {
          height: 100%;
          border-radius: 5px;
          transition: width 0.4s ease;
        }
        .si-criterion-band {
          font-size: 0.85rem;
          font-weight: 600;
          width: 28px;
          text-align: right;
        }
        .si-trend {
          font-size: 1rem;
          font-weight: 700;
          width: 20px;
          text-align: center;
        }
        .si-weakest {
          border: 1px solid #F59E0B;
          border-radius: var(--radius-md);
          padding: var(--spacing-sm) var(--spacing-md);
          background: #FFFBEB;
          margin-bottom: var(--spacing-md);
          font-size: 0.85rem;
          color: #92400E;
        }
        [data-theme="dark"] .si-weakest {
          background: #78350F22;
          color: #FCD34D;
        }
        .si-weakest-rec {
          margin-top: 4px;
          font-weight: 400;
        }
        .si-recent {
          margin-top: var(--spacing-sm);
        }
        .si-recent-title {
          font-size: 0.85rem;
          font-weight: 600;
          margin-bottom: var(--spacing-xs);
          color: var(--color-text-primary);
        }
        .si-session-row {
          display: flex;
          align-items: center;
          gap: var(--spacing-sm);
          padding: 4px 0;
          font-size: 0.8rem;
        }
        .si-session-date {
          color: var(--color-text-secondary);
          width: 90px;
          flex-shrink: 0;
        }
        .si-session-band {
          font-weight: 700;
          width: 28px;
        }
        .si-session-topic {
          color: var(--color-text-secondary);
          flex: 1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .empty-state {
          text-align: center;
          padding: var(--spacing-lg);
          color: var(--color-text-secondary);
        }

        .loading-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: 400px;
          gap: var(--spacing-md);
        }

        .loading-spinner {
          width: 40px;
          height: 40px;
          border: 3px solid var(--color-border);
          border-top-color: var(--color-primary);
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  );
}