import { NavLink, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { 
  LayoutDashboard, 
  BookOpen, 
  AlertCircle, 
  Target, 
  GraduationCap,
  Settings, 
  LogOut,
  Sun,
  Moon,
  Menu,
  X
} from 'lucide-react';
import { useAppStore } from '../store';
import { useState } from 'react';

const navItems = [
  { path: '/', icon: LayoutDashboard, labelKey: 'nav.dashboard' },
  { path: '/practice', icon: BookOpen, labelKey: 'nav.practice' },
  { path: '/mistakes', icon: AlertCircle, labelKey: 'nav.mistakes' },
  { path: '/topics', icon: GraduationCap, labelKey: 'nav.topics' },
  { path: '/goals', icon: Target, labelKey: 'nav.goals' },
  { path: '/settings', icon: Settings, labelKey: 'nav.settings' },
];

export default function Sidebar() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { theme, setTheme, language, setLanguage, logout, user } = useAppStore();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const toggleLanguage = () => {
    const newLang = language === 'en' ? 'zh' : 'en';
    setLanguage(newLang);
    i18n.changeLanguage(newLang);
  };

  const toggleTheme = () => {
    setTheme(theme === 'light' ? 'dark' : 'light');
  };

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `sidebar-link ${isActive ? 'active' : ''}`;

  return (
    <>
      {/* Mobile menu button */}
      <button className="mobile-menu-btn" onClick={() => setMobileOpen(!mobileOpen)}>
        {mobileOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* Overlay for mobile */}
      {mobileOpen && (
        <div className="sidebar-overlay" onClick={() => setMobileOpen(false)} />
      )}

      <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="logo">
            <GraduationCap size={32} />
            <span className="logo-text">{t('app.name')}</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink key={item.path} to={item.path} className={navLinkClass} onClick={() => setMobileOpen(false)}>
              <item.icon size={20} />
              <span>{t(item.labelKey)}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-controls">
            <button className="sidebar-btn" onClick={toggleLanguage} title={t('settings.language')}>
              <span className="lang-icon">{language === 'en' ? '中' : 'EN'}</span>
              <span>{language === 'en' ? '中文' : 'English'}</span>
            </button>
            <button className="sidebar-btn" onClick={toggleTheme} title={t('settings.theme')}>
              {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
              <span>{theme === 'light' ? t('settings.dark') : t('settings.light')}</span>
            </button>
          </div>
          
          {user && (
            <div className="user-info">
              <div className="user-avatar">
                {user.username?.charAt(0).toUpperCase()}
              </div>
              <div className="user-details">
                <span className="user-name">{user.username}</span>
                <span className="user-email">{user.email}</span>
              </div>
            </div>
          )}
          
          <button className="sidebar-btn logout-btn" onClick={handleLogout}>
            <LogOut size={20} />
            <span>{t('auth.logout')}</span>
          </button>
        </div>
      </aside>

      <style>{`
        .sidebar {
          position: fixed;
          left: 0;
          top: 0;
          bottom: 0;
          width: var(--sidebar-width);
          background-color: var(--color-surface);
          border-right: 1px solid var(--color-border);
          display: flex;
          flex-direction: column;
          z-index: 100;
          transition: transform var(--transition-normal);
        }

        .mobile-menu-btn {
          display: none;
          position: fixed;
          top: var(--spacing-md);
          left: var(--spacing-md);
          z-index: 101;
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          padding: var(--spacing-sm);
          cursor: pointer;
          color: var(--color-text-primary);
        }

        .sidebar-overlay {
          display: none;
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.5);
          z-index: 99;
        }

        @media (max-width: 1024px) {
          .mobile-menu-btn {
            display: flex;
          }
          .sidebar-overlay {
            display: block;
          }
          .sidebar {
            transform: translateX(-100%);
          }
          .sidebar.open {
            transform: translateX(0);
          }
        }

        .sidebar-header {
          padding: var(--spacing-lg);
          border-bottom: 1px solid var(--color-border);
        }

        .logo {
          display: flex;
          align-items: center;
          gap: var(--spacing-sm);
          color: var(--color-primary);
        }

        .logo-text {
          font-size: 1.25rem;
          font-weight: 700;
        }

        .sidebar-nav {
          flex: 1;
          padding: var(--spacing-md);
          overflow-y: auto;
        }

        .sidebar-link {
          display: flex;
          align-items: center;
          gap: var(--spacing-sm);
          padding: var(--spacing-sm) var(--spacing-md);
          border-radius: var(--radius-md);
          color: var(--color-text-secondary);
          font-weight: 500;
          transition: all var(--transition-fast);
          margin-bottom: var(--spacing-xs);
        }

        .sidebar-link:hover {
          background-color: var(--color-background);
          color: var(--color-text-primary);
          text-decoration: none;
        }

        .sidebar-link.active {
          background-color: var(--color-primary);
          color: white;
        }

        .sidebar-footer {
          padding: var(--spacing-md);
          border-top: 1px solid var(--color-border);
        }

        .sidebar-controls {
          display: flex;
          flex-direction: column;
          gap: var(--spacing-xs);
          margin-bottom: var(--spacing-md);
        }

        .sidebar-btn {
          display: flex;
          align-items: center;
          gap: var(--spacing-sm);
          padding: var(--spacing-sm) var(--spacing-md);
          background: transparent;
          border: none;
          border-radius: var(--radius-md);
          color: var(--color-text-secondary);
          font-size: 0.875rem;
          cursor: pointer;
          transition: all var(--transition-fast);
          text-align: left;
        }

        .sidebar-btn:hover {
          background-color: var(--color-background);
          color: var(--color-text-primary);
        }

        .lang-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 24px;
          height: 24px;
          background: var(--color-primary);
          color: white;
          border-radius: var(--radius-sm);
          font-size: 0.75rem;
          font-weight: 600;
        }

        .user-info {
          display: flex;
          align-items: center;
          gap: var(--spacing-sm);
          padding: var(--spacing-sm);
          background: var(--color-background);
          border-radius: var(--radius-md);
          margin-bottom: var(--spacing-sm);
        }

        .user-avatar {
          width: 40px;
          height: 40px;
          border-radius: var(--radius-full);
          background: var(--color-primary);
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 600;
        }

        .user-details {
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }

        .user-name {
          font-weight: 600;
          font-size: 0.875rem;
          color: var(--color-text-primary);
        }

        .user-email {
          font-size: 0.75rem;
          color: var(--color-text-secondary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .logout-btn {
          width: 100%;
          color: var(--color-error);
        }

        .logout-btn:hover {
          background: rgba(239, 68, 68, 0.1);
        }
      `}</style>
    </>
  );
}