import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AppLayout } from '@/components/AppLayout'
import { Empty } from '@/components/ui'
import { AdminDashboardPage } from '@/features/admin/AdminDashboardPage'
import { AdminImportPage } from '@/features/admin/AdminImportPage'
import { AdminOffersPage } from '@/features/admin/AdminOffersPage'
import { AdminSourcesPage } from '@/features/admin/AdminSourcesPage'
import { AdminUsersPage } from '@/features/admin/AdminUsersPage'
import { ApplicationsPage } from '@/features/applications/ApplicationsPage'
import { AssistantPage } from '@/features/assistant/AssistantPage'
import { AuthProvider } from '@/features/auth/AuthContext'
import { LoginPage, RegisterPage } from '@/features/auth/AuthPages'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { CalendarPage } from '@/features/calendar/CalendarPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { MyOffersPage } from '@/features/my-offers/MyOffersPage'
import { NewOfferPage } from '@/features/offers/NewOfferPage'
import { OfferDetailPage } from '@/features/offers/OfferDetailPage'
import { OffersPage } from '@/features/offers/OffersPage'
import { ProfilePage } from '@/features/profile/ProfilePage'
import { ResumesPage } from '@/features/resumes/ResumesPage'
import { SearchPage } from '@/features/search/SearchPage'

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<RequireAuth />}>
            <Route element={<AppLayout />}>
              {/* One line per feature; see COMMIT_PLAN.md for the order they land in. */}
              <Route index element={<DashboardPage />} />
              <Route path="profile" element={<ProfilePage />} />
              <Route path="cvs" element={<ResumesPage />} />
              <Route path="search" element={<SearchPage />} />
              <Route path="offers" element={<OffersPage />} />
              <Route path="offers/new" element={<NewOfferPage />} />
              <Route path="offers/:id" element={<OfferDetailPage />} />
              <Route path="my-offers" element={<MyOffersPage />} />
              {/* the old name of My offers, so old links still work */}
              <Route path="saved" element={<Navigate to="/my-offers" replace />} />
              <Route path="applications" element={<ApplicationsPage />} />
              <Route path="calendar" element={<CalendarPage />} />
              <Route path="assistant" element={<AssistantPage />} />
              <Route path="admin" element={<AdminDashboardPage />} />
              <Route path="admin/users" element={<AdminUsersPage />} />
              <Route path="admin/offers" element={<AdminOffersPage />} />
              <Route path="admin/import" element={<AdminImportPage />} />
              <Route path="admin/sources" element={<AdminSourcesPage />} />
              <Route path="*" element={<Empty title="Page not found" />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
