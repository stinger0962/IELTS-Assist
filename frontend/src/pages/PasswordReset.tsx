import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Mail, Lock, ArrowLeft } from 'lucide-react';
import { authAPI } from '../api';

/**
 * Request a reset link.
 *
 * The backend deliberately answers identically whether or not the address is
 * registered, so this screen must not imply otherwise — saying "no such
 * account" here would reintroduce the account-enumeration leak the API avoids.
 */
export function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await authAPI.forgotPassword(email);
    } catch {
      // Deliberately ignored: a failure here would reveal server-side state.
    } finally {
      setLoading(false);
      setSent(true);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <h1>Reset your password</h1>
          <p>We'll email you a link to choose a new one</p>
        </div>

        {sent ? (
          <div className="auth-form">
            <p style={{ lineHeight: 1.6 }}>
              If <strong>{email}</strong> is registered, a reset link is on its way.
              The link expires in an hour and can be used once.
            </p>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
              Nothing arrived? Check your spam folder, then try again.
            </p>
            <Link to="/login" className="btn btn-primary" style={{ textAlign: 'center' }}>
              Back to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-group">
              <label className="form-label">Email</label>
              <div className="input-with-icon">
                <Mail size={18} />
                <input
                  type="email"
                  className="form-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  required
                  autoFocus
                />
              </div>
            </div>

            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Sending…' : 'Send reset link'}
            </button>

            <p className="auth-footer">
              <Link to="/login">
                <ArrowLeft size={14} style={{ verticalAlign: 'middle' }} /> Back to sign in
              </Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}

/** Choose a new password using the token from the emailed link. */
export function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token') || '';

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password.length < 8) {
      setError('Please use at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setError('Those passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      await authAPI.resetPassword(token, password);
      // Any existing session is invalidated server-side, so sign in again.
      navigate('/login?reset=1');
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
        'This reset link is invalid or has expired. Please request a new one.'
      );
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <div className="auth-header">
            <h1>Link incomplete</h1>
            <p>That reset link is missing its token.</p>
          </div>
          <div className="auth-form">
            <Link to="/forgot-password" className="btn btn-primary" style={{ textAlign: 'center' }}>
              Request a new link
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <h1>Choose a new password</h1>
          <p>You'll sign in again once it's saved</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="auth-error">{error}</div>}

          <div className="form-group">
            <label className="form-label">New password</label>
            <div className="input-with-icon">
              <Lock size={18} />
              <input
                type="password"
                className="form-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                required
                autoFocus
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Confirm new password</label>
            <div className="input-with-icon">
              <Lock size={18} />
              <input
                type="password"
                className="form-input"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Type it again"
                required
              />
            </div>
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Saving…' : 'Save new password'}
          </button>

          <p className="auth-footer">
            <Link to="/login">Back to sign in</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
