import { useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'

import { navSections } from '@/app/nav'
import { useAuth } from '@/features/auth/AuthContext'
import { useTheme } from '@/lib/theme'

import { Icon } from './Icon'
import { useDemoFeatures } from '@/lib/useDemoFeatures'
import { useIsAdmin } from '@/lib/useIsAdmin'

const COLLAPSE_KEY = 'jobradar.sidebar'

export function AppLayout() {
  const { user, logout } = useAuth()
  const [theme, toggleTheme] = useTheme()
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === '1'
    } catch {
      return false
    }
  })
  const [mobileOpen, setMobileOpen] = useState(false)
  const demo = useDemoFeatures()
  const isAdmin = useIsAdmin()
  const { pathname } = useLocation()

  function toggleCollapsed() {
    setCollapsed((c) => {
      try {
        localStorage.setItem(COLLAPSE_KEY, c ? '0' : '1')
      } catch {
        // not important
      }
      return !c
    })
  }

  return (
    <div className="app" data-collapsed={collapsed} data-mobile-open={mobileOpen}>
      <aside className="sidebar" aria-label="Main navigation">
        <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'nowrap' }}>
          <Link to="/" className="brand">
            <img src="/radar.svg" alt="" className="brand-mark" />
            <span className="collapsible">
              <div className="brand-name">JobRadar</div>
            </span>
          </Link>
          <button
            className="btn btn-ghost btn-icon collapsible"
            onClick={toggleCollapsed}
            aria-label="Collapse sidebar"
          >
            <Icon name="sidebar" />
          </button>
        </div>
        {collapsed && (
          <button
            className="btn btn-ghost btn-icon"
            onClick={toggleCollapsed}
            aria-label="Expand sidebar"
          >
            <Icon name="right" />
          </button>
        )}

        <Link
          to="/offers/new"
          className="btn btn-primary btn-new"
          onClick={() => setMobileOpen(false)}
          title="Add an offer"
        >
          <Icon name="plus" size={18} />
          <span className="collapsible">Add an offer</span>
        </Link>

        <nav>
          {navSections
            .filter((section) => isAdmin || !section.adminOnly)
            .map((section, i) => (
              <div key={section.title ?? i}>
                {section.title && <div className="nav-section collapsible">{section.title}</div>}
                {section.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/' || item.to === '/admin'}
                    // NavLink marks every page under `to` as active, but /offers/new is the
                    // "Add an offer" button's page, not "Job offers"
                    className={({ isActive }) =>
                      isActive && !item.except?.includes(pathname) ? 'nav-link active' : 'nav-link'
                    }
                    aria-current={item.except?.includes(pathname) ? 'false' : 'page'}
                    onClick={() => setMobileOpen(false)}
                    title={item.label}
                  >
                    <Icon name={item.icon} />
                    <span className="collapsible">{item.label}</span>
                  </NavLink>
                ))}
              </div>
            ))}
        </nav>

        <div className="sidebar-foot">
          {demo.length > 0 && (
            <p className="small faint collapsible" style={{ padding: '0 12px 8px' }}>
              Demo data in: {demo.join(', ')}. These endpoints aren&apos;t in the backend yet.
            </p>
          )}
          <button
            className="nav-link btn-ghost"
            style={{ border: 0, cursor: 'pointer' }}
            onClick={toggleTheme}
          >
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
            <span className="collapsible">{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
          </button>
          <div className="user-chip">
            <span
              className="collapsible small"
              style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}
            >
              {user?.email}
            </span>
            <button
              className="btn btn-ghost btn-icon"
              onClick={() => void logout()}
              aria-label="Sign out"
            >
              <Icon name="logout" size={18} />
            </button>
          </div>
        </div>
      </aside>

      <div className="main">
        <div className="mobile-bar">
          <button
            className="btn btn-ghost btn-icon"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <Icon name="menu" />
          </button>
          <span className="brand-name" style={{ fontSize: '1.25rem' }}>
            JobRadar
          </span>
        </div>
        {mobileOpen && <div className="drawer-backdrop" onClick={() => setMobileOpen(false)} />}
        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
