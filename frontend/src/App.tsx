import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AppLayout } from '@/components/AppLayout'
import { Empty } from '@/components/ui'
import { AuthProvider } from '@/features/auth/AuthContext'
import { LoginPage, RegisterPage } from '@/features/auth/AuthPages'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { ProfilePage } from '@/features/profile/ProfilePage'

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
              <Route
                index
                element={<Empty title="Welcome to JobRadar">Pages appear here as they land.</Empty>}
              />
              <Route path="profile" element={<ProfilePage />} />
              <Route path="*" element={<Empty title="Page not found" />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
