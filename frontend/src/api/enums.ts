/** Mirrors backend/app/models/enums.py. Keep the string values identical. */

export const EXPERIENCE_LEVELS = ['trainee', 'junior', 'middle', 'senior', 'lead'] as const
export type ExperienceLevel = (typeof EXPERIENCE_LEVELS)[number]

export const EMPLOYMENT_TYPES = ['full_time', 'part_time', 'contract', 'internship', 'b2b'] as const
export type EmploymentType = (typeof EMPLOYMENT_TYPES)[number]

export const SOURCE_KINDS = ['search', 'browser', 'manual', 'posted'] as const
export type SourceKind = (typeof SOURCE_KINDS)[number]

/**
 * Milestone 9 statuses (planned): the backend enum has saved/applied/interview/rejected/accepted
 * and gains screening, offer and declined. A saved offer is an application with status `saved`;
 * moving it to `applied` is when the user applied.
 */
export const APPLICATION_STATUSES = [
  'saved',
  'applied',
  'screening',
  'interview',
  'offer',
  'accepted',
  'rejected',
  'declined',
] as const
export type ApplicationStatus = (typeof APPLICATION_STATUSES)[number]

/** Funnel stages in order; an application's stage is the furthest one it reached. */
export const FUNNEL_STAGES = ['applied', 'screening', 'interview', 'offer', 'accepted'] as const
export type FunnelStage = (typeof FUNNEL_STAGES)[number]
