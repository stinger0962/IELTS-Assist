export type SkillType = 'reading' | 'listening' | 'writing' | 'speaking';

export interface User {
  id: number;
  email: string;
  username: string;
  full_name?: string;
  target_band: number;
  test_date?: string;
  preferred_language: string;
  created_at: string;
}

export interface UserProgress {
  id: number;
  skill: SkillType;
  band_score: number;
  total_exercises: number;
  correct_answers: number;
  study_time_minutes: number;
  last_practiced?: string;
}

export interface ProgressStats {
  total_study_time: number;
  total_exercises: number;
  average_band: number;
  streak_days: number;
  progress: UserProgress[];
}

export interface StudySession {
  id: number;
  skill?: SkillType;
  duration_minutes: number;
  notes?: string;
  completed: boolean;
  created_at: string;
}

export interface Mistake {
  id: number;
  skill: SkillType;
  question: string;
  user_answer: string;
  correct_answer: string;
  mistake_type?: string;
  explanation?: string;
  times_repeated: number;
  last_reviewed?: string;
  created_at: string;
}

export interface PracticeResult {
  id: number;
  skill: SkillType;
  exercise_id: string;
  score: number;
  total_questions: number;
  correct_answers: number;
  time_taken_seconds?: number;
  created_at: string;
}

export interface Topic {
  id: number;
  skill: SkillType;
  category: string;
  title: string;
  content: string;
  content_zh?: string;
  example?: string;
  example_zh?: string;
  difficulty: number;
}

export interface FlashCard {
  topic: Topic;
  next_review?: string;
  ease_factor: number;
  interval_days: number;
  repetitions: number;
}

export interface Goal {
  id: number;
  title: string;
  description?: string;
  target_date?: string;
  target_minutes?: number;
  completed: boolean;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface ReadingExercise {
  id: string;
  title: string;
  content: string;
  questions: Question[];
}

export interface Question {
  id: string;
  question: string;
  options: string[];
  answer: number;
}

export interface ListeningExercise {
  id: string;
  title: string;
  script: string;
  questions: Question[];
}

export interface WritingTopic {
  id: string;
  type: string;
  question: string;
}

export interface SpeakingTopic {
  id: string;
  part: string;
  question: string;
}

// AI-generated reading practice types
export interface TFNGQuestionItem {
  question_number: number;
  statement: string;
}

export interface TFNGAnswerItem {
  question_number: number;
  answer: 'TRUE' | 'FALSE' | 'NOT GIVEN';
}

export interface MCQQuestionItem {
  question_number: number;
  question: string;
  options: Record<string, string>;
}

export interface MCQAnswerItem {
  question_number: number;
  answer: string;
}

export interface MatchingHeadingItem {
  id: string;
  text: string;
}

export interface MatchingParagraphItem {
  number: number;
  title: string;
}

export interface MatchingHeadingData {
  headings: MatchingHeadingItem[];
  paragraphs: MatchingParagraphItem[];
}

export interface MatchingAnswerItem {
  paragraph_number: number;
  answer: string;
}

export interface AIReadingPractice {
  meta: {
    module: string;
    target_band: number;
    word_count: number;
    topic: string;
  };
  passage: string;
  questions: {
    true_false_not_given: TFNGQuestionItem[];
    second_type: {
      type: 'multiple_choice' | 'matching_headings';
      items: MCQQuestionItem[] | MatchingHeadingData;
    };
  };
  answer_key: {
    true_false_not_given: TFNGAnswerItem[];
    second_type_answers: MCQAnswerItem[] | MatchingAnswerItem[];
  };
}