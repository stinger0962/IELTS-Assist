import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { BookOpen, Headphones, Pen, MessageCircle, Check, X } from 'lucide-react';
import { practiceAPI, progressAPI, mistakesAPI } from '../api';
import type { SkillType, ReadingExercise, ListeningExercise, WritingTopic, SpeakingTopic } from '../types';

type Exercise = ReadingExercise | ListeningExercise;

const skillConfig = [
  { type: 'reading' as SkillType, icon: BookOpen, color: '#4F46E5' },
  { type: 'listening' as SkillType, icon: Headphones, color: '#10B981' },
  { type: 'writing' as SkillType, icon: Pen, color: '#F59E0B' },
  { type: 'speaking' as SkillType, icon: MessageCircle, color: '#EF4444' },
];

function ReadingExerciseView({ exercise, onComplete }: { 
  exercise: ReadingExercise; 
  onComplete: (correct: number, total: number, answers: {question: string, userAnswer: string, correctAnswer: string}[]) => void 
}) {
  const { t } = useTranslation();
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [answers, setAnswers] = useState<{question: string, userAnswer: string, correctAnswer: string}[]>([]);
  const [startTime] = useState(Date.now());

  const question = exercise.questions[currentQuestion];

  const handleAnswer = () => {
    if (selectedAnswer === null) return;
    
    const isCorrect = selectedAnswer === question.answer;
    const answerRecord = {
      question: question.question,
      userAnswer: question.options[selectedAnswer],
      correctAnswer: question.options[question.answer]
    };
    
    setAnswers([...answers, answerRecord]);
    setShowResult(true);
    
    // Record mistake if wrong
    if (!isCorrect) {
      mistakesAPI.create({
        skill: 'reading',
        question: question.question,
        user_answer: question.options[selectedAnswer],
        correct_answer: question.options[question.answer],
        mistake_type: 'reading_comprehension'
      });
    }
  };

  const handleNext = () => {
    if (currentQuestion < exercise.questions.length - 1) {
      setCurrentQuestion(currentQuestion + 1);
      setSelectedAnswer(null);
      setShowResult(false);
    } else {
      const timeTaken = Math.round((Date.now() - startTime) / 1000);
      const correct = answers.filter(a => a.userAnswer === a.correctAnswer).length + (showResult && selectedAnswer === question.answer ? 1 : 0);
      const total = exercise.questions.length;
      
      // Submit results
      practiceAPI.submit({
        skill: 'reading',
        exercise_id: exercise.id,
        score: (correct / total) * 100,
        total_questions: total,
        correct_answers: correct,
        time_taken_seconds: timeTaken
      });

      // Update progress
      progressAPI.updateProgress({
        skill: 'reading',
        total_questions: total,
        correct_answers: correct
      });

      onComplete(correct, total, answers);
    }
  };

  return (
    <div className="exercise-view">
      <div className="exercise-passage">
        <h3>{exercise.title}</h3>
        <p>{exercise.content}</p>
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
                showResult ? (index === question.answer ? 'correct' : (selectedAnswer === index ? 'incorrect' : '')) : ''
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

export default function Practice() {
  const { t } = useTranslation();
  const [, setSelectedSkill] = useState<SkillType | null>(null);
  const [readingExercises, setReadingExercises] = useState<ReadingExercise[]>([]);
  const [listeningExercises, setListeningExercises] = useState<ListeningExercise[]>([]);
  const [writingTopics, setWritingTopics] = useState<WritingTopic[]>([]);
  const [speakingTopics, setSpeakingTopics] = useState<SpeakingTopic[]>([]);
  const [currentExercise, setCurrentExercise] = useState<Exercise | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [result, setResult] = useState<{correct: number; total: number} | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadExercises();
  }, []);

  const loadExercises = async () => {
    setLoading(true);
    try {
      const [reading, listening, writing, speaking] = await Promise.all([
        practiceAPI.getReading(),
        practiceAPI.getListening(),
        practiceAPI.getWriting(),
        practiceAPI.getSpeaking(),
      ]);
      setReadingExercises(reading.data);
      setListeningExercises(listening.data);
      setWritingTopics(writing.data);
      setSpeakingTopics(speaking.data);
    } catch (error) {
      console.error('Failed to load exercises:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleComplete = (correct: number, total: number) => {
    setResult({ correct, total });
    setShowResult(true);
  };

  const handleBack = () => {
    setCurrentExercise(null);
    setShowResult(false);
    setResult(null);
  };

  // Result screen
  if (showResult && result) {
    const percentage = Math.round((result.correct / result.total) * 100);
    return (
      <div className="practice result-view">
        <div className="result-card">
          <div className="result-circle" style={{ '--percentage': percentage } as React.CSSProperties}>
            <span className="result-score">{percentage}%</span>
          </div>
          <h2>{t('practice.score')}</h2>
          <p>{result.correct} / {result.total} {t('practice.correct')}</p>
          <button className="btn btn-primary btn-lg" onClick={handleBack}>
            Continue
          </button>
        </div>
        <style>{`
          .result-view {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 60vh;
          }
          .result-card {
            text-align: center;
            padding: var(--spacing-2xl);
          }
          .result-circle {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            background: conic-gradient(var(--color-primary) var(--percentage, 0), var(--color-border) 0);
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto var(--spacing-lg);
          }
          .result-score {
            font-size: 2.5rem;
            font-weight: 700;
          }
        `}</style>
      </div>
    );
  }

  // Exercise view
  if (currentExercise) {
    const isReading = 'content' in currentExercise;
    return (
      <div className="practice">
        <button className="back-btn" onClick={handleBack}>
          ← Back
        </button>
        {isReading ? (
          <ReadingExerciseView 
            exercise={currentExercise as ReadingExercise} 
            onComplete={handleComplete}
          />
        ) : (
          <ReadingExerciseView 
            exercise={{...currentExercise, content: (currentExercise as ListeningExercise).script} as ReadingExercise}
            onComplete={handleComplete}
          />
        )}
        <style>{`
          .back-btn {
            background: none;
            border: none;
            color: var(--color-primary);
            font-size: 1rem;
            cursor: pointer;
            margin-bottom: var(--spacing-md);
          }
          .exercise-view {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: var(--spacing-lg);
          }
          @media (max-width: 1024px) {
            .exercise-view {
              grid-template-columns: 1fr;
            }
          }
          .exercise-passage {
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            padding: var(--spacing-lg);
          }
          .exercise-passage h3 {
            margin-bottom: var(--spacing-md);
          }
          .exercise-passage p {
            line-height: 1.8;
            color: var(--color-text-primary);
          }
          .exercise-question {
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            padding: var(--spacing-lg);
          }
          .question-header {
            margin-bottom: var(--spacing-md);
          }
          .question-number {
            background: var(--color-primary);
            color: white;
            padding: var(--spacing-xs) var(--spacing-sm);
            border-radius: var(--radius-sm);
            font-size: 0.75rem;
            font-weight: 600;
          }
          .question-text {
            font-size: 1.125rem;
            font-weight: 500;
            margin-bottom: var(--spacing-md);
            color: var(--color-text-primary);
          }
          .options {
            display: flex;
            flex-direction: column;
            gap: var(--spacing-sm);
            margin-bottom: var(--spacing-lg);
          }
          .option {
            display: flex;
            align-items: center;
            gap: var(--spacing-sm);
            padding: var(--spacing-md);
            background: var(--color-background);
            border: 2px solid var(--color-border);
            border-radius: var(--radius-md);
            cursor: pointer;
            text-align: left;
            transition: all var(--transition-fast);
          }
          .option:hover:not(:disabled) {
            border-color: var(--color-primary);
          }
          .option.selected {
            border-color: var(--color-primary);
            background: rgba(79, 70, 229, 0.1);
          }
          .option.correct {
            border-color: var(--color-success);
            background: rgba(16, 185, 129, 0.1);
          }
          .option.incorrect {
            border-color: var(--color-error);
            background: rgba(239, 68, 68, 0.1);
          }
          .option:disabled {
            cursor: default;
          }
          .option-letter {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: var(--color-border);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 0.875rem;
          }
          .option.selected .option-letter {
            background: var(--color-primary);
            color: white;
          }
          .option-text {
            flex: 1;
          }
          .result-icon {
            margin-left: auto;
          }
          .result-icon.correct {
            color: var(--color-success);
          }
          .result-icon.incorrect {
            color: var(--color-error);
          }
          .question-actions {
            display: flex;
            justify-content: flex-end;
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="practice">
      <header className="page-header">
        <h1>{t('practice.title')}</h1>
      </header>

      {loading ? (
        <div className="loading">
          <div className="loading-spinner" />
        </div>
      ) : (
        <div className="practice-grid">
          {/* Reading */}
          <div className="practice-section">
            <div className="section-header" style={{ borderColor: skillConfig[0].color }}>
              <BookOpen size={24} style={{ color: skillConfig[0].color }} />
              <h2>{t('practice.reading')}</h2>
            </div>
            <div className="exercise-list">
              {readingExercises.map((exercise) => (
                <button
                  key={exercise.id}
                  className="exercise-item"
                  onClick={() => {
                    setSelectedSkill('reading');
                    setCurrentExercise(exercise);
                  }}
                >
                  <span className="exercise-title">{exercise.title}</span>
                  <span className="exercise-meta">{exercise.questions.length} questions</span>
                </button>
              ))}
            </div>
          </div>

          {/* Listening */}
          <div className="practice-section">
            <div className="section-header" style={{ borderColor: skillConfig[1].color }}>
              <Headphones size={24} style={{ color: skillConfig[1].color }} />
              <h2>{t('practice.listening')}</h2>
            </div>
            <div className="exercise-list">
              {listeningExercises.map((exercise) => (
                <button
                  key={exercise.id}
                  className="exercise-item"
                  onClick={() => {
                    setSelectedSkill('listening');
                    setCurrentExercise(exercise);
                  }}
                >
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
              {writingTopics.map((topic) => (
                <button
                  key={topic.id}
                  className="exercise-item"
                  onClick={() => {
                    alert(`Writing Topic:\n\n${topic.question}`);
                  }}
                >
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
              {speakingTopics.map((topic) => (
                <button
                  key={topic.id}
                  className="exercise-item"
                  onClick={() => {
                    alert(`Speaking Topic (${topic.part}):\n\n${topic.question}`);
                  }}
                >
                  <span className="exercise-title">{topic.part.toUpperCase()}</span>
                  <span className="exercise-meta">Click to view</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <style>{`
        .practice {
          max-width: 1200px;
          margin: 0 auto;
        }

        .page-header {
          margin-bottom: var(--spacing-lg);
        }

        .practice-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: var(--spacing-lg);
        }

        @media (max-width: 1024px) {
          .practice-grid {
            grid-template-columns: 1fr;
          }
        }

        .practice-section {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          overflow: hidden;
        }

        .section-header {
          display: flex;
          align-items: center;
          gap: var(--spacing-sm);
          padding: var(--spacing-md) var(--spacing-lg);
          border-bottom: 3px solid;
          background: var(--color-background);
        }

        .exercise-list {
          padding: var(--spacing-md);
          display: flex;
          flex-direction: column;
          gap: var(--spacing-sm);
        }

        .exercise-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: var(--spacing-md);
          background: var(--color-background);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          cursor: pointer;
          transition: all var(--transition-fast);
          text-align: left;
        }

        .exercise-item:hover {
          border-color: var(--color-primary);
          transform: translateX(4px);
        }

        .exercise-title {
          font-weight: 500;
          color: var(--color-text-primary);
        }

        .exercise-meta {
          font-size: 0.75rem;
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