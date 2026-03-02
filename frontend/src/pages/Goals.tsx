import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Target, Plus, Check, Trash2, Calendar } from 'lucide-react';
import { goalsAPI } from '../api';
import type { Goal } from '../types';

export default function Goals() {
  const { t } = useTranslation();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [newGoal, setNewGoal] = useState({
    title: '',
    description: '',
    target_date: '',
    target_minutes: 30,
  });
  const [filter, setFilter] = useState<'all' | 'active' | 'completed'>('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadGoals();
  }, [filter]);

  const loadGoals = async () => {
    setLoading(true);
    try {
      const completed = filter === 'completed' ? true : (filter === 'active' ? false : undefined);
      const res = await goalsAPI.getAll(completed);
      setGoals(res.data);
    } catch (error) {
      console.error('Failed to load goals:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGoal.title.trim()) return;

    try {
      const res = await goalsAPI.create({
        title: newGoal.title,
        description: newGoal.description,
        target_date: newGoal.target_date || undefined,
        target_minutes: newGoal.target_minutes,
      });
      setGoals([res.data, ...goals]);
      setShowForm(false);
      setNewGoal({ title: '', description: '', target_date: '', target_minutes: 30 });
    } catch (error) {
      console.error('Failed to create goal:', error);
    }
  };

  const handleToggleComplete = async (goal: Goal) => {
    try {
      await goalsAPI.update(goal.id, { completed: !goal.completed });
      setGoals(goals.map(g => g.id === goal.id ? { ...g, completed: !g.completed } : g));
    } catch (error) {
      console.error('Failed to update goal:', error);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this goal?')) return;
    try {
      await goalsAPI.delete(id);
      setGoals(goals.filter(g => g.id !== id));
    } catch (error) {
      console.error('Failed to delete goal:', error);
    }
  };

  const activeGoals = goals.filter(g => !g.completed);
  const completedGoals = goals.filter(g => g.completed);

  return (
    <div className="goals-page">
      <header className="page-header">
        <h1>{t('goals.title')}</h1>
        <button className="btn btn-primary" onClick={() => setShowForm(true)}>
          <Plus size={20} />
          {t('goals.addGoal')}
        </button>
      </header>

      {/* Filter tabs */}
      <div className="filter-tabs">
        <button 
          className={`tab ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All ({goals.length})
        </button>
        <button 
          className={`tab ${filter === 'active' ? 'active' : ''}`}
          onClick={() => setFilter('active')}
        >
          {t('goals.active')} ({activeGoals.length})
        </button>
        <button 
          className={`tab ${filter === 'completed' ? 'active' : ''}`}
          onClick={() => setFilter('completed')}
        >
          {t('goals.completed')} ({completedGoals.length})
        </button>
      </div>

      {/* Add Goal Form */}
      {showForm && (
        <div className="goal-form-card">
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Title</label>
              <input
                type="text"
                className="form-input"
                value={newGoal.title}
                onChange={(e) => setNewGoal({ ...newGoal, title: e.target.value })}
                placeholder="e.g., Practice reading 30 min daily"
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Description (optional)</label>
              <textarea
                className="form-textarea"
                value={newGoal.description}
                onChange={(e) => setNewGoal({ ...newGoal, description: e.target.value })}
                placeholder="Additional details..."
                rows={2}
              />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Target Date</label>
                <input
                  type="date"
                  className="form-input"
                  value={newGoal.target_date}
                  onChange={(e) => setNewGoal({ ...newGoal, target_date: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Minutes/Day</label>
                <input
                  type="number"
                  className="form-input"
                  value={newGoal.target_minutes}
                  onChange={(e) => setNewGoal({ ...newGoal, target_minutes: parseInt(e.target.value) })}
                  min={15}
                  max={480}
                />
              </div>
            </div>
            <div className="form-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>
                {t('common.cancel')}
              </button>
              <button type="submit" className="btn btn-primary">
                {t('common.save')}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Goals List */}
      {loading ? (
        <div className="loading"><div className="loading-spinner" /></div>
      ) : goals.length === 0 ? (
        <div className="empty-state">
          <Target size={48} />
          <p>{t('goals.noGoals')}</p>
          <button className="btn btn-primary" onClick={() => setShowForm(true)}>
            <Plus size={20} />
            {t('goals.addGoal')}
          </button>
        </div>
      ) : (
        <div className="goals-list">
          {goals.map((goal) => (
            <div key={goal.id} className={`goal-card ${goal.completed ? 'completed' : ''}`}>
              <button 
                className="goal-check"
                onClick={() => handleToggleComplete(goal)}
              >
                {goal.completed ? <Check size={20} /> : <div className="empty-check" />}
              </button>
              <div className="goal-content">
                <h3 className="goal-title">{goal.title}</h3>
                {goal.description && (
                  <p className="goal-description">{goal.description}</p>
                )}
                <div className="goal-meta">
                  {goal.target_date && (
                    <span className="meta-item">
                      <Calendar size={14} />
                      {new Date(goal.target_date).toLocaleDateString()}
                    </span>
                  )}
                  {goal.target_minutes && (
                    <span className="meta-item">
                      <Target size={14} />
                      {goal.target_minutes} min/day
                    </span>
                  )}
                </div>
              </div>
              <button 
                className="goal-delete"
                onClick={() => handleDelete(goal.id)}
              >
                <Trash2 size={18} />
              </button>
            </div>
          ))}
        </div>
      )}

      <style>{`
        .goals-page {
          max-width: 800px;
          margin: 0 auto;
        }

        .page-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: var(--spacing-lg);
        }

        .filter-tabs {
          display: flex;
          gap: var(--spacing-sm);
          margin-bottom: var(--spacing-lg);
        }

        .tab {
          padding: var(--spacing-sm) var(--spacing-md);
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-full);
          color: var(--color-text-secondary);
          cursor: pointer;
          transition: all var(--transition-fast);
          font-size: 0.875rem;
        }

        .tab:hover {
          border-color: var(--color-primary);
        }

        .tab.active {
          background: var(--color-primary);
          border-color: var(--color-primary);
          color: white;
        }

        .goal-form-card {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: var(--spacing-lg);
          margin-bottom: var(--spacing-lg);
        }

        .form-row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: var(--spacing-md);
        }

        .form-textarea {
          width: 100%;
          padding: var(--spacing-sm) var(--spacing-md);
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          color: var(--color-text-primary);
          resize: vertical;
        }

        .form-actions {
          display: flex;
          justify-content: flex-end;
          gap: var(--spacing-sm);
          margin-top: var(--spacing-md);
        }

        .goals-list {
          display: flex;
          flex-direction: column;
          gap: var(--spacing-sm);
        }

        .goal-card {
          display: flex;
          align-items: flex-start;
          gap: var(--spacing-md);
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: var(--spacing-md);
          transition: all var(--transition-fast);
        }

        .goal-card.completed {
          opacity: 0.7;
        }

        .goal-card.completed .goal-title {
          text-decoration: line-through;
        }

        .goal-check {
          width: 28px;
          height: 28px;
          border: 2px solid var(--color-border);
          border-radius: 50%;
          background: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          transition: all var(--transition-fast);
        }

        .goal-check:hover {
          border-color: var(--color-success);
        }

        .goal-card.completed .goal-check {
          background: var(--color-success);
          border-color: var(--color-success);
          color: white;
        }

        .empty-check {
          width: 12px;
          height: 12px;
          border-radius: 50%;
        }

        .goal-content {
          flex: 1;
        }

        .goal-title {
          font-size: 1rem;
          margin-bottom: var(--spacing-xs);
        }

        .goal-description {
          font-size: 0.875rem;
          color: var(--color-text-secondary);
          margin-bottom: var(--spacing-sm);
        }

        .goal-meta {
          display: flex;
          gap: var(--spacing-md);
          font-size: 0.75rem;
          color: var(--color-text-secondary);
        }

        .meta-item {
          display: flex;
          align-items: center;
          gap: var(--spacing-xs);
        }

        .goal-delete {
          background: none;
          border: none;
          color: var(--color-error);
          cursor: pointer;
          padding: var(--spacing-xs);
          opacity: 0.5;
          transition: opacity var(--transition-fast);
        }

        .goal-delete:hover {
          opacity: 1;
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

        .empty-state p {
          margin-bottom: var(--spacing-md);
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
      `}</style>
    </div>
  );
}