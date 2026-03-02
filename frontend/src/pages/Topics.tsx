import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { GraduationCap } from 'lucide-react';
import { topicsAPI } from '../api';
import type { Topic, SkillType } from '../types';
import { useAppStore } from '../store';

const skillColors: Record<string, string> = {
  reading: '#4F46E5',
  listening: '#10B981',
  writing: '#F59E0B',
  speaking: '#EF4444',
};

export default function Topics() {
  const { t } = useTranslation();
  const { language } = useAppStore();
  const [mode, setMode] = useState<'list' | 'flashcard'>('list');
  const [topics, setTopics] = useState<Topic[]>([]);
  const [flashcards, setFlashcards] = useState<{topic: Topic; ease_factor: number; interval_days: number; repetitions: number}[]>([]);
  const [filterSkill, setFilterSkill] = useState<SkillType | ''>('');
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [currentCard, setCurrentCard] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadTopics();
  }, [filterSkill, filterCategory]);

  const loadTopics = async () => {
    setLoading(true);
    try {
      if (mode === 'flashcard') {
        const res = await topicsAPI.getFlashcards(filterSkill || undefined, 10);
        setFlashcards(res.data);
      } else {
        const res = await topicsAPI.getAll(filterSkill || undefined, filterCategory || undefined);
        setTopics(res.data);
      }
    } catch (error) {
      console.error('Failed to load topics:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (mode === 'flashcard') {
      loadTopics();
      setCurrentCard(0);
      setShowAnswer(false);
    }
  }, [mode]);

  const handleReview = async (quality: number) => {
    if (flashcards.length === 0) return;
    
    const card = flashcards[currentCard];
    try {
      await topicsAPI.review(card.topic.id, quality);
      if (currentCard < flashcards.length - 1) {
        setCurrentCard(currentCard + 1);
        setShowAnswer(false);
      } else {
        // Reload for next round
        loadTopics();
        setCurrentCard(0);
        setShowAnswer(false);
      }
    } catch (error) {
      console.error('Failed to review:', error);
    }
  };

  const categories = ['vocabulary', 'grammar', 'topic_idea'];
  const categoryLabels: Record<string, string> = {
    vocabulary: t('topics.vocabulary'),
    grammar: t('topics.grammar'),
    topic_idea: t('topics.ideas'),
  };

  if (mode === 'flashcard') {
    return (
      <div className="topics-page">
        <header className="page-header">
          <div className="header-row">
            <h1>{t('topics.flashcards')}</h1>
            <button className="btn btn-secondary" onClick={() => setMode('list')}>
              {t('topics.vocabulary')}
            </button>
          </div>
        </header>

        {loading ? (
          <div className="loading"><div className="loading-spinner" /></div>
        ) : flashcards.length === 0 ? (
          <div className="empty-state">
            <GraduationCap size={48} />
            <p>No cards to review</p>
          </div>
        ) : (
          <div className="flashcard-container">
            <div className="flashcard-progress">
              {currentCard + 1} / {flashcards.length}
            </div>
            
            <div className={`flashcard ${showAnswer ? 'flipped' : ''}`}>
              <div className="flashcard-inner">
                <div className="flashcard-front">
                  <span 
                    className="card-skill"
                    style={{ background: skillColors[flashcards[currentCard].topic.skill] }}
                  >
                    {flashcards[currentCard].topic.skill}
                  </span>
                  <h3 className="card-title">{flashcards[currentCard].topic.title}</h3>
                  <button 
                    className="btn btn-primary"
                    onClick={() => setShowAnswer(true)}
                  >
                    {t('topics.showAnswer')}
                  </button>
                </div>
                <div className="flashcard-back">
                  <span 
                    className="card-skill"
                    style={{ background: skillColors[flashcards[currentCard].topic.skill] }}
                  >
                    {flashcards[currentCard].topic.skill}
                  </span>
                  <h3 className="card-title">{flashcards[currentCard].topic.title}</h3>
                  <p className="card-content">
                    {language === 'zh' && flashcards[currentCard].topic.content_zh 
                      ? flashcards[currentCard].topic.content_zh 
                      : flashcards[currentCard].topic.content}
                  </p>
                  {flashcards[currentCard].topic.example && (
                    <div className="card-example">
                      <strong>Example:</strong>
                      <p>{language === 'zh' && flashcards[currentCard].topic.example_zh 
                        ? flashcards[currentCard].topic.example_zh 
                        : flashcards[currentCard].topic.example}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {showAnswer && (
              <div className="review-buttons">
                <button className="review-btn hard" onClick={() => handleReview(1)}>
                  {t('topics.again')}
                </button>
                <button className="review-btn good" onClick={() => handleReview(3)}>
                  {t('topics.good')}
                </button>
                <button className="review-btn easy" onClick={() => handleReview(5)}>
                  {t('topics.easy')}
                </button>
              </div>
            )}
          </div>
        )}

        <style>{`
          .header-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
          }

          .flashcard-container {
            max-width: 600px;
            margin: 0 auto;
            text-align: center;
          }

          .flashcard-progress {
            margin-bottom: var(--spacing-md);
            color: var(--color-text-secondary);
          }

          .flashcard {
            perspective: 1000px;
            height: 350px;
            margin-bottom: var(--spacing-lg);
          }

          .flashcard-inner {
            position: relative;
            width: 100%;
            height: 100%;
            transition: transform 0.6s;
            transform-style: preserve-3d;
          }

          .flashcard.flipped .flashcard-inner {
            transform: rotateY(180deg);
          }

          .flashcard-front,
          .flashcard-back {
            position: absolute;
            width: 100%;
            height: 100%;
            backface-visibility: hidden;
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-xl);
            padding: var(--spacing-xl);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
          }

          .flashcard-back {
            transform: rotateY(180deg);
          }

          .card-skill {
            position: absolute;
            top: var(--spacing-md);
            left: var(--spacing-md);
            padding: var(--spacing-xs) var(--spacing-sm);
            border-radius: var(--radius-full);
            font-size: 0.625rem;
            font-weight: 600;
            color: white;
            text-transform: uppercase;
          }

          .card-title {
            font-size: 1.5rem;
            margin-bottom: var(--spacing-lg);
            text-align: center;
          }

          .card-content {
            font-size: 1rem;
            line-height: 1.8;
            text-align: left;
            color: var(--color-text-primary);
          }

          .card-example {
            margin-top: var(--spacing-md);
            padding: var(--spacing-md);
            background: var(--color-background);
            border-radius: var(--radius-md);
            text-align: left;
            font-size: 0.875rem;
          }

          .review-buttons {
            display: flex;
            justify-content: center;
            gap: var(--spacing-md);
          }

          .review-btn {
            padding: var(--spacing-sm) var(--spacing-lg);
            border: none;
            border-radius: var(--radius-md);
            font-weight: 600;
            cursor: pointer;
            transition: all var(--transition-fast);
          }

          .review-btn.hard {
            background: var(--color-error);
            color: white;
          }

          .review-btn.good {
            background: var(--color-warning);
            color: white;
          }

          .review-btn.easy {
            background: var(--color-success);
            color: white;
          }

          .review-btn:hover {
            transform: translateY(-2px);
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="topics-page">
      <header className="page-header">
        <div className="header-row">
          <h1>{t('topics.title')}</h1>
          <button className="btn btn-primary" onClick={() => setMode('flashcard')}>
            {t('topics.flashcards')}
          </button>
        </div>
      </header>

      {/* Filters */}
      <div className="filters">
        <select
          value={filterSkill}
          onChange={(e) => setFilterSkill(e.target.value as SkillType | '')}
          className="filter-select"
        >
          <option value="">All Skills</option>
          <option value="reading">{t('skills.reading')}</option>
          <option value="listening">{t('skills.listening')}</option>
          <option value="writing">{t('skills.writing')}</option>
          <option value="speaking">{t('skills.speaking')}</option>
        </select>
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="filter-select"
        >
          <option value="">All Categories</option>
          {categories.map(cat => (
            <option key={cat} value={cat}>{categoryLabels[cat]}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="loading"><div className="loading-spinner" /></div>
      ) : (
        <div className="topics-grid">
          {topics.map((topic) => (
            <div key={topic.id} className="topic-card">
              <div className="topic-header">
                <span 
                  className="topic-skill"
                  style={{ background: skillColors[topic.skill] }}
                >
                  {topic.skill}
                </span>
                <span className="topic-category">{categoryLabels[topic.category] || topic.category}</span>
              </div>
              <h3 className="topic-title">{topic.title}</h3>
              <p className="topic-content">
                {language === 'zh' && topic.content_zh ? topic.content_zh : topic.content}
              </p>
              {topic.example && (
                <div className="topic-example">
                  <strong>Example:</strong>
                  <p>{language === 'zh' && topic.example_zh ? topic.example_zh : topic.example}</p>
                </div>
              )}
              <div className="topic-footer">
                <span className="topic-difficulty">
                  {[...Array(5)].map((_, i) => (
                    <span key={i} className={i < topic.difficulty ? 'filled' : ''}>★</span>
                  ))}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      <style>{`
        .topics-page {
          max-width: 1200px;
          margin: 0 auto;
        }

        .page-header {
          margin-bottom: var(--spacing-lg);
        }

        .header-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .filters {
          display: flex;
          gap: var(--spacing-md);
          margin-bottom: var(--spacing-lg);
        }

        .filter-select {
          padding: var(--spacing-sm) var(--spacing-md);
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          color: var(--color-text-primary);
        }

        .topics-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: var(--spacing-md);
        }

        @media (max-width: 1024px) {
          .topics-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 768px) {
          .topics-grid {
            grid-template-columns: 1fr;
          }
        }

        .topic-card {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: var(--spacing-md);
        }

        .topic-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: var(--spacing-sm);
        }

        .topic-skill {
          padding: 2px 8px;
          border-radius: var(--radius-full);
          font-size: 0.625rem;
          font-weight: 600;
          color: white;
          text-transform: uppercase;
        }

        .topic-category {
          font-size: 0.75rem;
          color: var(--color-text-secondary);
        }

        .topic-title {
          font-size: 1rem;
          margin-bottom: var(--spacing-sm);
        }

        .topic-content {
          font-size: 0.875rem;
          line-height: 1.6;
          color: var(--color-text-secondary);
          margin-bottom: var(--spacing-sm);
        }

        .topic-example {
          font-size: 0.75rem;
          padding: var(--spacing-sm);
          background: var(--color-background);
          border-radius: var(--radius-sm);
          margin-bottom: var(--spacing-sm);
        }

        .topic-footer {
          display: flex;
          justify-content: flex-end;
        }

        .topic-difficulty {
          font-size: 0.75rem;
          color: var(--color-text-secondary);
        }

        .topic-difficulty .filled {
          color: var(--color-warning);
        }

        .empty-state {
          text-align: center;
          padding: var(--spacing-2xl);
          color: var(--color-text-secondary);
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