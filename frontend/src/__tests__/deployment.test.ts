import { afterEach, expect, it, vi } from 'vitest';

afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

it.each([
  { base: '/', prefix: '', api: 'https://custom.example/api', key: 'auth', audio: '/audio/sample.wav' },
  { base: '/__ielts-billing-test/', prefix: '/__ielts-billing-test',
    api: '/__ielts-billing-test/api', key: 'ielts-billing-test:auth',
    audio: '/__ielts-billing-test/audio/sample.wav' },
])('keeps the build’s API, audio, storage, and receipt in the right scope: $base', async ({ base, prefix, api, key, audio }) => {
  vi.stubEnv('BASE_URL', base);
  const deploy = await import('../deployment');
  expect(deploy.appPath('/checkout/return?order_id=fixture')).toBe(prefix + '/checkout/return?order_id=fixture');
  expect(deploy.sameOriginApiBase('https://custom.example/api')).toBe(api);
  expect(deploy.browserStorageKey('auth')).toBe(key);
  expect(deploy.practiceAudioUrl('/audio/sample.wav')).toBe(audio);
  if (prefix) expect(deploy.practiceAudioUrl('https://custom.example/sample.wav')).toBe('');
});
