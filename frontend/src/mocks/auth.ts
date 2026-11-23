import type { Token, UserRead } from '@/api/auth'

import { daysFromNow } from './util'

let user: UserRead = {
  id: 1,
  email: 'demo@jobradar.local',
  role_id: 2,
  role: 'admin',
  created_at: daysFromNow(-90),
}

export const mockAuth = {
  login(email: string): Token {
    user = { ...user, email }
    return { access_token: 'demo-token', token_type: 'bearer' }
  },
  register(email: string): UserRead {
    user = { ...user, email }
    return user
  },
  me: (): UserRead => user,
}
