import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { GraduationCap, Plus, BookmarkPlus, Check } from 'lucide-react';
import { topicsAPI } from '../api';
import type { Topic, SkillType } from '../types';
import { useAppStore } from '../store';

const POS_ABBR: Record<string, string> = {
  verb: 'v.', noun: 'n.', adjective: 'adj.', adverb: 'adv.',
  preposition: 'prep.', conjunction: 'conj.', pronoun: 'pron.', interjection: 'interj.',
};

function parseDictionaryEntry(data: any[]): { content: string; example: string } {
  if (!data?.length) return { content: '', example: '' };
  const lines: string[] = [];
  let firstExample = '';
  for (const meaning of (data[0].meanings ?? []).slice(0, 3)) {
    const abbr = POS_ABBR[meaning.partOfSpeech] ?? `${meaning.partOfSpeech}.`;
    for (const def of (meaning.definitions ?? []).slice(0, 2)) {
      lines.push(`${abbr} ${def.definition}${def.example ? ` e.g. "${def.example}"` : ''}`);
      if (!firstExample && def.example) firstExample = def.example;
    }
  }
  return { content: lines.join('\n'), example: firstExample };
}

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
  const [dueCount, setDueCount] = useState(0);
  const [addedIds, setAddedIds] = useState<Set<number>>(new Set());

  // Add Word form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newWord, setNewWord] = useState({ title: '', content: '', content_zh: '', example: '' });
  const [saving, setSaving] = useState(false);
  const [dictLoading, setDictLoading] = useState(false);

  const resetForm = () => {
    setNewWord({ title: '', content: '', content_zh: '', example: '' });
    setDictLoading(false);
    setShowAddForm(false);
  };

  const lookupWord = async (word: string) => {
    if (!word.trim() || newWord.content.trim()) return; // don't overwrite user's own text
    setDictLoading(true);
    try {
      const res = await fetch(`https://api.dictionaryapi.dev/api/v2/entries/en/${encodeURIComponent(word.trim())}`);
      if (res.ok) {
        const data = await res.json();
        const { content, example } = parseDictionaryEntry(data);
        if (content) {
          setNewWord(p => ({ ...p, content: p.content || content, example: p.example || example }));
          if (language === 'zh') {
            topicsAPI.translateDefinition(word.trim(), content)
              .then(r => { if (r.data.content_zh) setNewWord(p => ({ ...p, content_zh: r.data.content_zh })); })
              .catch(() => {});
          }
        }
      }
    } catch { /* ignore */ } finally {
      setDictLoading(false);
    }
  };

  useEffect(() => {
    loadTopics();
    topicsAPI.getDueCount().then(res => setDueCount(res.data.due)).catch(() => {});
  }, [filterSkill, filterCategory]);

  const loadTopics = async () => {
    setLoading(true);
    try {
      if (mode === 'flashcard') {
        const res = await topicsAPI.getFlashcards(filterSkill || undefined, 20);
        setFlashcards(res.data);
      } else {
        const res = await topicsAPI.getAll(filterSkill || undefined, filterCategory || undefined);
        setTopics(res.data);
        setAddedIds(new Set(res.data.filter((t: Topic) => t.in_deck).map((t: Topic) => t.id)));
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
    } else {
      topicsAPI.getDueCount().then(res => setDueCount(res.data.due)).catch(() => {});
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
        loadTopics();
        setCurrentCard(0);
        setShowAnswer(false);
      }
    } catch (error) {
      console.error('Failed to review:', error);
    }
  };

  const handleAddWord = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWord.title.trim() || !newWord.content.trim()) return;
    setSaving(true);
    try {
      const res = await topicsAPI.create({
        title: newWord.title.trim(),
        content: newWord.content.trim(),
        content_zh: newWord.content_zh.trim() || undefined,
        example: newWord.example.trim() || undefined,
        skill: filterSkill || 'reading',
        category: 'vocabulary',
      });
      setTopics(prev => [res.data, ...prev]);
      setAddedIds(prev => new Set(prev).add(res.data.id));
      resetForm();
      setDueCount(d => d + 1);
    } catch (error) {
      console.error('Failed to add word:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleAddToDeck = async (topicId: number) => {
    try {
      const res = await topicsAPI.addToDeck(topicId);
      setAddedIds(prev => new Set(prev).add(topicId));
      if (res.data.added) setDueCount(d => d + 1);
    } catch (error) {
      console.error('Failed to add to deck:', error);
    }
  };

  const handleRemoveFromDeck = async (topicId: number) => {
    try {
      const res = await topicsAPI.removeFromDeck(topicId);
      if (res.data.removed) {
        setAddedIds(prev => { const next = new Set(prev); next.delete(topicId); return next; });
        topicsAPI.getDueCount().then(r => setDueCount(r.data.due)).catch(() => {});
      }
    } catch (error) {
      console.error('Failed to remove from deck:', error);
    }
  };

  const categories = ['vocabulary', 'grammar', 'topic_idea'];
  const categoryLabels: Record<string, string> = {
    vocabulary: t('topics.vocabulary'),
    grammar: t('topics.grammar'),
    topic_idea: t('topics.ideas'),
  };

  // ── Flashcard mode ──────────────────────────────────────────────────────────

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
            <p>No cards due for review</p>
            <button className="btn btn-secondary" onClick={() => setMode('list')}>Browse vocabulary</button>
          </div>
        ) : (
          <div className="flashcard-container">
            <div className="flashcard-progress">{currentCard + 1} / {flashcards.length}</div>
            <div className={`flashcard ${showAnswer ? 'flipped' : ''}`}>
              <div className="flashcard-inner">
                <div className="flashcard-front">
                  <span className="card-skill" style={{ background: skillColors[flashcards[currentCard].topic.skill] }}>
                    {flashcards[currentCard].topic.skill}
                  </span>
                  <h3 className="card-title">{flashcards[currentCard].topic.title}</h3>
                  <button className="btn btn-primary" onClick={() => setShowAnswer(true)}>
                    {t('topics.showAnswer')}
                  </button>
                </div>
                <div className="flashcard-back">
                  <span className="card-skill" style={{ background: skillColors[flashcards[currentCard].topic.skill] }}>
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
                <button className="review-btn hard" onClick={() => handleReview(1)}>{t('topics.again')}</button>
                <button className="review-btn good" onClick={() => handleReview(3)}>{t('topics.good')}</button>
                <button className="review-btn easy" onClick={() => handleReview(5)}>{t('topics.easy')}</button>
              </div>
            )}
          </div>
        )}

        <style>{flashcardStyles}</style>
      </div>
    );
  }

  // ── List mode ───────────────────────────────────────────────────────────────

  return (
    <div className="topics-page">
      <header className="page-header">
        <div className="header-row">
          <h1>{t('topics.title')}</h1>
          <div className="header-actions">
            <button className="btn btn-secondary icon-btn" onClick={() => setShowAddForm(v => !v)}>
              <Plus size={16} /> Add Word
            </button>
            <button className="btn btn-primary flashcard-btn" onClick={() => setMode('flashcard')}>
              {t('topics.flashcards')}
              {dueCount > 0 && <span className="due-badge">{dueCount}</span>}
            </button>
          </div>
        </div>
      </header>

      {/* Add Word inline form */}
      {showAddForm && (
        <div className="add-word-form">
          <form onSubmit={handleAddWord}>
            <div className="form-row-3">
              <div className="form-group">
                <label className="form-label">Word / Phrase *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. mitigate"
                  value={newWord.title}
                  onChange={e => setNewWord(p => ({ ...p, title: e.target.value }))}
                  onBlur={e => lookupWord(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <div className="form-group">
                <label className="form-label">
                  Definition *
                  {dictLoading && <span className="dict-loading"> · Looking up…</span>}
                </label>
                <textarea
                  className="form-textarea"
                  placeholder={dictLoading ? 'Looking up…' : 'Auto-filled: v. meaning… n. meaning…'}
                  value={newWord.content}
                  onChange={e => setNewWord(p => ({ ...p, content: e.target.value }))}
                  rows={3}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Example (optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Auto-filled or type manually"
                  value={newWord.example}
                  onChange={e => setNewWord(p => ({ ...p, example: e.target.value }))}
                />
              </div>
            </div>
            <div className="form-actions-right">
              <button type="button" className="btn btn-secondary" onClick={resetForm}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Saving…' : 'Save & Add to Deck'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filters */}
      <div className="filters">
        <select value={filterSkill} onChange={e => setFilterSkill(e.target.value as SkillType | '')} className="filter-select">
          <option value="">All Skills</option>
          <option value="reading">{t('skills.reading')}</option>
          <option value="listening">{t('skills.listening')}</option>
          <option value="writing">{t('skills.writing')}</option>
          <option value="speaking">{t('skills.speaking')}</option>
        </select>
        <select value={filterCategory} onChange={e => setFilterCategory(e.target.value)} className="filter-select">
          <option value="">All Categories</option>
          {categories.map(cat => (
            <option key={cat} value={cat}>{categoryLabels[cat]}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="loading"><div className="loading-spinner" /></div>
      ) : topics.length === 0 ? (
        <div className="empty-state">
          <GraduationCap size={48} />
          <p>No topics yet. Add a word or complete an AI reading exercise to populate your vocabulary.</p>
        </div>
      ) : (
        <div className="topics-grid">
          {topics.map(topic => {
            const inDeck = addedIds.has(topic.id);
            return (
              <div key={topic.id} className="topic-card">
                <div className="topic-header">
                  <span className="topic-skill" style={{ background: skillColors[topic.skill] }}>{topic.skill}</span>
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
                  <button
                    className={`add-deck-btn ${inDeck ? 'in-deck' : ''}`}
                    onClick={() => inDeck ? handleRemoveFromDeck(topic.id) : handleAddToDeck(topic.id)}
                    title={inDeck ? 'Click to remove from deck' : 'Add to flashcard deck'}
                  >
                    {inDeck ? <><Check size={13} /> In Deck</> : <><BookmarkPlus size={13} /> Add to Deck</>}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <style>{listStyles}</style>
    </div>
  );
}

const flashcardStyles = `
  .header-row { display: flex; justify-content: space-between; align-items: center; }
  .flashcard-container { max-width: 600px; margin: 0 auto; text-align: center; }
  .flashcard-progress { margin-bottom: var(--spacing-md); color: var(--color-text-secondary); }
  .flashcard { perspective: 1000px; height: 350px; margin-bottom: var(--spacing-lg); }
  .flashcard-inner { position: relative; width: 100%; height: 100%; transition: transform 0.6s; transform-style: preserve-3d; }
  .flashcard.flipped .flashcard-inner { transform: rotateY(180deg); }
  .flashcard-front, .flashcard-back { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--spacing-xl); display: flex; flex-direction: column; align-items: center; justify-content: center; }
  .flashcard-back { transform: rotateY(180deg); }
  .card-skill { position: absolute; top: var(--spacing-md); left: var(--spacing-md); padding: var(--spacing-xs) var(--spacing-sm); border-radius: var(--radius-full); font-size: 0.625rem; font-weight: 600; color: white; text-transform: uppercase; }
  .card-title { font-size: 1.5rem; margin-bottom: var(--spacing-lg); text-align: center; }
  .card-content { font-size: 1rem; line-height: 1.8; text-align: left; color: var(--color-text-primary); }
  .card-example { margin-top: var(--spacing-md); padding: var(--spacing-md); background: var(--color-background); border-radius: var(--radius-md); text-align: left; font-size: 0.875rem; }
  .review-buttons { display: flex; justify-content: center; gap: var(--spacing-md); }
  .review-btn { padding: var(--spacing-sm) var(--spacing-lg); border: none; border-radius: var(--radius-md); font-weight: 600; cursor: pointer; transition: all var(--transition-fast); }
  .review-btn.hard { background: var(--color-error); color: white; }
  .review-btn.good { background: var(--color-warning); color: white; }
  .review-btn.easy { background: var(--color-success); color: white; }
  .review-btn:hover { transform: translateY(-2px); }
  .empty-state { text-align: center; padding: var(--spacing-2xl); color: var(--color-text-secondary); display: flex; flex-direction: column; align-items: center; gap: var(--spacing-md); }
  .empty-state svg { opacity: 0.5; }
  .loading { display: flex; justify-content: center; padding: var(--spacing-2xl); }
  .loading-spinner { width: 40px; height: 40px; border: 3px solid var(--color-border); border-top-color: var(--color-primary); border-radius: 50%; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
`;

const listStyles = `
  .topics-page { max-width: 1200px; margin: 0 auto; }
  .page-header { margin-bottom: var(--spacing-lg); }
  .header-row { display: flex; justify-content: space-between; align-items: center; }
  .header-actions { display: flex; gap: var(--spacing-sm); align-items: center; }
  .icon-btn { display: inline-flex; align-items: center; gap: 6px; }
  .flashcard-btn { position: relative; }
  .due-badge { position: absolute; top: -6px; right: -6px; background: var(--color-error); color: white; font-size: 0.65rem; font-weight: 700; min-width: 18px; height: 18px; border-radius: 9px; display: flex; align-items: center; justify-content: center; padding: 0 4px; }
  .add-word-form { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-md) var(--spacing-lg); margin-bottom: var(--spacing-lg); }
  .form-row-3 { display: grid; grid-template-columns: 1fr 2fr 1fr; gap: var(--spacing-md); align-items: start; }
  @media (max-width: 768px) { .form-row-3 { grid-template-columns: 1fr; } }
  .form-group { display: flex; flex-direction: column; gap: 4px; }
  .form-label { font-size: 0.8rem; font-weight: 600; color: var(--color-text-secondary); }
  .form-textarea { width: 100%; padding: 7px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-background); color: var(--color-text-primary); font-size: 0.875rem; resize: vertical; font-family: inherit; line-height: 1.5; box-sizing: border-box; }
  .form-textarea:focus { outline: none; border-color: var(--color-primary); }
  .dict-loading { font-weight: 400; font-style: italic; color: var(--color-text-secondary); opacity: 0.7; }
  .form-actions-right { display: flex; justify-content: flex-end; gap: var(--spacing-sm); margin-top: var(--spacing-md); }
  .filters { display: flex; gap: var(--spacing-md); margin-bottom: var(--spacing-lg); }
  .filter-select { padding: var(--spacing-sm) var(--spacing-md); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); color: var(--color-text-primary); }
  .topics-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--spacing-md); }
  @media (max-width: 1024px) { .topics-grid { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 768px) { .topics-grid { grid-template-columns: 1fr; } }
  .topic-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-md); display: flex; flex-direction: column; }
  .topic-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--spacing-sm); }
  .topic-skill { padding: 2px 8px; border-radius: var(--radius-full); font-size: 0.625rem; font-weight: 600; color: white; text-transform: uppercase; }
  .topic-category { font-size: 0.75rem; color: var(--color-text-secondary); }
  .topic-title { font-size: 1rem; margin-bottom: var(--spacing-sm); }
  .topic-content { font-size: 0.875rem; line-height: 1.6; color: var(--color-text-secondary); margin-bottom: var(--spacing-sm); flex: 1; }
  .topic-example { font-size: 0.75rem; padding: var(--spacing-sm); background: var(--color-background); border-radius: var(--radius-sm); margin-bottom: var(--spacing-sm); }
  .topic-footer { display: flex; justify-content: space-between; align-items: center; margin-top: auto; padding-top: var(--spacing-sm); }
  .topic-difficulty { font-size: 0.75rem; color: var(--color-text-secondary); }
  .topic-difficulty .filled { color: var(--color-warning); }
  .add-deck-btn { display: inline-flex; align-items: center; gap: 4px; background: none; border: 1px solid var(--color-border); color: var(--color-text-secondary); padding: 3px 10px; border-radius: var(--radius-sm); font-size: 0.75rem; font-weight: 500; cursor: pointer; transition: all var(--transition-fast); }
  .add-deck-btn:hover:not(:disabled) { border-color: var(--color-primary); color: var(--color-primary); }
  .add-deck-btn.in-deck { border-color: var(--color-success); color: var(--color-success); cursor: default; }
  .empty-state { text-align: center; padding: var(--spacing-2xl); color: var(--color-text-secondary); display: flex; flex-direction: column; align-items: center; gap: var(--spacing-md); }
  .empty-state svg { opacity: 0.5; }
  .loading { display: flex; justify-content: center; padding: var(--spacing-2xl); }
  .loading-spinner { width: 40px; height: 40px; border: 3px solid var(--color-border); border-top-color: var(--color-primary); border-radius: 50%; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
`;
