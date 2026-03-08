import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { BookOpen, Headphones, Pen, MessageCircle, Check, X, Sparkles, RefreshCw, ChevronLeft, Play, Pause, RotateCcw } from 'lucide-react';
import { practiceAPI, progressAPI, mistakesAPI, topicsAPI } from '../api';
import { useAppStore } from '../store';
import type {
  SkillType, WritingTopic, SpeakingTopic,
  AIReadingPractice, AIListeningPractice, TFNGAnswerItem, MCQQuestionItem, MCQAnswerItem,
  MatchingHeadingData, MatchingAnswerItem,
} from '../types';

const skillConfig = [
  { type: 'reading' as SkillType, icon: BookOpen, color: '#4F46E5' },
  { type: 'listening' as SkillType, icon: Headphones, color: '#10B981' },
  { type: 'writing' as SkillType, icon: Pen, color: '#F59E0B' },
  { type: 'speaking' as SkillType, icon: MessageCircle, color: '#EF4444' },
];

// ─── Dictionary helpers ───────────────────────────────────────────────────────

const POS_ABBR: Record<string, string> = {
  verb: 'v.', noun: 'n.', adjective: 'adj.', adverb: 'adv.',
  preposition: 'prep.', conjunction: 'conj.', pronoun: 'pron.', interjection: 'interj.',
};

function parseDictionaryEntry(data: any[]): string {
  if (!data?.length) return '';
  const lines: string[] = [];
  for (const meaning of (data[0].meanings ?? []).slice(0, 3)) {
    const abbr = POS_ABBR[meaning.partOfSpeech] ?? `${meaning.partOfSpeech}.`;
    for (const def of (meaning.definitions ?? []).slice(0, 2)) {
      lines.push(`${abbr} ${def.definition}${def.example ? ` e.g. "${def.example}"` : ''}`);
    }
  }
  return lines.join('\n');
}

// ─── AI Reading Exercise View ────────────────────────────────────────────────

function AIReadingExerciseView({
  exercise,
  onComplete,
}: {
  exercise: AIReadingPractice;
  onComplete: (correct: number, total: number) => void;
}) {
  const { language } = useAppStore();
  const [userAnswers, setUserAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const [score, setScore] = useState<{ correct: number; total: number } | null>(null);
  const [startTime] = useState(Date.now());
  const [explanations, setExplanations] = useState<Record<string, string>>({});
  const [explanationsLoading, setExplanationsLoading] = useState(false);
  const [vocabWord, setVocabWord] = useState('');
  const [vocabPopupPos, setVocabPopupPos] = useState<{ x: number; y: number } | null>(null);
  const [showVocabModal, setShowVocabModal] = useState(false);
  const [vocabDef, setVocabDef] = useState('');
  const [vocabDefZh, setVocabDefZh] = useState('');
  const [vocabPhonetic, setVocabPhonetic] = useState('');
  const [vocabAudioUrl, setVocabAudioUrl] = useState('');
  const [vocabDefLoading, setVocabDefLoading] = useState(false);
  const [vocabSaving, setVocabSaving] = useState(false);
  const [vocabDuplicate, setVocabDuplicate] = useState(false);
  const [vocabSaved, setVocabSaved] = useState(false);

  const tfngQuestions = exercise.questions.true_false_not_given ?? [];
  const secondType = exercise.questions.second_type;
  const isMCQ = secondType?.type === 'multiple_choice';
  const mcqItems = isMCQ ? (secondType.items as MCQQuestionItem[]) : [];
  const matchingData = !isMCQ ? (secondType.items as MatchingHeadingData) : null;

  const setAnswer = (key: string, value: string) => {
    if (!submitted) setUserAnswers(prev => ({ ...prev, [key]: value }));
  };

  const allAnswered = () => {
    const tfngDone = tfngQuestions.every(q => userAnswers[`tfng_${q.question_number}`]);
    if (isMCQ) return tfngDone && mcqItems.every((_, idx) => userAnswers[`mc_${idx}`]);
    return tfngDone && (matchingData?.paragraphs ?? []).every(p => userAnswers[`mh_${p.number}`]);
  };

  const handleSubmit = () => {
    let correct = 0;
    type WrongEntry = { key: string; question_type: string; question: string; user_answer: string; correct_answer: string };
    const wrongAnswers: WrongEntry[] = [];

    // Score T/F/NG
    tfngQuestions.forEach(q => {
      const key = `tfng_${q.question_number}`;
      const userAns = userAnswers[key];
      const correctAns = (exercise.answer_key.true_false_not_given as TFNGAnswerItem[]).find(
        a => a.question_number === q.question_number
      )?.answer;
      if (userAns === correctAns) {
        correct++;
      } else {
        wrongAnswers.push({ key, question_type: 'T/F/NG', question: q.statement, user_answer: userAns ?? '(unanswered)', correct_answer: correctAns ?? '' });
        mistakesAPI.create({
          skill: 'reading', question: q.statement,
          user_answer: userAns ?? '(unanswered)', correct_answer: correctAns ?? '',
          mistake_type: 'true_false_not_given',
        }).catch(() => {});
      }
    });

    // Score second type
    const secondAnswers = exercise.answer_key.second_type_answers;
    if (isMCQ) {
      mcqItems.forEach((item, idx) => {
        const key = `mc_${idx}`;
        const userAns = userAnswers[key];
        const correctAns = (secondAnswers as MCQAnswerItem[]).find(
          a => a.question_number === item.question_number
        )?.answer;
        if (userAns === correctAns) {
          correct++;
        } else {
          const opts = item.options ?? {};
          const userLabel = userAns ? `${userAns}. ${opts[userAns] ?? ''}` : '(unanswered)';
          const correctLabel = correctAns ? `${correctAns}. ${opts[correctAns] ?? ''}` : '';
          wrongAnswers.push({ key, question_type: 'MCQ', question: item.question, user_answer: userLabel, correct_answer: correctLabel });
          mistakesAPI.create({
            skill: 'reading', question: item.question,
            user_answer: userLabel, correct_answer: correctLabel,
            mistake_type: 'multiple_choice',
          }).catch(() => {});
        }
      });
    } else if (matchingData) {
      matchingData.paragraphs.forEach(para => {
        const userAns = userAnswers[`mh_${para.number}`];
        const correctAns = (secondAnswers as MatchingAnswerItem[]).find(
          a => a.paragraph_number === para.number
        )?.answer;
        if (userAns === correctAns) correct++;
      });
    }

    const secondCount = isMCQ ? mcqItems.length : (matchingData?.paragraphs.length ?? 0);
    const total = tfngQuestions.length + secondCount;
    setScore({ correct, total });
    setSubmitted(true);

    const timeTaken = Math.round((Date.now() - startTime) / 1000);
    const exerciseId = `ai_${exercise.meta.topic.replace(/\s+/g, '_').slice(0, 40)}`;
    const scoreVal = total > 0 ? (correct / total) * 100 : 0;
    practiceAPI.submit({
      skill: 'reading', exercise_id: exerciseId,
      score: scoreVal,
      total_questions: total, correct_answers: correct, time_taken_seconds: timeTaken,
    }).catch(() => {});
    if (exercise.practice_db_id) {
      practiceAPI.submitAIReading(
        exercise.practice_db_id,
        JSON.stringify(userAnswers),
        scoreVal, correct, total,
      ).catch(() => {});
    }
    const studyMinutes = Math.max(1, Math.round(timeTaken / 60));
    const estimatedBand = total > 0 ? Math.round((3.5 + (correct / total) * 4.5) * 2) / 2 : 0;
    progressAPI.updateProgress({
      skill: 'reading',
      total_questions: total,
      correct_answers: correct,
      study_time_minutes: studyMinutes,
      band_score: estimatedBand,
    }).catch(() => {});
    progressAPI.createSession({ skill: 'reading', duration_minutes: studyMinutes }).catch(() => {});
    practiceAPI.extractVocabulary(exercise.passage, exercise.meta.topic).catch(() => {});

    // Fetch one-sentence explanations for every wrong answer
    if (wrongAnswers.length > 0) {
      setExplanationsLoading(true);
      practiceAPI.explainMistakes(exercise.passage, wrongAnswers)
        .then(res => {
          const map: Record<string, string> = {};
          for (const item of (res.data.explanations ?? [])) map[item.key] = item.explanation;
          setExplanations(map);
        })
        .catch(() => {})
        .finally(() => setExplanationsLoading(false));
    }
  };

  const tfngCorrect = (qNum: number) =>
    (exercise.answer_key.true_false_not_given as TFNGAnswerItem[]).find(a => a.question_number === qNum)?.answer;
  const mcqCorrect = (qNum: number) =>
    (exercise.answer_key.second_type_answers as MCQAnswerItem[]).find(a => a.question_number === qNum)?.answer;
  const matchingCorrect = (paraNum: number) =>
    (exercise.answer_key.second_type_answers as MatchingAnswerItem[]).find(a => a.paragraph_number === paraNum)?.answer;

  const paragraphs = exercise.passage.split(/\n\n+/).filter(Boolean);

  const openVocabModal = async (word: string) => {
    setVocabWord(word);
    setVocabDef('');
    setVocabDefZh('');
    setVocabPhonetic('');
    setVocabAudioUrl('');
    setVocabDefLoading(true);
    setShowVocabModal(true);
    setVocabPopupPos(null);
    try {
      const res = await fetch(`https://api.dictionaryapi.dev/api/v2/entries/en/${encodeURIComponent(word)}`);
      if (res.ok) {
        const data = await res.json();
        const formatted = parseDictionaryEntry(data);
        const phonetic = data[0]?.phonetic || data[0]?.phonetics?.find((p: any) => p.text)?.text || '';
        const audioUrl = data[0]?.phonetics?.find((p: any) => p.audio?.endsWith('.mp3'))?.audio || '';
        setVocabPhonetic(phonetic);
        setVocabAudioUrl(audioUrl);
        if (formatted) {
          setVocabDef(formatted);
          if (language === 'zh') {
            const quotes: string[] = [];
            const tokenized = formatted.replace(/"([^"]*)"/g, (_, q) => {
              quotes.push(`"${q}"`);
              return `__Q${quotes.length - 1}__`;
            });
            topicsAPI.translateDefinition(word, tokenized)
              .then(r => {
                if (r.data.content_zh) {
                  const restored = r.data.content_zh.replace(/__Q(\d+)__/g, (_: string, i: string) => quotes[+i] ?? '');
                  setVocabDefZh(restored);
                }
              })
              .catch(() => {});
          }
        }
      }
    } catch { /* ignore — user can type manually */ } finally {
      setVocabDefLoading(false);
    }
  };

  const handleTextSelect = () => {
    const sel = window.getSelection();
    const text = sel?.toString().trim() ?? '';
    if (text.length >= 2 && text.length <= 60 && !text.includes('\n')) {
      try {
        const rect = sel!.getRangeAt(0).getBoundingClientRect();
        setVocabWord(text);
        // Position popup BELOW the selection so it doesn't clash with the
        // browser's native Copy / Google Search toolbar which appears above
        setVocabPopupPos({ x: rect.left + rect.width / 2, y: rect.bottom });
      } catch { /* ignore */ }
    } else {
      setVocabPopupPos(null);
    }
  };

  // Listen on document so mobile handle-drag selections are also detected
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const onSelChange = () => {
      clearTimeout(timer);
      timer = setTimeout(handleTextSelect, 200);
    };
    document.addEventListener('selectionchange', onSelChange);
    return () => { clearTimeout(timer); document.removeEventListener('selectionchange', onSelChange); };
  }, []);

  const handleSaveVocab = async () => {
    if (!vocabDef.trim()) return;
    setVocabSaving(true);
    setVocabDuplicate(false);
    try {
      await topicsAPI.create({ title: vocabWord, content: vocabDef, content_zh: vocabDefZh || undefined, skill: 'reading', category: 'vocabulary', phonetic: vocabPhonetic || undefined, audio_url: vocabAudioUrl || undefined });
      setVocabSaved(true);
      setShowVocabModal(false);
      setVocabDef('');
      setTimeout(() => setVocabSaved(false), 3000);
    } catch (error: any) {
      if (error?.response?.status === 409) setVocabDuplicate(true);
    } finally {
      setVocabSaving(false);
    }
  };

  return (
    <div className="ai-exercise-view">
      {/* Floating "Add to Vocab" popup on text selection */}
      {vocabPopupPos && !showVocabModal && (
        <div
          className="vocab-popup"
          style={{ left: vocabPopupPos.x, top: vocabPopupPos.y + 10 }}
          onMouseDown={e => { e.preventDefault(); openVocabModal(vocabWord); }}
          onTouchEnd={e => { e.preventDefault(); openVocabModal(vocabWord); }}
        >
          + Add to Vocab
        </div>
      )}

      {/* Vocab modal */}
      {showVocabModal && (
        <div className="vocab-modal-overlay" onClick={() => { setShowVocabModal(false); setVocabDef(''); }}>
          <div className="vocab-modal" onClick={e => e.stopPropagation()}>
            <h4>Add to Vocabulary</h4>
            <label className="vocab-label">Word</label>
            <input className="vocab-input" value={vocabWord} onChange={e => setVocabWord(e.target.value)} />
            <label className="vocab-label">
              Definition
              {vocabDefLoading && <span className="vocab-loading-hint"> · Looking up…</span>}
            </label>
            <textarea
              className="vocab-textarea"
              placeholder={vocabDefLoading ? 'Looking up definition…' : 'Edit or enter a definition…'}
              value={vocabDef}
              onChange={e => setVocabDef(e.target.value)}
              rows={3}
              autoFocus={!vocabDefLoading}
            />
            {vocabDuplicate && <p className="vocab-duplicate-msg">This word is already in your deck</p>}
            <div className="vocab-modal-actions">
              <button className="btn btn-secondary" onClick={() => { setShowVocabModal(false); setVocabDef(''); setVocabDuplicate(false); }}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSaveVocab} disabled={vocabSaving || vocabDefLoading || !vocabDef.trim()}>
                {vocabSaving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Vocab saved toast */}
      {vocabSaved && <div className="vocab-toast">✓ Added to vocabulary!</div>}

      {/* Passage */}
      <div className="exercise-passage">
        <div className="passage-meta">
          <h3>{exercise.meta.topic}</h3>
          <span className="passage-badge">
            <Sparkles size={12} /> AI · {exercise.meta.word_count} words · Band {exercise.meta.target_band}
          </span>
        </div>
        {paragraphs.map((para, i) => <p key={i} className="passage-para">{para}</p>)}
      </div>

      {/* Questions panel */}
      <div className="exercise-questions">

        {/* Section 1: T/F/NG */}
        <div className="question-section">
          <h4 className="section-title">Section 1 — True / False / Not Given</h4>
          {tfngQuestions.map(q => {
            const key = `tfng_${q.question_number}`;
            const userAns = userAnswers[key];
            const correct = tfngCorrect(q.question_number);
            return (
              <div key={q.question_number} className={`tfng-row ${submitted ? (userAns === correct ? 'row-correct' : 'row-wrong') : ''}`}>
                <div className="tfng-statement">
                  <span className="q-num">{q.question_number}.</span>
                  <span>{q.statement}</span>
                </div>
                <div className="tfng-btns">
                  {(['TRUE', 'FALSE', 'NOT GIVEN'] as const).map(opt => (
                    <button
                      key={opt}
                      className={`tfng-btn ${userAns === opt ? 'selected' : ''} ${
                        submitted ? (opt === correct ? 'btn-correct' : userAns === opt ? 'btn-wrong' : '') : ''
                      }`}
                      onClick={() => setAnswer(key, opt)}
                      disabled={submitted}
                    >
                      {opt === 'NOT GIVEN' ? 'NG' : opt.charAt(0)}
                    </button>
                  ))}
                </div>
                {submitted && userAns !== correct && (
                  <span className="inline-hint">→ {correct}</span>
                )}
                {submitted && userAns !== correct && (
                  explanations[key]
                    ? <p className="answer-explanation">{explanations[key]}</p>
                    : explanationsLoading
                      ? <p className="explanation-loading">Explaining…</p>
                      : null
                )}
              </div>
            );
          })}
        </div>

        {/* Section 2: MCQ or Matching */}
        <div className="question-section">
          <h4 className="section-title">
            Section 2 — {isMCQ ? 'Multiple Choice' : 'Matching Headings'}
          </h4>

          {isMCQ && mcqItems.map((item, idx) => {
            const key = `mc_${idx}`;
            const userAns = userAnswers[key];
            const correct = submitted ? mcqCorrect(item.question_number) : undefined;
            const opts = item.options ?? {};
            return (
              <div key={idx} className="mcq-question">
                <p className="q-text">
                  <span className="q-num">{item.question_number}.</span> {item.question}
                </p>
                <div className="options">
                  {Object.entries(opts).map(([letter, text]) => (
                    <button
                      key={letter}
                      className={`option ${userAns === letter ? 'selected' : ''} ${
                        submitted ? (letter === correct ? 'correct' : userAns === letter ? 'incorrect' : '') : ''
                      }`}
                      onClick={() => setAnswer(key, letter)}
                      disabled={submitted}
                    >
                      <span className="option-letter">{letter}</span>
                      <span className="option-text">{text}</span>
                      {submitted && letter === correct && <Check size={14} className="result-icon correct" />}
                      {submitted && userAns === letter && letter !== correct && <X size={14} className="result-icon incorrect" />}
                    </button>
                  ))}
                </div>
                {submitted && userAns !== correct && (
                  explanations[key]
                    ? <p className="answer-explanation">{explanations[key]}</p>
                    : explanationsLoading
                      ? <p className="explanation-loading">Explaining…</p>
                      : null
                )}
              </div>
            );
          })}

          {!isMCQ && matchingData && (
            <div className="matching-section">
              <div className="headings-bank">
                <h5>Headings Bank</h5>
                {(matchingData.headings ?? []).map(h => (
                  <div key={h.id} className="heading-entry">
                    <strong>{h.id}.</strong> {h.text}
                  </div>
                ))}
              </div>
              {(matchingData.paragraphs ?? []).map(para => {
                const key = `mh_${para.number}`;
                const userAns = userAnswers[key];
                const correct = submitted ? matchingCorrect(para.number) : undefined;
                return (
                  <div key={para.number} className={`match-row ${submitted ? (userAns === correct ? 'row-correct' : 'row-wrong') : ''}`}>
                    <span className="para-label">Paragraph {para.number}: <em>{para.title}</em></span>
                    <select
                      value={userAns ?? ''}
                      onChange={e => setAnswer(key, e.target.value)}
                      disabled={submitted}
                      className={submitted ? (userAns === correct ? 'select-correct' : 'select-wrong') : ''}
                    >
                      <option value="">Select…</option>
                      {(matchingData.headings ?? []).map(h => (
                        <option key={h.id} value={h.id}>{h.id}</option>
                      ))}
                    </select>
                    {submitted && userAns !== correct && (
                      <span className="inline-hint">→ {correct}</span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Submit / Finish */}
        <div className="question-actions">
          {!submitted ? (
            <button className="btn btn-primary" onClick={handleSubmit} disabled={!allAnswered()}>
              Submit Answers
            </button>
          ) : (
            <div className="ai-result-summary">
              <div className="ai-score">
                <span className="score-big">{score?.correct}/{score?.total}</span>
                <span className="score-sub">correct</span>
              </div>
              <button className="btn btn-primary" onClick={() => onComplete(score!.correct, score!.total)}>
                Finish
              </button>
            </div>
          )}
        </div>
      </div>

      <style>{`
        .ai-exercise-view { display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-lg); align-items: start; }
        @media (max-width: 1024px) { .ai-exercise-view { grid-template-columns: 1fr; } }
        .passage-meta { margin-bottom: var(--spacing-md); }
        .passage-meta h3 { margin-bottom: var(--spacing-xs); }
        .passage-badge { display: inline-flex; align-items: center; gap: 4px; background: rgba(79,70,229,0.1); color: var(--color-primary); padding: 2px 8px; border-radius: var(--radius-full); font-size: 0.75rem; }
        .passage-para { line-height: 1.8; margin-bottom: var(--spacing-md); color: var(--color-text-primary); }
        .exercise-questions { display: flex; flex-direction: column; gap: var(--spacing-lg); }
        .question-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); }
        .section-title { font-size: 0.8rem; font-weight: 700; color: var(--color-primary); margin-bottom: var(--spacing-md); text-transform: uppercase; letter-spacing: 0.06em; }
        .tfng-row { margin-bottom: var(--spacing-md); padding: var(--spacing-sm); border-radius: var(--radius-md); }
        .tfng-row.row-correct { background: rgba(16,185,129,0.08); }
        .tfng-row.row-wrong { background: rgba(239,68,68,0.08); }
        .tfng-statement { display: flex; gap: var(--spacing-sm); margin-bottom: var(--spacing-sm); font-size: 0.9rem; line-height: 1.5; }
        .tfng-btns { display: flex; gap: var(--spacing-xs); align-items: center; }
        .tfng-btn { padding: 4px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-background); cursor: pointer; font-size: 0.8rem; font-weight: 700; transition: all var(--transition-fast); }
        .tfng-btn:hover:not(:disabled) { border-color: var(--color-primary); color: var(--color-primary); }
        .tfng-btn.selected { background: var(--color-primary); color: white !important; border-color: var(--color-primary); }
        .tfng-btn.btn-correct { background: var(--color-success) !important; color: white !important; border-color: var(--color-success) !important; }
        .tfng-btn.btn-wrong { background: var(--color-error) !important; color: white !important; border-color: var(--color-error) !important; }
        .inline-hint { font-size: 0.8rem; color: var(--color-success); font-weight: 700; margin-left: var(--spacing-sm); }
        .q-num { font-weight: 700; color: var(--color-primary); min-width: 1.5rem; flex-shrink: 0; }
        .mcq-question { margin-bottom: var(--spacing-lg); }
        .q-text { font-size: 0.95rem; margin-bottom: var(--spacing-sm); display: flex; gap: var(--spacing-xs); line-height: 1.5; }
        .headings-bank { background: var(--color-background); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--spacing-md); margin-bottom: var(--spacing-md); }
        .headings-bank h5 { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-secondary); margin-bottom: var(--spacing-sm); }
        .heading-entry { font-size: 0.875rem; padding: 4px 0; border-bottom: 1px solid var(--color-border); }
        .heading-entry:last-child { border-bottom: none; }
        .match-row { display: flex; align-items: center; gap: var(--spacing-md); padding: var(--spacing-sm); border-radius: var(--radius-md); margin-bottom: var(--spacing-sm); flex-wrap: wrap; }
        .match-row.row-correct { background: rgba(16,185,129,0.08); }
        .match-row.row-wrong { background: rgba(239,68,68,0.08); }
        .para-label { flex: 1; font-size: 0.875rem; min-width: 150px; }
        .para-label em { color: var(--color-text-secondary); }
        select { padding: 6px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text-primary); font-size: 0.875rem; }
        select.select-correct { border-color: var(--color-success); background: rgba(16,185,129,0.08); }
        select.select-wrong { border-color: var(--color-error); background: rgba(239,68,68,0.08); }
        .ai-result-summary { display: flex; align-items: center; gap: var(--spacing-lg); }
        .ai-score { display: flex; flex-direction: column; }
        .score-big { font-size: 2rem; font-weight: 700; color: var(--color-primary); line-height: 1; }
        .score-sub { font-size: 0.75rem; color: var(--color-text-secondary); }
        .answer-explanation { font-size: 0.8rem; color: var(--color-text-secondary); font-style: italic; margin-top: var(--spacing-xs); line-height: 1.5; border-left: 2px solid var(--color-primary); padding-left: var(--spacing-sm); }
        .explanation-loading { font-size: 0.75rem; color: var(--color-text-secondary); font-style: italic; margin-top: var(--spacing-xs); opacity: 0.7; }
        .vocab-popup { position: fixed; transform: translateX(-50%); background: var(--color-primary); color: white; padding: 5px 12px; border-radius: var(--radius-full); font-size: 0.75rem; font-weight: 600; cursor: pointer; z-index: 1000; white-space: nowrap; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
        .vocab-popup:hover { background: #4338ca; }
        .vocab-modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 1001; display: flex; align-items: center; justify-content: center; }
        .vocab-modal { background: var(--color-surface); border-radius: var(--radius-lg); padding: var(--spacing-lg); width: min(400px, 90vw); box-shadow: 0 8px 32px rgba(0,0,0,0.15); }
        .vocab-modal h4 { margin-bottom: var(--spacing-md); font-size: 1rem; }
        .vocab-label { display: block; font-size: 0.8rem; font-weight: 600; color: var(--color-text-secondary); margin-bottom: 4px; margin-top: var(--spacing-sm); }
        .vocab-required { color: var(--color-error); }
        .vocab-input { width: 100%; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-background); color: var(--color-text-primary); font-size: 0.9rem; box-sizing: border-box; }
        .vocab-textarea { width: 100%; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-background); color: var(--color-text-primary); font-size: 0.9rem; resize: vertical; box-sizing: border-box; font-family: inherit; }
        .vocab-duplicate-msg { font-size: 0.8rem; color: var(--color-error); margin: var(--spacing-xs) 0 0; }
        .vocab-modal-actions { display: flex; justify-content: flex-end; gap: var(--spacing-sm); margin-top: var(--spacing-md); }
        .vocab-loading-hint { color: var(--color-text-secondary); font-weight: 400; font-style: italic; }
        .vocab-toast { position: fixed; bottom: 24px; right: 24px; background: var(--color-success); color: white; padding: 10px 18px; border-radius: var(--radius-md); font-size: 0.875rem; font-weight: 600; z-index: 1002; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }
      `}</style>
    </div>
  );
}

// ─── AI Listening Exercise View ──────────────────────────────────────────────

function AIListeningExerciseView({
  exercise,
  onComplete,
}: {
  exercise: AIListeningPractice;
  onComplete: (correct: number, total: number) => void;
}) {
  const { t } = useTranslation();
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [submitted, setSubmitted] = useState(false);
  const [startTime] = useState(Date.now());

  // Answer state: keyed by "comp_0", "mc_0", etc.
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const completionQs = exercise.questions.completion ?? [];
  const mcqQs = exercise.questions.multiple_choice ?? [];
  const totalQuestions = completionQs.length + mcqQs.length;

  // Audio URL — prepend VPS base if it's a relative path
  const audioUrl = exercise.meta.audio_url?.startsWith('http')
    ? exercise.meta.audio_url
    : exercise.meta.audio_url; // relative URL served by nginx

  // Audio controls
  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) { audio.pause(); } else { audio.play(); }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) setCurrentTime(audioRef.current.currentTime);
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) setDuration(audioRef.current.duration);
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (audioRef.current) { audioRef.current.currentTime = time; setCurrentTime(time); }
  };

  const changeSpeed = () => {
    const speeds = [0.75, 1, 1.25];
    const next = speeds[(speeds.indexOf(playbackRate) + 1) % speeds.length];
    setPlaybackRate(next);
    if (audioRef.current) audioRef.current.playbackRate = next;
  };

  const replay = () => {
    if (audioRef.current) { audioRef.current.currentTime = 0; audioRef.current.play(); }
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const setAnswer = (key: string, value: string) => {
    setAnswers(prev => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async () => {
    let correct = 0;

    // Score completion questions
    completionQs.forEach((q, i) => {
      const userAns = (answers[`comp_${i}`] ?? '').trim().toLowerCase();
      const correctAns = q.answer.trim().toLowerCase();
      if (userAns === correctAns) correct++;
    });

    // Score MCQ questions
    mcqQs.forEach((q, i) => {
      const userAns = (answers[`mc_${i}`] ?? '').trim().toUpperCase();
      if (userAns === q.answer) correct++;
    });

    setSubmitted(true);

    // Submit to backend
    if (exercise.practice_db_id) {
      const score = Math.round((3.5 + (correct / totalQuestions) * 4.5) * 2) / 2;
      practiceAPI.submitAIListening(
        exercise.practice_db_id,
        JSON.stringify(answers),
        score,
        correct,
        totalQuestions,
      ).catch(() => {});

      const studyMinutes = Math.max(1, Math.round((Date.now() - startTime) / 60000));
      progressAPI.updateProgress({
        skill: 'listening',
        correct_answers: correct,
        total_questions: totalQuestions,
        study_time_minutes: studyMinutes,
        band_score: score,
      }).catch(() => {});
      progressAPI.createSession({ skill: 'listening', duration_minutes: studyMinutes }).catch(() => {});
    }

    // Log wrong answers to Mistakes
    completionQs.forEach((q, i) => {
      const userAns = (answers[`comp_${i}`] ?? '').trim();
      if (userAns.toLowerCase() !== q.answer.trim().toLowerCase()) {
        mistakesAPI.create({
          skill: 'listening',
          question: q.text,
          user_answer: userAns || '(unanswered)',
          correct_answer: q.answer,
          mistake_type: 'completion',
        }).catch(() => {});
      }
    });
    mcqQs.forEach((q, i) => {
      const userAns = (answers[`mc_${i}`] ?? '').trim().toUpperCase();
      if (userAns !== q.answer) {
        mistakesAPI.create({
          skill: 'listening',
          question: q.question,
          user_answer: userAns || '(unanswered)',
          correct_answer: q.answer,
          mistake_type: 'multiple_choice',
        }).catch(() => {});
      }
    });

    onComplete(correct, totalQuestions);
  };

  // Merge all questions into a single list sorted by question_number for display
  const allQuestions = [
    ...completionQs.map((q, i) => ({ type: 'completion' as const, q, idx: i, num: q.question_number })),
    ...mcqQs.map((q, i) => ({ type: 'mcq' as const, q, idx: i, num: q.question_number })),
  ].sort((a, b) => a.num - b.num);

  return (
    <div className="ai-listening-view">
      {/* Audio Player */}
      <div className="audio-player">
        <audio
          ref={audioRef}
          src={audioUrl}
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={() => setIsPlaying(false)}
        />
        <div className="player-controls">
          <button className="player-btn" onClick={togglePlay} title={isPlaying ? 'Pause' : 'Play'}>
            {isPlaying ? <Pause size={20} /> : <Play size={20} />}
          </button>
          <span className="player-time">{formatTime(currentTime)}</span>
          <input
            className="player-progress"
            type="range"
            min={0}
            max={duration || 0}
            step={0.1}
            value={currentTime}
            onChange={handleSeek}
          />
          <span className="player-time">{formatTime(duration)}</span>
          <button className="player-btn speed-btn" onClick={changeSpeed} title="Change speed">
            {playbackRate}x
          </button>
          <button className="player-btn" onClick={replay} title="Replay from start">
            <RotateCcw size={16} />
          </button>
        </div>
        <div className="player-info">
          <span className="format-badge">{exercise.meta.format}</span>
          <span className="topic-label">{exercise.meta.topic}</span>
        </div>
      </div>

      {/* Questions */}
      <div className="listening-questions">
        <h3>Questions (1–{totalQuestions})</h3>
        {allQuestions.map(item => {
          if (item.type === 'completion') {
            const q = item.q;
            const key = `comp_${item.idx}`;
            const userAns = (answers[key] ?? '').trim().toLowerCase();
            const correctAns = q.answer.trim().toLowerCase();
            const isCorrect = submitted && userAns === correctAns;
            const isWrong = submitted && userAns !== correctAns;
            return (
              <div key={key} className={`question-block ${isCorrect ? 'q-correct' : ''} ${isWrong ? 'q-wrong' : ''}`}>
                <div className="q-number">{q.question_number}</div>
                <div className="q-body">
                  <p className="q-text">{q.text}</p>
                  <input
                    className={`completion-input ${isCorrect ? 'input-correct' : ''} ${isWrong ? 'input-wrong' : ''}`}
                    type="text"
                    placeholder="Type your answer…"
                    value={answers[key] ?? ''}
                    onChange={e => setAnswer(key, e.target.value)}
                    disabled={submitted}
                  />
                  {isWrong && <span className="correct-label">Correct: {q.answer}</span>}
                </div>
                {submitted && (isCorrect
                  ? <Check size={18} className="q-icon correct" />
                  : <X size={18} className="q-icon incorrect" />)}
              </div>
            );
          } else {
            const q = item.q;
            const key = `mc_${item.idx}`;
            const userAns = (answers[key] ?? '').trim().toUpperCase();
            const optionKeys = Object.keys(q.options);
            return (
              <div key={key} className={`question-block ${submitted && userAns === q.answer ? 'q-correct' : ''} ${submitted && userAns !== q.answer ? 'q-wrong' : ''}`}>
                <div className="q-number">{q.question_number}</div>
                <div className="q-body">
                  <p className="q-text">{q.question}</p>
                  <div className="mcq-options">
                    {optionKeys.map(letter => {
                      const selected = userAns === letter;
                      const isCorrectOption = submitted && letter === q.answer;
                      const isWrongSelection = submitted && selected && letter !== q.answer;
                      return (
                        <button
                          key={letter}
                          className={`option ${selected && !submitted ? 'selected' : ''} ${isCorrectOption ? 'correct' : ''} ${isWrongSelection ? 'incorrect' : ''}`}
                          onClick={() => !submitted && setAnswer(key, letter)}
                          disabled={submitted}
                        >
                          <span className="option-letter">{letter}</span>
                          <span className="option-text">{q.options[letter]}</span>
                          {isCorrectOption && <Check size={16} className="result-icon correct" />}
                          {isWrongSelection && <X size={16} className="result-icon incorrect" />}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          }
        })}

        {!submitted && (
          <div className="submit-row">
            <button className="btn btn-primary" onClick={handleSubmit}>
              {t('practice.submit')}
            </button>
          </div>
        )}
      </div>

      <style>{`
        .ai-listening-view { max-width: 800px; margin: 0 auto; }
        .audio-player { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); margin-bottom: var(--spacing-lg); }
        .player-controls { display: flex; align-items: center; gap: var(--spacing-sm); }
        .player-btn { background: none; border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; color: var(--color-text-primary); transition: all var(--transition-fast); }
        .player-btn:hover { border-color: var(--color-primary); color: var(--color-primary); }
        .speed-btn { font-size: 0.75rem; font-weight: 700; min-width: 40px; padding: 6px 8px; }
        .player-time { font-size: 0.75rem; color: var(--color-text-secondary); font-variant-numeric: tabular-nums; min-width: 36px; text-align: center; }
        .player-progress { flex: 1; height: 4px; accent-color: var(--color-primary); cursor: pointer; }
        .player-info { display: flex; align-items: center; gap: var(--spacing-sm); margin-top: var(--spacing-sm); }
        .format-badge { background: rgba(16,185,129,0.12); color: #10B981; padding: 2px 8px; border-radius: var(--radius-full); font-size: 0.7rem; font-weight: 700; text-transform: capitalize; }
        .topic-label { font-size: 0.85rem; color: var(--color-text-secondary); }

        .listening-questions { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); }
        .listening-questions h3 { margin-bottom: var(--spacing-md); font-size: 1rem; }
        .question-block { display: flex; align-items: flex-start; gap: var(--spacing-sm); padding: var(--spacing-md); border-radius: var(--radius-md); margin-bottom: var(--spacing-sm); border: 1px solid var(--color-border); background: var(--color-background); }
        .question-block.q-correct { border-color: var(--color-success); background: rgba(16,185,129,0.05); }
        .question-block.q-wrong { border-color: var(--color-error); background: rgba(239,68,68,0.05); }
        .q-number { width: 28px; height: 28px; border-radius: 50%; background: var(--color-primary); color: white; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; flex-shrink: 0; margin-top: 2px; }
        .q-body { flex: 1; min-width: 0; }
        .q-text { font-size: 0.9rem; color: var(--color-text-primary); margin-bottom: var(--spacing-sm); line-height: 1.5; }
        .q-icon { flex-shrink: 0; margin-top: 4px; }
        .q-icon.correct { color: var(--color-success); }
        .q-icon.incorrect { color: var(--color-error); }

        .completion-input { width: 100%; max-width: 300px; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text-primary); font-size: 0.875rem; }
        .completion-input:focus { outline: none; border-color: var(--color-primary); }
        .completion-input.input-correct { border-color: var(--color-success); background: rgba(16,185,129,0.08); }
        .completion-input.input-wrong { border-color: var(--color-error); background: rgba(239,68,68,0.08); }
        .completion-input:disabled { opacity: 0.8; cursor: default; }
        .correct-label { display: block; font-size: 0.8rem; color: var(--color-success); margin-top: 4px; font-weight: 600; }

        .mcq-options { display: flex; flex-direction: column; gap: var(--spacing-xs); }

        .submit-row { display: flex; justify-content: center; margin-top: var(--spacing-lg); }
      `}</style>
    </div>
  );
}

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

  const [writingTopics, setWritingTopics] = useState<WritingTopic[]>([]);
  const [speakingTopics, setSpeakingTopics] = useState<SpeakingTopic[]>([]);

  const [showResult, setShowResult] = useState(false);
  const [result, setResult] = useState<{ correct: number; total: number } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { loadExercises(); }, []);

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

  const loadExercises = async () => {
    setLoading(true);
    loadAIReadingExercises();
    loadAIListeningExercises();

    const [writing, speaking] = await Promise.allSettled([
      practiceAPI.getWriting(),
      practiceAPI.getSpeaking(),
    ]);

    if (writing.status === 'fulfilled') setWritingTopics(Array.isArray(writing.value.data) ? writing.value.data : []);
    if (speaking.status === 'fulfilled') setSpeakingTopics(Array.isArray(speaking.value.data) ? speaking.value.data : []);
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

  const handleComplete = (correct: number, total: number) => {
    setResult({ correct, total });
    setShowResult(true);
  };

  const handleBack = () => {
    setCurrentAIExercise(null);
    setCurrentAIListening(null);
    setShowResult(false);
    setResult(null);
    loadAIReadingExercises();
    loadAIListeningExercises();
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

  // Main list
  return (
    <div className="practice">
      <header className="page-header">
        <h1>{t('practice.title')}</h1>
      </header>

      {loading ? (
        <div className="loading"><div className="loading-spinner" /></div>
      ) : (
        <div className="practice-grid">

          {/* Reading — AI */}
          <div className="practice-section">
            <div className="section-header" style={{ borderColor: skillConfig[0].color }}>
              <BookOpen size={24} style={{ color: skillConfig[0].color }} />
              <h2>{t('practice.reading')}</h2>
              <span className="ai-chip"><Sparkles size={11} /> AI</span>
            </div>
            <div className="exercise-list">
              {readingLoading ? (
                <div className="generating-msg">
                  <div className="loading-spinner-sm" />
                  <span>Generating today's exercises…</span>
                </div>
              ) : aiReadingExercises.length === 0 ? (
                <p className="empty-list">No exercises yet — click Generate below.</p>
              ) : (
                aiReadingExercises.map((ex, i) => (
                  <button key={i} className="exercise-item" onClick={() => handleSelectAIExercise(ex)}>
                    <span className="exercise-title">{ex.meta.topic}</span>
                    <span className="exercise-meta">
                      {ex.meta.word_count}w · {
                        ex.questions.true_false_not_given.length +
                        (Array.isArray(ex.questions.second_type?.items) ? ex.questions.second_type.items.length : 3)
                      }q
                    </span>
                  </button>
                ))
              )}
              {aiReadingExercises.length < 3 && (
                poolEmpty ? (
                  <div className="pool-empty-msg">
                    <span>Next exercise generating in background (~2 min)</span>
                    <button className="retry-link" onClick={handleGenerateMore} disabled={generatingMore}>
                      {generatingMore ? 'Checking…' : 'Retry'}
                    </button>
                  </div>
                ) : (
                  <button
                    className="generate-more-btn"
                    onClick={handleGenerateMore}
                    disabled={generatingMore}
                  >
                    {generatingMore
                      ? <><div className="loading-spinner-sm" /> Checking pool…</>
                      : <><RefreshCw size={13} /> Generate More</>}
                  </button>
                )
              )}
            </div>
          </div>

          {/* Listening — AI */}
          <div className="practice-section">
            <div className="section-header" style={{ borderColor: skillConfig[1].color }}>
              <Headphones size={24} style={{ color: skillConfig[1].color }} />
              <h2>{t('practice.listening')}</h2>
              <span className="ai-chip"><Sparkles size={11} /> AI</span>
            </div>
            <div className="exercise-list">
              {listeningLoading ? (
                <div className="generating-msg">
                  <div className="loading-spinner-sm" />
                  <span>Loading listening exercises…</span>
                </div>
              ) : aiListeningExercises.length === 0 ? (
                <p className="empty-list">No exercises yet — click Generate below.</p>
              ) : (
                aiListeningExercises.map((ex, i) => (
                  <button key={i} className="exercise-item" onClick={() => handleSelectAIListening(ex)}>
                    <span className="exercise-title">{ex.meta.topic}</span>
                    <span className="exercise-meta">
                      {ex.meta.format} · {(ex.questions.completion?.length ?? 0) + (ex.questions.multiple_choice?.length ?? 0)}q
                    </span>
                  </button>
                ))
              )}
              {aiListeningExercises.length < 3 && (
                listeningPoolEmpty ? (
                  <div className="pool-empty-msg">
                    <span>Next exercise generating in background (~3 min)</span>
                    <button className="retry-link" onClick={handleGenerateMoreListening} disabled={listeningGeneratingMore}>
                      {listeningGeneratingMore ? 'Checking…' : 'Retry'}
                    </button>
                  </div>
                ) : (
                  <button
                    className="generate-more-btn"
                    onClick={handleGenerateMoreListening}
                    disabled={listeningGeneratingMore}
                  >
                    {listeningGeneratingMore
                      ? <><div className="loading-spinner-sm" /> Checking pool…</>
                      : <><RefreshCw size={13} /> Generate More</>}
                  </button>
                )
              )}
            </div>
          </div>

          {/* Writing */}
          <div className="practice-section">
            <div className="section-header" style={{ borderColor: skillConfig[2].color }}>
              <Pen size={24} style={{ color: skillConfig[2].color }} />
              <h2>{t('practice.writing')}</h2>
            </div>
            <div className="exercise-list">
              {writingTopics.map(topic => (
                <button key={topic.id} className="exercise-item" onClick={() => alert(`Writing Topic:\n\n${topic.question}`)}>
                  <span className="exercise-title">{topic.type.toUpperCase()}</span>
                  <span className="exercise-meta">Click to view</span>
                </button>
              ))}
            </div>
          </div>

          {/* Speaking */}
          <div className="practice-section">
            <div className="section-header" style={{ borderColor: skillConfig[3].color }}>
              <MessageCircle size={24} style={{ color: skillConfig[3].color }} />
              <h2>{t('practice.speaking')}</h2>
            </div>
            <div className="exercise-list">
              {speakingTopics.map(topic => (
                <button key={topic.id} className="exercise-item" onClick={() => alert(`Speaking Topic (${topic.part}):\n\n${topic.question}`)}>
                  <span className="exercise-title">{topic.part.toUpperCase()}</span>
                  <span className="exercise-meta">Click to view</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

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
  .practice { max-width: 1200px; margin: 0 auto; }
  .page-header { margin-bottom: var(--spacing-lg); }
  .practice-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--spacing-lg); }
  @media (max-width: 1024px) { .practice-grid { grid-template-columns: 1fr; } }
  .practice-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); overflow: hidden; }
  .section-header { display: flex; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-md) var(--spacing-lg); border-bottom: 3px solid; background: var(--color-background); }
  .ai-chip { margin-left: auto; display: inline-flex; align-items: center; gap: 3px; background: rgba(79,70,229,0.12); color: var(--color-primary); padding: 2px 8px; border-radius: var(--radius-full); font-size: 0.7rem; font-weight: 700; }
  .exercise-list { padding: var(--spacing-md); display: flex; flex-direction: column; gap: var(--spacing-sm); }
  .exercise-item { display: flex; justify-content: space-between; align-items: center; padding: var(--spacing-md); background: var(--color-background); border: 1px solid var(--color-border); border-radius: var(--radius-md); cursor: pointer; transition: all var(--transition-fast); text-align: left; }
  .exercise-item:hover { border-color: var(--color-primary); transform: translateX(4px); }
  .exercise-title { font-weight: 500; color: var(--color-text-primary); }
  .exercise-meta { font-size: 0.75rem; color: var(--color-text-secondary); }
  .empty-list { font-size: 0.875rem; color: var(--color-text-secondary); text-align: center; padding: var(--spacing-md) 0; }
  .generating-msg { display: flex; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-sm) 0; font-size: 0.875rem; color: var(--color-text-secondary); }
  .generate-more-btn { display: flex; align-items: center; justify-content: center; gap: 6px; padding: var(--spacing-sm) var(--spacing-md); background: var(--color-background); border: 1px dashed var(--color-border); border-radius: var(--radius-md); cursor: pointer; font-size: 0.8rem; color: var(--color-text-secondary); transition: all var(--transition-fast); margin-top: 2px; }
  .generate-more-btn:hover:not(:disabled) { border-color: var(--color-primary); color: var(--color-primary); }
  .generate-more-btn:disabled { opacity: 0.6; cursor: not-allowed; }
  .pool-empty-msg { display: flex; align-items: center; justify-content: space-between; padding: var(--spacing-sm) var(--spacing-md); background: rgba(245,158,11,0.08); border: 1px dashed rgba(245,158,11,0.4); border-radius: var(--radius-md); font-size: 0.8rem; color: var(--color-text-secondary); gap: var(--spacing-sm); }
  .retry-link { background: none; border: none; color: var(--color-primary); font-size: 0.8rem; cursor: pointer; padding: 0; text-decoration: underline; }
  .retry-link:disabled { opacity: 0.6; cursor: not-allowed; }
  .loading { display: flex; justify-content: center; padding: var(--spacing-2xl); }
  .loading-spinner { width: 40px; height: 40px; border: 3px solid var(--color-border); border-top-color: var(--color-primary); border-radius: 50%; animation: spin 1s linear infinite; }
  .loading-spinner-sm { width: 14px; height: 14px; border: 2px solid var(--color-border); border-top-color: var(--color-primary); border-radius: 50%; animation: spin 1s linear infinite; flex-shrink: 0; }
  @keyframes spin { to { transform: rotate(360deg); } }
`;
