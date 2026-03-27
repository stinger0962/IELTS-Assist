import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  BookOpen,
  GraduationCap,
  Target,
  Settings,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

const tabs = [
  { path: '/', icon: LayoutDashboard, labelKey: 'nav.dashboard' },
  { path: '/practice', icon: BookOpen, labelKey: 'nav.practice' },
  { path: '/topics', icon: GraduationCap, labelKey: 'nav.topics' },
  { path: '/goals', icon: Target, labelKey: 'nav.goals' },
  { path: '/settings', icon: Settings, labelKey: 'nav.settings' },
];

export default function BottomNav() {
  const { t } = useTranslation();
  const location = useLocation();

  return (
    <>
      <nav className="bottom-nav">
        {tabs.map((tab) => {
          const isActive = tab.path === '/'
            ? location.pathname === '/'
            : location.pathname.startsWith(tab.path);
          return (
            <NavLink
              key={tab.path}
              to={tab.path}
              className={`bottom-nav-item ${isActive ? 'active' : ''}`}
            >
              <tab.icon size={20} strokeWidth={isActive ? 2.5 : 1.8} />
              <span className="bottom-nav-label">{t(tab.labelKey)}</span>
            </NavLink>
          );
        })}
      </nav>

      <style>{`
        .bottom-nav {
          display: none;
        }

        @media (max-width: 1024px) {
          .bottom-nav {
            display: flex;
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 100;
            background: var(--color-surface);
            border-top: 1px solid var(--color-border);
            padding: 4px 0;
            padding-bottom: max(4px, env(safe-area-inset-bottom));
            justify-content: space-around;
            align-items: center;
          }

          .bottom-nav-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
            padding: 6px 12px;
            border-radius: 8px;
            color: var(--color-text-secondary);
            text-decoration: none;
            transition: color 0.15s ease;
            -webkit-tap-highlight-color: transparent;
            min-width: 56px;
          }

          .bottom-nav-item.active {
            color: var(--color-primary);
          }

          .bottom-nav-item:active {
            transform: scale(0.92);
          }

          .bottom-nav-label {
            font-size: 0.6rem;
            font-weight: 500;
            letter-spacing: 0.01em;
          }

          .bottom-nav-item.active .bottom-nav-label {
            font-weight: 700;
          }
        }
      `}</style>
    </>
  );
}
