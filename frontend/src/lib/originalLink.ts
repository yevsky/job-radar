/**
 * Offers posted on JobRadar itself (the demo seed) have no page anywhere else: their link is
 * a placeholder on jobradar.local, kept only because every offer needs a unique link. Such an
 * offer is opened inside the app; any other offer also links to its original posting.
 */
export const PLACEHOLDER_HOST = 'jobradar.local'

export function hasOriginal(url: string): boolean {
  try {
    return new URL(url).hostname !== PLACEHOLDER_HOST
  } catch {
    return false
  }
}
