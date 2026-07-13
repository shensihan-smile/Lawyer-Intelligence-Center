import React, { useEffect, useState } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import MainLayout from './components/MainLayout';
import LoginPage from './pages/login/LoginPage';
import DashboardPage from './pages/dashboard/DashboardPage';
import CommunicationPage from './pages/communication/CommunicationPage';
import CasesPage from './pages/cases/CasesPage';
import DocumentsPage from './pages/documents/DocumentsPage';
import SchedulePage from './pages/schedule/SchedulePage';
import BillingPage from './pages/billing/BillingPage';
import SystemPage from './pages/system/SystemPage';
import apiClient from './utils/api';

/** 需要登录才能访问的页面包装 */
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = localStorage.getItem('auth_token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

/** 已登录则自动跳转到工作台 */
const LoginGuard: React.FC = () => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    return <Navigate to="/dashboard" replace />;
  }
  return <LoginPage />;
};

const App: React.FC = () => {
  const navigate = useNavigate();

  // 监听 401 事件 —— api.ts 拦截器中修改了 window.location.hash，这里同步处理
  useEffect(() => {
    const handleHashChange = () => {
      if (window.location.hash === '#/login') {
        window.location.hash = '';
        navigate('/login');
      }
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, [navigate]);

  return (
    <Routes>
      <Route path="/login" element={<LoginGuard />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="communication" element={<CommunicationPage />} />
        <Route path="cases" element={<CasesPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="schedule" element={<SchedulePage />} />
        <Route path="billing" element={<BillingPage />} />
        <Route path="system" element={<SystemPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

export default App;
