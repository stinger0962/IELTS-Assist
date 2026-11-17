import { api } from './index';

export interface CheckoutOffer {
  enabled: true;
  test_mode: true;
  sku: string;
  amount_minor: number;
  currency: 'USD';
  reviews: number;
  duration_days: 30;
}
export interface CheckoutOrder {
  id: string;
  state: 'pending' | 'fulfilled' | 'refunded' | 'review';
  checkout_url: string | null;
  test_mode: true;
}
export const isOrderId = (value: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);

export function isCheckoutOffer(value: unknown): value is CheckoutOffer {
  if (!value || typeof value !== 'object') return false;
  const v = value as Record<string, unknown>;
  return v.enabled === true && v.test_mode === true && typeof v.sku === 'string' && v.sku.length > 0 &&
    Number.isSafeInteger(v.amount_minor) && Number(v.amount_minor) > 0 &&
    v.currency === 'USD' && Number.isSafeInteger(v.reviews) && Number(v.reviews) > 0 && v.duration_days === 30;
}
export function isCheckoutOrder(value: unknown): value is CheckoutOrder {
  if (!value || typeof value !== 'object') return false;
  const v = value as Record<string, unknown>;
  return typeof v.id === 'string' && isOrderId(v.id) && v.test_mode === true &&
    ['pending', 'fulfilled', 'refunded', 'review'].includes(String(v.state)) &&
    (v.checkout_url === null || typeof v.checkout_url === 'string');
}
export function safeStripeCheckoutUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && url.hostname === 'checkout.stripe.com' &&
      !url.username && !url.password && !url.port ? url.href : null;
  } catch { return null; }
}
export function checkoutReturnPath(value: string | null): string | null {
  if (!value) return null;
  // Only our two known return routes with one owned-order identifier can survive login.
  const match = /^(\/checkout\/(?:return|cancel))\?order_id=([0-9a-f-]+)$/i.exec(value);
  return match && isOrderId(match[2]) ? value : null;
}
export const checkoutAPI = {
  offer: () => api.get('/checkout/offer'),
  create: (idempotencyKey: string) => api.post('/checkout/orders', { idempotency_key: idempotencyKey }),
  status: (id: string) => api.get('/checkout/orders/' + encodeURIComponent(id)),
};
