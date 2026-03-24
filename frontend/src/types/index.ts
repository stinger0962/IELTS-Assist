export type SkillType = 'reading' | 'listening' | 'writing' | 'speaking' | 'grammar';

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
  user_id?: number | null;
  skill: SkillType;
  category: string;
  title: string;
  content: string;
  content_zh?: string;
  example?: string;
  example_zh?: string;
  difficulty: number;
  phonetic?: string;
  audio_url?: string;
  in_deck?: boolean;
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
  skill?: string;
  goal_type?: string;
  completed: boolean;
  created_at: string;
}

export interface GoalTodayProgressItem {
  goal_id: number;
  title: string;
  skill?: string;
  goal_type: string;
  target: number;
  actual: number;
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

// AI-generated listening practice types
export interface AIListeningCompletionQuestion {
  question_number: number;
  text: string;
  answer: string;
  subtype?: 'form' | 'table' | 'note' | 'summary' | 'sentence';
  group_title?: string;
}

export interface AIListeningMCQQuestion {
  question_number: number;
  question: string;
  options: Record<string, string>;
  answer: string;
}

export interface AIListeningMatchingBlock {
  question_number_start: number;
  question_number_end: number;
  instruction: string;
  stems: { question_number: number; text: string }[];
  options: string[];
  answers: Record<string, string>;
}

export interface AIListeningPractice {
  practice_db_id?: number;
  meta: {
    module: string;
    format: 'conversation' | 'monologue' | 'discussion' | 'lecture';
    target_band: number;
    word_count: number;
    topic: string;
    speakers: string[];
    audio_url: string;
  };
  transcript: string;
  line_timestamps?: { line_index: number; start: number; end: number; text?: string }[];
  questions: {
    completion: AIListeningCompletionQuestion[];
    multiple_choice: AIListeningMCQQuestion[];
    matching?: AIListeningMatchingBlock[];
  };
}

// New flexible question group structure for reading
export type ReadingQuestionType =
  | 'true_false_not_given'
  | 'multiple_choice'
  | 'matching_headings'
  | 'matching_information'
  | 'sentence_completion'
  | 'summary_completion'
  | 'short_answer';

export interface ReadingQuestionGroup {
  type: ReadingQuestionType;
  items: any[];  // type-specific items
  summary_text?: string;  // only for summary_completion
  answers?: any[];  // for matching_headings
}

export interface ReadingSentenceCompletionItem {
  question_number: number;
  text: string;
  answer: string;
  word_limit?: number;
  explanation?: string;
}

export interface ReadingSummaryCompletionItem {
  question_number: number;
  answer: string;
  word_limit?: number;
  explanation?: string;
}

export interface ReadingMatchingInfoItem {
  question_number: number;
  statement: string;
  answer: string;
  explanation?: string;
}

export interface ReadingShortAnswerItem {
  question_number: number;
  question: string;
  answer: string;
  word_limit?: number;
  explanation?: string;
}

export interface AIReadingPractice {
  practice_db_id?: number;  // injected by backend when dealt to user
  meta: {
    module: string;
    target_band: number;
    word_count: number;
    topic: string;
  };
  passage: string;
  questions: {
    // Legacy format (backward compat)
    true_false_not_given?: TFNGQuestionItem[];
    second_type?: {
      type: 'multiple_choice' | 'matching_headings';
      items: MCQQuestionItem[] | MatchingHeadingData;
    };
    // New flexible format
    groups?: ReadingQuestionGroup[];
  };
  // Legacy only; new format has answers inline
  answer_key?: {
    true_false_not_given: TFNGAnswerItem[];
    second_type_answers: MCQAnswerItem[] | MatchingAnswerItem[];
  };
}

// AI-generated grammar practice types
export interface GrammarErrorCorrectionItem {
  question_number: number;
  sentence: string;
  answer: string;
  error_description: string;
  explanation: string;
}

export interface GrammarGapFillItem {
  question_number: number;
  sentence: string;
  hint: string;
  answer: string;
  explanation: string;
}

export interface GrammarMCQItem {
  question_number: number;
  question: string;
  options: Record<string, string>;
  answer: string;
  explanation: string;
}

export interface GrammarTransformationItem {
  question_number: number;
  instruction: string;
  original_sentence: string;
  answer: string;
  explanation: string;
}

export interface GrammarCombinationItem {
  question_number: number;
  sentences: string[];
  instruction: string;
  answer: string;
  explanation: string;
}

export interface GrammarContextCompletionItem {
  question_number: number;
  paragraph: string;
  hint: string;
  answer: string;
  explanation: string;
}

export interface GrammarParaphraseItem {
  question_number: number;
  original_sentence: string;
  options: Record<string, string>;
  answer: string;
  explanation: string;
}

export interface GrammarFunctionIdItem {
  question_number: number;
  sentence: string;
  question: string;
  options: Record<string, string>;
  answer: string;
  explanation: string;
}

export type GrammarQuestionType =
  | 'error_correction' | 'gap_fill' | 'grammar_mcq'
  | 'sentence_transformation' | 'sentence_combination' | 'context_completion'
  | 'paraphrase_rewrite' | 'grammar_function_id';

export interface GrammarQuestionGroup {
  type: GrammarQuestionType;
  items: (GrammarErrorCorrectionItem | GrammarGapFillItem | GrammarMCQItem
    | GrammarTransformationItem | GrammarCombinationItem | GrammarContextCompletionItem
    | GrammarParaphraseItem | GrammarFunctionIdItem)[];
}

// AI Writing practice types
export interface WritingAnnotation {
  start_char: number;
  end_char: number;
  original_text: string;
  category: 'grammar' | 'vocabulary' | 'spelling' | 'punctuation' | 'coherence' | 'style';
  suggestion: string;
  severity: 'minor' | 'major';
}

export interface WritingCriterionScore {
  band: number;
  evidence: string;
  task_completion?: {
    answered_all_parts: boolean;
    clear_position: boolean;
    sufficient_support: boolean;
    paragraphing_effective: boolean;
  };
}

export interface WritingExaminerResult {
  task_response: WritingCriterionScore;
  coherence_cohesion: WritingCriterionScore;
  lexical_resource: WritingCriterionScore;
  grammatical_range_accuracy: WritingCriterionScore;
  overall_band: number;
}

export interface WritingCoachingFeedback {
  summary: string;
  strengths: string[];
  improvements: string[];
}

export interface WritingGradingResult {
  examiner_result: WritingExaminerResult;
  coaching_feedback: WritingCoachingFeedback;
  annotations: WritingAnnotation[];
  grader_version: string;
  model: string;
}

export interface AIWritingPractice {
  practice_db_id?: number;
  meta: {
    module: string;
    essay_type: string;
    domain: string;
    topic: string;
    word_limit: { min: number; recommended: number };
  };
  prompt: {
    statement: string;
    instruction: string;
    notes: string;
  };
}

// AI Speaking practice types
export interface SpeakingCueCard {
  topic_line: string;
  bullets: string[];
  follow_up: string;
}

export interface SpeakingTopicSet {
  area: string;
  questions: string[];
}

export interface AISpeakingPractice {
  practice_db_id: number;
  meta: { module: string; domain?: string; topic: string };
  cue_card?: SpeakingCueCard;                // Part 2 only
  topics?: SpeakingTopicSet[];               // Part 1 only
  cue_card_metadata?: Record<string, any>;
}

export interface SpeakingPronunciationWord {
  word: string;
  accuracy_score: number;
  error_type: string;
}

export interface SpeakingGradingResult {
  examiner_result: {
    fluency_coherence: { band: number; evidence: string };
    lexical_resource: { band: number; evidence: string };
    grammatical_range_accuracy: { band: number; evidence: string };
    pronunciation: { band: number; evidence: string; azure_scores?: Record<string, number> };
    overall_band: number;
  };
  coaching_feedback: {
    summary: string;
    strengths: string[];
    improvements: string[];
  };
  transcript: string;
  pronunciation_words?: SpeakingPronunciationWord[];
  grader_version: string;
  model: string;
}

export type SpeakingTrend = 'improving' | 'declining' | 'stable' | 'insufficient';

export interface SpeakingCriterionInsight {
  name: string;
  label: string;
  average: number;
  trend: SpeakingTrend;
}

export interface SpeakingSessionSummary {
  date: string;
  overall_band: number;
  topic: string | null;
}

export interface SpeakingInsights {
  total_sessions: number;
  criteria: SpeakingCriterionInsight[];
  weakest_criterion: string | null;
  weakest_recommendation: string | null;
  best_session_band: number | null;
  worst_session_band: number | null;
  overall_average: number | null;
  recent_sessions: SpeakingSessionSummary[];
}

export interface AIGrammarPractice {
  practice_db_id?: number;
  meta: {
    module: string;
    grammar_topic: string;
    key_pattern?: string;
    band_level: string;
    context_theme: string;
    question_count: number;
  };
  grammar_tip?: string;
  highlight_phrases?: string[];
  context: string;
  questions: {
    groups: GrammarQuestionGroup[];
  };
}