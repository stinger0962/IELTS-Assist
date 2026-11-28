import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AxiosHeaders } from 'axios';
import type { AxiosResponse } from 'axios';
import { MemoryRouter } from 'react-router-dom';
import '../i18n';
import i18n from '../i18n';
import StudyPassCheckout, { checkoutNavigation } from '../components/StudyPassCheckout';
import CheckoutReturn from '../pages/CheckoutReturn';
import { checkoutAPI, checkoutReturnPath, isCheckoutOffer, safeStripeCheckoutUrl } from '../api/checkout';
import { api } from '../api';
import { CHECKOUT_ATTEMPT_TTL_MS } from '../utils/checkoutAttempt';
import { useAppStore } from '../store';
import * as deployment from '../deployment';

const response = (data: unknown): AxiosResponse => ({ data, status: 200, statusText: 'OK', headers: {}, config: { headers: new AxiosHeaders() } });
const id = '1cc2ab9b-dd41-4c33-aaa1-f1ba2e9c8bb1';
const offer = { enabled: true, test_mode: true, sku: 'test-pass', amount_minor: 1200, currency: 'USD', reviews: 10, duration_days: 30 };
const order = { id, state: 'pending', checkout_url: 'https://checkout.stripe.com/c/pay/cs_test_fixture', test_mode: true };
const pass = { enabled: true, status: 'active', expires_at: null, writing_reviews_remaining: 10, full_mock_access: true };

beforeEach(async () => {
  await i18n.changeLanguage('en');
  sessionStorage.clear();
  useAppStore.setState({ token: 'test-token', user: { id: 11, email: 'test@example.test', username: 'test', role: 'free', target_band: 7, preferred_language: 'en', created_at: '2026-01-01' } });
  vi.spyOn(checkoutNavigation, 'assign').mockImplementation(() => {});
  vi.spyOn(checkoutAPI, 'offer').mockResolvedValue(response(offer));
  vi.spyOn(api, 'get').mockResolvedValue(response(pass));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('Test checkout offer', () => {
  it.each([null, { enabled: false, test_mode: true }, { ...offer, test_mode: false }])('has no checkout when unavailable or non-test', async value => {
    vi.mocked(checkoutAPI.offer).mockResolvedValue(response(value));
    render(<StudyPassCheckout />);
    await act(async () => {});
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.getByText(/Purchasing is not available/)).toBeInTheDocument();
  });
  it('displays server offered test price and opens only validated hosted URL', async () => {
    const create = vi.spyOn(checkoutAPI, 'create').mockResolvedValue(response(order));
    render(<StudyPassCheckout />);
    fireEvent.click(await screen.findByRole('button', { name: 'Open Stripe test checkout' }));
    expect(screen.getByText(/\$12.00 USD test amount/)).toBeInTheDocument();
    expect(screen.getByText(/No actual charge/)).toBeInTheDocument();
    await waitFor(() => expect(checkoutNavigation.assign).toHaveBeenCalledWith(order.checkout_url));
    expect(create).toHaveBeenCalledWith(expect.any(String));
    expect(create).toHaveBeenCalledTimes(1);
  });
  it('keeps idempotency key on retry and ignores repeated in-flight clicks', async () => {
    let fail!: (value: unknown) => void;
    const create = vi.spyOn(checkoutAPI, 'create')
      .mockImplementationOnce(() => new Promise((_, reject) => { fail = reject; }))
      .mockRejectedValue(new Error('offline'));
    render(<StudyPassCheckout />);
    const button = await screen.findByRole('button', { name: 'Open Stripe test checkout' });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(create).toHaveBeenCalledTimes(1);
    await act(async () => { fail(new Error('offline')); });
    fireEvent.click(button);
    await screen.findByRole('alert');
    expect(create).toHaveBeenCalledTimes(2);
    expect(create.mock.calls[1][0]).toBe(create.mock.calls[0][0]);
  });
  it('uses the app base for the terminal receipt on an idempotent replay', async () => {
    const qualified = vi.spyOn(deployment, 'appPath').mockImplementation(path => '/__ielts-billing-test' + path);
    const create = vi.spyOn(checkoutAPI, 'create').mockRejectedValueOnce(new Error('lost response'))
      .mockResolvedValue(response({ ...order, state: 'fulfilled', checkout_url: null }));
    render(<StudyPassCheckout />);
    fireEvent.click(await screen.findByRole('button', { name: 'Open Stripe test checkout' }));
    await screen.findByRole('alert');
    fireEvent.click(screen.getByRole('button', { name: 'Check previous test checkout' }));
    await waitFor(() => expect(checkoutNavigation.assign).toHaveBeenCalledWith('/__ielts-billing-test/checkout/return?order_id=' + id));
    expect(qualified).toHaveBeenCalledWith('/checkout/return?order_id=' + id);
    expect(create.mock.calls[0][0]).toBe(create.mock.calls[1][0]);
  });
  it('does not start checkout while an essay exists', async () => {
    const create = vi.spyOn(checkoutAPI, 'create');
    render(<StudyPassCheckout hasDraft />);
    const button = await screen.findByRole('button', { name: 'Open Stripe test checkout' });
    expect(button).toBeDisabled();
    expect(screen.getByText(/Keep or copy your work/)).toBeInTheDocument();
    fireEvent.click(button);
    expect(create).not.toHaveBeenCalled();
  });
  it('does not leave if a draft is typed during order creation', async () => {
    let resolve!: (value: AxiosResponse) => void;
    vi.spyOn(checkoutAPI, 'create').mockImplementationOnce(() => new Promise(r => { resolve = r; }));
    const { rerender } = render(<StudyPassCheckout />);
    fireEvent.click(await screen.findByRole('button', { name: 'Open Stripe test checkout' }));
    rerender(<StudyPassCheckout hasDraft />);
    await act(async () => { resolve(response(order)); });
    expect(checkoutNavigation.assign).not.toHaveBeenCalled();
  });
  it('does not leave after logout while creating an order', async () => {
    let resolve!: (value: AxiosResponse) => void;
    vi.spyOn(checkoutAPI, 'create').mockImplementationOnce(() => new Promise(r => { resolve = r; }));
    render(<StudyPassCheckout />);
    fireEvent.click(await screen.findByRole('button', { name: 'Open Stripe test checkout' }));
    act(() => useAppStore.setState({ token: null }));
    await act(async () => { resolve(response(order)); });
    expect(checkoutNavigation.assign).not.toHaveBeenCalled();
  });
  it('rejects a non-test order or unsafe redirect without navigation', async () => {
    vi.spyOn(checkoutAPI, 'create').mockResolvedValue(response({ ...order, checkout_url: 'https://checkout.stripe.com.evil.test/pay' }));
    render(<StudyPassCheckout />);
    fireEvent.click(await screen.findByRole('button', { name: 'Open Stripe test checkout' }));
    await screen.findByRole('alert');
    expect(checkoutNavigation.assign).not.toHaveBeenCalled();
  });
  it('recovers the same request key after remount without automatic checkout', async () => {
    const create = vi.spyOn(checkoutAPI, 'create').mockResolvedValue(response(order));
    const first = render(<StudyPassCheckout />);
    fireEvent.click(await screen.findByRole('button', { name: 'Open Stripe test checkout' }));
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    const originalKey = create.mock.calls[0][0];
    first.unmount();
    vi.mocked(checkoutNavigation.assign).mockClear();
    render(<StudyPassCheckout />);
    await screen.findByRole('button', { name: 'Check previous test checkout' });
    expect(create).toHaveBeenCalledTimes(1);
    expect(checkoutNavigation.assign).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Check previous test checkout' }));
    const resume = await screen.findByRole('button', { name: 'Resume existing test checkout' });
    expect(create.mock.calls[1][0]).toBe(originalKey);
    expect(checkoutNavigation.assign).not.toHaveBeenCalled();
    fireEvent.click(resume);
    expect(checkoutNavigation.assign).toHaveBeenCalledWith(order.checkout_url);
    expect(create).toHaveBeenCalledTimes(2);
  });
  it('isolates request keys across account switches and restores the original account key', async () => {
    const create = vi.spyOn(checkoutAPI, 'create').mockRejectedValue(new Error('offline'));
    render(<StudyPassCheckout />);
    fireEvent.click(await screen.findByRole('button', { name: 'Open Stripe test checkout' }));
    await screen.findByRole('alert');
    const originalKey = create.mock.calls[0][0];
    act(() => useAppStore.setState({ user: { ...useAppStore.getState().user!, id: 22 } }));
    fireEvent.click(await screen.findByRole('button', { name: 'Open Stripe test checkout' }));
    await screen.findByRole('alert');
    expect(create.mock.calls[1][0]).not.toBe(originalKey);
    act(() => useAppStore.setState({ user: { ...useAppStore.getState().user!, id: 11 } }));
    fireEvent.click(await screen.findByRole('button', { name: 'Check previous test checkout' }));
    await screen.findByRole('alert');
    expect(create.mock.calls[2][0]).toBe(originalKey);
  });
  it('does not rotate an expired attempt into a fresh request', async () => {
    const create = vi.spyOn(checkoutAPI, 'create').mockRejectedValue(new Error('offline'));
    const first = render(<StudyPassCheckout />);
    fireEvent.click(await screen.findByRole('button', { name: 'Open Stripe test checkout' }));
    await screen.findByRole('alert');
    first.unmount();
    const key = sessionStorage.key(0)!;
    const record = JSON.parse(sessionStorage.getItem(key)!);
    sessionStorage.setItem(key, JSON.stringify({ ...record, createdAt: Date.now() - CHECKOUT_ATTEMPT_TTL_MS - 1 }));
    render(<StudyPassCheckout />);
    expect(await screen.findByRole('alert')).toHaveTextContent('needs recovery');
    expect(screen.getByRole('button', { name: 'Find existing test order' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Open Stripe test checkout' })).not.toBeInTheDocument();
    expect(create).toHaveBeenCalledTimes(1);
  });
  it('stops on a pending-order conflict instead of cycling new keys', async () => {
    const create = vi.spyOn(checkoutAPI, 'create').mockRejectedValue({ response: { status: 409 } });
    render(<StudyPassCheckout />);
    fireEvent.click(await screen.findByRole('button', { name: 'Open Stripe test checkout' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('needs recovery');
    expect(screen.getByRole('button', { name: 'Find existing test order' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Open Stripe test checkout' })).not.toBeInTheDocument();
    expect(create).toHaveBeenCalledTimes(1);
  });
  it('recovers a conflicting order without creating another checkout or visiting Stripe', async () => {
    const create = vi.spyOn(checkoutAPI, 'create').mockRejectedValue({ response: { status: 409 } });
    const current = vi.spyOn(checkoutAPI, 'current').mockResolvedValue(response({ id, test_mode: true }));
    vi.spyOn(deployment, 'appPath').mockImplementation(path => '/__ielts-billing-test' + path);
    render(<StudyPassCheckout />);
    fireEvent.click(await screen.findByRole('button', { name: 'Open Stripe test checkout' }));
    const find = await screen.findByRole('button', { name: 'Find existing test order' });
    expect(current).not.toHaveBeenCalled();
    fireEvent.click(find);
    fireEvent.click(find);
    await waitFor(() => expect(checkoutNavigation.assign).toHaveBeenCalledWith('/__ielts-billing-test/checkout/return?order_id=' + id));
    expect(create).toHaveBeenCalledTimes(1);
    expect(current).toHaveBeenCalledTimes(1);
  });
  it.each([null, { id, test_mode: false }, { id: '//example.test', test_mode: true }])(
    'keeps payment blocked when order recovery cannot be confirmed', async data => {
      const create = vi.spyOn(checkoutAPI, 'create').mockRejectedValue({ response: { status: 409 } });
      vi.spyOn(checkoutAPI, 'current').mockResolvedValue(response(data));
      render(<StudyPassCheckout />);
      fireEvent.click(await screen.findByRole('button', { name: 'Open Stripe test checkout' }));
      fireEvent.click(await screen.findByRole('button', { name: 'Find existing test order' }));
      expect(await screen.findByRole('status')).toHaveTextContent('Could not verify an existing test order');
      expect(checkoutNavigation.assign).not.toHaveBeenCalled();
      expect(create).toHaveBeenCalledTimes(1);
    });
  it('ignores a recovery lookup that returns after logout', async () => {
    vi.spyOn(checkoutAPI, 'create').mockRejectedValue({ response: { status: 409 } });
    let resolve!: (value: AxiosResponse) => void;
    vi.spyOn(checkoutAPI, 'current').mockImplementationOnce(() => new Promise(r => { resolve = r; }));
    render(<StudyPassCheckout />);
    fireEvent.click(await screen.findByRole('button', { name: 'Open Stripe test checkout' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Find existing test order' }));
    act(() => useAppStore.setState({ token: null }));
    await act(async () => { resolve(response({ id, test_mode: true })); });
    expect(checkoutNavigation.assign).not.toHaveBeenCalled();
  });
  it('stores only opaque request and time, never token, draft or redirect', async () => {
    vi.spyOn(checkoutAPI, 'create').mockResolvedValue(response(order));
    render(<StudyPassCheckout />);
    fireEvent.click(await screen.findByRole('button', { name: 'Open Stripe test checkout' }));
    await waitFor(() => expect(checkoutNavigation.assign).toHaveBeenCalled());
    const raw = sessionStorage.getItem(sessionStorage.key(0)!)!;
    expect(Object.keys(JSON.parse(raw)).sort()).toEqual(['createdAt', 'key']);
    expect(raw).not.toContain('test-token');
    expect(raw).not.toContain('checkout.stripe.com');
  });
  it('supports Chinese checkout copy', async () => {
    await i18n.changeLanguage('zh');
    render(<StudyPassCheckout />);
    expect(await screen.findByRole('button', { name: '打开 Stripe 测试结账' })).toBeInTheDocument();
    expect(screen.getByText(/不会实际扣款/)).toBeInTheDocument();
  });
});

describe('Checkout request deadlines', () => {
  it('sets finite deadlines on the actual client and preserves the create key', async () => {
    const read = vi.mocked(api.get);
    const create = vi.spyOn(api, 'post').mockResolvedValue(response(order));
    vi.mocked(checkoutAPI.offer).mockRestore();
    await checkoutAPI.offer();
    await checkoutAPI.status(id);
    await checkoutAPI.current();
    await checkoutAPI.create(id);
    expect(read).toHaveBeenCalledWith('/checkout/offer', { timeout: 8_000 });
    expect(read).toHaveBeenCalledWith('/checkout/orders/' + id, { timeout: 8_000 });
    expect(read).toHaveBeenCalledWith('/checkout/orders/current', { timeout: 8_000 });
    expect(create).toHaveBeenCalledWith('/checkout/orders', { idempotency_key: id }, { timeout: 30_000 });
  });
});

describe('Owned checkout return', () => {
  it('shows pending, then refreshed server fulfillment without creating or granting', async () => {
    const status = vi.spyOn(checkoutAPI, 'status').mockResolvedValueOnce(response(order)).mockResolvedValue(response({ ...order, state: 'fulfilled', checkout_url: null }));
    const create = vi.spyOn(checkoutAPI, 'create');
    render(<MemoryRouter initialEntries={['/checkout/return?order_id=' + id]}><CheckoutReturn /></MemoryRouter>);
    expect(await screen.findByText(/Payment confirmation is pending/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Check again' }));
    expect(await screen.findByText(/Test order fulfilled/)).toBeInTheDocument();
    expect(status).toHaveBeenCalledWith(id);
    expect(create).not.toHaveBeenCalled();
    expect(checkoutNavigation.assign).not.toHaveBeenCalled();
  });
  it('cancel displays closed and relies on real order status, never grants', async () => {
    vi.spyOn(checkoutAPI, 'status').mockResolvedValue(response(order));
    const create = vi.spyOn(checkoutAPI, 'create');
    render(<MemoryRouter initialEntries={['/checkout/cancel?order_id=' + id]}><CheckoutReturn /></MemoryRouter>);
    expect(await screen.findByText(/Payment confirmation is pending/)).toBeInTheDocument();
    expect(screen.getByText(/Returning to this page does not activate/)).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Resume existing test checkout' }));
    expect(checkoutNavigation.assign).toHaveBeenCalledWith(order.checkout_url);
    expect(create).not.toHaveBeenCalled();
  });
  it('does not report fulfillment when order is missing or unauthorized', async () => {
    vi.spyOn(checkoutAPI, 'status').mockRejectedValue({ response: { status: 404 } });
    render(<MemoryRouter initialEntries={['/checkout/return?order_id=' + id]}><CheckoutReturn /></MemoryRouter>);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not verify');
    expect(screen.queryByText(/Test order fulfilled/)).not.toBeInTheDocument();
  });
  it('after a network deadline can manually check the same order without starting checkout', async () => {
    const status = vi.spyOn(checkoutAPI, 'status')
      .mockRejectedValueOnce(Object.assign(new Error('timeout'), { code: 'ECONNABORTED' }))
      .mockResolvedValue(response({ ...order, state: 'fulfilled', checkout_url: null }));
    const create = vi.spyOn(checkoutAPI, 'create');
    render(<MemoryRouter initialEntries={['/checkout/return?order_id=' + id]}><CheckoutReturn /></MemoryRouter>);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not verify');
    const retry = screen.getByRole('button', { name: 'Check again' });
    expect(retry).toBeEnabled();
    fireEvent.click(retry);
    expect(await screen.findByText(/Test order fulfilled/)).toBeInTheDocument();
    expect(status.mock.calls).toEqual([[id], [id]]);
    expect(create).not.toHaveBeenCalled();
    expect(checkoutNavigation.assign).not.toHaveBeenCalled();
  });
  it('requires authentication and preserves a bounded login return link', () => {
    useAppStore.setState({ token: null });
    const status = vi.spyOn(checkoutAPI, 'status');
    render(<MemoryRouter initialEntries={['/checkout/return?order_id=' + id]}><CheckoutReturn /></MemoryRouter>);
    const link = screen.getByRole('link', { name: 'Sign in to check your test order' });
    expect(link).toHaveAttribute('href', '/login?returnTo=' + encodeURIComponent('/checkout/return?order_id=' + id));
    expect(status).not.toHaveBeenCalled();
  });
});

describe('Checkout boundaries', () => {
  it('rejects redirect lookalikes and credential URLs', () => {
    for (const url of ['javascript:alert(1)', '//checkout.stripe.com/pay', 'http://checkout.stripe.com/pay', 'https://evil.test/pay', 'https://checkout.stripe.com.evil.test/pay', 'https://user:pass@checkout.stripe.com/pay']) {
      expect(safeStripeCheckoutUrl(url)).toBeNull();
    }
    expect(safeStripeCheckoutUrl(order.checkout_url)).toBe(order.checkout_url);
  });
  it('rejects live, missing and invalid price data', () => {
    expect(isCheckoutOffer(offer)).toBe(true);
    expect(isCheckoutOffer({ ...offer, test_mode: false })).toBe(false);
    expect(isCheckoutOffer({ ...offer, amount_minor: -1 })).toBe(false);
    expect(isCheckoutOffer({ ...offer, currency: 'EUR' })).toBe(false);
  });
  it('only allows known order return paths through login', () => {
    expect(checkoutReturnPath('/checkout/return?order_id=' + id)).toBe('/checkout/return?order_id=' + id);
    expect(checkoutReturnPath('https://evil.test/checkout/return?order_id=' + id)).toBeNull();
    expect(checkoutReturnPath('//evil.test')).toBeNull();
    expect(checkoutReturnPath('/checkout/return?order_id=' + id + '&success=true')).toBeNull();
  });
});
