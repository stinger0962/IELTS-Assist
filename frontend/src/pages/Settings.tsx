import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Sun, Moon, Globe, Target, Calendar, Volume2, VolumeX, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../store';
import { authAPI } from '../api';
import { getSoundEnabled, setSoundEnabled, playClick } from '../hooks/useSoundEffects';

export default function Settings() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { theme, setTheme, language, setLanguage, user, setAuth, logout } = useAppStore();
  const [formData, setFormData] = useState({
    target_band: user?.target_band || 7.0,
    test_date: user?.test_date ? new Date(user.test_date).toISOString().split('T')[0] : '',
    preferred_language: user?.preferred_language || 'en',
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [soundOn, setSoundOn] = useState(getSoundEnabled());

  useEffect(() => {
    if (user) {
      setFormData({
        target_band: user.target_band,
        test_date: user.test_date ? new Date(user.test_date).toISOString().split('T')[0] : '',
        preferred_language: user.preferred_language,
      });
    }
  }, [user]);

  // Auto-save on change (debounced) — use ref to avoid re-trigger loops
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevFormRef = useRef(JSON.stringify(formData));

  useEffect(() => {
    const current = JSON.stringify(formData);
    if (current === prevFormRef.current) return; // no change
    prevFormRef.current = current;

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(async () => {
      setSaving(true);
      setMessage('');
      try {
        const res = await authAPI.updateSettings({
          target_band: formData.target_band,
          test_date: formData.test_date || undefined,
          preferred_language: formData.preferred_language,
        });
        if (formData.preferred_language !== language) {
          setLanguage(formData.preferred_language as 'en' | 'zh');
          i18n.changeLanguage(formData.preferred_language);
        }
        setAuth(useAppStore.getState().token!, res.data);
        setMessage('Saved');
        setTimeout(() => setMessage(''), 1500);
      } catch {
        setMessage('Failed to save');
      } finally {
        setSaving(false);
      }
    }, 600);
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current); };
  });

  return (
    <div className="settings-page">
      <header className="page-header">
        <h1>{t('settings.title')}</h1>
      </header>

      <div className="settings-grid">
        {/* Theme */}
        <div className="settings-card">
          <div className="settings-icon">
            {theme === 'light' ? <Sun size={24} /> : <Moon size={24} />}
          </div>
          <div className="settings-info">
            <h3>{t('settings.theme')}</h3>
            <p>Current: {theme === 'light' ? t('settings.light') : t('settings.dark')}</p>
          </div>
          <div className="settings-control">
            <button 
              className={`theme-btn ${theme === 'light' ? 'active' : ''}`}
              onClick={() => setTheme('light')}
            >
              <Sun size={18} />
              {t('settings.light')}
            </button>
            <button 
              className={`theme-btn ${theme === 'dark' ? 'active' : ''}`}
              onClick={() => setTheme('dark')}
            >
              <Moon size={18} />
              {t('settings.dark')}
            </button>
          </div>
        </div>

        {/* Language */}
        <div className="settings-card">
          <div className="settings-icon">
            <Globe size={24} />
          </div>
          <div className="settings-info">
            <h3>{t('settings.language')}</h3>
            <p>Select your preferred language</p>
          </div>
          <div className="settings-control">
            <button 
              className={`lang-btn ${formData.preferred_language === 'en' ? 'active' : ''}`}
              onClick={() => setFormData({ ...formData, preferred_language: 'en' })}
            >
              🇬🇧 English
            </button>
            <button 
              className={`lang-btn ${formData.preferred_language === 'zh' ? 'active' : ''}`}
              onClick={() => setFormData({ ...formData, preferred_language: 'zh' })}
            >
              🇨🇳 中文
            </button>
          </div>
        </div>

        {/* Target Band */}
        <div className="settings-card">
          <div className="settings-icon">
            <Target size={24} />
          </div>
          <div className="settings-info">
            <h3>{t('settings.targetBand')}</h3>
            <p>Your target IELTS band score</p>
          </div>
          <div className="settings-control">
            <input
              type="number"
              className="band-input"
              value={formData.target_band}
              onChange={(e) => setFormData({ ...formData, target_band: parseFloat(e.target.value) })}
              min={1}
              max={9}
              step={0.5}
            />
          </div>
        </div>

        {/* Test Date */}
        <div className="settings-card">
          <div className="settings-icon">
            <Calendar size={24} />
          </div>
          <div className="settings-info">
            <h3>{t('settings.testDate')}</h3>
            <p>Your scheduled test date</p>
          </div>
          <div className="settings-control">
            <input
              type="date"
              className="date-input"
              value={formData.test_date}
              onChange={(e) => setFormData({ ...formData, test_date: e.target.value })}
            />
          </div>
        </div>
        {/* Sound Effects */}
        <div className="settings-card">
          <div className="settings-icon">
            {soundOn ? <Volume2 size={24} /> : <VolumeX size={24} />}
          </div>
          <div className="settings-info">
            <h3>Sound Effects</h3>
            <p>Play sounds on interactions</p>
          </div>
          <div className="settings-control">
            <button
              className={`theme-btn ${soundOn ? 'active' : ''}`}
              onClick={() => { setSoundEnabled(true); setSoundOn(true); playClick(); }}
            >
              <Volume2 size={18} /> On
            </button>
            <button
              className={`theme-btn ${!soundOn ? 'active' : ''}`}
              onClick={() => { setSoundEnabled(false); setSoundOn(false); }}
            >
              <VolumeX size={18} /> Off
            </button>
          </div>
        </div>
      </div>

      {/* Auto-save status */}
      {(saving || message) && (
        <div className="settings-status">
          {saving ? <span className="saving-indicator">Saving...</span> : null}
          {message && (
            <span className={`message ${message.includes('Failed') ? 'error' : 'success'}`}>
              {message}
            </span>
          )}
        </div>
      )}

      {/* Logout */}
      <button className="logout-btn" onClick={() => { logout(); navigate('/login'); }}>
        <LogOut size={18} />
        <span>{t('auth.logout')}</span>
      </button>

      <style>{`
        .settings-page {
          max-width: 800px;
          margin: 0 auto;
        }

        .page-header {
          margin-bottom: var(--spacing-lg);
        }

        .settings-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: var(--spacing-md);
          margin-bottom: var(--spacing-xl);
        }

        @media (max-width: 768px) {
          .settings-grid {
            grid-template-columns: 1fr;
          }
        }

        .settings-card {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: var(--spacing-lg);
          display: flex;
          flex-direction: column;
          gap: var(--spacing-md);
        }

        .settings-icon {
          width: 48px;
          height: 48px;
          border-radius: var(--radius-md);
          background: var(--color-primary);
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .settings-info h3 {
          font-size: 1rem;
          margin-bottom: var(--spacing-xs);
        }

        .settings-info p {
          font-size: 0.875rem;
          color: var(--color-text-secondary);
        }

        .settings-control {
          display: flex;
          gap: var(--spacing-sm);
        }

        .theme-btn,
        .lang-btn {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--spacing-xs);
          padding: var(--spacing-sm) var(--spacing-md);
          background: var(--color-background);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          color: var(--color-text-secondary);
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .theme-btn:hover,
        .lang-btn:hover {
          border-color: var(--color-primary);
        }

        .theme-btn.active,
        .lang-btn.active {
          background: var(--color-primary);
          border-color: var(--color-primary);
          color: white;
        }

        .band-input,
        .date-input {
          width: 100%;
          padding: var(--spacing-sm) var(--spacing-md);
          background: var(--color-background);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          color: var(--color-text-primary);
          font-size: 1rem;
        }

        .settings-status {
          text-align: center;
          padding: var(--spacing-sm) 0;
          font-size: 0.8rem;
        }

        .saving-indicator {
          color: var(--color-text-secondary);
        }

        .message {
          font-size: 0.8rem;
        }

        .message.success {
          color: var(--color-success);
        }

        .message.error {
          color: var(--color-error);
        }

        .logout-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--spacing-sm);
          width: 100%;
          padding: var(--spacing-md);
          margin-top: var(--spacing-xl);
          background: none;
          border: 1px solid var(--color-error);
          border-radius: var(--radius-md);
          color: var(--color-error);
          font-size: 1rem;
          font-weight: 600;
          cursor: pointer;
          transition: all var(--transition-fast);
        }
        .logout-btn:hover {
          background: rgba(239, 68, 68, 0.08);
        }
      `}</style>
    </div>
  );
}