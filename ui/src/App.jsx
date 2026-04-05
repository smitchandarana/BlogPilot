import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ErrorBoundary from './components/ErrorBoundary'
import ProtectedRoute from './components/ProtectedRoute'
import AdminRoute from './components/AdminRoute'
import SuperUserRoute from './components/SuperUserRoute'
import AppShell from './components/AppShell'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Dashboard from './pages/Dashboard'
import EngineControl from './pages/EngineControl'
import Topics from './pages/Topics'
import FeedEngagement from './pages/FeedEngagement'
import ContentStudio from './pages/ContentStudio'
import Campaigns from './pages/Campaigns'
import Leads from './pages/Leads'
import Analytics from './pages/Analytics'
import PromptEditor from './pages/PromptEditor'
import Settings from './pages/Settings'
import AdminDashboard from './pages/AdminDashboard'
import Billing from './pages/Billing'
import ResetPassword from './pages/ResetPassword'

export default function App() {
  return (
    <ErrorBoundary>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/reset-password" element={<ResetPassword />} />

          {/* Protected — wrapped in Layout */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/control" element={<EngineControl />} />
              <Route path="/topics" element={<Topics />} />
              <Route path="/feed" element={<FeedEngagement />} />
              <Route path="/content" element={<ContentStudio />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/prompts" element={<PromptEditor />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/billing" element={<Billing />} />
            </Route>
          </Route>

          {/* Admin only — /admin dashboard */}
          <Route element={<AdminRoute />}>
            <Route element={<AppShell />}>
              <Route path="/admin" element={<AdminDashboard />} />
            </Route>
          </Route>

          {/* Superuser + Admin — campaigns and leads */}
          <Route element={<SuperUserRoute />}>
            <Route element={<AppShell />}>
              <Route path="/campaigns" element={<Campaigns />} />
              <Route path="/leads" element={<Leads />} />
            </Route>
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
    </ErrorBoundary>
  )
}
