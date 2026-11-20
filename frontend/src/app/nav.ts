import type { IconName } from '@/components/Icon'

export interface NavItem {
  to: string
  label: string
  icon: IconName
}

export interface NavSection {
  title?: string
  /** Shown only to users the backend lets into /admin. */
  adminOnly?: boolean
  items: NavItem[]
}

/** Sidebar links. Add a line here when a page lands (see COMMIT_PLAN.md). */
export const navSections: NavSection[] = [
  { items: [{ to: '/', label: 'Dashboard', icon: 'home' }] },
  {
    title: 'You',
    items: [
      { to: '/profile', label: 'Profile', icon: 'user' },
      { to: '/cvs', label: 'My CVs', icon: 'file' },
    ],
  },
  {
    title: 'Job search',
    items: [
      { to: '/search', label: 'Find jobs', icon: 'search' },
      { to: '/offers', label: 'Job offers', icon: 'list' },
      { to: '/saved', label: 'Saved offers', icon: 'bookmark' },
      { to: '/applications', label: 'Applications', icon: 'board' },
      { to: '/calendar', label: 'Calendar', icon: 'calendar' },
    ],
  },
]
