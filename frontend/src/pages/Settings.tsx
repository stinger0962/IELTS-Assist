import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Sun, Moon, Globe, Target, Calendar } from 'lucide-react';
import { useAppStore } from '../store';
import { authAPI } from '../api';

export default function Settings() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme, language, setLanguage, user, setAuth } = useAppStore();
  const [formData, setFormData] = useState({
    target_band: user?.target_band || 7.0,
    test_date: user?.test_date ? new Date(user.test_date).toISOString().split('T')[0] : '',
    preferred_language: user?.preferred_language || 'en',
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (user) {
      setFormData({
        target_band: user.target_band,
        test_date: user.test_date ? new Date(user.test_date).toISOString().split('T')[0] : '',
        preferred_language: user.preferred_language,
      });
    }
  }, [user]);

  const handleSave = async () => {
    setSaving(true);
    setMessage('');
    try {
      const res = await authAPI.updateSettings({
        target_band: formData.target_band,
        test_date: formData.test_date || undefined,
        preferred_language: formData.preferred_language,
      });
      
      // Update store
      if (formData.preferred_language !== language) {
        setLanguage(formData.preferred_language as 'en' | 'zh');
        i18n.changeLanguage(formData.preferred_language);
      }
      
      setAuth(useAppStore.getState().token!, res.data);
      setMessage('Settings saved successfully!');
    } catch (error) {
      setMessage('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

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
      </div>

      <div className="settings-actions">
        <button 
          className="btn btn-primary btn-lg" 
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? 'Saving...' : t('settings.save')}
        </button>
        {message && (
          <span className={`message ${message.includes('Failed') ? 'error' : 'success'}`}>
            {message}
          </span>
        )}
      </div>

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

        .settings-actions {
          display: flex;
          align-items: center;
          gap: var(--spacing-md);
        }

        .message {
          font-size: 0.875rem;
        }

        .message.success {
          color: var(--color-success);
        }

        .message.error {
          color: var(--color-error);
        }
      `}</style>
    </div>
  );
}