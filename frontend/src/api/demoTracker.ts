/** Remembers which features are showing demo data, so the UI can say so honestly. */
type Listener = (features: string[]) => void

const features = new Set<string>()
const listeners = new Set<Listener>()

export function markDemo(feature: string) {
  if (features.has(feature)) return
  features.add(feature)
  const list = [...features]
  listeners.forEach((l) => l(list))
}

export function subscribeDemo(listener: Listener): () => void {
  listeners.add(listener)
  listener([...features])
  return () => listeners.delete(listener)
}
