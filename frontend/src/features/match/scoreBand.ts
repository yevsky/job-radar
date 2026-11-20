/** 0-100 score as a ring. Colour bands: <45 weak, <70 partial, else strong. */
export function scoreBand(score: number): { label: string; color: string } {
  if (score >= 70) return { label: 'Strong match', color: 'var(--st-accepted)' }
  if (score >= 45) return { label: 'Partial match', color: 'var(--st-offer)' }
  return { label: 'Weak match', color: 'var(--st-rejected)' }
}
