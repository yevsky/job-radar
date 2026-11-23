import { useState } from 'react'

import { deleteUser, listUsers, setRole, setSearchLimit, type AdminUser } from '@/api/admin'
import type { RoleName } from '@/api/auth'
import { Icon } from '@/components/Icon'
import { Empty, ErrorBox, Loading, PageHeader } from '@/components/ui'
import { useAuth } from '@/features/auth/AuthContext'
import { formatDate } from '@/lib/format'
import { useAsync } from '@/lib/useAsync'

/** Admin: every account, its role, its daily search limit, and a delete button. */
export function AdminUsersPage() {
  const users = useAsync(() => listUsers(), [])
  const [query, setQuery] = useState('')
  const shown = (users.data ?? []).filter((u) =>
    u.email.toLowerCase().includes(query.trim().toLowerCase()),
  )

  return (
    <>
      <PageHeader
        icon="user"
        title="Users"
        lead="Change roles, set how many searches someone can run per day (empty = the server default), or delete an account. You can't change or delete your own account."
      />
      {users.loading && <Loading />}
      {users.error && <ErrorBox error={users.error} onRetry={users.reload} />}
      {users.data?.length === 0 && <Empty title="No users yet" />}
      {users.data && users.data.length > 0 && (
        <div className="card stack">
          <input
            className="input"
            type="search"
            placeholder="Find by email"
            aria-label="Find a user by email"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ maxWidth: 320 }}
          />
          <div style={{ overflowX: 'auto' }}>
            <table className="data">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Joined</th>
                  <th>Role</th>
                  <th>Searches per day</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {shown.map((u) => (
                  <UserRow key={u.id} user={u} onDeleted={users.reload} />
                ))}
              </tbody>
            </table>
          </div>
          <p className="small muted">
            {shown.length} of {users.data.length} accounts
          </p>
        </div>
      )}
    </>
  )
}

function UserRow({ user, onDeleted }: { user: AdminUser; onDeleted: () => void }) {
  const { user: me } = useAuth()
  const isMe = me?.id === user.id
  const [role, setRoleValue] = useState<RoleName>(user.role)
  const [roleStatus, setRoleStatus] = useState<string>()
  const [deleting, setDeleting] = useState(false)

  async function changeRole(next: RoleName) {
    const before = role
    setRoleValue(next)
    try {
      await setRole(user.id, next)
      setRoleStatus('Saved')
    } catch (err) {
      setRoleValue(before)
      setRoleStatus(err instanceof Error ? err.message : 'Could not save')
    }
  }

  async function remove() {
    if (!window.confirm(`Delete ${user.email} and all their data? This can't be undone.`)) return
    setDeleting(true)
    try {
      await deleteUser(user.id)
      onDeleted()
    } catch (err) {
      setDeleting(false)
      setRoleStatus(err instanceof Error ? err.message : 'Could not delete')
    }
  }

  return (
    <tr>
      <td>
        {user.email}
        {isMe && (
          <span className="tag tag-info" style={{ marginLeft: 8 }}>
            you
          </span>
        )}
      </td>
      <td className="muted">{formatDate(user.created_at)}</td>
      <td>
        <div className="row" style={{ gap: 8, flexWrap: 'nowrap' }}>
          <select
            className="select"
            value={role}
            disabled={isMe}
            aria-label={`Role of ${user.email}`}
            onChange={(e) => void changeRole(e.target.value as RoleName)}
          >
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>
          {roleStatus && <span className="small muted">{roleStatus}</span>}
        </div>
      </td>
      <td>
        <LimitForm user={user} />
      </td>
      <td>
        {!isMe && (
          <button
            className="btn btn-sm btn-ghost"
            onClick={() => void remove()}
            disabled={deleting}
            aria-label={`Delete ${user.email}`}
            title="Delete account"
          >
            <Icon name="trash" size={16} />
          </button>
        )}
      </td>
    </tr>
  )
}

function LimitForm({ user }: { user: AdminUser }) {
  const [value, setValue] = useState(
    user.search_daily_limit == null ? '' : String(user.search_daily_limit),
  )
  const [status, setStatus] = useState<string>()
  const [busy, setBusy] = useState(false)

  async function save() {
    const limit = value.trim() === '' ? null : Number(value)
    if (limit !== null && (!Number.isInteger(limit) || limit < 0 || limit > 1000)) {
      setStatus('Use a whole number from 0 to 1000')
      return
    }
    setBusy(true)
    try {
      const r = await setSearchLimit(user.id, limit)
      setStatus(
        r.search_daily_limit === null
          ? `Default (${r.effective_limit} a day)`
          : `Saved: ${r.effective_limit} a day`,
      )
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Could not save')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form
      className="row"
      style={{ gap: 8 }}
      onSubmit={(e) => {
        e.preventDefault()
        void save()
      }}
    >
      <input
        className="input"
        type="number"
        min={0}
        max={1000}
        placeholder="default"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        aria-label={`Daily searches for ${user.email}`}
        style={{ width: 110 }}
      />
      <button className="btn btn-sm" disabled={busy}>
        {busy ? 'Saving…' : 'Save'}
      </button>
      {status && <span className="small muted">{status}</span>}
    </form>
  )
}
