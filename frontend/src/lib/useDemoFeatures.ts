import { useEffect, useState } from 'react'

import { subscribeDemo } from '@/api/demoTracker'

/** Names of features currently showing demo data. */
export function useDemoFeatures(): string[] {
  const [features, setFeatures] = useState<string[]>([])
  useEffect(() => subscribeDemo(setFeatures), [])
  return features
}
