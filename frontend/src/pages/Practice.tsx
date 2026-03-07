import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { BookOpen, Headphones, Pen, MessageCircle, Check, X, Sparkles, RefreshCw, ChevronLeft } from 'lucide-react';
import { practiceAPI, progressAPI, mistakesAPI, topicsAPI } from '../api';
import { useAppStore } from '../store';
import type {
  SkillType, ListeningExercise, WritingTopic, SpeakingTopic,
  AIReadingPractice, TFNGAnswerItem, MCQQuestionItem, MCQAnswerItem,
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
        setVocabPopupPos({ x: rect.left + rect.width / 2, y: rect.bottom + window.scrollY });
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

// ─── Listening Exercise View ─────────────────────────────────────────────────

function ListeningExerciseView({
  exercise,
  onComplete,
}: {
  exercise: ListeningExercise;
  onComplete: (correct: number, total: number) => void;
}) {
  const { t } = useTranslation();
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [answers, setAnswers] = useState<{ question: string; userAnswer: string; correctAnswer: string }[]>([]);
  const [startTime] = useState(Date.now());

  const question = exercise.questions[currentQuestion];

  const handleAnswer = () => {
    if (selectedAnswer === null) return;
    const isCorrect = selectedAnswer === question.answer;
    setAnswers(prev => [...prev, {
      question: question.question,
      userAnswer: question.options[selectedAnswer],
      correctAnswer: question.options[question.answer],
    }]);
    setShowResult(true);
    if (!isCorrect) {
      mistakesAPI.create({
        skill: 'listening', question: question.question,
        user_answer: question.options[selectedAnswer],
        correct_answer: question.options[question.answer],
        mistake_type: 'listening_comprehension',
      }).catch(() => {});
    }
  };

  const handleNext = () => {
    if (currentQuestion < exercise.questions.length - 1) {
      setCurrentQuestion(q => q + 1);
      setSelectedAnswer(null);
      setShowResult(false);
    } else {
      const timeTaken = Math.round((Date.now() - startTime) / 1000);
      const correct = answers.filter(a => a.userAnswer === a.correctAnswer).length +
        (showResult && selectedAnswer === question.answer ? 1 : 0);
      const total = exercise.questions.length;
      practiceAPI.submit({
        skill: 'listening', exercise_id: exercise.id,
        score: (correct / total) * 100,
        total_questions: total, correct_answers: correct, time_taken_seconds: timeTaken,
      }).catch(() => {});
      progressAPI.updateProgress({ skill: 'listening', total_questions: total, correct_answers: correct }).catch(() => {});
      onComplete(correct, total);
    }
  };

  return (
    <div className="exercise-view">
      <div className="exercise-passage">
        <h3>{exercise.title}</h3>
        <p>{exercise.script}</p>
      </div>
      <div className="exercise-question">
        <div className="question-header">
          <span className="question-number">Question {currentQuestion + 1} of {exercise.questions.length}</span>
        </div>
        <p className="question-text">{question.question}</p>
        <div className="options">
          {question.options.map((option, index) => (
            <button
              key={index}
              className={`option ${selectedAnswer === index ? 'selected' : ''} ${
                showResult ? (index === question.answer ? 'correct' : selectedAnswer === index ? 'incorrect' : '') : ''
              }`}
              onClick={() => !showResult && setSelectedAnswer(index)}
              disabled={showResult}
            >
              <span className="option-letter">{String.fromCharCode(65 + index)}</span>
              <span className="option-text">{option}</span>
              {showResult && index === question.answer && <Check size={16} className="result-icon correct" />}
              {showResult && selectedAnswer === index && index !== question.answer && <X size={16} className="result-icon incorrect" />}
            </button>
          ))}
        </div>
        <div className="question-actions">
          {!showResult ? (
            <button className="btn btn-primary" onClick={handleAnswer} disabled={selectedAnswer === null}>
              {t('practice.submit')}
            </button>
          ) : (
            <button className="btn btn-primary" onClick={handleNext}>
              {currentQuestion < exercise.questions.length - 1 ? t('practice.next') : t('practice.finish')}
            </button>
          )}
        </div>
      </div>
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

  const [listeningExercises, setListeningExercises] = useState<ListeningExercise[]>([]);
  const [writingTopics, setWritingTopics] = useState<WritingTopic[]>([]);
  const [speakingTopics, setSpeakingTopics] = useState<SpeakingTopic[]>([]);
  const [currentExercise, setCurrentExercise] = useState<ListeningExercise | null>(null);

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

  const loadExercises = async () => {
    setLoading(true);
    loadAIReadingExercises();

    const [listening, writing, speaking] = await Promise.allSettled([
      practiceAPI.getListening(),
      practiceAPI.getWriting(),
      practiceAPI.getSpeaking(),
    ]);

    if (listening.status === 'fulfilled') setListeningExercises(Array.isArray(listening.value.data) ? listening.value.data : []);
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

  const handleComplete = (correct: number, total: number) => {
    setResult({ correct, total });
    setShowResult(true);
  };

  const handleBack = () => {
    setCurrentAIExercise(null);
    setCurrentExercise(null);
    setShowResult(false);
    setResult(null);
    loadAIReadingExercises();
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

  // Listening exercise view
  if (currentExercise) {
    return (
      <div className="practice">
        <button className="back-btn" onClick={handleBack}><ChevronLeft size={16} /> Back</button>
        <ListeningExerciseView exercise={currentExercise} onComplete={handleComplete} />
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

          {/* Listening */}
          <div className="practice-section">
            <div className="section-header" style={{ borderColor: skillConfig[1].color }}>
              <Headphones size={24} style={{ color: skillConfig[1].color }} />
              <h2>{t('practice.listening')}</h2>
            </div>
            <div className="exercise-list">
              {listeningExercises.map(exercise => (
                <button key={exercise.id} className="exercise-item" onClick={() => setCurrentExercise(exercise)}>
                  <span className="exercise-title">{exercise.title}</span>
                  <span className="exercise-meta">{exercise.questions.length} questions</span>
                </button>
              ))}
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
