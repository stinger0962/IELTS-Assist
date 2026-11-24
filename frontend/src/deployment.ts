/** Only the dedicated billing-test build uses a path or new browser state. */
const BILLING_TEST_BASE = '/__ielts-billing-test/';
export const IS_BILLING_TEST = import.meta.env.BASE_URL === BILLING_TEST_BASE;
export const APP_BASE = IS_BILLING_TEST ? BILLING_TEST_BASE : '/';
export const appPath = (route: `/${string}`) => APP_BASE.slice(0, -1) + route;
export const browserStorageKey = (key: string) => IS_BILLING_TEST ? 'ielts-billing-test:' + key : key;
export const sameOriginApiBase = (fallback?: string) => IS_BILLING_TEST ? APP_BASE + 'api' : fallback || '/api';

export function practiceAudioUrl(value: string | undefined): string {
  if (!value || !IS_BILLING_TEST) return value || '';
  // Test bundles must not pull audio from the live site's root or third parties.
  return /^\/audio\/(?:[A-Za-z0-9_-]+\/)*[A-Za-z0-9_-]+\.(?:wav|mp3|ogg|m4a)$/.test(value)
    ? APP_BASE + value.substring(1) : '';
}
