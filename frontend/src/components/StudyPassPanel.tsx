import { useTranslation } from 'react-i18next';
import type { StudyPassStatus } from '../hooks/useStudyPass';

export default function StudyPassPanel({ status }: { status: StudyPassStatus | null }) {
  const { t, i18n } = useTranslation();
  if (!status?.enabled) return null;
  return (
    <section className="study-pass" aria-label={t('studyPass.title')}>
      <h3>{t('studyPass.title')}</h3>
      <p>{t('studyPass.description')}</p>
      {status.status === 'active' ? (
        <p role="status">
          {t('studyPass.active')}
          {status.expires_at && <> · {t('studyPass.expires', { date: new Date(status.expires_at).toLocaleDateString(i18n.language) })}</>}
          {status.writing_reviews_remaining !== null && <> · {t('studyPass.remaining', { count: status.writing_reviews_remaining })}</>}
        </p>
      ) : (
        <div>
          {status.status === 'expired' && <p>{t('studyPass.expired')}</p>}
          <p>{status.writing_reviews_remaining === null && status.full_mock_access
            ? t('studyPass.legacy')
            : status.writing_reviews_remaining === 0 ? t('studyPass.usedTrial') : t('studyPass.trial')}</p>
        </div>
      )}
      <details>
        <summary>{t('studyPass.details')}</summary>
        <ul>
          <li>{t('studyPass.mocks')}</li>
          <li>{t('studyPass.reviews')}</li>
          <li>{t('studyPass.basic')}</li>
        </ul>
        <p>{t('studyPass.unavailable')}</p>
        <p>{t('studyPass.disclaimer')}</p>
      </details>
      <style>{`
        .study-pass { padding: 16px; margin: 12px 0; border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-surface); overflow-wrap: anywhere; text-align: left; }
        .study-pass h3 { margin: 0 0 8px; font-size: 1rem; }
        .study-pass p, .study-pass li { font-size: .875rem; line-height: 1.6; margin: 8px 0; }
        .study-pass summary { cursor: pointer; padding: 12px 0; min-height: 44px; }
        .study-pass ul { padding-left: 20px; }
      `}</style>
    </section>
  );
}
