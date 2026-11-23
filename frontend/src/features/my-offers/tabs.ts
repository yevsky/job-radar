import type { MyOffer } from '@/api/jobOffers'

/** The filters on top of My offers. An offer can be in several (e.g. from search and saved). */
export const TABS = [
  { value: 'all', label: 'All' },
  { value: 'saved', label: 'Saved' },
  { value: 'applied', label: 'Applied' },
  { value: 'manual', label: 'Added by you' },
  { value: 'search', label: 'From search' },
] as const

export type Tab = (typeof TABS)[number]['value']

export function inTab(offer: MyOffer, tab: Tab): boolean {
  const status = offer.application?.status
  switch (tab) {
    case 'all':
      return true
    case 'saved':
      return status === 'saved'
    case 'applied': // anything past saved: applied, interview, offer, rejected…
      return status !== undefined && status !== 'saved'
    default: // where an offer you added came from
      return offer.is_private && offer.source === tab
  }
}

export function countByTab(offers: MyOffer[]): Record<Tab, number> {
  return Object.fromEntries(
    TABS.map((t) => [t.value, offers.filter((o) => inTab(o, t.value)).length]),
  ) as Record<Tab, number>
}
