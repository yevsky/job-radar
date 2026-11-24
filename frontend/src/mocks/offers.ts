import type {
  JobOfferCreate,
  JobOfferDraft,
  JobOfferFilters,
  JobOfferListItem,
  JobOfferPage,
  JobOfferRead,
  OfferSummary,
  WorkMode,
} from '@/api/jobOffers'
import { MIN_SUMMARY_DESCRIPTION } from '@/api/jobOffers'
import { ApiError } from '@/api/client'
import type { SourceKind } from '@/api/enums'

import { daysFromNow, newId, notFound } from './util'

type Seed = Omit<
  JobOfferRead,
  'id' | 'is_active' | 'last_seen_at' | 'created_at' | 'is_private' | 'found_via'
> & {
  age: number
}

const KNOWN_TECHS = ['Python', 'FastAPI', 'Django', 'PostgreSQL', 'Docker', 'React', 'TypeScript']

const seeds: Seed[] = [
  {
    title: 'Junior Python Developer',
    company_name: 'Northwind Analytics',
    location: 'Wrocław',
    employment_type: 'full_time',
    experience_level: 'junior',
    deadline: daysFromNow(9),
    technologies: ['Python', 'FastAPI', 'PostgreSQL', 'Docker'],
    source: 'posted',
    url: 'https://jobs.northwind.local/junior-python',
    description:
      'Join a small team building internal data APIs.\n\nYou will:\n- write FastAPI services backed by PostgreSQL\n- add tests with pytest\n- review pull requests with a senior mentor\n\nWe offer a hybrid model (2 days in the Wrocław office), a training budget and a 3-month onboarding plan.',
    age: 3,
  },
  {
    title: 'Backend Engineer (Python)',
    company_name: 'Lumen Health',
    location: 'Remote',
    employment_type: 'b2b',
    experience_level: 'middle',
    deadline: daysFromNow(14),
    technologies: ['Python', 'Django', 'PostgreSQL', 'Celery', 'AWS'],
    source: 'posted',
    url: 'https://careers.lumenhealth.local/backend',
    description:
      'Lumen builds scheduling software for clinics. You will own services for appointment booking and notifications.\n\nRequirements: 2+ years with Python, Django or FastAPI, SQL, message queues. Nice to have: AWS, healthcare data.',
    age: 6,
  },
  {
    title: 'Python Developer – Data Platform',
    company_name: 'Quarry Logistics',
    location: 'Warszawa',
    employment_type: 'full_time',
    experience_level: 'middle',
    deadline: daysFromNow(4),
    technologies: ['Python', 'Airflow', 'Kafka', 'SQL'],
    source: 'manual',
    url: 'https://quarry.local/jobs/data-platform',
    description:
      'Build pipelines that move shipment events from Kafka into our warehouse. On-site in Warsaw 3 days a week.',
    age: 10,
  },
  {
    title: 'Full-stack Developer (FastAPI + React)',
    company_name: 'Pine & Co',
    location: 'Kraków',
    employment_type: 'full_time',
    experience_level: 'junior',
    deadline: daysFromNow(20),
    technologies: ['Python', 'FastAPI', 'React', 'TypeScript'],
    source: 'posted',
    url: 'https://pineco.local/careers/fullstack',
    description:
      'Product team of six building a booking platform for small hotels. You will work on both the FastAPI backend and the React frontend.',
    age: 2,
  },
  {
    title: 'Backend Intern',
    company_name: 'Orbit Labs',
    location: 'Wrocław',
    employment_type: 'internship',
    experience_level: 'trainee',
    deadline: daysFromNow(2),
    technologies: ['Python', 'SQL', 'Git'],
    source: 'posted',
    url: 'https://orbitlabs.local/intern',
    description: 'Paid 3-month internship, 30 hours a week, with a mentor and a real project.',
    age: 12,
  },
  {
    title: 'Senior Platform Engineer',
    company_name: 'Halcyon Bank',
    location: 'Warszawa',
    employment_type: 'full_time',
    experience_level: 'senior',
    deadline: null,
    technologies: ['Kubernetes', 'Go', 'Terraform', 'Python'],
    source: 'manual',
    url: 'https://halcyon.local/careers/platform',
    description:
      'Run the platform our 40 product teams deploy to. 6+ years of experience required.',
    age: 20,
  },
  {
    title: 'Python Developer (Contract)',
    company_name: 'Brightline Studio',
    location: 'Remote',
    employment_type: 'contract',
    experience_level: 'middle',
    deadline: daysFromNow(30),
    technologies: ['Python', 'FastAPI', 'Redis', 'Docker'],
    source: 'posted',
    url: 'https://brightline.local/jobs/python-contract',
    description:
      '6-month contract to rebuild a reporting API. Fully remote within EU time zones. Must be available to start within 2 weeks.',
    age: 1,
  },
  {
    title: 'Junior Backend Developer (Node.js)',
    company_name: 'Tessellate',
    location: 'Gdańsk',
    employment_type: 'full_time',
    experience_level: 'junior',
    deadline: daysFromNow(11),
    technologies: ['Node.js', 'TypeScript', 'PostgreSQL'],
    source: 'posted',
    url: 'https://tessellate.local/junior-backend',
    description: 'Help us build APIs for a design collaboration tool.',
    age: 8,
  },
  {
    title: 'Data Engineer',
    company_name: 'Meridian Energy',
    location: 'Wrocław',
    employment_type: 'b2b',
    experience_level: 'middle',
    deadline: daysFromNow(17),
    technologies: ['Python', 'Spark', 'SQL', 'Azure'],
    source: 'manual',
    url: 'https://meridian.local/careers/data-engineer',
    description:
      'Model energy usage data and maintain the batch pipelines that feed our forecasts.',
    age: 15,
  },
  {
    title: 'QA Automation Engineer',
    company_name: 'Northwind Analytics',
    location: 'Remote',
    employment_type: 'part_time',
    experience_level: 'junior',
    deadline: daysFromNow(25),
    technologies: ['Python', 'pytest', 'Playwright'],
    source: 'posted',
    url: 'https://jobs.northwind.local/qa-automation',
    description: 'Part-time (24h/week) role writing end-to-end tests with Playwright and pytest.',
    age: 5,
  },
  {
    title: 'Backend Developer (Java)',
    company_name: 'Granite Insurance',
    location: 'Poznań',
    employment_type: 'full_time',
    experience_level: 'middle',
    deadline: daysFromNow(6),
    technologies: ['Java', 'Spring', 'Oracle'],
    source: 'manual',
    url: 'https://granite.local/careers/java',
    description: 'Maintain policy services in Java 21 and Spring Boot.',
    age: 18,
  },
  {
    title: 'Machine Learning Engineer',
    company_name: 'Cobalt AI',
    location: 'Remote',
    employment_type: 'b2b',
    experience_level: 'senior',
    deadline: daysFromNow(21),
    technologies: ['Python', 'PyTorch', 'FastAPI', 'Kubernetes'],
    source: 'posted',
    url: 'https://cobalt.local/jobs/ml-engineer',
    description: 'Serve and monitor LLM-based ranking models in production.',
    age: 4,
  },
]

const offers: JobOfferRead[] = seeds.map(({ age, ...seed }, index) => ({
  ...seed,
  id: index + 1,
  found_via: null,
  is_active: true,
  is_private: false,
  last_seen_at: daysFromNow(-age),
  created_at: daysFromNow(-age),
}))

export function toListItem(offer: JobOfferRead): JobOfferListItem {
  const { id, title, company_name, location, employment_type, experience_level, deadline } = offer
  return {
    id,
    title,
    company_name,
    location,
    employment_type,
    experience_level,
    deadline,
    technologies: offer.technologies,
  }
}

export const allMockOffers = () => offers

const summaries = new Map<number, OfferSummary>()

/** A demo summary built from the description by plain rules (the real one is the AI's). */
function demoSummary(offer: JobOfferRead): OfferSummary {
  const text = offer.description ?? ''
  const lower = text.toLowerCase()
  const firstParagraph = text.split(/\n\s*\n/)[0].trim()
  const bullets = text
    .split('\n')
    .filter((line) => line.trim().startsWith('-'))
    .map((line) => line.replace(/^\s*-\s*/, '').trim())
  const mode: WorkMode | null = lower.includes('remote')
    ? 'remote'
    : lower.includes('hybrid')
      ? 'hybrid'
      : lower.includes('on-site') || lower.includes('office')
        ? 'onsite'
        : null
  const salary = /\d[\d\s]*(k|000)?\s*(pln|eur)/i.exec(text)?.[0] ?? null
  const missing = [!salary && 'Salary', !mode && 'Work mode'].filter((m): m is string => !!m)
  return {
    job_offer_id: offer.id,
    overview: firstParagraph,
    responsibilities: bullets.slice(0, 6),
    must_have: offer.technologies.slice(0, 5),
    nice_to_have: [],
    benefits: lower.includes('training') ? ['Training budget'] : [],
    salary,
    work_mode: mode,
    missing_info: missing,
    summary_with: 'fake/demo-model',
    prompt_version: 'offer-summary-v1',
    created_at: new Date().toISOString(),
  }
}

function matches(offer: JobOfferRead, f: JobOfferFilters): boolean {
  const techs = offer.technologies.map((t) => t.toLowerCase())
  if (f.technology.some((t) => !techs.includes(t.toLowerCase()))) return false
  if (f.location && !(offer.location ?? '').toLowerCase().includes(f.location.toLowerCase()))
    return false
  if (f.experience_level.length && !f.experience_level.includes(offer.experience_level!))
    return false
  if (f.employment_type.length && !f.employment_type.includes(offer.employment_type!)) return false
  return offer.is_active
}

export const mockOffers = {
  list(filters: JobOfferFilters, limit: number, offset: number): JobOfferPage {
    // the job board: offers the user added live in My offers instead
    const found = offers
      .filter((o) => !o.is_private && matches(o, filters))
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
    return {
      items: found.slice(offset, offset + limit).map(toListItem),
      total: found.length,
      limit,
      offset,
    }
  },
  get(id: number): JobOfferRead {
    return offers.find((o) => o.id === id) ?? notFound('Job offer')
  },
  create(data: JobOfferCreate, source: SourceKind, foundVia: string | null = null): JobOfferRead {
    const known = offers.find((o) => o.url === data.url)
    if (known) return known
    const now = new Date().toISOString()
    const offer: JobOfferRead = {
      id: newId(),
      title: data.title,
      company_name: data.company_name,
      url: data.url,
      location: data.location ?? null,
      employment_type: data.employment_type ?? null,
      experience_level: data.experience_level ?? null,
      deadline: data.deadline ?? null,
      technologies: data.technologies ?? [],
      description: data.description ?? null,
      source,
      found_via: foundVia,
      is_active: true,
      is_private: true,
      last_seen_at: now,
      created_at: now,
    }
    offers.unshift(offer)
    return offer
  },
  /** A rough stand-in for the AI: first line as the title, known technologies, first link. */
  parse(text: string): JobOfferDraft {
    const lower = text.toLowerCase()
    const title = text.trim().split('\n')[0].trim().slice(0, 200)
    return {
      title,
      company_name: null,
      location: null,
      experience_level:
        (['junior', 'senior', 'lead'] as const).find((l) => lower.includes(l)) ?? null,
      employment_type: lower.includes('b2b') ? 'b2b' : null,
      deadline: null,
      technologies: KNOWN_TECHS.filter((t) => lower.includes(t.toLowerCase())),
      url: /https?:\/\/[^\s<>"'()]+/i.exec(text)?.[0].replace(/[.,;:!?]+$/, '') ?? null,
      description: text,
      parsed_with: 'demo',
    }
  },
  getSummary(id: number): OfferSummary | null {
    mockOffers.get(id)
    return summaries.get(id) ?? null
  },
  summarise(id: number): OfferSummary {
    const offer = mockOffers.get(id)
    if ((offer.description ?? '').trim().length < MIN_SUMMARY_DESCRIPTION)
      throw new ApiError(
        422,
        'This offer has no description to summarise. Open the original posting.',
      )
    const summary = demoSummary(offer)
    summaries.set(id, summary)
    return summary
  },
  remove(id: number): void {
    const index = offers.findIndex((o) => o.id === id)
    if (index === -1) notFound('Job offer')
    offers.splice(index, 1)
  },
}
