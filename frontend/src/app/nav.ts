import type { IconName } from '@/components/Icon'

export interface NavItem {
  to: string
  label: string
  icon: IconName
  /** Pages under `to` that aren't this item (they have their own button), e.g. /offers/new */
  except?: string[]
}

export interface NavSection {
  title?: string
  /** Shown only to users the backend lets into /admin. */
  adminOnly?: boolean
  items: NavItem[]
}

/** Sidebar links. Add a line here when a page lands (see COMMIT_PLAN.md). */
export const navSections: NavSection[] = [
  {
    items: [
      { to: '/', label: 'Dashboard', icon: 'home' },
      { to: '/assistant', label: 'AI assistant', icon: 'sparkle' },
    ],
  },
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
      { to: '/offers', label: 'Job board', icon: 'list', except: ['/offers/new'] },
      { to: '/my-offers', label: 'My offers', icon: 'bookmark' },
      { to: '/applications', label: 'Applications', icon: 'board' },
      { to: '/calendar', label: 'Calendar', icon: 'calendar' },
    ],
  },
  {
    title: 'Admin',
    adminOnly: true,
    items: [
      { to: '/admin', label: 'Admin dashboard', icon: 'sliders' },
      { to: '/admin/users', label: 'Users', icon: 'user' },
      { to: '/admin/offers', label: 'Imported offers', icon: 'layers' },
      { to: '/admin/import', label: 'Import offers', icon: 'upload' },
      { to: '/admin/sources', label: 'Search sources', icon: 'globe' },
    ],
  },
]
