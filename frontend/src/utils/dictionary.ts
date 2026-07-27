import { api } from '../api';

export const POS_ABBR: Record<string, string> = {
  verb: 'v.', noun: 'n.', adjective: 'adj.', adverb: 'adv.',
  preposition: 'prep.', conjunction: 'conj.', pronoun: 'pron.', interjection: 'interj.',
};

export interface WordEntry {
  word: string;
  definition_en: string;
  definition_zh: string | null;
  example: string | null;
  phonetic: string | null;
  audio_url: string | null;
  cached: boolean;
}

/**
 * Look up a word via our backend.
 *
 * Replaces direct calls to api.dictionaryapi.dev — a free service with no SLA
 * whose audio URLs we were persisting, so an outage there would have broken
 * already-saved vocabulary. Definition, Chinese, IPA and self-hosted audio all
 * arrive in one response, and results are cached server-side across all users.
 *
 * `context` is the sentence the word appeared in, used to pick the right sense.
 */
export async function lookupWord(word: string, context?: string): Promise<WordEntry> {
  const { data } = await api.post<WordEntry>('/generate/define-word', { word, context });
  return data;
}
