import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AppLayout } from '@/components/AppLayout'
import { Empty } from '@/components/ui'
import { ApplicationsPage } from '@/features/applications/ApplicationsPage'
import { AuthProvider } from '@/features/auth/AuthContext'
import { LoginPage, RegisterPage } from '@/features/auth/AuthPages'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { CalendarPage } from '@/features/calendar/CalendarPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { NewOfferPage } from '@/features/offers/NewOfferPage'
import { OfferDetailPage } from '@/features/offers/OfferDetailPage'
import { OffersPage } from '@/features/offers/OffersPage'
import { ProfilePage } from '@/features/profile/ProfilePage'
import { SavedPage } from '@/features/saved/SavedPage'
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
              <Route path="search" element={<SearchPage />} />
              <Route path="offers" element={<OffersPage />} />
              <Route path="offers/new" element={<NewOfferPage />} />
              <Route path="offers/:id" element={<OfferDetailPage />} />
              <Route path="saved" element={<SavedPage />} />
              <Route path="applications" element={<ApplicationsPage />} />
              <Route path="calendar" element={<CalendarPage />} />
              <Route path="*" element={<Empty title="Page not found" />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
