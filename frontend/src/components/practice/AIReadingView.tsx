import { useState } from 'react';
import { Check, X, Sparkles } from 'lucide-react';
import { practiceAPI, progressAPI, mistakesAPI } from '../../api';
import { completionMatch } from '../../utils/completionMatch';
import { useVocabSelection } from '../../hooks/useVocabSelection';
import type {
  AIReadingPractice, TFNGAnswerItem, MCQQuestionItem, MCQAnswerItem,
  MatchingHeadingData, MatchingAnswerItem, ReadingQuestionGroup,
} from '../../types';

function AIReadingExerciseView({
  exercise,
  onComplete,
}: {
  exercise: AIReadingPractice;
  onComplete: (correct: number, total: number) => void;
}) {
  const [userAnswers, setUserAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const [score, setScore] = useState<{ correct: number; total: number } | null>(null);
  const [startTime] = useState(Date.now());
  const [explanations, setExplanations] = useState<Record<string, string>>({});
  const [explanationsLoading, setExplanationsLoading] = useState(false);

  const vocab = useVocabSelection({ enabled: true, skill: 'reading' });
  const [viewTab, setViewTab] = useState<'passage' | 'questions'>('passage');

  // Detect format: new (groups) vs legacy (true_false_not_given + second_type)
  const isNewFormat = !!(exercise.questions.groups && exercise.questions.groups.length > 0);

  // Legacy format helpers
  const tfngQuestions = exercise.questions.true_false_not_given ?? [];
  const secondType = exercise.questions.second_type;
  const isMCQ = secondType?.type === 'multiple_choice';
  const mcqItems = isMCQ ? (secondType!.items as MCQQuestionItem[]) : [];
  const matchingData = (!isMCQ && secondType) ? (secondType.items as MatchingHeadingData) : null;

  const setAnswer = (key: string, value: string) => {
    if (!submitted) setUserAnswers(prev => ({ ...prev, [key]: value }));
  };

  // ── Collect all answer keys for new format ──
  const getNewFormatAnswerMap = (): Record<string, { answer: string; explanation?: string }> => {
    const map: Record<string, { answer: string; explanation?: string }> = {};
    if (!isNewFormat) return map;
    for (let gi = 0; gi < exercise.questions.groups!.length; gi++) {
      const group = exercise.questions.groups![gi];
      if (group.type === 'matching_headings') {
        for (const ans of (group.answers ?? [])) {
          map[`mh_${gi}_${ans.paragraph_number}`] = { answer: ans.answer, explanation: ans.explanation };
        }
      } else {
        for (const item of group.items) {
          map[`q_${gi}_${item.question_number}`] = { answer: item.answer, explanation: item.explanation };
        }
      }
    }
    return map;
  };

  const allAnswered = () => {
    if (isNewFormat) {
      const answerMap = getNewFormatAnswerMap();
      return Object.keys(answerMap).every(key => {
        const val = userAnswers[key];
        return val !== undefined && val !== '';
      });
    }
    // Legacy
    const tfngDone = tfngQuestions.every(q => userAnswers[`tfng_${q.question_number}`]);
    if (isMCQ) return tfngDone && mcqItems.every((_, idx) => userAnswers[`mc_${idx}`]);
    return tfngDone && (matchingData?.paragraphs ?? []).every(p => userAnswers[`mh_${p.number}`]);
  };

  const handleSubmit = () => {
    let correct = 0;
    let total = 0;
    type WrongEntry = { key: string; question_type: string; question: string; user_answer: string; correct_answer: string };
    const wrongAnswers: WrongEntry[] = [];

    if (isNewFormat) {
      // Score new format
      for (let gi = 0; gi < exercise.questions.groups!.length; gi++) {
        const group = exercise.questions.groups![gi];
        const gtype = group.type;

        if (gtype === 'matching_headings') {
          const answers = group.answers ?? [];
          for (const ans of answers) {
            total++;
            const key = `mh_${gi}_${ans.paragraph_number}`;
            const userAns = userAnswers[key] ?? '';
            if (userAns === ans.answer) {
              correct++;
            }
          }
        } else {
          for (const item of group.items) {
            total++;
            const key = `q_${gi}_${item.question_number}`;
            const userAns = userAnswers[key] ?? '';
            const correctAns = item.answer ?? '';

            if (gtype === 'true_false_not_given' || gtype === 'multiple_choice' || gtype === 'matching_information') {
              if (userAns === correctAns) {
                correct++;
              } else {
                const qText = item.statement || item.question || `Question ${item.question_number}`;
                wrongAnswers.push({ key, question_type: gtype, question: qText, user_answer: userAns || '(unanswered)', correct_answer: correctAns });
                mistakesAPI.create({
                  skill: 'reading', question: qText,
                  user_answer: userAns || '(unanswered)', correct_answer: correctAns,
                  mistake_type: gtype,
                }).catch(() => {});
              }
            } else {
              // Text input types: sentence_completion, summary_completion, short_answer
              if (completionMatch(userAns, correctAns)) {
                correct++;
              } else {
                const qText = item.text || item.question || `Question ${item.question_number}`;
                wrongAnswers.push({ key, question_type: gtype, question: qText, user_answer: userAns || '(unanswered)', correct_answer: correctAns });
                mistakesAPI.create({
                  skill: 'reading', question: qText,
                  user_answer: userAns || '(unanswered)', correct_answer: correctAns,
                  mistake_type: gtype,
                }).catch(() => {});
              }
            }
          }
        }
      }
    } else {
      // Score legacy format
      tfngQuestions.forEach(q => {
        total++;
        const key = `tfng_${q.question_number}`;
        const userAns = userAnswers[key];
        const correctAns = (exercise.answer_key!.true_false_not_given as TFNGAnswerItem[]).find(
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

      const secondAnswers = exercise.answer_key!.second_type_answers;
      if (isMCQ) {
        mcqItems.forEach((item, idx) => {
          total++;
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
          total++;
          const userAns = userAnswers[`mh_${para.number}`];
          const correctAns = (secondAnswers as MatchingAnswerItem[]).find(
            a => a.paragraph_number === para.number
          )?.answer;
          if (userAns === correctAns) correct++;
        });
      }
    }

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
    const studyMinutes = Math.max(1, Math.min(30, Math.round(timeTaken / 60)));
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

    // Fetch explanations for wrong answers (legacy only — new format has inline explanations)
    if (!isNewFormat && wrongAnswers.length > 0) {
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

  // Legacy helpers
  const tfngCorrect = (qNum: number) =>
    (exercise.answer_key?.true_false_not_given as TFNGAnswerItem[] | undefined)?.find(a => a.question_number === qNum)?.answer;
  const mcqCorrect = (qNum: number) =>
    (exercise.answer_key?.second_type_answers as MCQAnswerItem[] | undefined)?.find(a => a.question_number === qNum)?.answer;
  const matchingCorrect = (paraNum: number) =>
    (exercise.answer_key?.second_type_answers as MatchingAnswerItem[] | undefined)?.find(a => a.paragraph_number === paraNum)?.answer;

  const paragraphs = exercise.passage.split(/\n\n+/).filter(Boolean);

  // ── Render a question group (new format) ──
  const renderGroup = (group: ReadingQuestionGroup, groupIdx: number) => {
    const gtype = group.type;
    const label = gtype.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    const items = group.items ?? [];

    // Compute question number range for section header
    let qStart = 0, qEnd = 0;
    if (gtype === 'matching_headings') {
      const answers = group.answers ?? [];
      if (answers.length > 0) {
        qStart = answers[0].paragraph_number;
        qEnd = answers[answers.length - 1].paragraph_number;
      }
    } else if (items.length > 0) {
      qStart = items[0].question_number;
      qEnd = items[items.length - 1].question_number;
    }
    const rangeLabel = qStart === qEnd ? `Question ${qStart}` : `Questions ${qStart}–${qEnd}`;

    return (
      <div key={groupIdx} className="question-section">
        <h4 className="section-title">{rangeLabel}: {label}</h4>

        {gtype === 'true_false_not_given' && items.map((item: any) => {
          const key = `q_${groupIdx}_${item.question_number}`;
          const userAns = userAnswers[key];
          const correctAns = item.answer;
          const isCorrect = userAns === correctAns;
          return (
            <div key={item.question_number} className={`tfng-row ${submitted ? (isCorrect ? 'row-correct' : 'row-wrong') : ''}`}>
              <div className="tfng-statement">
                <span className="q-num">{item.question_number}.</span>
                <span>{item.statement}</span>
              </div>
              <div className="tfng-btns">
                {(['TRUE', 'FALSE', 'NOT GIVEN'] as const).map(opt => (
                  <button
                    key={opt}
                    className={`tfng-btn ${userAns === opt ? 'selected' : ''} ${
                      submitted ? (opt === correctAns ? 'btn-correct' : userAns === opt ? 'btn-wrong' : '') : ''
                    }`}
                    onClick={() => setAnswer(key, opt)}
                    disabled={submitted}
                  >
                    {opt === 'NOT GIVEN' ? 'NG' : opt.charAt(0)}
                  </button>
                ))}
              </div>
              {submitted && !isCorrect && <span className="inline-hint">{'\u2192'} {correctAns}</span>}
              {submitted && !isCorrect && item.explanation && (
                <p className="answer-explanation">{item.explanation}</p>
              )}
            </div>
          );
        })}

        {gtype === 'multiple_choice' && items.map((item: any) => {
          const key = `q_${groupIdx}_${item.question_number}`;
          const userAns = userAnswers[key];
          const correctAns = item.answer;
          const opts = item.options ?? {};
          return (
            <div key={item.question_number} className="mcq-question">
              <p className="q-text">
                <span className="q-num">{item.question_number}.</span> {item.question}
              </p>
              <div className="options">
                {Object.entries(opts).map(([letter, text]) => (
                  <button
                    key={letter}
                    className={`option ${userAns === letter ? 'selected' : ''} ${
                      submitted ? (letter === correctAns ? 'correct' : userAns === letter ? 'incorrect' : '') : ''
                    }`}
                    onClick={() => setAnswer(key, letter)}
                    disabled={submitted}
                  >
                    <span className="option-letter">{letter}</span>
                    <span className="option-text">{text as string}</span>
                    {submitted && letter === correctAns && <Check size={14} className="result-icon correct" />}
                    {submitted && userAns === letter && letter !== correctAns && <X size={14} className="result-icon incorrect" />}
                  </button>
                ))}
              </div>
              {submitted && userAns !== correctAns && item.explanation && (
                <p className="answer-explanation">{item.explanation}</p>
              )}
            </div>
          );
        })}

        {gtype === 'matching_headings' && (() => {
          const headingsData = items as any;
          const headings = headingsData.headings ?? [];
          const paras = headingsData.paragraphs ?? [];
          const answers = group.answers ?? [];
          return (
            <div className="matching-section">
              <div className="headings-bank">
                <h5>Headings Bank</h5>
                {headings.map((h: any) => (
                  <div key={h.id} className="heading-entry">
                    <strong>{h.id}.</strong> {h.text}
                  </div>
                ))}
              </div>
              {paras.map((para: any) => {
                const key = `mh_${groupIdx}_${para.number}`;
                const userAns = userAnswers[key] ?? '';
                const correctAns = answers.find((a: any) => a.paragraph_number === para.number)?.answer;
                const explanation = answers.find((a: any) => a.paragraph_number === para.number)?.explanation;
                return (
                  <div key={para.number} className={`match-row ${submitted ? (userAns === correctAns ? 'row-correct' : 'row-wrong') : ''}`}>
                    <span className="para-label">Paragraph {para.number}: <em>{para.title}</em></span>
                    <select
                      value={userAns}
                      onChange={e => setAnswer(key, e.target.value)}
                      disabled={submitted}
                      className={submitted ? (userAns === correctAns ? 'select-correct' : 'select-wrong') : ''}
                    >
                      <option value="">Select...</option>
                      {headings.map((h: any) => (
                        <option key={h.id} value={h.id}>{h.id}</option>
                      ))}
                    </select>
                    {submitted && userAns !== correctAns && <span className="inline-hint">{'\u2192'} {correctAns}</span>}
                    {submitted && userAns !== correctAns && explanation && (
                      <p className="answer-explanation">{explanation}</p>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })()}

        {gtype === 'matching_information' && items.map((item: any) => {
          const key = `q_${groupIdx}_${item.question_number}`;
          const userAns = userAnswers[key] ?? '';
          const correctAns = item.answer;
          const paraLabels = paragraphs.map((_, i) => String.fromCharCode(65 + i));
          return (
            <div key={item.question_number} className={`match-row ${submitted ? (userAns === correctAns ? 'row-correct' : 'row-wrong') : ''}`}>
              <span className="para-label"><span className="q-num">{item.question_number}.</span> {item.statement}</span>
              <select
                value={userAns}
                onChange={e => setAnswer(key, e.target.value)}
                disabled={submitted}
                className={submitted ? (userAns === correctAns ? 'select-correct' : 'select-wrong') : ''}
              >
                <option value="">Select...</option>
                {paraLabels.map(l => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
              {submitted && userAns !== correctAns && <span className="inline-hint">{'\u2192'} {correctAns}</span>}
              {submitted && userAns !== correctAns && item.explanation && (
                <p className="answer-explanation">{item.explanation}</p>
              )}
            </div>
          );
        })}

        {gtype === 'sentence_completion' && items.map((item: any) => {
          const key = `q_${groupIdx}_${item.question_number}`;
          const userAns = userAnswers[key] ?? '';
          const correctAns = item.answer;
          const isCorrect = submitted && completionMatch(userAns, correctAns);
          const parts = (item.text ?? '').split('___');
          return (
            <div key={item.question_number} className={`completion-row ${submitted ? (isCorrect ? 'row-correct' : 'row-wrong') : ''}`}>
              <div className="completion-sentence">
                <span className="q-num">{item.question_number}.</span>
                <span>
                  {parts[0]}
                  <input
                    type="text"
                    className={`completion-input ${submitted ? (isCorrect ? 'input-correct' : 'input-wrong') : ''}`}
                    value={userAns}
                    onChange={e => setAnswer(key, e.target.value)}
                    disabled={submitted}
                    placeholder={item.word_limit ? `(${item.word_limit} words max)` : '___'}
                  />
                  {parts[1] ?? ''}
                </span>
              </div>
              {submitted && !isCorrect && <span className="inline-hint">{'\u2192'} {correctAns}</span>}
              {submitted && !isCorrect && item.explanation && (
                <p className="answer-explanation">{item.explanation}</p>
              )}
            </div>
          );
        })}

        {gtype === 'summary_completion' && (() => {
          const summaryText = group.summary_text ?? '';
          return (
            <div className="summary-block">
              <div className="summary-text">
                {summaryText.split(/(___\d+___)/).map((segment, si) => {
                  const blankMatch = segment.match(/___(\d+)___/);
                  if (blankMatch) {
                    const qn = parseInt(blankMatch[1]);
                    const item = items.find((it: any) => it.question_number === qn);
                    const key = `q_${groupIdx}_${qn}`;
                    const userAns = userAnswers[key] ?? '';
                    const correctAns = item?.answer ?? '';
                    const isCorrect = submitted && completionMatch(userAns, correctAns);
                    return (
                      <React.Fragment key={si}>
                        <input
                          type="text"
                          className={`completion-input inline-blank ${submitted ? (isCorrect ? 'input-correct' : 'input-wrong') : ''}`}
                          value={userAns}
                          onChange={e => setAnswer(key, e.target.value)}
                          disabled={submitted}
                          placeholder={`(${qn})`}
                        />
                        {submitted && !isCorrect && <span className="inline-hint">{'\u2192'} {correctAns}</span>}
                      </React.Fragment>
                    );
                  }
                  return <span key={si}>{segment}</span>;
                })}
              </div>
              {submitted && items.map((item: any) => {
                const key = `q_${groupIdx}_${item.question_number}`;
                const userAns = userAnswers[key] ?? '';
                const isCorrect = completionMatch(userAns, item.answer);
                return !isCorrect && item.explanation ? (
                  <p key={item.question_number} className="answer-explanation">Q{item.question_number}: {item.explanation}</p>
                ) : null;
              })}
            </div>
          );
        })()}

        {gtype === 'short_answer' && items.map((item: any) => {
          const key = `q_${groupIdx}_${item.question_number}`;
          const userAns = userAnswers[key] ?? '';
          const correctAns = item.answer;
          const isCorrect = submitted && completionMatch(userAns, correctAns);
          return (
            <div key={item.question_number} className={`completion-row ${submitted ? (isCorrect ? 'row-correct' : 'row-wrong') : ''}`}>
              <div className="completion-sentence">
                <span className="q-num">{item.question_number}.</span>
                <span>{item.question}</span>
              </div>
              <input
                type="text"
                className={`completion-input ${submitted ? (isCorrect ? 'input-correct' : 'input-wrong') : ''}`}
                value={userAns}
                onChange={e => setAnswer(key, e.target.value)}
                disabled={submitted}
                placeholder={item.word_limit ? `(${item.word_limit} words max)` : 'Type answer...'}
              />
              {submitted && !isCorrect && <span className="inline-hint">{'\u2192'} {correctAns}</span>}
              {submitted && !isCorrect && item.explanation && (
                <p className="answer-explanation">{item.explanation}</p>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="ai-exercise-view">
      {/* Floating "Add to Vocab" popup on text selection */}
      {vocab.popupPos && !vocab.showModal && (
        <div className="vocab-popup" style={{ left: vocab.popupPos.x, top: vocab.popupPos.y + 10 }}
          onMouseDown={e => { e.preventDefault(); vocab.openModal(vocab.word); }}
          onTouchEnd={e => { e.preventDefault(); vocab.openModal(vocab.word); }}>
          + Add to Vocab
        </div>
      )}

      {vocab.showModal && (
        <div className="vocab-modal-overlay" onClick={vocab.closeModal}>
          <div className="vocab-modal" onClick={e => e.stopPropagation()}>
            <h4>Add to Vocabulary</h4>
            <label className="vocab-label">Word</label>
            <input className="vocab-input" value={vocab.word} onChange={e => vocab.setWord(e.target.value)} />
            <label className="vocab-label">Definition{vocab.defLoading && <span className="vocab-loading-hint"> · Looking up...</span>}</label>
            <textarea className="vocab-textarea" placeholder={vocab.defLoading ? 'Looking up...' : 'Enter definition...'} value={vocab.def} onChange={e => vocab.setDef(e.target.value)} rows={3} />
            {vocab.duplicate && <p className="vocab-duplicate-msg">Already in your deck</p>}
            <div className="vocab-modal-actions">
              <button className="btn btn-secondary" onClick={vocab.closeModal}>Cancel</button>
              <button className="btn btn-primary" onClick={vocab.save} disabled={vocab.saving || vocab.defLoading || !vocab.def.trim()}>
                {vocab.saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {vocab.saved && <div className="vocab-toast">Added to vocabulary!</div>}

      {/* Passage / Questions tab toggle */}
      <div className="reading-tab-toggle">
        <button className={viewTab === 'passage' ? 'active' : ''} onClick={() => { setViewTab('passage'); window.scrollTo(0, 0); }}>Passage</button>
        <button className={viewTab === 'questions' ? 'active' : ''} onClick={() => { setViewTab('questions'); window.scrollTo(0, 0); }}>Questions</button>
      </div>

      {/* Passage */}
      {viewTab === 'passage' && (
        <div className="exercise-passage">
          <div className="passage-meta">
            <h3>{exercise.meta.topic}</h3>
            <span className="passage-badge">
              <Sparkles size={12} /> AI · {exercise.meta.word_count} words · Band {exercise.meta.target_band}
            </span>
          </div>
          {paragraphs.map((para, i) => <p key={i} className="passage-para">{para}</p>)}
        </div>
      )}

      {/* Questions panel */}
      {viewTab === 'questions' && <div className="exercise-questions">

        {isNewFormat ? (
          // New format: render each group
          exercise.questions.groups!.map((group, idx) => renderGroup(group, idx))
        ) : (
          // Legacy format: T/F/NG + MCQ or Matching
          <>
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
                      <span className="inline-hint">{'\u2192'} {correct}</span>
                    )}
                    {submitted && userAns !== correct && (
                      explanations[key]
                        ? <p className="answer-explanation">{explanations[key]}</p>
                        : explanationsLoading
                          ? <p className="explanation-loading">Explaining...</p>
                          : null
                    )}
                  </div>
                );
              })}
            </div>

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
                          ? <p className="explanation-loading">Explaining...</p>
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
                          <option value="">Select...</option>
                          {(matchingData.headings ?? []).map(h => (
                            <option key={h.id} value={h.id}>{h.id}</option>
                          ))}
                        </select>
                        {submitted && userAns !== correct && (
                          <span className="inline-hint">{'\u2192'} {correct}</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </>
        )}

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
      </div>}

      <style>{`
        .ai-exercise-view { display: flex; flex-direction: column; gap: var(--spacing-md); }
        .reading-tab-toggle { display: flex; background: var(--color-background); border-radius: 8px; padding: 3px; margin-bottom: var(--spacing-sm); position: sticky; top: 0; z-index: 5; }
        .reading-tab-toggle button { flex: 1; padding: 10px; border: none; background: transparent; border-radius: 6px; font-size: 0.9rem; font-weight: 600; cursor: pointer; color: var(--color-text-secondary); transition: all 0.2s; }
        .reading-tab-toggle button.active { background: var(--color-primary); color: white; box-shadow: 0 1px 3px rgba(79,70,229,0.3); }
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
        .completion-row { margin-bottom: var(--spacing-md); padding: var(--spacing-sm); border-radius: var(--radius-md); }
        .completion-row.row-correct { background: rgba(16,185,129,0.08); }
        .completion-row.row-wrong { background: rgba(239,68,68,0.08); }
        .completion-sentence { display: flex; gap: var(--spacing-sm); font-size: 0.9rem; line-height: 1.8; margin-bottom: var(--spacing-xs); flex-wrap: wrap; align-items: baseline; }
        .completion-input { padding: 4px 8px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-background); color: var(--color-text-primary); font-size: 0.875rem; width: 160px; font-family: inherit; }
        .completion-input.inline-blank { width: 120px; margin: 0 4px; display: inline; }
        .completion-input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 2px rgba(79,70,229,0.15); }
        .completion-input.input-correct { border-color: var(--color-success); background: rgba(16,185,129,0.08); }
        .completion-input.input-wrong { border-color: var(--color-error); background: rgba(239,68,68,0.08); }
        .summary-block { margin-bottom: var(--spacing-md); }
        .summary-text { font-size: 0.9rem; line-height: 2; color: var(--color-text-primary); }
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

export default AIReadingExerciseView;
