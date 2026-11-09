import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { auth } from '@/lib/api';
import { ToastProvider } from '@/components/ui';
import { AppShell } from '@/components/AppShell';
import { LoginPage } from '@/pages/Login';
import { DashboardPage } from '@/pages/Dashboard';
import { MeetingsPage } from '@/pages/Meetings';
import { MeetingDetailPage } from '@/pages/MeetingDetail';
import { DocsPage } from '@/pages/Docs';
import { DocEditorPage } from '@/pages/DocEditor';
import { KbPage } from '@/pages/Kb';
import { TasksPage } from '@/pages/Tasks';
import { WeeklyPage } from '@/pages/Weekly';
import { InsightsPage } from '@/pages/Insights';
import { RunDetailPage } from '@/pages/RunDetail';
import { SettingsPage } from '@/pages/Settings';

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!auth.token) return <Navigate to="/login" replace />;
  return <AppShell>{children}</AppShell>;
}

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<RequireAuth><DashboardPage /></RequireAuth>} />
          <Route path="/meetings" element={<RequireAuth><MeetingsPage /></RequireAuth>} />
          <Route path="/meetings/:id" element={<RequireAuth><MeetingDetailPage /></RequireAuth>} />
          <Route path="/docs" element={<RequireAuth><DocsPage /></RequireAuth>} />
          <Route path="/docs/:id" element={<RequireAuth><DocEditorPage /></RequireAuth>} />
          <Route path="/kb" element={<RequireAuth><KbPage /></RequireAuth>} />
          <Route path="/tasks" element={<RequireAuth><TasksPage /></RequireAuth>} />
          <Route path="/weekly" element={<RequireAuth><WeeklyPage /></RequireAuth>} />
          <Route path="/insights" element={<RequireAuth><InsightsPage /></RequireAuth>} />
          <Route path="/runs/:id" element={<RequireAuth><RunDetailPage /></RequireAuth>} />
          <Route path="/settings" element={<RequireAuth><SettingsPage /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}
