import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, Link } from 'react-router-dom';
import { Mail, Lock, User } from 'lucide-react';
import { useAppStore } from '../store';
import { authAPI } from '../api';

export function Login() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { setAuth, setLanguage } = useAppStore();
  const [formData, setFormData] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const tokenRes = await authAPI.login(formData.email, formData.password);
      const userRes = await authAPI.me();
      
      setAuth(tokenRes.data.access_token, userRes.data);
      
      // Set language preference
      if (userRes.data.preferred_language) {
        setLanguage(userRes.data.preferred_language as 'en' | 'zh');
      }
      
      navigate('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <h1>{t('auth.login')}</h1>
          <p>Welcome back to IELTS Assist</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="auth-error">{error}</div>}
          
          <div className="form-group">
            <label className="form-label">{t('auth.email')}</label>
            <div className="input-with-icon">
              <Mail size={18} />
              <input
                type="email"
                className="form-input"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="your@email.com"
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">{t('auth.password')}</label>
            <div className="input-with-icon">
              <Lock size={18} />
              <input
                type="password"
                className="form-input"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                placeholder="••••••••"
                required
              />
            </div>
          </div>

          <button type="submit" className="btn btn-primary btn-lg" disabled={loading}>
            {loading ? 'Logging in...' : t('auth.login')}
          </button>
        </form>

        <p className="auth-footer">
          {t('auth.noAccount')} <Link to="/register">{t('auth.register')}</Link>
        </p>
      </div>

      <style>{`
        .auth-page {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: var(--spacing-lg);
          background: linear-gradient(135deg, var(--color-background) 0%, var(--color-surface) 100%);
        }

        .auth-card {
          width: 100%;
          max-width: 400px;
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-xl);
          padding: var(--spacing-2xl);
        }

        .auth-header {
          text-align: center;
          margin-bottom: var(--spacing-xl);
        }

        .auth-header h1 {
          margin-bottom: var(--spacing-xs);
        }

        .auth-header p {
          color: var(--color-text-secondary);
        }

        .auth-form {
          display: flex;
          flex-direction: column;
          gap: var(--spacing-md);
        }

        .auth-error {
          padding: var(--spacing-sm) var(--spacing-md);
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid var(--color-error);
          border-radius: var(--radius-md);
          color: var(--color-error);
          font-size: 0.875rem;
        }

        .input-with-icon {
          position: relative;
        }

        .input-with-icon svg {
          position: absolute;
          left: var(--spacing-md);
          top: 50%;
          transform: translateY(-50%);
          color: var(--color-text-secondary);
        }

        .input-with-icon .form-input {
          padding-left: 44px;
        }

        .auth-form .btn {
          margin-top: var(--spacing-md);
        }

        .auth-footer {
          text-align: center;
          margin-top: var(--spacing-lg);
          color: var(--color-text-secondary);
        }

        .auth-footer a {
          color: var(--color-primary);
          font-weight: 600;
        }
      `}</style>
    </div>
  );
}

export function Register() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { setAuth, setLanguage } = useAppStore();
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    password: '',
    full_name: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await authAPI.register(formData);
      
      // Auto login after register
      const tokenRes = await authAPI.login(formData.email, formData.password);
      const userRes = await authAPI.me();
      
      setAuth(tokenRes.data.access_token, userRes.data);
      setLanguage(userRes.data.preferred_language as 'en' | 'zh');
      
      navigate('/');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <h1>{t('auth.register')}</h1>
          <p>Start your IELTS journey</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="auth-error">{error}</div>}
          
          <div className="form-group">
            <label className="form-label">{t('auth.email')}</label>
            <div className="input-with-icon">
              <Mail size={18} />
              <input
                type="email"
                className="form-input"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="your@email.com"
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">{t('auth.username')}</label>
            <div className="input-with-icon">
              <User size={18} />
              <input
                type="text"
                className="form-input"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                placeholder="johndoe"
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">{t('auth.fullName')}</label>
            <div className="input-with-icon">
              <User size={18} />
              <input
                type="text"
                className="form-input"
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                placeholder="John Doe"
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">{t('auth.password')}</label>
            <div className="input-with-icon">
              <Lock size={18} />
              <input
                type="password"
                className="form-input"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                placeholder="••••••••"
                required
                minLength={6}
              />
            </div>
          </div>

          <button type="submit" className="btn btn-primary btn-lg" disabled={loading}>
            {loading ? 'Creating account...' : t('auth.register')}
          </button>
        </form>

        <p className="auth-footer">
          {t('auth.haveAccount')} <Link to="/login">{t('auth.login')}</Link>
        </p>
      </div>

      <style>{`
        .auth-page {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: var(--spacing-lg);
          background: linear-gradient(135deg, var(--color-background) 0%, var(--color-surface) 100%);
        }

        .auth-card {
          width: 100%;
          max-width: 400px;
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-xl);
          padding: var(--spacing-2xl);
        }

        .auth-header {
          text-align: center;
          margin-bottom: var(--spacing-xl);
        }

        .auth-header h1 {
          margin-bottom: var(--spacing-xs);
        }

        .auth-header p {
          color: var(--color-text-secondary);
        }

        .auth-form {
          display: flex;
          flex-direction: column;
          gap: var(--spacing-md);
        }

        .auth-error {
          padding: var(--spacing-sm) var(--spacing-md);
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid var(--color-error);
          border-radius: var(--radius-md);
          color: var(--color-error);
          font-size: 0.875rem;
        }

        .input-with-icon {
          position: relative;
        }

        .input-with-icon svg {
          position: absolute;
          left: var(--spacing-md);
          top: 50%;
          transform: translateY(-50%);
          color: var(--color-text-secondary);
        }

        .input-with-icon .form-input {
          padding-left: 44px;
        }

        .auth-form .btn {
          margin-top: var(--spacing-md);
        }

        .auth-footer {
          text-align: center;
          margin-top: var(--spacing-lg);
          color: var(--color-text-secondary);
        }

        .auth-footer a {
          color: var(--color-primary);
          font-weight: 600;
        }
      `}</style>
    </div>
  );
}