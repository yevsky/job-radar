import { useState } from 'react'

import { listUsers, setSearchLimit, type AdminUser } from '@/api/admin'
import { Empty, ErrorBox, Loading, PageHeader } from '@/components/ui'
import { formatDate } from '@/lib/format'
import { useAsync } from '@/lib/useAsync'

/** Admin: every user's daily search limit (PUT /admin/users/{id}/search-limit). */
export function AdminUsersPage() {
  const users = useAsync(() => listUsers(), [])
  return (
    <>
      <PageHeader
        icon="sliders"
        title="Users and search limits"
        lead="How many searches each user can run per day. Leave the box empty to use the default from the server settings."
      />
      {users.loading && <Loading />}
      {users.error && <ErrorBox error={users.error} onRetry={users.reload} />}
      {users.data?.length === 0 && <Empty title="No users yet" />}
      {users.data && users.data.length > 0 && (
        <div className="card" style={{ overflowX: 'auto' }}>
          <table className="data">
            <thead>
              <tr>
                <th>Email</th>
                <th>Joined</th>
                <th>Searches per day</th>
              </tr>
            </thead>
            <tbody>
              {users.data.map((u) => (
                <LimitRow key={u.id} user={u} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function LimitRow({ user }: { user: AdminUser }) {
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
    <tr>
      <td>{user.email}</td>
      <td className="muted">{formatDate(user.created_at)}</td>
      <td>
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
            placeholder={user.search_daily_limit === undefined ? 'unchanged' : 'default'}
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
      </td>
    </tr>
  )
}
