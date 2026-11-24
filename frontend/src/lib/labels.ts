import type { ApplicationStatus, EmploymentType, ExperienceLevel, SourceKind } from '@/api/enums'
import type { WorkMode } from '@/api/jobOffers'

export const experienceLabel: Record<ExperienceLevel, string> = {
  trainee: 'Trainee',
  junior: 'Junior',
  middle: 'Mid',
  senior: 'Senior',
  lead: 'Lead',
}

export const employmentLabel: Record<EmploymentType, string> = {
  full_time: 'Full-time',
  part_time: 'Part-time',
  contract: 'Contract',
  internship: 'Internship',
  b2b: 'B2B',
}

export const sourceLabel: Record<SourceKind, string> = {
  search: 'Found by search',
  browser: 'Sent from browser',
  manual: 'Added by you',
  posted: 'Posted',
}

export const statusLabel: Record<ApplicationStatus, string> = {
  saved: 'Saved',
  applied: 'Applied',
  screening: 'Screening',
  interview: 'Interview',
  offer: 'Offer',
  accepted: 'Accepted',
  rejected: 'Rejected',
  declined: 'Declined',
}

/** CSS colour variable for a status, used by badges, the board and the charts. */
export const statusColor = (status: ApplicationStatus) => `var(--st-${status})`

const SEARCH_SOURCE_LABELS: Record<string, string> = {
  tavily: 'Tavily (job boards)',
  jsearch: 'JSearch (Google Jobs)',
  fake: 'Demo source',
}

/** 'jsearch' -> 'JSearch (Google Jobs)'; an unknown name is shown as it is. */
export const searchSourceLabel = (name: string) => SEARCH_SOURCE_LABELS[name] ?? name

export const workModeLabel: Record<WorkMode, string> = {
  remote: 'Remote',
  hybrid: 'Hybrid',
  onsite: 'On-site',
}
