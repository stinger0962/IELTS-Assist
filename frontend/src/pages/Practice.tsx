import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { BookOpen, Headphones, Pen, MessageCircle, Sparkles, RefreshCw, ChevronLeft, Type } from 'lucide-react';
import { practiceAPI, progressAPI } from '../api';
import type {
  AIReadingPractice, AIListeningPractice, AIGrammarPractice,
  AIWritingPractice, AISpeakingPractice,
} from '../types';
import AIReadingExerciseView from '../components/practice/AIReadingView';
import AIListeningExerciseView from '../components/practice/AIListeningView';
import AIWritingExerciseView from '../components/practice/AIWritingView';
import AIGrammarExerciseView from '../components/practice/AIGrammarView';
import AISpeakingExerciseView from '../components/practice/AISpeakingView';
import AISpeakingPart1View from '../components/practice/AISpeakingPart1View';
import AISpeakingPart3View from '../components/practice/AISpeakingPart3View';
import AISpeakingFullTestView from '../components/practice/AISpeakingFullTestView';

// Error boundary to prevent white screens from component crashes
class ExerciseErrorBoundary extends React.Component<
  { children: React.ReactNode; onBack: () => void },
  { hasError: boolean; error: string }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false, error: '' };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message };
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ExerciseErrorBoundary]', error, info.componentStack);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <h2>Something went wrong</h2>
          <p style={{ color: '#888', margin: '1rem 0' }}>{this.state.error}</p>
          <button className="btn btn-primary" onClick={this.props.onBack}>Go Back</button>
        </div>
      );
    }
    return this.props.children;
  }
}


const ESSAY_TYPE_LABELS: Record<string, string> = {
  opinion: 'Opinion Essay',
  discussion: 'Discussion Essay',
  problem_solution: 'Problem & Solution',
  advantages_disadvantages: 'Advantages & Disadvantages',
  two_part: 'Two-Part Question',
};

// ─── Main Practice Page ──────────────────────────────────────────────────────

export default function Practice() {
  const { t } = useTranslation();

  const [aiReadingExercises, setAIReadingExercises] = useState<AIReadingPractice[]>([]);
  const [currentAIExercise, setCurrentAIExercise] = useState<AIReadingPractice | null>(null);
  const [generatingMore, setGeneratingMore] = useState(false);
  const [poolEmpty, setPoolEmpty] = useState(false);
  const [readingLoading, setReadingLoading] = useState(false);

  const [aiListeningExercises, setAIListeningExercises] = useState<AIListeningPractice[]>([]);
  const [currentAIListening, setCurrentAIListening] = useState<AIListeningPractice | null>(null);
  const [listeningLoading, setListeningLoading] = useState(false);
  const [listeningGeneratingMore, setListeningGeneratingMore] = useState(false);
  const [listeningPoolEmpty, setListeningPoolEmpty] = useState(false);

  const [aiGrammarExercises, setAIGrammarExercises] = useState<AIGrammarPractice[]>([]);
  const [currentAIGrammar, setCurrentAIGrammar] = useState<AIGrammarPractice | null>(null);
  const [grammarLoading, setGrammarLoading] = useState(false);
  const [grammarGeneratingMore, setGrammarGeneratingMore] = useState(false);
  const [grammarPoolEmpty, setGrammarPoolEmpty] = useState(false);

  const [aiWritingExercises, setAIWritingExercises] = useState<AIWritingPractice[]>([]);
  const [currentAIWriting, setCurrentAIWriting] = useState<AIWritingPractice | null>(null);
  const [writingLoading, setWritingLoading] = useState(false);
  const [writingGeneratingMore, setWritingGeneratingMore] = useState(false);
  const [writingPoolEmpty, setWritingPoolEmpty] = useState(false);

  const [aiSpeakingExercises, setAISpeakingExercises] = useState<AISpeakingPractice[]>([]);
  const [currentAISpeaking, setCurrentAISpeaking] = useState<AISpeakingPractice | null>(null);
  const [speakingLoading, setSpeakingLoading] = useState(false);
  const [speakingGeneratingMore, setSpeakingGeneratingMore] = useState(false);
  const [speakingPoolEmpty, setSpeakingPoolEmpty] = useState(false);

  const [showResult, setShowResult] = useState(false);
  const [result, setResult] = useState<{ correct: number; total: number } | null>(null);
  const [loading, setLoading] = useState(false);

  // Tab + mode state
  type SkillTab = 'reading' | 'listening' | 'grammar' | 'writing' | 'speaking';
  type PracticeMode = 'practice' | 'exam';
  const [activeSkill, setActiveSkill] = useState<SkillTab>('reading');
  const [practiceMode, setPracticeMode] = useState<PracticeMode>('practice');

  // Skill insights for snapshot
  const [skillInsights, setSkillInsights] = useState<any>(null);

  useEffect(() => { loadExercises(); }, []);

  // Load insights when active skill changes
  useEffect(() => {
    const loadInsights = async () => {
      try {
        if (activeSkill === 'speaking') {
          const res = await progressAPI.getSpeakingInsights();
          setSkillInsights(res.data);
        } else if (activeSkill === 'writing') {
          const res = await progressAPI.getWritingInsights();
          setSkillInsights(res.data);
        } else {
          const res = await progressAPI.getAccuracyInsights(activeSkill);
          setSkillInsights(res.data);
        }
      } catch {
        setSkillInsights(null);
      }
    };
    loadInsights();
  }, [activeSkill]);

  const loadAIReadingExercises = async () => {
    setReadingLoading(true);
    try {
      const res = await practiceAPI.getDailyReading();
      const practices = res.data?.practices;
      setAIReadingExercises(Array.isArray(practices) ? practices : []);
      setPoolEmpty(false);
    } catch {
      // keep existing list
    } finally {
      setReadingLoading(false);
    }
  };

  const loadAIListeningExercises = async () => {
    setListeningLoading(true);
    try {
      const res = await practiceAPI.getDailyListening();
      const practices = res.data?.practices;
      setAIListeningExercises(Array.isArray(practices) ? practices : []);
      setListeningPoolEmpty(false);
    } catch {
      // keep existing list
    } finally {
      setListeningLoading(false);
    }
  };

  const loadAIGrammarExercises = async () => {
    setGrammarLoading(true);
    try {
      const res = await practiceAPI.getDailyGrammar();
      const practices = res.data?.practices;
      setAIGrammarExercises(Array.isArray(practices) ? practices : []);
      setGrammarPoolEmpty(false);
    } catch {
      // keep existing list
    } finally {
      setGrammarLoading(false);
    }
  };

  const loadAIWritingExercises = async () => {
    setWritingLoading(true);
    try {
      const res = await practiceAPI.getDailyWriting();
      const practices = res.data?.practices;
      setAIWritingExercises(Array.isArray(practices) ? practices : []);
      setWritingPoolEmpty(false);
    } catch {
      // keep existing list
    } finally {
      setWritingLoading(false);
    }
  };

  const loadAISpeakingExercises = async () => {
    setSpeakingLoading(true);
    try {
      const res = await practiceAPI.getDailySpeaking();
      const practices = res.data?.practices;
      setAISpeakingExercises(Array.isArray(practices) ? practices : []);
      setSpeakingPoolEmpty(false);
    } catch {
      // keep existing list
    } finally {
      setSpeakingLoading(false);
    }
  };

  const loadExercises = async () => {
    setLoading(true);
    loadAIReadingExercises();
    loadAIListeningExercises();
    loadAIGrammarExercises();
    loadAIWritingExercises();
    loadAISpeakingExercises();
    setLoading(false);
  };

  const handleSelectAIExercise = (ex: AIReadingPractice) => {
    setCurrentAIExercise(ex);
    practiceAPI.triggerReplenish().catch(() => {});
  };

  const handleGenerateMore = async () => {
    setGeneratingMore(true);
    try {
      const res = await practiceAPI.generateMore();
      if (res.data?.pool_empty) {
        setPoolEmpty(true);
      } else {
        const newPractices: AIReadingPractice[] = res.data?.practices ?? [];
        if (newPractices.length > 0) {
          setAIReadingExercises(prev => [...prev, ...newPractices]);
          setPoolEmpty(false);
        }
      }
    } catch (err) {
      console.error('Failed to generate more:', err);
    } finally {
      setGeneratingMore(false);
    }
  };

  const handleSelectAIListening = (ex: AIListeningPractice) => {
    setCurrentAIListening(ex);
  };

  const handleGenerateMoreListening = async () => {
    setListeningGeneratingMore(true);
    try {
      const res = await practiceAPI.generateMoreListening();
      if (res.data?.pool_empty) {
        setListeningPoolEmpty(true);
      } else {
        const newPractices: AIListeningPractice[] = res.data?.practices ?? [];
        if (newPractices.length > 0) {
          setAIListeningExercises(prev => [...prev, ...newPractices]);
          setListeningPoolEmpty(false);
        }
      }
    } catch (err) {
      console.error('Failed to generate more listening:', err);
    } finally {
      setListeningGeneratingMore(false);
    }
  };

  const handleSelectAIWriting = (ex: AIWritingPractice) => {
    setCurrentAIWriting(ex);
  };

  const handleGenerateMoreWriting = async () => {
    setWritingGeneratingMore(true);
    try {
      const res = await practiceAPI.generateMoreWriting();
      if (res.data?.pool_empty) {
        setWritingPoolEmpty(true);
      } else {
        const newPractices: AIWritingPractice[] = res.data?.practices ?? [];
        if (newPractices.length > 0) {
          setAIWritingExercises(prev => [...prev, ...newPractices]);
          setWritingPoolEmpty(false);
        }
      }
    } catch (err) {
      console.error('Failed to generate more writing:', err);
    } finally {
      setWritingGeneratingMore(false);
    }
  };

  const handleSelectAIGrammar = (ex: AIGrammarPractice) => {
    setCurrentAIGrammar(ex);
  };

  const handleGenerateMoreGrammar = async () => {
    setGrammarGeneratingMore(true);
    try {
      const res = await practiceAPI.generateMoreGrammar();
      if (res.data?.pool_empty) {
        setGrammarPoolEmpty(true);
      } else {
        const newPractices: AIGrammarPractice[] = res.data?.practices ?? [];
        if (newPractices.length > 0) {
          setAIGrammarExercises(prev => [...prev, ...newPractices]);
          setGrammarPoolEmpty(false);
        }
      }
    } catch (err) {
      console.error('Failed to generate more grammar:', err);
    } finally {
      setGrammarGeneratingMore(false);
    }
  };

  const handleSelectAISpeaking = (ex: AISpeakingPractice) => {
    setCurrentAISpeaking(ex);
  };

  const handleGenerateMoreSpeaking = async () => {
    setSpeakingGeneratingMore(true);
    try {
      const res = await practiceAPI.generateMoreSpeaking();
      if (res.data?.pool_empty) {
        setSpeakingPoolEmpty(true);
      } else {
        const newPractices: AISpeakingPractice[] = res.data?.practices ?? [];
        if (newPractices.length > 0) {
          setAISpeakingExercises(prev => [...prev, ...newPractices]);
          setSpeakingPoolEmpty(false);
        }
      }
    } catch (err) {
      console.error('Failed to generate more speaking:', err);
    } finally {
      setSpeakingGeneratingMore(false);
    }
  };

  const handleComplete = (correct: number, total: number) => {
    setResult({ correct, total });
    setShowResult(true);
  };

  const handleBack = () => {
    setCurrentAIExercise(null);
    setCurrentAIListening(null);
    setCurrentAIGrammar(null);
    setCurrentAIWriting(null);
    setCurrentAISpeaking(null);
    setShowResult(false);
    setResult(null);
    loadAIReadingExercises();
    loadAIListeningExercises();
    loadAIGrammarExercises();
    loadAIWritingExercises();
    loadAISpeakingExercises();
  };

  // Result screen
  if (showResult && result) {
    const percentage = Math.round((result.correct / result.total) * 100);
    return (
      <div className="practice result-view">
        <div className="result-card">
          <div className="result-circle" style={{ '--percentage': `${percentage}%` } as React.CSSProperties}>
            <span className="result-score">{percentage}%</span>
          </div>
          <h2>{t('practice.score')}</h2>
          <p>{result.correct} / {result.total} {t('practice.correct')}</p>
          <button className="btn btn-primary btn-lg" onClick={handleBack}>Continue</button>
        </div>
        <style>{`
          .result-view { display: flex; justify-content: center; align-items: center; min-height: 60vh; }
          .result-card { text-align: center; padding: var(--spacing-2xl); }
          .result-circle { width: 150px; height: 150px; border-radius: 50%; background: conic-gradient(var(--color-primary) var(--percentage, 0%), var(--color-border) 0%); display: flex; align-items: center; justify-content: center; margin: 0 auto var(--spacing-lg); }
          .result-score { font-size: 2.5rem; font-weight: 700; }
        `}</style>
      </div>
    );
  }

  // AI Reading exercise view
  if (currentAIExercise) {
    return (
      <div className="practice">
        <button className="back-btn" onClick={handleBack}><ChevronLeft size={16} /> Back</button>
        <AIReadingExerciseView exercise={currentAIExercise} onComplete={handleComplete} />
        <style>{sharedExerciseStyles}</style>
      </div>
    );
  }

  // AI Listening exercise view
  if (currentAIListening) {
    return (
      <div className="practice">
        <button className="back-btn" onClick={handleBack}><ChevronLeft size={16} /> Back</button>
        <AIListeningExerciseView exercise={currentAIListening} onComplete={handleComplete} />
        <style>{sharedExerciseStyles}</style>
      </div>
    );
  }

  // AI Grammar exercise view
  if (currentAIGrammar) {
    return (
      <div className="practice">
        <button className="back-btn" onClick={handleBack}><ChevronLeft size={16} /> Back</button>
        <AIGrammarExerciseView exercise={currentAIGrammar} onComplete={handleComplete} />
        <style>{sharedExerciseStyles}</style>
      </div>
    );
  }

  // AI Writing exercise view
  if (currentAIWriting) {
    return (
      <div className="practice">
        <button className="back-btn" onClick={handleBack}><ChevronLeft size={16} /> Back</button>
        <AIWritingExerciseView exercise={currentAIWriting} onBack={handleBack} />
        <style>{sharedExerciseStyles}</style>
      </div>
    );
  }

  // AI Speaking exercise view
  if (currentAISpeaking) {
    const mod = currentAISpeaking.meta.module;
    return (
      <div className="practice">
        <button className="back-btn" onClick={handleBack}><ChevronLeft size={16} /> Back</button>
        <ExerciseErrorBoundary onBack={handleBack}>
          {mod === 'speaking_part1' ? (
            <AISpeakingPart1View exercise={currentAISpeaking} onBack={handleBack} />
          ) : mod === 'speaking_part3' ? (
            <AISpeakingPart3View exercise={currentAISpeaking} onBack={handleBack} />
          ) : mod === 'speaking_full_test' ? (
            <AISpeakingFullTestView exercise={currentAISpeaking} onBack={handleBack} />
          ) : (
            <AISpeakingExerciseView exercise={currentAISpeaking} onBack={handleBack} />
          )}
        </ExerciseErrorBoundary>
        <style>{sharedExerciseStyles}</style>
      </div>
    );
  }

  // ─── Helpers for rendering exercise lists ────
  const renderExerciseList = (
    exercises: any[],
    isLoading: boolean,
    isPoolEmpty: boolean,
    isGenerating: boolean,
    onGenerateMore: () => void,
    renderCard: (ex: any, i: number) => React.ReactNode,
    loadingMsg = 'Loading exercises…',
    genTime = '~2 min',
  ) => (
    <div className="exercise-list stagger-in">
      {isLoading ? (
        <div className="generating-msg"><div className="loading-spinner-sm" /><span>{loadingMsg}</span></div>
      ) : exercises.length === 0 ? (
        <p className="empty-list">No exercises yet — click Generate below.</p>
      ) : (
        exercises.map((ex, i) => renderCard(ex, i))
      )}
      {exercises.length < 3 && (
        isPoolEmpty ? (
          <div className="pool-empty-msg">
            <span>Generating in background ({genTime})</span>
            <button className="retry-link" onClick={onGenerateMore} disabled={isGenerating}>
              {isGenerating ? 'Checking…' : 'Retry'}
            </button>
          </div>
        ) : (
          <button className="generate-more-btn" onClick={onGenerateMore} disabled={isGenerating}>
            {isGenerating
              ? <><div className="loading-spinner-sm" /> Checking pool…</>
              : <><RefreshCw size={13} /> Generate More</>}
          </button>
        )
      )}
    </div>
  );

  // Skill tab config
  const skillTabs: { key: SkillTab; label: string; icon: typeof BookOpen; color: string; gradient: string }[] = [
    { key: 'reading', label: t('practice.reading'), icon: BookOpen, color: '#4F46E5', gradient: 'linear-gradient(135deg, #4F46E5, #6366F1)' },
    { key: 'listening', label: t('practice.listening'), icon: Headphones, color: '#10B981', gradient: 'linear-gradient(135deg, #10B981, #34D399)' },
    { key: 'speaking', label: t('practice.speaking'), icon: MessageCircle, color: '#EF4444', gradient: 'linear-gradient(135deg, #EF4444, #F97316)' },
    { key: 'writing', label: t('practice.writing'), icon: Pen, color: '#F59E0B', gradient: 'linear-gradient(135deg, #F59E0B, #FBBF24)' },
    { key: 'grammar', label: t('practice.grammar'), icon: Type, color: '#8B5CF6', gradient: 'linear-gradient(135deg, #8B5CF6, #A78BFA)' },
  ];

  const activeTab = skillTabs.find(s => s.key === activeSkill)!;

  // Snapshot renderer
  const renderSnapshot = () => {
    if (!skillInsights) return null;
    const isCriterion = activeSkill === 'speaking' || activeSkill === 'writing';
    const ins = skillInsights as any;
    if (!ins.total_sessions || ins.total_sessions === 0) return null;

    return (
      <div className="skill-snapshot">
        <div className="snapshot-header">
          <span className="snapshot-title">{activeTab.label} Progress</span>
          <span className="snapshot-sessions">{ins.total_sessions} sessions</span>
        </div>
        {isCriterion ? (
          <>
            <div className="snapshot-stats">
              <span className="snapshot-band" style={{ color: ins.overall_average >= 7 ? '#10B981' : ins.overall_average >= 6 ? '#F59E0B' : '#EF4444' }}>
                Band {ins.overall_average?.toFixed(1)}
              </span>
              {ins.weakest_criterion && (
                <span className="snapshot-weak">Focus: {ins.weakest_criterion}</span>
              )}
            </div>
          </>
        ) : (
          <div className="snapshot-stats">
            <span className="snapshot-band" style={{ color: (ins.overall_accuracy || 0) >= 80 ? '#10B981' : (ins.overall_accuracy || 0) >= 60 ? '#F59E0B' : '#EF4444' }}>
              {ins.overall_accuracy?.toFixed(0)}% accuracy
            </span>
            <span className="snapshot-weak">{ins.total_correct}/{ins.total_questions_answered} correct</span>
          </div>
        )}
        {ins.recent_sessions && ins.recent_sessions.length > 0 && (
          <div className="snapshot-recent">
            {ins.recent_sessions.slice(0, 3).map((s: any, i: number) => (
              <div key={i} className="snapshot-session">
                <span className="snapshot-date">
                  {new Date(s.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                </span>
                <span className="snapshot-topic">{s.topic || '—'}</span>
                <span className="snapshot-score" style={{
                  color: isCriterion
                    ? (s.overall_band >= 7 ? '#10B981' : s.overall_band >= 6 ? '#F59E0B' : '#EF4444')
                    : ((s.accuracy || 0) >= 80 ? '#10B981' : (s.accuracy || 0) >= 60 ? '#F59E0B' : '#EF4444')
                }}>
                  {isCriterion ? s.overall_band : `${s.accuracy?.toFixed(0)}%`}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // Main list
  return (
    <div className="practice">
      {/* Skill icon grid — always fully visible */}
      <div className="skill-icon-grid">
        {skillTabs.map((tab) => {
          const isActive = activeSkill === tab.key;
          return (
            <button
              key={tab.key}
              className={`skill-icon-btn ${isActive ? 'active' : ''}`}
              onClick={() => setActiveSkill(tab.key)}
            >
              <div className="skill-icon-circle" style={isActive ? { background: tab.gradient, color: '#fff' } : {}}>
                <tab.icon size={18} />
              </div>
              <span className="skill-icon-label" style={isActive ? { color: tab.color } : {}}>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Mode toggle */}
      <div className="mode-toggle">
        <button
          className={`mode-btn ${practiceMode === 'practice' ? 'active' : ''}`}
          onClick={() => setPracticeMode('practice')}
        >
          Practice
        </button>
        <button
          className={`mode-btn ${practiceMode === 'exam' ? 'active' : ''}`}
          onClick={() => setPracticeMode('exam')}
        >
          Exam
        </button>
      </div>

      {loading ? (
        <div className="loading"><div className="loading-spinner" /></div>
      ) : practiceMode === 'exam' ? (
        /* ─── Exam mode ─── */
        <div className="exercise-list">
          {activeSkill === 'speaking' ? (
            aiSpeakingExercises.filter(ex => ex.meta.module === 'speaking_full_test').length > 0 ? (
              aiSpeakingExercises.filter(ex => ex.meta.module === 'speaking_full_test').map((ex, i) => (
                <button key={i} className="exercise-item exercise-item-highlight" onClick={() => handleSelectAISpeaking(ex)}>
                  <span className="exercise-title">{ex.meta.topic}</span>
                  <span className="exercise-meta">Full Test · ~14 min</span>
                </button>
              ))
            ) : (
              <p className="empty-list">No full test available. Generate more speaking exercises.</p>
            )
          ) : (
            <div className="exam-coming-soon">
              <Sparkles size={32} />
              <h3>Full {activeTab.label} Test</h3>
              <p>Coming soon — full-length IELTS {activeTab.label.toLowerCase()} test simulation.</p>
            </div>
          )}
        </div>
      ) : (
        /* ─── Practice mode ─── */
        <>
          {activeSkill === 'reading' && renderExerciseList(
            aiReadingExercises, readingLoading, poolEmpty, generatingMore,
            handleGenerateMore,
            (ex, i) => (
              <button key={i} className="exercise-item" style={{ borderLeftColor: '#4F46E5' }} onClick={() => handleSelectAIExercise(ex)}>
                <span className="exercise-title">{ex.meta.topic}</span>
                <span className="exercise-meta">
                  {ex.meta.word_count}w · {
                    ex.questions.groups
                      ? ex.questions.groups.reduce((n: number, g: any) => n + (g.answers?.length ?? g.items?.length ?? 0), 0)
                      : (ex.questions.true_false_not_given?.length ?? 0) +
                        (Array.isArray(ex.questions.second_type?.items) ? ex.questions.second_type!.items.length : 3)
                  }q
                </span>
              </button>
            ),
          )}

          {activeSkill === 'listening' && renderExerciseList(
            aiListeningExercises, listeningLoading, listeningPoolEmpty, listeningGeneratingMore,
            handleGenerateMoreListening,
            (ex, i) => (
              <button key={i} className="exercise-item" style={{ borderLeftColor: '#10B981' }} onClick={() => handleSelectAIListening(ex)}>
                <span className="exercise-title">{ex.meta.topic}</span>
                <span className="exercise-meta">{ex.meta.format} · {(ex.questions.completion?.length ?? 0) + (ex.questions.multiple_choice?.length ?? 0)}q</span>
              </button>
            ),
            'Loading listening exercises…', '~3 min',
          )}

          {activeSkill === 'grammar' && renderExerciseList(
            aiGrammarExercises, grammarLoading, grammarPoolEmpty, grammarGeneratingMore,
            handleGenerateMoreGrammar,
            (ex, i) => (
              <button key={i} className="exercise-item" style={{ borderLeftColor: '#8B5CF6' }} onClick={() => handleSelectAIGrammar(ex)}>
                <span className="exercise-title">{ex.meta.grammar_topic}</span>
                <span className="exercise-meta">{ex.meta.band_level} · {ex.meta.question_count}q</span>
              </button>
            ),
          )}

          {activeSkill === 'writing' && renderExerciseList(
            aiWritingExercises, writingLoading, writingPoolEmpty, writingGeneratingMore,
            handleGenerateMoreWriting,
            (ex, i) => (
              <button key={i} className="exercise-item" style={{ borderLeftColor: '#F59E0B' }} onClick={() => handleSelectAIWriting(ex)}>
                <span className="exercise-title">{ex.meta.topic}</span>
                <span className="exercise-meta">
                  {ESSAY_TYPE_LABELS[ex.meta.essay_type] || ex.meta.essay_type.replace(/_/g, ' ')} · {ex.meta.domain} · 250w
                </span>
              </button>
            ),
          )}

          {activeSkill === 'speaking' && renderExerciseList(
            aiSpeakingExercises.filter(ex => ex.meta.module !== 'speaking_full_test'),
            speakingLoading, speakingPoolEmpty, speakingGeneratingMore,
            handleGenerateMoreSpeaking,
            (ex, i) => {
              const mod = ex.meta.module;
              const label = mod === 'speaking_part1' ? 'Interview · 3 topics'
                : mod === 'speaking_part3' ? `Discussion · ${ex.meta.topic}`
                : `Long Turn · ${ex.meta.domain || 'speaking'}`;
              return (
                <button key={i} className="exercise-item" style={{ borderLeftColor: '#EF4444' }} onClick={() => handleSelectAISpeaking(ex)}>
                  <span className="exercise-title">{ex.meta.topic}</span>
                  <span className="exercise-meta">{label}</span>
                </button>
              );
            },
          )}
        </>
      )}

      {/* Skill snapshot + recent scores */}
      {renderSnapshot()}

      <style>{listStyles}</style>
    </div>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────


const sharedExerciseStyles = `
  .back-btn { display: inline-flex; align-items: center; gap: 4px; background: none; border: none; color: var(--color-text-secondary); padding: 4px 8px; border-radius: var(--radius-sm); font-size: 0.875rem; font-weight: 500; cursor: pointer; transition: all var(--transition-fast); margin-bottom: var(--spacing-md); }
  .back-btn:hover { color: var(--color-primary); background: rgba(79,70,229,0.06); }
  .exercise-view { display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-lg); }
  @media (max-width: 1024px) { .exercise-view { grid-template-columns: 1fr; } }
  .exercise-passage { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); }
  .exercise-passage h3 { margin-bottom: var(--spacing-md); }
  .exercise-passage p { line-height: 1.8; color: var(--color-text-primary); }
  .exercise-question { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); }
  .question-header { margin-bottom: var(--spacing-md); }
  .question-number { background: var(--color-primary); color: white; padding: var(--spacing-xs) var(--spacing-sm); border-radius: var(--radius-sm); font-size: 0.75rem; font-weight: 600; }
  .question-text { font-size: 1.125rem; font-weight: 500; margin-bottom: var(--spacing-md); color: var(--color-text-primary); }
  .options { display: flex; flex-direction: column; gap: var(--spacing-sm); margin-bottom: var(--spacing-lg); }
  .option { display: flex; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-md); background: var(--color-background); border: 2px solid var(--color-border); border-radius: var(--radius-md); cursor: pointer; text-align: left; transition: all var(--transition-fast); }
  .option:hover:not(:disabled) { border-color: var(--color-primary); }
  .option.selected { border-color: var(--color-primary); background: rgba(79,70,229,0.1); }
  .option.correct { border-color: var(--color-success); background: rgba(16,185,129,0.1); }
  .option.incorrect { border-color: var(--color-error); background: rgba(239,68,68,0.1); }
  .option:disabled { cursor: default; }
  .option-letter { width: 28px; height: 28px; border-radius: 50%; background: var(--color-border); display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 0.875rem; flex-shrink: 0; }
  .option.selected .option-letter { background: var(--color-primary); color: white; }
  .option-text { flex: 1; }
  .result-icon { margin-left: auto; }
  .result-icon.correct { color: var(--color-success); }
  .result-icon.incorrect { color: var(--color-error); }
  .question-actions { display: flex; justify-content: flex-end; }
`;

const listStyles = `
  .practice { max-width: 600px; margin: 0 auto; }

  /* Skill icon grid — always fully visible */
  .skill-icon-grid { display: flex; justify-content: space-between; margin-bottom: var(--spacing-sm); padding: 4px 0; }
  .skill-icon-btn { display: flex; flex-direction: column; align-items: center; gap: 4px; background: none; border: none; cursor: pointer; padding: 4px 0; -webkit-tap-highlight-color: transparent; flex: 1; }
  .skill-icon-btn:active { transform: scale(0.92); }
  .skill-icon-circle { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: var(--color-border); color: var(--color-text-secondary); transition: all 0.15s ease; }
  .skill-icon-btn.active .skill-icon-circle { box-shadow: 0 2px 8px rgba(0,0,0,0.15); }
  .skill-icon-label { font-size: 0.65rem; font-weight: 500; color: var(--color-text-secondary); transition: all 0.15s ease; }
  .skill-icon-btn.active .skill-icon-label { font-weight: 700; }

  /* Mode toggle */
  .mode-toggle { display: flex; background: var(--color-border); border-radius: var(--radius-md); padding: 3px; margin-bottom: var(--spacing-md); }
  .mode-btn { flex: 1; padding: 8px 16px; border: none; background: none; border-radius: calc(var(--radius-md) - 2px); font-size: 0.85rem; font-weight: 600; cursor: pointer; color: var(--color-text-secondary); transition: all 0.15s ease; }
  .mode-btn.active { background: var(--color-surface); color: var(--color-text-primary); box-shadow: 0 1px 3px rgba(0,0,0,0.08); }

  /* Exam coming soon */
  .exam-coming-soon { text-align: center; padding: var(--spacing-2xl) var(--spacing-md); color: var(--color-text-secondary); }
  .exam-coming-soon h3 { font-size: 1.1rem; color: var(--color-text-primary); margin: var(--spacing-sm) 0 var(--spacing-xs); }
  .exam-coming-soon p { font-size: 0.85rem; line-height: 1.5; }

  /* Exercise list */
  .exercise-list { display: flex; flex-direction: column; gap: var(--spacing-sm); }
  .exercise-item { display: flex; justify-content: space-between; align-items: center; padding: var(--spacing-md) var(--spacing-md) var(--spacing-md) calc(var(--spacing-md) + 4px); background: var(--color-surface); border: 1px solid var(--color-border); border-left: 4px solid var(--color-primary); border-radius: var(--radius-md); cursor: pointer; transition: all 0.2s ease; text-align: left; box-shadow: var(--shadow-card); }
  .exercise-item:hover { box-shadow: var(--shadow-card-hover); transform: translateY(-1px); }
  .exercise-item:active { transform: translateY(0); box-shadow: var(--shadow-card); }
  .exercise-item-highlight { border-left-width: 4px; border-left-color: var(--color-primary); background: linear-gradient(135deg, var(--color-surface), color-mix(in srgb, var(--color-primary) 5%, var(--color-surface))); }
  .exercise-title { font-weight: 600; color: var(--color-text-primary); font-size: 0.9rem; }
  .exercise-meta { font-size: 0.72rem; color: var(--color-text-secondary); flex-shrink: 0; margin-left: 8px; }
  .empty-list { font-size: 0.875rem; color: var(--color-text-secondary); text-align: center; padding: var(--spacing-lg) 0; }
  .generating-msg { display: flex; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-sm) 0; font-size: 0.875rem; color: var(--color-text-secondary); }
  .generate-more-btn { display: flex; align-items: center; justify-content: center; gap: 6px; padding: var(--spacing-sm) var(--spacing-md); background: var(--color-surface); border: 1px dashed var(--color-border); border-radius: var(--radius-md); cursor: pointer; font-size: 0.8rem; color: var(--color-text-secondary); transition: all var(--transition-fast); margin-top: 2px; }
  .generate-more-btn:hover:not(:disabled) { border-color: var(--color-primary); color: var(--color-primary); }
  .generate-more-btn:disabled { opacity: 0.6; cursor: not-allowed; }
  .pool-empty-msg { display: flex; align-items: center; justify-content: space-between; padding: var(--spacing-sm) var(--spacing-md); background: rgba(245,158,11,0.08); border: 1px dashed rgba(245,158,11,0.4); border-radius: var(--radius-md); font-size: 0.8rem; color: var(--color-text-secondary); gap: var(--spacing-sm); }
  .retry-link { background: none; border: none; color: var(--color-primary); font-size: 0.8rem; cursor: pointer; padding: 0; text-decoration: underline; }
  .retry-link:disabled { opacity: 0.6; cursor: not-allowed; }
  .loading { display: flex; justify-content: center; padding: var(--spacing-2xl); }
  .loading-spinner { width: 40px; height: 40px; border: 3px solid var(--color-border); border-top-color: var(--color-primary); border-radius: 50%; animation: spin 1s linear infinite; }
  .loading-spinner-sm { width: 14px; height: 14px; border: 2px solid var(--color-border); border-top-color: var(--color-primary); border-radius: 50%; animation: spin 1s linear infinite; flex-shrink: 0; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Skill snapshot */
  .skill-snapshot { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-md); margin-top: var(--spacing-md); }
  .snapshot-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .snapshot-title { font-size: 0.85rem; font-weight: 600; color: var(--color-text-primary); }
  .snapshot-sessions { font-size: 0.72rem; color: var(--color-text-secondary); }
  .snapshot-stats { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
  .snapshot-band { font-size: 1rem; font-weight: 700; }
  .snapshot-weak { font-size: 0.75rem; color: var(--color-text-secondary); }
  .snapshot-recent { border-top: 1px solid var(--color-border); padding-top: 8px; }
  .snapshot-session { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
  .snapshot-date { font-size: 0.72rem; color: var(--color-text-secondary); width: 48px; flex-shrink: 0; }
  .snapshot-topic { font-size: 0.78rem; color: var(--color-text-secondary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .snapshot-score { font-size: 0.82rem; font-weight: 700; flex-shrink: 0; }
`;
