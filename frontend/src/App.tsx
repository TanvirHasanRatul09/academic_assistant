import { lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AppLayout } from './components/AppLayout'
import { ProtectedRoute } from './components/ProtectedRoute'

const AssistantPage = lazy(() => import('./pages/AssistantPage').then((module) => ({ default: module.AssistantPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then((module) => ({ default: module.DashboardPage })))
const DesignSystemPage = lazy(() => import('./pages/DesignSystemPage').then((module) => ({ default: module.DesignSystemPage })))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage').then((module) => ({ default: module.NotFoundPage })))
const NotificationsPage = lazy(() => import('./pages/NotificationsPage').then((module) => ({ default: module.NotificationsPage })))
const OnboardingPage = lazy(() => import('./pages/OnboardingPage').then((module) => ({ default: module.OnboardingPage })))
const RelevanceDebugPage = lazy(() => import('./pages/RelevanceDebugPage').then((module) => ({ default: module.RelevanceDebugPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((module) => ({ default: module.SettingsPage })))
const ProfilePage = lazy(() => import('./pages/ProfilePage').then((module) => ({ default: module.ProfilePage })))
const WelcomePage = lazy(() => import('./pages/WelcomePage').then((module) => ({ default: module.WelcomePage })))

export function App() {
  return <BrowserRouter><Routes><Route element={<AppLayout />}>
    <Route index element={<WelcomePage />} />
    <Route path="onboarding" element={<ProtectedRoute requireOnboarding={false}><OnboardingPage /></ProtectedRoute>} />
    <Route path="dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
    <Route path="assistant" element={<ProtectedRoute><AssistantPage /></ProtectedRoute>} />
    <Route path="settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
    <Route path="profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
    <Route path="notifications" element={<ProtectedRoute><NotificationsPage /></ProtectedRoute>} />
    <Route path="home" element={<Navigate to="/dashboard" replace />} />
    {import.meta.env.DEV && <Route path="dev/design-system" element={<DesignSystemPage />} />}
    {import.meta.env.DEV && <Route path="dev/relevance" element={<ProtectedRoute><RelevanceDebugPage /></ProtectedRoute>} />}
    <Route path="*" element={<NotFoundPage />} />
  </Route></Routes></BrowserRouter>
}

