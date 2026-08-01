# Database Schema

![ER diagram of the database schema](./img/db-schema.png)

This document describes the initial relational database schema for the job offer monitoring and analysis application. It covers the core functionality: user management, job offer storage, technology tagging, and application tracking.

> **Note:** Tables related to the AI assistant module (e.g. query history, generated summaries, match scores) are **not included yet**. These will be added in a later development phase once the AI module is designed and integrated. This document will be updated accordingly at that point.

## Overview

The schema is organized around five functional areas:

1. **Access control** — users, roles, and user profiles
2. **Job offer data** — job offers, job sources, and technologies
3. **User preferences** — skills and standing filter preferences used for matching
4. **User activity** — saved jobs and applications
5. *(Planned)* **AI assistant module** — to be added later

## Enums

### `employment_type`
Describes the type of employment contract associated with a job offer.

| Value | Description |
|---|---|
| `full_time` | Full-time employment |
| `part_time` | Part-time employment |
| `contract` | Fixed-term contract |
| `internship` | Internship position |
| `b2b` | Business-to-business contract (common in the Polish IT market) |

### `experience_level`
Describes the seniority level of a job offer or a user's declared experience.

| Value | Description |
|---|---|
| `internship` | Entry-level / internship |
| `junior` | Junior |
| `mid` | Mid-level |
| `senior` | Senior |
| `lead` | Lead / management-adjacent |

### `application_status`
Tracks the state of a user's application to a given job offer.

| Value | Description |
|---|---|
| `saved` | Offer saved but not yet applied to |
| `applied` | Application submitted |
| `interview` | In the interview process |
| `rejected` | Application rejected |
| `accepted` | Offer accepted |

## Tables

### `roles`
Defines system-level user roles (e.g. `admin`, `user`).

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `name` | varchar | Unique, not null |

### `users`
Application user accounts, including authentication data.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `email` | varchar | Unique, not null |
| `hashed_password` | varchar | Not null |
| `role_id` | integer | FK → `roles.id` |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

### `user_profiles`
Extended profile information for a user, one-to-one with `users`.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `user_id` | integer | FK → `users.id`, unique |
| `first_name` | varchar | |
| `last_name` | varchar | |
| `bio` | text | |
| `experience_level` | experience_level | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

### `user_preferred_locations`
Standing location preferences used for filtering and future matching features. A user may have multiple preferred locations.

| Column | Type | Notes |
|---|---|---|
| `user_id` | integer | FK → `users.id`, part of composite PK |
| `location` | varchar | Free-text, part of composite PK |

### `user_preferred_employment_types`
Standing employment type preferences used for filtering and future matching features. A user may prefer more than one employment type.

| Column | Type | Notes |
|---|---|---|
| `user_id` | integer | FK → `users.id`, part of composite PK |
| `employment_type` | employment_type | Part of composite PK |

### `job_sources`
External sources (e.g. job boards) from which offers are imported or scraped.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `name` | varchar | Unique, not null |
| `base_url` | varchar | |
| `is_active` | boolean | Not null, default `true` |
| `last_scraped_at` | timestamp | Used by the admin panel / scraper scheduler |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

### `job_offers`
Core table storing individual job postings imported from external sources.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `title` | varchar | Not null |
| `company_name` | varchar | Not null |
| `source_id` | integer | FK → `job_sources.id` |
| `location` | varchar | Free-text |
| `description` | text | |
| `employment_type` | employment_type | |
| `experience_level` | experience_level | |
| `url` | varchar | Not null, unique — used as the dedup key when re-importing |
| `is_active` | boolean | Not null, default `true` — marks whether the offer is still live |
| `scraped_at` | timestamp | When the offer was last fetched/refreshed |
| `expires_at` | timestamp | Optional expiry date, if known |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

Indexed on `location`, `employment_type`, `experience_level`, and `is_active` to support filtering.

### `technologies`
A flat vocabulary of technologies/skills (e.g. "React", "Python", "Docker") referenced by both job offers and user profiles.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `name` | varchar | Unique, not null |

### `job_offer_technologies`
Many-to-many mapping between job offers and the technologies they require.

| Column | Type | Notes |
|---|---|---|
| `job_offer_id` | integer | FK → `job_offers.id`, part of composite PK |
| `technology_id` | integer | FK → `technologies.id`, part of composite PK |

### `user_technologies`
Many-to-many mapping between users and the technologies they know, used for matching and filtering.

| Column | Type | Notes |
|---|---|---|
| `user_id` | integer | FK → `users.id`, part of composite PK |
| `technology_id` | integer | FK → `technologies.id`, part of composite PK |

### `saved_jobs`
Tracks which job offers a user has bookmarked for later.

| Column | Type | Notes |
|---|---|---|
| `user_id` | integer | FK → `users.id`, part of composite PK |
| `job_id` | integer | FK → `job_offers.id`, part of composite PK |
| `created_at` | timestamp | |

### `applications`
Tracks a user's application to a specific job offer, including status and notes.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `user_id` | integer | FK → `users.id` |
| `job_id` | integer | FK → `job_offers.id` |
| `status` | application_status | |
| `applied_at` | timestamp | |
| `notes` | text | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

## Relationships Summary

- `users.role_id` → `roles.id`
- `user_profiles.user_id` → `users.id` (1:1)
- `user_preferred_locations.user_id` → `users.id` (1:N)
- `user_preferred_employment_types.user_id` → `users.id` (1:N)
- `job_offers.source_id` → `job_sources.id`
- `job_offer_technologies` links `job_offers` ↔ `technologies` (M:N)
- `user_technologies` links `users` ↔ `technologies` (M:N)
- `saved_jobs` links `users` ↔ `job_offers` (M:N)
- `applications` links `users` ↔ `job_offers` (1 application row per user–job pair, extended with status/notes)

## Design Notes

- **Deduplication of imported offers** relies on the `url` uniqueness constraint on `job_offers`. When the scraper re-encounters an existing URL, the corresponding row should be updated (`scraped_at`, `is_active`) rather than duplicated.
- **Location and preference matching** currently use free-text fields rather than a normalized `locations` table. Scraped location strings vary significantly between sources (e.g. "Warszawa" vs "Warsaw, PL" vs "Remote/Warsaw"), so normalization/geocoding is left as a possible future improvement rather than solved at this stage.
- **`technologies` and `roles`** are treated as static lookup tables. `created_at` was intentionally omitted from `technologies` since no current feature depends on knowing when a technology entry was created; this may be revisited if technology "trend over time" analysis is added later.

## Planned Additions (Future Work)

As development progresses, the following will be introduced to support the AI assistant module:

- A table to store AI assistant query history (per user, per job offer), including the query type (e.g. summary, requirements extraction, match scoring), the context sent to the model, and the generated response.
- Possible extensions to `job_offer_technologies` (e.g. required vs. nice-to-have flags) if AI-driven matching requires finer-grained weighting.

These will be documented separately once the AI module's design is finalized.