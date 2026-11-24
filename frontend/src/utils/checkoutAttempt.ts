import { browserStorageKey } from '../deployment';
import type { CheckoutOffer } from '../api/checkout';
import { isOrderId } from '../api/checkout';

// Tab-scoped recovery only. Never store tokens, hosted URLs, essays or card data.
export const CHECKOUT_ATTEMPT_TTL_MS = 24 * 60 * 60 * 1000;
interface Attempt { key: string; createdAt: number }
export type AttemptState = { kind: 'none' } | { kind: 'ready'; attempt: Attempt } | { kind: 'blocked' };

function storageKey(userId: number, offer: CheckoutOffer) {
  return browserStorageKey('ielts:test-checkout:v1:' + userId + ':' + encodeURIComponent(
    [offer.sku, offer.amount_minor, offer.currency, offer.reviews, offer.duration_days].join('|')));
}
export function readCheckoutAttempt(userId: number, offer: CheckoutOffer, now = Date.now()): AttemptState {
  try {
    const raw = sessionStorage.getItem(storageKey(userId, offer));
    if (!raw) return { kind: 'none' };
    const value = JSON.parse(raw) as Partial<Attempt>;
    if (typeof value.key !== 'string' || !isOrderId(value.key) ||
        typeof value.createdAt !== 'number' || !Number.isFinite(value.createdAt) ||
        now < value.createdAt || now - value.createdAt >= CHECKOUT_ATTEMPT_TTL_MS) {
      // Never rotate an unresolved/expired request into a fresh purchase.
      return { kind: 'blocked' };
    }
    return { kind: 'ready', attempt: value as Attempt };
  } catch { return { kind: 'blocked' }; }
}
export function obtainCheckoutAttempt(userId: number, offer: CheckoutOffer): { key: string; recovered: boolean } {
  const existing = readCheckoutAttempt(userId, offer);
  if (existing.kind === 'blocked') throw new Error('checkout_attempt_needs_review');
  if (existing.kind === 'ready') return { key: existing.attempt.key, recovered: true };
  const attempt: Attempt = { key: crypto.randomUUID(), createdAt: Date.now() };
  // Must persist BEFORE the network request, otherwise an uncertain request is unrecoverable.
  sessionStorage.setItem(storageKey(userId, offer), JSON.stringify(attempt));
  return { key: attempt.key, recovered: false };
}
