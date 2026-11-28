import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { checkoutAPI, isCheckoutOffer, isCheckoutOrder, isOrderId, safeStripeCheckoutUrl } from '../api/checkout';
import { obtainCheckoutAttempt, readCheckoutAttempt } from '../utils/checkoutAttempt';
import type { CheckoutOffer } from '../api/checkout';
import { useAppStore } from '../store';
import { appPath } from '../deployment';

export const checkoutNavigation = { assign: (url: string) => window.location.assign(url) };

export default function StudyPassCheckout({ hasDraft = false }: { hasDraft?: boolean }) {
  const { t, i18n } = useTranslation();
  const token = useAppStore(state => state.token);
  const userId = useAppStore(state => state.user?.id);
  const draftRef = useRef(hasDraft);
  draftRef.current = hasDraft;
  const [offerState, setOfferState] = useState<{ token: string; userId: number; offer: CheckoutOffer } | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [recoveryFailed, setRecoveryFailed] = useState(false);
  const [previous, setPrevious] = useState(false);
  const [resumeUrl, setResumeUrl] = useState<string | null>(null);
  const generation = useRef(0);
  const inFlight = useRef(false);
  const offer = offerState?.token === token && offerState.userId === userId ? offerState.offer : null;

  useEffect(() => {
    const generationId = ++generation.current;
    setOfferState(null);
    setResumeUrl(null);
    setBlocked(false);
    setRecoveryFailed(false);
    setPrevious(false);
    inFlight.current = false;
    setBusy(false);
    setFailed(false);
    if (token && userId !== undefined) {
      void checkoutAPI.offer().then(({ data }) => {
        if (generation.current === generationId && isCheckoutOffer(data)) {
          setOfferState({ token, userId, offer: data });
          const attempt = readCheckoutAttempt(userId, data);
          setPrevious(attempt.kind === 'ready');
          setBlocked(attempt.kind === 'blocked');
        }
      }).catch(() => { /* Missing/off endpoint keeps purchasing unavailable. */ });
    }
    return () => { ++generation.current; };
  }, [token, userId]);

  const begin = async () => {
    if (!offer || userId === undefined || hasDraft || blocked || inFlight.current) return;
    if (resumeUrl) { checkoutNavigation.assign(resumeUrl); return; }
    inFlight.current = true;
    setBusy(true);
    setFailed(false);
    const generationId = generation.current;
    try {
      const attempt = obtainCheckoutAttempt(userId, offer);
      setPrevious(true);
      const { data } = await checkoutAPI.create(attempt.key);
      if (generationId !== generation.current || draftRef.current) return;
      if (!isCheckoutOrder(data)) throw new Error('Invalid checkout response');
      if (data.state !== 'pending') {
        checkoutNavigation.assign(appPath(`/checkout/return?order_id=${encodeURIComponent(data.id)}`));
        return;
      }
      const url = safeStripeCheckoutUrl(data.checkout_url);
      if (!url) throw new Error('Invalid checkout destination');
      if (attempt.recovered) setResumeUrl(url);
      else checkoutNavigation.assign(url);
    } catch (error: unknown) {
      if (generationId === generation.current) {
        const conflict = (error as { response?: { status?: number } })?.response?.status === 409;
        const stale = readCheckoutAttempt(userId, offer).kind === 'blocked';
        if (conflict || stale) setBlocked(true);
        else setFailed(true);
      }
    } finally {
      if (generationId === generation.current) {
        inFlight.current = false;
        setBusy(false);
      }
    }
  };

  const recover = async () => {
    if (!offer || hasDraft || !blocked || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setRecoveryFailed(false);
    const generationId = generation.current;
    try {
      const { data } = await checkoutAPI.current();
      if (generationId !== generation.current || draftRef.current) return;
      if (data?.test_mode !== true || typeof data.id !== 'string' || !isOrderId(data.id)) {
        throw new Error('Invalid recovery response');
      }
      checkoutNavigation.assign(appPath(`/checkout/return?order_id=${encodeURIComponent(data.id)}`));
    } catch {
      if (generationId === generation.current) setRecoveryFailed(true);
    } finally {
      if (generationId === generation.current) {
        inFlight.current = false;
        setBusy(false);
      }
    }
  };

  if (!offer) return <p>{t('studyPass.unavailable')}</p>;
  const amount = new Intl.NumberFormat(i18n.language, { style: 'currency', currency: offer.currency }).format(offer.amount_minor / 100);
  return (
    <div className="study-pass-checkout">
      <p><strong>{t('checkout.testOnly')}</strong></p>
      <p>{t('checkout.offer', { amount, currency: offer.currency, count: offer.reviews })}</p>
      {hasDraft && <p role="status">{t('checkout.keepDraft')}</p>}
      {previous && !resumeUrl && !blocked && <p role="status">{t('checkout.previous')}</p>}
      {resumeUrl && <p role="status">{t('checkout.pending')}</p>}
      {blocked && <p role="alert">{t('checkout.recovery')}</p>}
      {failed && <p role="alert">{t('checkout.failed')}</p>}
      {recoveryFailed && <p role="status">{t('checkout.findFailed')}</p>}
      {blocked ? (
        <button type="button" className="btn btn-primary" onClick={() => { void recover(); }} disabled={busy || hasDraft}>
          {busy ? t('checkout.checking') : t('checkout.findExisting')}
        </button>
      ) : (
        <button type="button" className="btn btn-primary" onClick={() => { void begin(); }} disabled={busy || hasDraft}>
          {busy ? t('checkout.opening') : resumeUrl ? t('checkout.resume') : previous ? t('checkout.recheck') : t('checkout.start')}
        </button>
      )}
    </div>
  );
}
