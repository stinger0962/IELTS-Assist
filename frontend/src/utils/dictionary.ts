export const POS_ABBR: Record<string, string> = {
  verb: 'v.', noun: 'n.', adjective: 'adj.', adverb: 'adv.',
  preposition: 'prep.', conjunction: 'conj.', pronoun: 'pron.', interjection: 'interj.',
};

export function parseDictionaryEntry(data: any[]): string {
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
