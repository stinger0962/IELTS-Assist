export const WORD_TO_NUM: Record<string, number> = {
  zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7,
  eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12, thirteen: 13,
  fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18,
  nineteen: 19, twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60,
  seventy: 70, eighty: 80, ninety: 90,
};
export const MULTIPLIERS: Record<string, number> = { hundred: 100, thousand: 1000, million: 1_000_000 };

/** Try to parse an English number phrase like "two hundred eighty" → 280. Returns NaN on failure. */
export function wordsToNumber(text: string): number {
  const tokens = text.toLowerCase().replace(/-/g, ' ').replace(/\band\b/g, ' ').trim().split(/\s+/);
  let total = 0, current = 0;
  for (const t of tokens) {
    if (WORD_TO_NUM[t] !== undefined) { current += WORD_TO_NUM[t]; }
    else if (MULTIPLIERS[t]) {
      current = (current === 0 ? 1 : current) * MULTIPLIERS[t];
      if (MULTIPLIERS[t] >= 1000) { total += current; current = 0; }
    } else { return NaN; }
  }
  return total + current;
}

/** Normalize text for comparison: lowercase, strip punctuation/articles, collapse whitespace, normalize hyphens. */
export function normalize(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[$£€]/g, '')              // strip currency symbols
    .replace(/[.,;:!?'"()]/g, '')       // strip punctuation
    .replace(/\b(dollars?|pounds?|euros?|cents?|pence)\b/g, '') // strip currency words
    .replace(/^(the|a|an)\s+/i, '')     // strip leading articles
    .replace(/-/g, ' ')                 // hyphens → spaces
    .replace(/\s+/g, ' ')              // collapse whitespace
    .trim();
}

/** Simple plural match: "dollar" ≈ "dollars", "library" ≈ "libraries", "box" ≈ "boxes". */
export function pluralMatch(a: string, b: string): boolean {
  if (a === b) return true;
  // One is the other + "s"
  if (a + 's' === b || b + 's' === a) return true;
  // "es" suffix: box→boxes, class→classes
  if (a + 'es' === b || b + 'es' === a) return true;
  // "ies" ↔ "y": library→libraries
  if (a.endsWith('y') && b === a.slice(0, -1) + 'ies') return true;
  if (b.endsWith('y') && a === b.slice(0, -1) + 'ies') return true;
  return false;
}

/** Levenshtein distance between two strings. */
export function editDistance(a: string, b: string): number {
  const m = a.length, n = b.length;
  if (Math.abs(m - n) > 2) return Math.abs(m - n); // early exit
  const dp: number[] = Array.from({ length: n + 1 }, (_, i) => i);
  for (let i = 1; i <= m; i++) {
    let prev = i - 1;
    dp[0] = i;
    for (let j = 1; j <= n; j++) {
      const tmp = dp[j];
      dp[j] = a[i - 1] === b[j - 1] ? prev : 1 + Math.min(prev, dp[j], dp[j - 1]);
      prev = tmp;
    }
  }
  return dp[n];
}

/** Flexible match: case-insensitive, punctuation/article tolerant, plural, number words, minor typo (1 edit). */
export function completionMatch(userRaw: string, correctRaw: string): boolean {
  const u = normalize(userRaw);
  const c = normalize(correctRaw);
  if (!u) return false;
  // Exact after normalization
  if (u === c) return true;
  // Plural variants
  if (pluralMatch(u, c)) return true;
  // Numeric equivalence (digits ↔ words)
  const uNum = Number(u) || wordsToNumber(u);
  const cNum = Number(c) || wordsToNumber(c);
  if (!isNaN(uNum) && !isNaN(cNum) && uNum === cNum) return true;
  // Minor typo: allow 1 edit for words ≥ 4 chars
  if (c.length >= 4 && editDistance(u, c) <= 1) return true;
  return false;
}
