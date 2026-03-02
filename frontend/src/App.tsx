import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAppStore } from './store';
import { authAPI } from './api';
import './i18n';
import './styles/global.css';

import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Practice from './pages/Practice';
import Mistakes from './pages/Mistakes';
import Topics from './pages/Topics';
import Goals from './pages/Goals';
import Settings from './pages/Settings';
import { Login, Register } from './pages/Auth';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAppStore((state) => state.token);
  
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
}

function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}

export default function App() {
  const { i18n } = useTranslation();
  const { theme, language, token, setAuth, logout } = useAppStore();

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    i18n.changeLanguage(language);
  }, [language, i18n]);

  useEffect(() => {
    // Check auth on mount
    const initAuth = async () => {
      if (token) {
        try {
          const res = await authAPI.me();
          setAuth(token, res.data);
        } catch {
          logout();
        }
      }
    };
    initAuth();
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        
        <Route path="/" element={
          <ProtectedRoute>
            <AppLayout>
              <Dashboard />
            </AppLayout>
          </ProtectedRoute>
        } />
        
        <Route path="/practice" element={
          <ProtectedRoute>
            <AppLayout>
              <Practice />
            </AppLayout>
          </ProtectedRoute>
        } />
        
        <Route path="/mistakes" element={
          <ProtectedRoute>
            <AppLayout>
              <Mistakes />
            </AppLayout>
          </ProtectedRoute>
        } />
        
        <Route path="/topics" element={
          <ProtectedRoute>
            <AppLayout>
              <Topics />
            </AppLayout>
          </ProtectedRoute>
        } />
        
        <Route path="/goals" element={
          <ProtectedRoute>
            <AppLayout>
              <Goals />
            </AppLayout>
          </ProtectedRoute>
        } />
        
        <Route path="/settings" element={
          <ProtectedRoute>
            <AppLayout>
              <Settings />
            </AppLayout>
          </ProtectedRoute>
        } />
        
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}