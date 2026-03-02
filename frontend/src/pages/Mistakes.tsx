import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertCircle, Trash2, Filter, BookOpen, Headphones, Pen, MessageCircle } from 'lucide-react';
import { mistakesAPI } from '../api';
import type { Mistake, SkillType } from '../types';

const skillIcons = {
  reading: BookOpen,
  listening: Headphones,
  writing: Pen,
  speaking: MessageCircle,
};

const skillColors = {
  reading: '#4F46E5',
  listening: '#10B981',
  writing: '#F59E0B',
  speaking: '#EF4444',
};

export default function Mistakes() {
  const { t } = useTranslation();
  const [mistakes, setMistakes] = useState<Mistake[]>([]);
  const [filterSkill, setFilterSkill] = useState<SkillType | ''>('');
  const [stats, setStats] = useState<{total_mistakes: number; by_skill: Record<string, number>; by_type: Record<string, number>} | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedMistake, setSelectedMistake] = useState<Mistake | null>(null);

  useEffect(() => {
    loadData();
  }, [filterSkill]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [mistakesRes, statsRes] = await Promise.all([
        mistakesAPI.getAll(filterSkill || undefined),
        mistakesAPI.getStats(),
      ]);
      setMistakes(mistakesRes.data);
      setStats(statsRes.data);
    } catch (error) {
      console.error('Failed to load mistakes:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this mistake?')) return;
    try {
      await mistakesAPI.delete(id);
      setMistakes(mistakes.filter(m => m.id !== id));
    } catch (error) {
      console.error('Failed to delete mistake:', error);
    }
  };

  const getSkillIcon = (skill: SkillType) => {
    const Icon = skillIcons[skill];
    return <Icon size={16} />;
  };

  return (
    <div className="mistakes-page">
      <header className="page-header">
        <h1>{t('mistakes.title')}</h1>
      </header>

      {/* Stats */}
      {stats && (
        <div className="stats-row">
          <div className="stat-card">
            <span className="stat-value">{stats.total_mistakes}</span>
            <span className="stat-label">Total Mistakes</span>
          </div>
          {Object.entries(stats.by_skill).map(([skill, count]) => (
            <div key={skill} className="stat-card" style={{ borderLeftColor: skillColors[skill as SkillType] }}>
              <span className="stat-value">{count}</span>
              <span className="stat-label">{skill}</span>
            </div>
          ))}
        </div>
      )}

      {/* Filter */}
      <div className="filter-bar">
        <Filter size={20} />
        <select
          value={filterSkill}
          onChange={(e) => setFilterSkill(e.target.value as SkillType | '')}
          className="filter-select"
        >
          <option value="">All Skills</option>
          <option value="reading">Reading</option>
          <option value="listening">Listening</option>
          <option value="writing">Writing</option>
          <option value="speaking">Speaking</option>
        </select>
      </div>

      {loading ? (
        <div className="loading">
          <div className="loading-spinner" />
        </div>
      ) : mistakes.length === 0 ? (
        <div className="empty-state">
          <AlertCircle size={48} />
          <p>{t('mistakes.noMistakes')}</p>
        </div>
      ) : (
        <div className="mistakes-grid">
          {mistakes.map((mistake) => (
            <div
              key={mistake.id}
              className={`mistake-card ${selectedMistake?.id === mistake.id ? 'selected' : ''}`}
              onClick={() => setSelectedMistake(mistake)}
            >
              <div className="mistake-header">
                <span className="mistake-skill" style={{ color: skillColors[mistake.skill] }}>
                  {getSkillIcon(mistake.skill)}
                  {mistake.skill}
                </span>
                {mistake.mistake_type && (
                  <span className="mistake-type badge">{mistake.mistake_type}</span>
                )}
              </div>
              
              <p className="mistake-question">{mistake.question}</p>
              
              <div className="mistake-answers">
                <div className="answer-row incorrect">
                  <span className="answer-label">{t('mistakes.yourAnswer')}:</span>
                  <span className="answer-text">{mistake.user_answer}</span>
                </div>
                <div className="answer-row correct">
                  <span className="answer-label">{t('mistakes.correctAnswer')}:</span>
                  <span className="answer-text">{mistake.correct_answer}</span>
                </div>
              </div>
              
              <div className="mistake-footer">
                <span className="repeat-count">
                  {t('mistakes.repeated')}: {mistake.times_repeated}
                </span>
                <button
                  className="delete-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(mistake.id);
                  }}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Detail Modal */}
      {selectedMistake && (
        <div className="modal-overlay" onClick={() => setSelectedMistake(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Mistake Detail</h2>
              <button className="close-btn" onClick={() => setSelectedMistake(null)}>×</button>
            </div>
            <div className="modal-body">
              <div className="detail-row">
                <span className="detail-label">Skill:</span>
                <span className="detail-value" style={{ color: skillColors[selectedMistake.skill] }}>
                  {getSkillIcon(selectedMistake.skill)} {selectedMistake.skill}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Type:</span>
                <span className="detail-value">{selectedMistake.mistake_type || 'N/A'}</span>
              </div>
              <div className="detail-section">
                <span className="detail-label">{t('mistakes.question')}:</span>
                <p className="detail-content">{selectedMistake.question}</p>
              </div>
              <div className="detail-row">
                <span className="detail-label">{t('mistakes.yourAnswer')}:</span>
                <span className="detail-value answer-incorrect">{selectedMistake.user_answer}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">{t('mistakes.correctAnswer')}:</span>
                <span className="detail-value answer-correct">{selectedMistake.correct_answer}</span>
              </div>
              {selectedMistake.explanation && (
                <div className="detail-section">
                  <span className="detail-label">{t('mistakes.explanation')}:</span>
                  <p className="detail-content">{selectedMistake.explanation}</p>
                </div>
              )}
              <div className="detail-row">
                <span className="detail-label">{t('mistakes.repeated')}:</span>
                <span className="detail-value">{selectedMistake.times_repeated} times</span>
              </div>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .mistakes-page {
          max-width: 1200px;
          margin: 0 auto;
        }

        .page-header {
          margin-bottom: var(--spacing-lg);
        }

        .stats-row {
          display: flex;
          gap: var(--spacing-md);
          margin-bottom: var(--spacing-lg);
          flex-wrap: wrap;
        }

        .stat-card {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-left: 3px solid var(--color-primary);
          border-radius: var(--radius-md);
          padding: var(--spacing-md);
          min-width: 120px;
        }

        .stat-value {
          display: block;
          font-size: 1.5rem;
          font-weight: 700;
        }

        .stat-label {
          font-size: 0.75rem;
          color: var(--color-text-secondary);
          text-transform: capitalize;
        }

        .filter-bar {
          display: flex;
          align-items: center;
          gap: var(--spacing-sm);
          margin-bottom: var(--spacing-lg);
          color: var(--color-text-secondary);
        }

        .filter-select {
          padding: var(--spacing-sm) var(--spacing-md);
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          color: var(--color-text-primary);
        }

        .mistakes-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: var(--spacing-md);
        }

        @media (max-width: 1024px) {
          .mistakes-grid {
            grid-template-columns: 1fr;
          }
        }

        .mistake-card {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: var(--spacing-md);
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .mistake-card:hover {
          border-color: var(--color-primary);
        }

        .mistake-card.selected {
          border-color: var(--color-primary);
          box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.2);
        }

        .mistake-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: var(--spacing-sm);
        }

        .mistake-skill {
          display: flex;
          align-items: center;
          gap: var(--spacing-xs);
          font-weight: 600;
          font-size: 0.875rem;
          text-transform: capitalize;
        }

        .mistake-type {
          font-size: 0.625rem;
          padding: 2px 8px;
          background: var(--color-background);
          border-radius: var(--radius-full);
          color: var(--color-text-secondary);
        }

        .mistake-question {
          font-size: 0.875rem;
          margin-bottom: var(--spacing-sm);
          color: var(--color-text-primary);
        }

        .mistake-answers {
          font-size: 0.75rem;
          margin-bottom: var(--spacing-sm);
        }

        .answer-row {
          display: flex;
          gap: var(--spacing-xs);
          margin-bottom: var(--spacing-xs);
        }

        .answer-label {
          color: var(--color-text-secondary);
          min-width: 80px;
        }

        .answer-row.incorrect .answer-text {
          color: var(--color-error);
          text-decoration: line-through;
        }

        .answer-row.correct .answer-text {
          color: var(--color-success);
        }

        .mistake-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 0.75rem;
          color: var(--color-text-secondary);
        }

        .delete-btn {
          background: none;
          border: none;
          color: var(--color-error);
          cursor: pointer;
          padding: var(--spacing-xs);
        }

        .delete-btn:hover {
          background: rgba(239, 68, 68, 0.1);
          border-radius: var(--radius-sm);
        }

        .empty-state {
          text-align: center;
          padding: var(--spacing-2xl);
          color: var(--color-text-secondary);
        }

        .empty-state svg {
          margin-bottom: var(--spacing-md);
          opacity: 0.5;
        }

        .loading {
          display: flex;
          justify-content: center;
          padding: var(--spacing-2xl);
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
          to { transform: rotate(360deg); }
        }

        .modal-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }

        .modal {
          background: var(--color-surface);
          border-radius: var(--radius-lg);
          width: 90%;
          max-width: 600px;
          max-height: 80vh;
          overflow: auto;
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: var(--spacing-md) var(--spacing-lg);
          border-bottom: 1px solid var(--color-border);
        }

        .close-btn {
          background: none;
          border: none;
          font-size: 1.5rem;
          cursor: pointer;
          color: var(--color-text-secondary);
        }

        .modal-body {
          padding: var(--spacing-lg);
        }

        .detail-row {
          display: flex;
          gap: var(--spacing-md);
          margin-bottom: var(--spacing-md);
        }

        .detail-label {
          font-weight: 600;
          min-width: 120px;
          color: var(--color-text-secondary);
        }

        .detail-value {
          color: var(--color-text-primary);
        }

        .detail-section {
          margin-bottom: var(--spacing-md);
        }

        .detail-content {
          margin-top: var(--spacing-xs);
          padding: var(--spacing-sm);
          background: var(--color-background);
          border-radius: var(--radius-sm);
        }

        .answer-incorrect {
          color: var(--color-error);
        }

        .answer-correct {
          color: var(--color-success);
        }
      `}</style>
    </div>
  );
}