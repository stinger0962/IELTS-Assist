import React, { useState, useEffect } from 'react';
import { Check, X } from 'lucide-react';
import { practiceAPI, progressAPI, topicsAPI } from '../../api';
import { useAppStore } from '../../store';
import { parseDictionaryEntry } from '../../utils/dictionary';
import type { AIGrammarPractice } from '../../types';

function AIGrammarExerciseView({
  exercise,
  onComplete,
}: {
  exercise: AIGrammarPractice;
  onComplete: (correct: number, total: number) => void;
}) {
  const { language } = useAppStore();
  const [userAnswers, setUserAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const [score, setScore] = useState<{ correct: number; total: number } | null>(null);
  const [startTime] = useState(Date.now());

  // Vocab popup state (same pattern as reading)
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
  const [grammarTipZh, setGrammarTipZh] = useState('');

  const groups = exercise.questions?.groups ?? [];

  // Translate grammar tip for Chinese users
  useEffect(() => {
    if (language === 'zh' && exercise.grammar_tip) {
      topicsAPI.translateDefinition('grammar_tip', exercise.grammar_tip)
        .then(r => { if (r.data?.content_zh) setGrammarTipZh(r.data.content_zh); })
        .catch(() => {});
    }
  }, [language, exercise.grammar_tip]);

  // ── Vocab selection handlers ──
  const handleTextSelect = () => {
    const sel = window.getSelection();
    const text = sel?.toString().trim() ?? '';
    if (text.length >= 2 && text.length <= 60 && !text.includes('\n')) {
      try {
        const rect = sel!.getRangeAt(0).getBoundingClientRect();
        setVocabWord(text);
        setVocabPopupPos({ x: rect.left + rect.width / 2, y: rect.bottom });
      } catch { /* ignore */ }
    } else {
      setVocabPopupPos(null);
    }
  };

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const onSelChange = () => { clearTimeout(timer); timer = setTimeout(handleTextSelect, 200); };
    document.addEventListener('selectionchange', onSelChange);
    return () => { clearTimeout(timer); document.removeEventListener('selectionchange', onSelChange); };
  }, []);

  const openVocabModal = async (word: string) => {
    setVocabWord(word);
    setShowVocabModal(true);
    setVocabPopupPos(null);
    setVocabDef('');
    setVocabDefZh('');
    setVocabPhonetic('');
    setVocabAudioUrl('');
    setVocabDefLoading(true);
    setVocabDuplicate(false);
    setVocabSaved(false);
    try {
      const res = await fetch(`https://api.dictionaryapi.dev/api/v2/entries/en/${encodeURIComponent(word.toLowerCase())}`);
      if (res.ok) {
        const data = await res.json();
        setVocabDef(parseDictionaryEntry(data));
        const phonetics = data[0]?.phonetics ?? [];
        const ipa = phonetics.find((p: any) => p.text)?.text ?? '';
        const audio = phonetics.find((p: any) => p.audio)?.audio ?? '';
        setVocabPhonetic(ipa);
        setVocabAudioUrl(audio);
        if (language === 'zh') {
          const formatted = parseDictionaryEntry(data);
          const quotes: string[] = [];
          const tokenized = formatted.replace(/"([^"]*)"/g, (_: string, q: string) => {
            quotes.push(`"${q}"`);
            return `__Q${quotes.length - 1}__`;
          });
          topicsAPI.translateDefinition(word, tokenized)
            .then(r => {
              if (r.data?.content_zh) {
                const restored = r.data.content_zh.replace(/__Q(\d+)__/g, (_: string, i: string) => quotes[+i] ?? '');
                setVocabDefZh(restored);
              }
            })
            .catch(() => {});
        }
      }
    } catch { /* ignore */ }
    setVocabDefLoading(false);
  };

  const handleSaveVocab = async () => {
    if (!vocabDef.trim()) return;
    setVocabSaving(true);
    setVocabDuplicate(false);
    try {
      await topicsAPI.create({ title: vocabWord, content: vocabDef, content_zh: vocabDefZh || undefined, skill: 'grammar', category: 'vocabulary', phonetic: vocabPhonetic || undefined, audio_url: vocabAudioUrl || undefined });
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

  // ── Highlight grammar phrases in context ──
  const renderHighlightedContext = (text: string) => {
    const phrases = exercise.highlight_phrases ?? [];
    if (phrases.length === 0) return text;
    // Build a regex that matches any of the phrases (case-insensitive)
    const escaped = phrases.map(p => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    const regex = new RegExp(`(${escaped.join('|')})`, 'gi');
    const parts = text.split(regex);
    // Use a fresh regex per test to avoid stateful lastIndex issue with 'g' flag
    const matchRegex = new RegExp(`^(${escaped.join('|')})$`, 'i');
    return parts.map((part, i) =>
      matchRegex.test(part) ? <mark key={i} className="grammar-highlight">{part}</mark> : part
    );
  };

  // Normalize sentence for comparison: loose on punctuation (commas, semicolons, colons, periods)
  const normalizeSentence = (s: string) =>
    s.trim().toLowerCase()
      .replace(/[;:]/g, '.')   // treat ; and : as .
      .replace(/,/g, '')       // strip commas (Oxford comma, appositives)
      .replace(/[.!?]+$/, '')  // strip trailing sentence punctuation
      .replace(/\s+/g, ' ')   // collapse whitespace
      .trim();

  const handleSubmit = async () => {
    let correct = 0;
    let total = 0;

    for (const group of groups) {
      for (const item of group.items as any[]) {
        total++;
        const key = `${group.type}_${item.question_number}`;
        const userAns = (userAnswers[key] || '').trim();

        if (group.type === 'error_correction' || group.type === 'sentence_transformation' || group.type === 'sentence_combination') {
          // Compare full sentence — flexible: case-insensitive, loose punctuation
          if (normalizeSentence(userAns) === normalizeSentence(item.answer || '')) correct++;
        } else if (group.type === 'gap_fill' || group.type === 'context_completion') {
          // Compare answer word(s) — case-insensitive
          if (userAns.toLowerCase() === (item.answer || '').trim().toLowerCase()) correct++;
        } else if (group.type === 'grammar_mcq' || group.type === 'paraphrase_rewrite' || group.type === 'grammar_function_id') {
          if (userAns === item.answer) correct++;
        }
      }
    }

    setScore({ correct, total });
    setSubmitted(true);

    // Calculate band score and submit
    const accuracy = total > 0 ? correct / total : 0;
    const bandScore = Math.round((3.5 + accuracy * 4.5) * 2) / 2;
    const minutes = Math.min(30, Math.round((Date.now() - startTime) / 60000));

    if (exercise.practice_db_id) {
      try {
        await practiceAPI.submitAIGrammar(
          exercise.practice_db_id,
          JSON.stringify(userAnswers),
          bandScore,
          correct,
          total,
        );
        await progressAPI.updateProgress({
          skill: 'grammar',
          band_score: bandScore,
          study_time_minutes: minutes,
          correct_answers: correct,
          total_questions: total,
        });
        await progressAPI.createSession({
          skill: 'grammar',
          duration_minutes: minutes,
          notes: `Grammar: ${exercise.meta.grammar_topic} (${exercise.meta.band_level}) — ${correct}/${total}`,
        });
      } catch {}
    }

    // Auto-extract wrong-answer grammar rules to Topics (category: Grammar)
    for (const group of groups) {
      for (const item of group.items as any[]) {
        const key = `${group.type}_${item.question_number}`;
        const userAns = (userAnswers[key] || '').trim();
        let wrong = false;
        if (group.type === 'error_correction' || group.type === 'sentence_transformation' || group.type === 'sentence_combination') {
          wrong = normalizeSentence(userAns) !== normalizeSentence(item.answer || '');
        } else if (group.type === 'gap_fill' || group.type === 'context_completion') {
          wrong = userAns.toLowerCase() !== (item.answer || '').trim().toLowerCase();
        } else if (group.type === 'grammar_mcq' || group.type === 'paraphrase_rewrite' || group.type === 'grammar_function_id') {
          wrong = userAns !== item.answer;
        }
        if (wrong && item.explanation) {
          // Build flashcard-friendly title (the question) and content (answer + explanation)
          let cardTitle = '';
          let cardContent = '';
          if (group.type === 'error_correction') {
            cardTitle = `Fix: ${item.sentence}`;
            cardContent = `\u2713 ${item.answer}\n\n${item.explanation}`;
          } else if (group.type === 'gap_fill') {
            cardTitle = item.sentence.replace('___', `___ (${item.hint})`);
            cardContent = `\u2713 ${item.answer}\n\n${item.explanation}`;
          } else if (group.type === 'grammar_mcq') {
            const optLines = Object.entries(item.options || {}).map(([k, v]) => `${k}) ${v}`).join('  ');
            cardTitle = `${item.question}\n${optLines}`;
            const correctText = item.options?.[item.answer] || item.answer;
            cardContent = `\u2713 ${item.answer}) ${correctText}\n\n${item.explanation}`;
          } else if (group.type === 'sentence_transformation') {
            cardTitle = `${item.instruction}: ${item.original_sentence}`;
            cardContent = `\u2713 ${item.answer}\n\n${item.explanation}`;
          } else if (group.type === 'sentence_combination') {
            cardTitle = `${item.instruction}: ${(item.sentences || []).join(' + ')}`;
            cardContent = `\u2713 ${item.answer}\n\n${item.explanation}`;
          } else if (group.type === 'context_completion') {
            cardTitle = (item.paragraph || '').replace('___', `___ (${item.hint || '...'})`);
            cardContent = `\u2713 ${item.answer}\n\n${item.explanation}`;
          } else if (group.type === 'paraphrase_rewrite') {
            const optLines = Object.entries(item.options || {}).map(([k, v]) => `${k}) ${v}`).join('  ');
            cardTitle = `Paraphrase: ${item.original_sentence}\n${optLines}`;
            const correctText = item.options?.[item.answer] || item.answer;
            cardContent = `\u2713 ${item.answer}) ${correctText}\n\n${item.explanation}`;
          } else if (group.type === 'grammar_function_id') {
            const optLines = Object.entries(item.options || {}).map(([k, v]) => `${k}) ${v}`).join('  ');
            cardTitle = `${item.question}: ${(item.sentence || '').replace(/\*\*/g, '')}\n${optLines}`;
            const correctText = item.options?.[item.answer] || item.answer;
            cardContent = `\u2713 ${item.answer}) ${correctText}\n\n${item.explanation}`;
          }
          topicsAPI.create({
            title: cardTitle || `${exercise.meta.grammar_topic} — Q${item.question_number}`,
            content: cardContent || item.explanation,
            skill: 'grammar',
            category: 'grammar',
          }).catch(() => {});
        }
      }
    }
  };

  const isCorrect = (groupType: string, item: any) => {
    const key = `${groupType}_${item.question_number}`;
    const userAns = (userAnswers[key] || '').trim();
    if (groupType === 'error_correction' || groupType === 'sentence_transformation' || groupType === 'sentence_combination') {
      return normalizeSentence(userAns) === normalizeSentence(item.answer || '');
    } else if (groupType === 'gap_fill' || groupType === 'context_completion') {
      return userAns.toLowerCase() === (item.answer || '').trim().toLowerCase();
    } else if (groupType === 'grammar_mcq' || groupType === 'paraphrase_rewrite' || groupType === 'grammar_function_id') {
      return userAns === item.answer;
    }
    return false;
  };

  return (
    <div className="grammar-exercise">
      {/* Header */}
      <div className="grammar-header">
        <h2>{exercise.meta.grammar_topic}</h2>
        <span className="grammar-band-badge">{exercise.meta.band_level}</span>
      </div>

      {/* Grammar Tip */}
      {(exercise.grammar_tip || exercise.meta.key_pattern) && (
        <div className="grammar-tip">
          <h3>{'\uD83D\uDCA1'} {language === 'zh' ? '\u8BED\u6CD5\u63D0\u793A' : 'Grammar Tip'}</h3>
          <p>{(language === 'zh' && grammarTipZh) ? grammarTipZh : (exercise.grammar_tip || `Key pattern: ${exercise.meta.key_pattern}`)}</p>
        </div>
      )}

      {/* Context paragraph with highlighted grammar phrases */}
      <div className="grammar-context">
        <h3>Context</h3>
        <p>{renderHighlightedContext(exercise.context)}</p>
      </div>

      {/* Question groups */}
      <div className="grammar-questions">
        {groups.map((group, gi) => (
          <div key={gi} className="grammar-group">
            <h3 className="group-type-label">
              {group.type === 'error_correction' && 'Error Correction'}
              {group.type === 'gap_fill' && 'Gap Fill'}
              {group.type === 'grammar_mcq' && 'Multiple Choice'}
              {group.type === 'sentence_transformation' && 'Sentence Transformation'}
              {group.type === 'sentence_combination' && 'Sentence Combination'}
              {group.type === 'context_completion' && 'Context Completion'}
              {group.type === 'paraphrase_rewrite' && 'Paraphrase Rewrite'}
              {group.type === 'grammar_function_id' && 'Grammar Function'}
            </h3>
            {group.type === 'error_correction' && (
              <p className="group-instruction">Find and correct the grammatical error in each sentence.</p>
            )}
            {group.type === 'gap_fill' && (
              <p className="group-instruction">Fill in the blank with the correct form of the word in parentheses.</p>
            )}
            {group.type === 'grammar_mcq' && (
              <p className="group-instruction">Choose the correct option.</p>
            )}
            {group.type === 'sentence_transformation' && (
              <p className="group-instruction">Rewrite each sentence as instructed.</p>
            )}
            {group.type === 'sentence_combination' && (
              <p className="group-instruction">Combine the sentences using the specified grammar structure.</p>
            )}
            {group.type === 'context_completion' && (
              <p className="group-instruction">Complete the gap with the correct grammatical structure.</p>
            )}
            {group.type === 'paraphrase_rewrite' && (
              <p className="group-instruction">Choose the option that correctly paraphrases the sentence using the target grammar.</p>
            )}
            {group.type === 'grammar_function_id' && (
              <p className="group-instruction">Identify the grammatical function of the highlighted word or phrase.</p>
            )}

            {(group.items as any[]).map((item, qi) => {
              const key = `${group.type}_${item.question_number}`;
              const correct = submitted ? isCorrect(group.type, item) : null;

              return (
                <div key={qi} className={`grammar-q ${submitted ? (correct ? 'correct' : 'incorrect') : ''}`}>
                  <span className="q-number">{item.question_number}</span>

                  {group.type === 'error_correction' && (
                    <div className="q-body">
                      <p className="q-sentence">{item.sentence}</p>
                      <input
                        type="text"
                        className="grammar-input"
                        placeholder="Type the corrected sentence…"
                        value={userAnswers[key] || ''}
                        onChange={e => setUserAnswers(prev => ({ ...prev, [key]: e.target.value }))}
                        disabled={submitted}
                      />
                      {submitted && (
                        <div className="q-feedback">
                          {correct
                            ? <span className="feedback-correct"><Check size={14} /> Correct</span>
                            : <span className="feedback-incorrect"><X size={14} /> {item.error_description}</span>}
                          {!correct && <p className="correct-answer">Correct: {item.answer}</p>}
                          <p className="q-explanation">{item.explanation}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {group.type === 'gap_fill' && (
                    <div className="q-body">
                      <p className="q-sentence">
                        {item.sentence.split('___').map((part: string, pi: number, arr: string[]) => (
                          <React.Fragment key={pi}>
                            {part}
                            {pi < arr.length - 1 && (
                              <input
                                type="text"
                                className="gap-input"
                                placeholder={item.hint}
                                value={userAnswers[key] || ''}
                                onChange={e => setUserAnswers(prev => ({ ...prev, [key]: e.target.value }))}
                                disabled={submitted}
                              />
                            )}
                          </React.Fragment>
                        ))}
                      </p>
                      {submitted && (
                        <div className="q-feedback">
                          {correct
                            ? <span className="feedback-correct"><Check size={14} /> Correct</span>
                            : <span className="feedback-incorrect"><X size={14} /> Answer: <strong>{item.answer}</strong></span>}
                          <p className="q-explanation">{item.explanation}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {group.type === 'grammar_mcq' && (
                    <div className="q-body">
                      <p className="q-sentence">{item.question}</p>
                      <div className="mcq-options">
                        {Object.entries(item.options as Record<string, string>).map(([letter, text]) => {
                          const selected = userAnswers[key] === letter;
                          const isRight = item.answer === letter;
                          let cls = 'mcq-opt';
                          if (submitted) {
                            if (isRight) cls += ' correct';
                            else if (selected && !isRight) cls += ' incorrect';
                          } else if (selected) {
                            cls += ' selected';
                          }
                          return (
                            <button
                              key={letter}
                              className={cls}
                              onClick={() => !submitted && setUserAnswers(prev => ({ ...prev, [key]: letter }))}
                              disabled={submitted}
                            >
                              <span className="mcq-letter">{letter}</span>
                              <span>{text}</span>
                              {submitted && isRight && <Check size={14} className="mcq-icon correct" />}
                              {submitted && selected && !isRight && <X size={14} className="mcq-icon incorrect" />}
                            </button>
                          );
                        })}
                      </div>
                      {submitted && (
                        <div className="q-feedback">
                          <p className="q-explanation">{item.explanation}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {group.type === 'sentence_transformation' && (
                    <div className="q-body">
                      <p className="q-instruction-text">{item.instruction}</p>
                      <p className="q-sentence">{item.original_sentence}</p>
                      <input
                        type="text"
                        className="grammar-input"
                        placeholder="Type the transformed sentence…"
                        value={userAnswers[key] || ''}
                        onChange={e => setUserAnswers(prev => ({ ...prev, [key]: e.target.value }))}
                        disabled={submitted}
                      />
                      {submitted && (
                        <div className="q-feedback">
                          {correct
                            ? <span className="feedback-correct"><Check size={14} /> Correct</span>
                            : <span className="feedback-incorrect"><X size={14} /> Your answer differs from the expected transformation</span>}
                          {!correct && <p className="correct-answer">Correct: {item.answer}</p>}
                          <p className="q-explanation">{item.explanation}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {group.type === 'sentence_combination' && (
                    <div className="q-body">
                      <p className="q-instruction-text">{item.instruction}</p>
                      <div className="combination-sentences">
                        {(item.sentences as string[] || []).map((s: string, si: number) => (
                          <p key={si} className="q-sentence">{'\u2022'} {s}</p>
                        ))}
                      </div>
                      <input
                        type="text"
                        className="grammar-input"
                        placeholder="Type the combined sentence…"
                        value={userAnswers[key] || ''}
                        onChange={e => setUserAnswers(prev => ({ ...prev, [key]: e.target.value }))}
                        disabled={submitted}
                      />
                      {submitted && (
                        <div className="q-feedback">
                          {correct
                            ? <span className="feedback-correct"><Check size={14} /> Correct</span>
                            : <span className="feedback-incorrect"><X size={14} /> Your combined sentence differs from the expected answer</span>}
                          {!correct && <p className="correct-answer">Correct: {item.answer}</p>}
                          <p className="q-explanation">{item.explanation}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {group.type === 'context_completion' && (
                    <div className="q-body">
                      <p className="q-sentence">
                        {(item.paragraph || '').split('___').map((part: string, pi: number, arr: string[]) => (
                          <React.Fragment key={pi}>
                            {part}
                            {pi < arr.length - 1 && (
                              <input
                                type="text"
                                className="gap-input"
                                placeholder={item.hint || 'complete the gap'}
                                value={userAnswers[key] || ''}
                                onChange={e => setUserAnswers(prev => ({ ...prev, [key]: e.target.value }))}
                                disabled={submitted}
                              />
                            )}
                          </React.Fragment>
                        ))}
                      </p>
                      {submitted && (
                        <div className="q-feedback">
                          {correct
                            ? <span className="feedback-correct"><Check size={14} /> Correct</span>
                            : <span className="feedback-incorrect"><X size={14} /> Answer: <strong>{item.answer}</strong></span>}
                          <p className="q-explanation">{item.explanation}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {group.type === 'paraphrase_rewrite' && (
                    <div className="q-body">
                      <p className="q-sentence">{item.original_sentence}</p>
                      <div className="mcq-options">
                        {Object.entries((item.options || {}) as Record<string, string>).map(([letter, text]) => {
                          const selected = userAnswers[key] === letter;
                          const isRight = item.answer === letter;
                          let cls = 'mcq-opt';
                          if (submitted) {
                            if (isRight) cls += ' correct';
                            else if (selected && !isRight) cls += ' incorrect';
                          } else if (selected) {
                            cls += ' selected';
                          }
                          return (
                            <button
                              key={letter}
                              className={cls}
                              onClick={() => !submitted && setUserAnswers(prev => ({ ...prev, [key]: letter }))}
                              disabled={submitted}
                            >
                              <span className="mcq-letter">{letter}</span>
                              <span>{text}</span>
                              {submitted && isRight && <Check size={14} className="mcq-icon correct" />}
                              {submitted && selected && !isRight && <X size={14} className="mcq-icon incorrect" />}
                            </button>
                          );
                        })}
                      </div>
                      {submitted && (
                        <div className="q-feedback">
                          <p className="q-explanation">{item.explanation}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {group.type === 'grammar_function_id' && (
                    <div className="q-body">
                      <p className="q-sentence" dangerouslySetInnerHTML={{ __html: (item.sentence || '').replace(/\*\*(.*?)\*\*/g, '<strong class="grammar-highlight-inline">$1</strong>') }} />
                      <p className="q-instruction-text">{item.question}</p>
                      <div className="mcq-options">
                        {Object.entries((item.options || {}) as Record<string, string>).map(([letter, text]) => {
                          const selected = userAnswers[key] === letter;
                          const isRight = item.answer === letter;
                          let cls = 'mcq-opt';
                          if (submitted) {
                            if (isRight) cls += ' correct';
                            else if (selected && !isRight) cls += ' incorrect';
                          } else if (selected) {
                            cls += ' selected';
                          }
                          return (
                            <button
                              key={letter}
                              className={cls}
                              onClick={() => !submitted && setUserAnswers(prev => ({ ...prev, [key]: letter }))}
                              disabled={submitted}
                            >
                              <span className="mcq-letter">{letter}</span>
                              <span>{text}</span>
                              {submitted && isRight && <Check size={14} className="mcq-icon correct" />}
                              {submitted && selected && !isRight && <X size={14} className="mcq-icon incorrect" />}
                            </button>
                          );
                        })}
                      </div>
                      {submitted && (
                        <div className="q-feedback">
                          <p className="q-explanation">{item.explanation}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Submit / Score + Finish */}
      <div className="grammar-actions">
        {!submitted ? (
          <button
            className="btn btn-primary btn-lg"
            onClick={handleSubmit}
            disabled={Object.keys(userAnswers).length === 0}
          >
            Submit Answers
          </button>
        ) : score && (
          <div className="grammar-score">
            <div className="score-summary">
              <span className="score-num">{score.correct}/{score.total}</span>
              <span className="score-label">correct</span>
              <span className="score-band">Band {Math.round((3.5 + (score.correct / score.total) * 4.5) * 2) / 2}</span>
            </div>
            <button className="btn btn-primary" onClick={() => onComplete(score.correct, score.total)}>
              Finish
            </button>
          </div>
        )}
      </div>

      {/* Vocab popup (appears on text selection) */}
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
        <div className="vocab-modal-overlay" onClick={() => setShowVocabModal(false)}>
          <div className="vocab-modal" onClick={e => e.stopPropagation()}>
            <h3>Add Word</h3>
            <input className="vocab-input" value={vocabWord} onChange={e => setVocabWord(e.target.value)} />
            {vocabDefLoading ? (
              <div className="generating-msg"><div className="loading-spinner-sm" /><span>Looking up…</span></div>
            ) : (
              <>
                <textarea className="vocab-def-input" rows={4} placeholder="Definition"
                  value={language === 'zh' && vocabDefZh ? vocabDefZh : vocabDef}
                  onChange={e => language === 'zh' ? setVocabDefZh(e.target.value) : setVocabDef(e.target.value)} />
                {vocabPhonetic && <p className="vocab-phonetic">{vocabPhonetic}</p>}
              </>
            )}
            <div className="vocab-modal-actions">
              <button className="btn btn-primary" onClick={handleSaveVocab} disabled={vocabSaving || !vocabDef.trim()}>
                {vocabSaving ? 'Saving…' : 'Save'}
              </button>
              <button className="btn" onClick={() => setShowVocabModal(false)}>Cancel</button>
            </div>
            {vocabDuplicate && <p className="vocab-error">Already in your deck</p>}
          </div>
        </div>
      )}
      {vocabSaved && <div className="vocab-saved-toast">{'\u2713'} Saved to vocabulary</div>}

      <style>{grammarStyles}</style>
    </div>
  );
}

const grammarStyles = `
  .grammar-exercise { max-width: 800px; margin: 0 auto; }
  .grammar-header { display: flex; align-items: center; gap: var(--spacing-md); margin-bottom: var(--spacing-lg); }
  .grammar-header h2 { margin: 0; }
  .grammar-band-badge { padding: 4px 12px; border-radius: var(--radius-full); font-size: 0.75rem; font-weight: 700; background: rgba(79,70,229,0.12); color: var(--color-primary); }
  .grammar-context { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--spacing-lg); margin-bottom: var(--spacing-lg); }
  .grammar-context h3 { margin: 0 0 var(--spacing-sm) 0; font-size: 0.875rem; color: var(--color-text-secondary); text-transform: uppercase; letter-spacing: 0.05em; }
  .grammar-context p { line-height: 1.8; color: var(--color-text-primary); margin: 0; }
  .grammar-group { margin-bottom: var(--spacing-lg); }
  .group-type-label { font-size: 1rem; font-weight: 600; color: var(--color-primary); margin: 0 0 4px 0; text-transform: uppercase; letter-spacing: 0.03em; font-size: 0.8rem; }
  .group-instruction { font-size: 0.8rem; color: var(--color-text-secondary); margin: 0 0 var(--spacing-md) 0; font-style: italic; }
  .grammar-q { display: flex; gap: var(--spacing-md); padding: var(--spacing-md); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); margin-bottom: var(--spacing-sm); transition: border-color 0.2s; }
  .grammar-q.correct { border-color: var(--color-success); background: rgba(16,185,129,0.04); }
  .grammar-q.incorrect { border-color: var(--color-error); background: rgba(239,68,68,0.04); }
  .q-number { width: 28px; height: 28px; border-radius: 50%; background: var(--color-primary); color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.8rem; flex-shrink: 0; }
  .q-body { flex: 1; min-width: 0; }
  .q-sentence { margin: 0 0 var(--spacing-sm) 0; line-height: 1.7; color: var(--color-text-primary); }
  .grammar-input { width: 100%; padding: 8px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-background); color: var(--color-text-primary); font-size: 0.875rem; font-family: inherit; }
  .grammar-input:focus { outline: none; border-color: var(--color-primary); }
  .grammar-input:disabled { opacity: 0.7; }
  .gap-input { display: inline-block; width: 140px; padding: 4px 8px; border: 1px dashed var(--color-primary); border-radius: var(--radius-sm); background: rgba(79,70,229,0.05); color: var(--color-text-primary); font-size: 0.875rem; font-family: inherit; text-align: center; margin: 0 4px; }
  .gap-input:focus { outline: none; border-style: solid; background: rgba(79,70,229,0.1); }
  .gap-input:disabled { opacity: 0.7; border-style: solid; }
  .gap-input::placeholder { color: var(--color-text-secondary); font-style: italic; font-size: 0.8rem; }
  .q-feedback { margin-top: var(--spacing-sm); padding: var(--spacing-sm); background: var(--color-background); border-radius: var(--radius-sm); font-size: 0.85rem; }
  .feedback-correct { color: var(--color-success); font-weight: 600; display: flex; align-items: center; gap: 4px; }
  .feedback-incorrect { color: var(--color-error); font-weight: 600; display: flex; align-items: center; gap: 4px; }
  .correct-answer { color: var(--color-success); margin: 4px 0 0 0; font-size: 0.8rem; }
  .q-explanation { color: var(--color-text-secondary); margin: 4px 0 0 0; font-style: italic; }
  .mcq-options { display: flex; flex-direction: column; gap: var(--spacing-xs); }
  .mcq-opt { display: flex; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-sm) var(--spacing-md); background: var(--color-background); border: 2px solid var(--color-border); border-radius: var(--radius-md); cursor: pointer; text-align: left; transition: all 0.15s; font-size: 0.875rem; }
  .mcq-opt:hover:not(:disabled) { border-color: var(--color-primary); }
  .mcq-opt.selected { border-color: var(--color-primary); background: rgba(79,70,229,0.08); }
  .mcq-opt.correct { border-color: var(--color-success); background: rgba(16,185,129,0.08); }
  .mcq-opt.incorrect { border-color: var(--color-error); background: rgba(239,68,68,0.08); }
  .mcq-opt:disabled { cursor: default; }
  .mcq-letter { width: 26px; height: 26px; border-radius: 50%; background: var(--color-border); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.8rem; flex-shrink: 0; }
  .mcq-opt.selected .mcq-letter { background: var(--color-primary); color: white; }
  .mcq-opt.correct .mcq-letter { background: var(--color-success); color: white; }
  .mcq-icon { margin-left: auto; flex-shrink: 0; }
  .mcq-icon.correct { color: var(--color-success); }
  .mcq-icon.incorrect { color: var(--color-error); }
  .grammar-actions { display: flex; justify-content: center; margin-top: var(--spacing-lg); }
  .grammar-score { display: flex; justify-content: center; margin-top: var(--spacing-lg); }
  .score-summary { display: flex; align-items: center; gap: var(--spacing-md); padding: var(--spacing-md) var(--spacing-xl); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); }
  .score-num { font-size: 1.5rem; font-weight: 700; color: var(--color-text-primary); }
  .score-label { font-size: 0.875rem; color: var(--color-text-secondary); }
  .score-band { padding: 4px 12px; border-radius: var(--radius-full); font-size: 0.8rem; font-weight: 700; background: rgba(79,70,229,0.12); color: var(--color-primary); }
  .grammar-tip { background: rgba(139,92,246,0.06); border: 1px solid rgba(139,92,246,0.2); border-radius: var(--radius-lg); padding: var(--spacing-md) var(--spacing-lg); margin-bottom: var(--spacing-lg); }
  .grammar-tip h3 { margin: 0 0 var(--spacing-xs) 0; font-size: 0.9rem; color: #8B5CF6; }
  .grammar-tip p { margin: 0; line-height: 1.7; color: var(--color-text-primary); font-size: 0.9rem; }
  .grammar-highlight { background: rgba(139,92,246,0.15); color: inherit; padding: 1px 3px; border-radius: 3px; font-weight: 500; }
  .grammar-highlight-inline { color: var(--color-primary); font-weight: 600; text-decoration: underline; text-decoration-style: dotted; }
  .q-instruction-text { font-style: italic; color: var(--color-text-secondary); margin-bottom: var(--spacing-sm); }
  .combination-sentences { margin-bottom: var(--spacing-sm); }
  .grammar-actions { flex-direction: column; align-items: center; gap: var(--spacing-md); }
  .vocab-popup { position: fixed; transform: translateX(-50%); background: var(--color-primary); color: white; padding: 5px 12px; border-radius: var(--radius-full); font-size: 0.75rem; font-weight: 600; cursor: pointer; z-index: 1000; white-space: nowrap; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
  .vocab-popup:hover { background: #4338ca; }
  .vocab-modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 1001; display: flex; align-items: center; justify-content: center; }
  .vocab-modal { background: var(--color-surface); border-radius: var(--radius-lg); padding: var(--spacing-lg); width: min(400px, 90vw); box-shadow: 0 8px 32px rgba(0,0,0,0.15); }
  .vocab-modal h3 { margin-bottom: var(--spacing-md); font-size: 1rem; }
  .vocab-input { width: 100%; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-background); color: var(--color-text-primary); font-size: 0.9rem; box-sizing: border-box; }
  .vocab-def-input { width: 100%; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-background); color: var(--color-text-primary); font-size: 0.9rem; resize: vertical; box-sizing: border-box; font-family: inherit; }
  .vocab-phonetic { font-size: 0.85rem; color: var(--color-text-secondary); margin: var(--spacing-xs) 0 0; }
  .vocab-error { font-size: 0.8rem; color: var(--color-error); margin: var(--spacing-xs) 0 0; }
  .vocab-saved-toast { position: fixed; bottom: 24px; right: 24px; background: var(--color-success); color: white; padding: 10px 18px; border-radius: var(--radius-md); font-size: 0.875rem; font-weight: 600; z-index: 1002; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }
`;

export default AIGrammarExerciseView;
