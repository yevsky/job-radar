import type { EmploymentType, ExperienceLevel } from '@/api/enums'
import type { JobOfferRead } from '@/api/jobOffers'
import type {
  SearchQuery,
  SearchResponse,
  SearchResult,
  SearchSources,
  SearchUsage,
  SourceFeature,
} from '@/api/search'

import { mockOffers } from './offers'
import { mockProfile } from './profile'
import { daysFromNow } from './util'

const PAGE_SIZE = 6

const LEVEL_WORD: Record<ExperienceLevel, string> = {
  trainee: 'Intern',
  junior: 'Junior',
  middle: 'Mid',
  senior: 'Senior',
  lead: 'Lead',
}

type Row = [string, string, string, ExperienceLevel, EmploymentType, string[], string]

/** Fictional companies on .local domains; never real postings. */
const rows: Row[] = [
  [
    'Python Developer (FastAPI)',
    'Saltmarsh Software',
    'Remote',
    'junior',
    'b2b',
    ['Python', 'FastAPI', 'PostgreSQL'],
    'Small agency building APIs for logistics clients. You will design REST endpoints, write pytest suites and review code with two senior developers.\n\nWe work async-first, fully remote within CET ±2h.',
  ],
  [
    'Junior Backend Engineer',
    'Kestrel Payments',
    'Wrocław',
    'junior',
    'full_time',
    ['Python', 'Django', 'Docker'],
    'Payments team, hybrid in Wrocław (3 days in the office).\n\nRequirements:\n- 1 year with Python\n- basic SQL\n- you have used Docker\n\nNice to have: Django REST Framework, Celery.',
  ],
  [
    'Software Engineer, APIs',
    'Fernhill',
    'Kraków',
    'middle',
    'full_time',
    ['Python', 'GraphQL', 'AWS'],
    'Own the public GraphQL API used by 300 partner shops. 2+ years of backend experience expected.',
  ],
  [
    'Backend Developer – Python / SQL',
    'Atlas Freight',
    'Remote',
    'junior',
    'contract',
    ['Python', 'SQLAlchemy', 'PostgreSQL', 'Redis'],
    'Contract to hire, 12 months. Migrate legacy reports to a FastAPI service with SQLAlchemy 2.0.',
  ],
  [
    'Python Intern – Data Tools',
    'Birchwood Labs',
    'Wrocław',
    'trainee',
    'internship',
    ['Python', 'pandas', 'Git'],
    'Paid summer internship (3 months, 30h/week). Build small internal tools for the data team. Mentor assigned from day one.',
  ],
  [
    'Junior Python Developer',
    'Heron Health',
    'Poznań',
    'junior',
    'full_time',
    ['Python', 'FastAPI', 'Docker', 'pytest'],
    'Telemedicine startup. You will help build appointment and notification services. Hybrid, 2 office days.',
  ],
  [
    'Backend Engineer (Python, Go)',
    'Quillon',
    'Remote',
    'middle',
    'b2b',
    ['Python', 'Go', 'Kubernetes'],
    'Platform team running ingestion services. Python today, some Go. On-call one week in six.',
  ],
  [
    'Graduate Software Engineer',
    'Northgate Systems',
    'Warszawa',
    'trainee',
    'full_time',
    ['Python', 'Java', 'SQL'],
    'Graduate programme with three 4-month rotations across backend, data and QA teams.',
  ],
  [
    'Python Developer – Automation',
    'Lantern Ops',
    'Remote',
    'junior',
    'part_time',
    ['Python', 'Playwright', 'pytest'],
    'Part-time (24h/week) role automating browser workflows and writing end-to-end tests.',
  ],
  [
    'Mid Python Developer',
    'Corvid Analytics',
    'Wrocław',
    'middle',
    'full_time',
    ['Python', 'FastAPI', 'PostgreSQL', 'Kafka'],
    'Event-driven analytics platform. FastAPI services consuming Kafka topics, Postgres for storage.',
  ],
  [
    'Junior Full-stack (Python + React)',
    'Maple & Moss',
    'Gdańsk',
    'junior',
    'full_time',
    ['Python', 'React', 'TypeScript'],
    'Product team of five building a booking app for small gyms.',
  ],
  [
    'Backend Trainee',
    'Orchid Insurance',
    'Wrocław',
    'trainee',
    'internship',
    ['Python', 'SQL'],
    '6-month traineeship that turns into a junior role. Training budget and a structured plan.',
  ],
  [
    'API Developer (Python)',
    'Sable Mobility',
    'Remote',
    'middle',
    'contract',
    ['Python', 'FastAPI', 'AWS', 'Terraform'],
    '9-month contract building APIs for an e-scooter fleet. AWS Lambda and API Gateway.',
  ],
  [
    'Python Engineer, Search',
    'Wren Books',
    'Kraków',
    'junior',
    'b2b',
    ['Python', 'Elasticsearch', 'FastAPI'],
    'Improve the search relevance of an online bookstore. Python + Elasticsearch.',
  ],
]

const pool: SearchResult[] = rows.map(
  (
    [title, company_name, location, experience_level, employment_type, technologies, description],
    i,
  ) => ({
    title,
    company_name,
    location,
    experience_level,
    employment_type,
    technologies,
    description,
    url: `https://${company_name.toLowerCase().replace(/[^a-z]+/g, '')}.local/jobs/${100 + i}`,
    deadline: i % 3 === 0 ? null : daysFromNow(4 + i),
    found_via: i % 4 === 3 ? 'jsearch' : 'tavily',
    ...salaryFor(i, employment_type, experience_level),
    posted_at: daysFromNow(-((i * 5) % 17)),
  }),
)

/** Hourly B2B/contract rates, monthly gross for employment; every 4th has no salary. */
function salaryFor(i: number, type: EmploymentType, level: ExperienceLevel) {
  if (i % 4 === 2)
    return { salary_min: null, salary_max: null, salary_currency: null, salary_period: null }
  const base = { trainee: 0.45, junior: 0.65, middle: 1, senior: 1.4, lead: 1.7 }[level]
  if (type === 'b2b' || type === 'contract') {
    const min = Math.round((90 * base) / 5) * 5
    return {
      salary_min: min,
      salary_max: min + 30,
      salary_currency: 'PLN',
      salary_period: 'hour' as const,
    }
  }
  const min = Math.round((14000 * base) / 500) * 500
  return {
    salary_min: min,
    salary_max: min + 3000,
    salary_currency: 'PLN',
    salary_period: 'month' as const,
  }
}

const AVAILABLE = ['tavily', 'jsearch']
const FEATURES: Record<string, SourceFeature[]> = {
  tavily: ['posted_within'],
  jsearch: ['country', 'pages', 'posted_within'],
}
let chosen: string[] | null = null
let usedToday = 0
const DAILY_LIMIT = 10

/** Same idea as the backend's app/core/locations.py, much shorter. */
const fold = (t: string) =>
  t
    .toLowerCase()
    .replace(/ł/g, 'l')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
const ALIASES: Record<string, string> = { warsaw: 'warszawa', cracow: 'krakow' }
const cityKey = (t: string) => ALIASES[fold(t).trim()] ?? fold(t).trim()

function fitsCities(location: string | null | undefined, cities: string[]) {
  if (cities.length === 0 || !location) return true
  const wanted = cities.map(cityKey)
  if (location === 'Remote') return wanted.includes('remote')
  return wanted.includes(cityKey(location))
}

const POSTED_DAYS = { day: 1, week: 7, month: 31 } as const

export const mockSearch = {
  sources(): SearchSources {
    return { available: AVAILABLE, chosen, features: FEATURES }
  },
  setSources(sources: string[] | null): SearchSources {
    chosen = sources
    return { available: AVAILABLE, chosen, features: FEATURES }
  },
  usage(): SearchUsage {
    return { daily_limit: DAILY_LIMIT, used_today: usedToday, left_today: DAILY_LIMIT - usedToday }
  },
  defaults(): SearchQuery {
    const p = mockProfile.get()
    const level = p.experience_level ? LEVEL_WORD[p.experience_level] : ''
    const hasLevel = /\b(intern|trainee|junior|mid|senior|lead)\b/i.test(p.desired_position ?? '')
    return {
      position: p.desired_position
        ? hasLevel || !level
          ? p.desired_position
          : `${level} ${p.desired_position}`
        : null,
      locations: p.preferred_locations.slice(0, 5),
      country: 'pl',
      posted_within: null,
    }
  },
  run(query: SearchQuery, page: number): SearchResponse {
    const cities = query.locations.map((l) => l.trim()).filter(Boolean)
    const text = [query.position?.trim(), cities.join(' OR ')].filter(Boolean).join(' ')
    const words = fold(query.position ?? '')
      .split(/\s+/)
      .filter((w) => w.length > 2 && !['developer', 'engineer', 'junior', 'mid'].includes(w))
    const since = query.posted_within
      ? Date.now() - POSTED_DAYS[query.posted_within] * 86_400_000
      : 0

    const found = pool.filter(
      (r) =>
        (chosen === null || chosen.includes(r.found_via)) &&
        fitsCities(r.location, cities) &&
        (!since || new Date(r.posted_at ?? 0).getTime() >= since) &&
        (words.length === 0 ||
          words.some((w) => fold(`${r.title} ${(r.technologies ?? []).join(' ')}`).includes(w))),
    )
    const start = (page - 1) * PAGE_SIZE
    if (page === 1) usedToday = Math.min(DAILY_LIMIT, usedToday + 1)
    return {
      searches_left_today: DAILY_LIMIT - usedToday,
      query: text,
      results: found.slice(start, start + PAGE_SIZE),
      errors: [],
      page,
      has_more: start + PAGE_SIZE < found.length,
    }
  },
  save(result: SearchResult): JobOfferRead {
    return mockOffers.create(result, 'search')
  },
}
