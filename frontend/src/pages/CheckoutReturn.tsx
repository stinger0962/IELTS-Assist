import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { checkoutAPI, isCheckoutOrder, isOrderId, safeStripeCheckoutUrl } from '../api/checkout';
import type { CheckoutOrder } from '../api/checkout';
import { useAppStore } from '../store';
import { useStudyPass } from '../hooks/useStudyPass';
import { checkoutNavigation } from '../components/StudyPassCheckout';
import StudyPassPanel from '../components/StudyPassPanel';
import { clearExpiredCheckoutAttempt } from '../utils/checkoutAttempt';

export default function CheckoutReturn() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const location = useLocation();
  const token = useAppStore(state => state.token);
  const userId = useAppStore(state => state.user?.id);
  const orderId = params.get('order_id') || '';
  const canceled = location.pathname === '/checkout/cancel';
  const { status: pass, refresh } = useStudyPass();
  const [result, setResult] = useState<{ token: string; order: CheckoutOrder } | null>(null);
  const [error, setError] = useState(false);
  const [checking, setChecking] = useState(false);
  const generation = useRef(0);
  const inFlight = useRef(false);
  const terminal = useRef(false);
  const order = result?.token === token && result.order.id === orderId ? result.order : null;
  const check = useCallback(async () => {
    if (!token || !isOrderId(orderId) || inFlight.current) return;
    const request = generation.current;
    inFlight.current = true;
    setChecking(true);
    setError(false);
    try {
      const { data } = await checkoutAPI.status(orderId);
      if (request !== generation.current) return;
      if (!isCheckoutOrder(data) || data.id !== orderId) throw new Error('Invalid order');
      setResult({ token, order: data });
      terminal.current = data.state !== 'pending';
      if (data.state === 'expired' && userId !== undefined) clearExpiredCheckoutAttempt(userId, data.id);
      if (data.state === 'fulfilled' || data.state === 'refunded') void refresh();
    } catch {
      if (request === generation.current) { setError(true); setResult(null); }
    } finally {
      if (request === generation.current) {
        inFlight.current = false;
        setChecking(false);
      }
    }
  }, [token, userId, orderId, refresh]);

  useEffect(() => {
    ++generation.current;
    inFlight.current = false;
    terminal.current = false;
    setError(false);
    void check();
    // Bounded polling; use explicit refresh after 60s instead of polling indefinitely.
    let attempts = 0;
    const timer = window.setInterval(() => {
      if (terminal.current || ++attempts > 12) { window.clearInterval(timer); return; }
      void check();
    }, 5000);
    return () => { ++generation.current; window.clearInterval(timer); };
  }, [check]);

  return (
    <section className="study-pass" style={{ maxWidth: 640, margin: '24px auto', padding: 20 }}>
      <h1>{t('checkout.returnTitle')}</h1>
      <p>{t('checkout.testOnly')}</p>
      {canceled && <p>{t('checkout.canceled')}</p>}
      {!isOrderId(orderId) ? <p role="alert">{t('checkout.invalid')}</p> : !token ? (
        <p><Link to={'/login?returnTo=' + encodeURIComponent(location.pathname + '?order_id=' + orderId)}>{t('checkout.signIn')}</Link></p>
      ) : <>
        <p role="status">{order ? t('checkout.' + order.state) : !error ? t('checkout.checking') : t('checkout.unknown')}</p>
        {error && <p role="alert">{t('checkout.checkFailed')}</p>}
        <button type="button" className="btn btn-primary" disabled={checking} onClick={() => { void check(); }}>{t('checkout.refresh')}</button>
        {order?.state === 'pending' && safeStripeCheckoutUrl(order.checkout_url) && (
          <button type="button" className="btn" disabled={checking} onClick={() => {
            const url = safeStripeCheckoutUrl(order.checkout_url);
            if (url) checkoutNavigation.assign(url);
          }}>{t('checkout.resume')}</button>
        )}
        {order?.state === 'fulfilled' && <StudyPassPanel status={pass} />}
      </>}
      <p><Link to="/practice">{t(order?.state === 'expired' ? 'checkout.reviewOffer' : 'checkout.back')}</Link></p>
    </section>
  );
}
