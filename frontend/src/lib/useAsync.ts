import { useCallback, useEffect, useState } from 'react'

export interface AsyncState<T> {
  data: T | undefined
  error: Error | undefined
  loading: boolean
  reload: () => void
  /** Replace the data locally (optimistic updates). */
  setData: (update: T | ((prev: T | undefined) => T)) => void
}

interface Settled<T> {
  key: string
  data: T | undefined
  error: Error | undefined
}

/**
 * Run an async loader when `deps` change. Small on purpose: no cache, no library.
 * `loading` is derived (the last settled request isn't the current one), so the effect never
 * sets state synchronously. The AbortSignal stops a stale response overwriting a newer one.
 */
export function useAsync<T>(
  loader: (signal: AbortSignal) => Promise<T>,
  deps: unknown[],
): AsyncState<T> {
  const [version, setVersion] = useState(0)
  const key = JSON.stringify([...deps, version])
  const [state, setState] = useState<Settled<T>>({ key: '', data: undefined, error: undefined })

  useEffect(() => {
    const controller = new AbortController()
    loader(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ key, data, error: undefined })
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        const error = err instanceof Error ? err : new Error(String(err))
        setState((prev) => ({ key, data: prev.data, error }))
      })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  const reload = useCallback(() => setVersion((v) => v + 1), [])
  const setData = useCallback((update: T | ((prev: T | undefined) => T)) => {
    setState((prev) => ({
      ...prev,
      data: typeof update === 'function' ? (update as (p: T | undefined) => T)(prev.data) : update,
    }))
  }, [])

  return {
    data: state.data,
    error: state.key === key ? state.error : undefined,
    loading: state.key !== key,
    reload,
    setData,
  }
}
