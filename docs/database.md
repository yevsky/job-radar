# Database Schema

![ER diagram of the database schema](./img/db-schema.png)

This document describes the relational database schema for the job offer discovery and analysis application. It covers the core functionality: user management, user profiles and preferences, job offer storage, technology tagging and application tracking (saved offers included).

Job offers are **not bulk-scraped** from job boards. They reach the application in three ways: a Tavily web search built from the user's profile, the "Send to JobRadar" browser button, or a manual import of a link. For those offers only the basic facts (link, title, company, location, deadline and source) are stored. The full text is stored only for offers posted on JobRadar itself (`source = posted`, for now the demo offers loaded by `just seed`).

> **Note:** The AI module's tables are added together with the features that use them: `resumes` (the user's CVs) and `ai_analyses` (match results).

## Overview

The schema is organized around five functional areas:

1. **Access control** — users, roles, and user profiles
2. **User preferences** — skills and standing filter preferences used for search and matching
3. **Job offer data** — job offers and technologies
4. **User activity** — applications (saved offers included), their status history and search runs
5. **AI assistant module** — CVs (`resumes`) and match results (`ai_analyses`)

## Enums

### `employment_type`
Describes the type of employment contract associated with a job offer or preferred by a user.

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
| `trainee` | Entry-level / trainee or intern |
| `junior` | Junior |
| `middle` | Mid-level |
| `senior` | Senior |
| `lead` | Lead / management-adjacent |

### `source_kind`
Describes how a job offer reached the application.

| Value | Description |
|---|---|
| `search` | A search result the user kept (`POST /search/results`); `found_via` names the search source |
| `browser` | Sent from the "Send to JobRadar" browser button |
| `manual` | Added by hand: a pasted link or an admin file import |
| `posted` | Published on JobRadar itself (for now the demo offers loaded by `just seed`); the only offers with a stored `description` |

### `application_status`
Tracks the state of a user's application to a given job offer.

| Value | Description |
|---|---|
| `saved` | Saved for later, not applied yet (the "Saved offers" list) |
| `applied` | Application submitted |
| `screening` | First contact or screening call |
| `interview` | In the interview process |
| `offer` | Received an offer |
| `accepted` | Offer accepted |
| `rejected` | Rejected by the company |
| `declined` | The user turned the offer down |

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
| `role_id` | integer | FK → `roles.id`, not null |
| `search_daily_limit` | integer | Nullable. This user's own daily search limit, set by an admin; `NULL` means the default from `SEARCH_DAILY_LIMIT` |
| `search_sources` | varchar(50)[] | Nullable. The search sources this user chose (`tavily`, `jsearch`); `NULL` means every enabled source |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

### `user_profiles`
Extended profile information for a user, one-to-one with `users`.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `user_id` | integer | FK → `users.id`, unique, not null |
| `first_name` | varchar | |
| `last_name` | varchar | |
| `bio` | text | |
| `experience_level` | experience_level | |
| `desired_position` | varchar | The role the user is looking for (e.g. "backend developer"), used to build search queries |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

### `user_preferred_locations`
Standing location preferences used for search and filtering. A user may have multiple preferred locations. `Remote` is a valid value, which is how a user expresses a preference for remote work.

| Column | Type | Notes |
|---|---|---|
| `user_id` | integer | FK → `users.id`, part of composite PK |
| `location` | varchar | Free-text, part of composite PK |

### `user_preferred_employment_types`
Standing employment type preferences used for search and filtering. A user may prefer more than one employment type.

| Column | Type | Notes |
|---|---|---|
| `user_id` | integer | FK → `users.id`, part of composite PK |
| `employment_type` | employment_type | Part of composite PK |

### `technologies`
A flat vocabulary of technologies/skills (e.g. "React", "Python", "Docker") referenced by both job offers and user profiles. New entries are created automatically when a user or an offer mentions a technology that is not in the table yet.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `name` | varchar | Unique, not null |

### `user_technologies`
Many-to-many mapping between users and the technologies they know, used for search and matching.

| Column | Type | Notes |
|---|---|---|
| `user_id` | integer | FK → `users.id`, part of composite PK |
| `technology_id` | integer | FK → `technologies.id`, part of composite PK |

### `job_offers`
Core table storing the basic facts of individual job postings. The full offer text is intentionally not stored.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `title` | varchar | Not null |
| `company_name` | varchar | Not null |
| `source` | source_kind | Not null — how the offer reached the application |
| `found_via` | varchar(50) | Nullable — which search source found the offer (`tavily`, `jsearch`); `NULL` for other sources |
| `location` | varchar | Free-text |
| `employment_type` | employment_type | |
| `experience_level` | experience_level | |
| `owner_id` | integer | FK → `users.id`, nullable, ON DELETE CASCADE — `NULL` for public offers; set for a private offer that a user added by hand or kept from a search, which only that user sees |
| `url` | varchar | Not null — the link to the original offer, used as the dedup key; unique together with `owner_id` (NULLS NOT DISTINCT): one public offer per URL plus one private copy per user |
| `description` | text | Full offer text; stored only for `posted` offers |
| `is_active` | boolean | Not null, default `true` — marks whether the offer is still live |
| `deadline` | timestamp | Application deadline, if known |
| `last_seen_at` | timestamp | When an import last found this offer |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

Indexed on `location`, `employment_type`, `experience_level`, and `is_active` to support filtering.

### `job_offer_technologies`
Many-to-many mapping between job offers and the technologies they require.

| Column | Type | Notes |
|---|---|---|
| `job_offer_id` | integer | FK → `job_offers.id`, part of composite PK |
| `technology_id` | integer | FK → `technologies.id`, part of composite PK |

### `applications`
One user's progress on one job offer, from saving it to the final answer. A saved offer is an application with status `saved`; moving it to any other status is when the user applied.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `user_id` | integer | FK → `users.id`, not null, ON DELETE CASCADE, indexed |
| `job_offer_id` | integer | FK → `job_offers.id`, not null, ON DELETE CASCADE, indexed |
| `status` | application_status | Not null |
| `resume_id` | integer | Which CV was sent; not yet a FK to `resumes` (see Design Notes) |
| `notes` | text | |
| `applied_at` | timestamp | Null while `saved`; set when it moves on |
| `interview_at` | timestamp | Next interview, shown on the calendar |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

Unique on (`user_id`, `job_offer_id`): a user has at most one application per offer.

### `application_status_changes`
Every status an application had, with the time it changed. The history, the calendar and the dashboard stats are computed from it.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `application_id` | integer | FK → `applications.id`, not null, ON DELETE CASCADE, indexed |
| `status` | application_status | Not null |
| `changed_at` | timestamp | |

### `search_runs`
One row per search a user ran, used to enforce the daily search limit. The search results themselves are **not** stored.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `user_id` | integer | FK → `users.id`, not null, ON DELETE CASCADE |
| `created_at` | timestamp | When the search ran (UTC) |
| `result_count` | integer | How many results the search returned |

Indexed on (`user_id`, `created_at`) for counting a user's searches today.

### `resumes`
One of a user's CVs ("Backend CV", "Data CV"): the text read from the uploaded PDF and what the AI read from that text. **The PDF itself is not stored**: it's read in memory and thrown away, so less personal data is kept.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `user_id` | integer | FK → `users.id`, not null, ON DELETE CASCADE, indexed |
| `label` | varchar(100) | Not null; the user's name for the CV |
| `file_name` | varchar(255) | Not null; the uploaded file's name, shown in the list |
| `text` | text | Not null; the text of every page of the PDF |
| `extracted` | jsonb | What the AI read: position, level, skills, locations, employment types, summary. Null if the AI failed (it can be retried) |
| `extracted_with` | varchar(100) | Which provider and model read it, e.g. `ollama/qwen2.5:3b` |
| `applied_to_profile_at` | timestamp | When the user last copied data from it into the profile |
| `created_at` | timestamp | |

Unique on (`user_id`, `label`). At most 10 CVs per user (checked by the app).

### `ai_analyses`
One match analysis of an offer for a user ("How you match"). **Every run adds a row**, so earlier results stay comparable (for example after a prompt change); the app shows the newest. Analyses of search results are not stored, like the results themselves.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `user_id` | integer | FK → `users.id`, not null, ON DELETE CASCADE |
| `job_offer_id` | integer | FK → `job_offers.id`, not null, ON DELETE CASCADE, indexed |
| `resume_id` | integer | FK → `resumes.id`, ON DELETE SET NULL; the CV the model read, null if none (or deleted since) |
| `score` | smallint | Not null, 0-100 (check constraint); computed by code from a fixed rubric |
| `breakdown` | jsonb | Not null; the points of each rubric part (required skills, nice-to-have, level, location, employment type, role fit), so every point can be explained |
| `summary` | text | Not null; the model's one or two sentences |
| `reasons` | jsonb | Not null; list of strings |
| `red_flags` | jsonb | Not null; list of strings |
| `matched_skills` | jsonb | Not null; the user's skills the offer asks for, in the user's spelling (checked by code) |
| `missing_skills` | jsonb | Not null; required things none of the user's skills covers |
| `provider` | varchar(50) | Not null, e.g. `ollama` |
| `model` | varchar(100) | Not null, e.g. `qwen2.5:3b` |
| `prompt_version` | varchar(50) | Not null, e.g. `offer-analysis-v2` |
| `created_at` | timestamp | |

Indexed on (`user_id`, `job_offer_id`, `created_at`) for "this user's newest analysis of this offer".

### `chat_conversations`
One conversation with the AI assistant. The title is the user's first message, cut to 80 characters.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `user_id` | integer | FK → `users.id`, not null, ON DELETE CASCADE, indexed |
| `title` | varchar(80) | Null until the first message |
| `created_at` | timestamp | |
| `updated_at` | timestamp | Last message or action; the list is sorted by it |

### `chat_messages`
One line of a conversation. `role` is `user`, `assistant` or `tool`. A `tool` row is one tool call the assistant made: `content` is the short line the user sees ("Searched jobs: 8 results"), and `data` keeps the call id, the arguments, the result the model read and, for a search, the found results (so "save result 3" works later). These search results are the one place where found offers are kept, and they go away with the conversation.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `conversation_id` | integer | FK → `chat_conversations.id`, not null, ON DELETE CASCADE, indexed |
| `role` | varchar(20) | Not null: `user`, `assistant` or `tool` |
| `content` | text | Not null |
| `tool_name` | varchar(50) | Tool rows only, e.g. `search_jobs` |
| `data` | jsonb | Tool rows only |
| `created_at` | timestamp | |

### `chat_actions`
A change the assistant asked for (save an offer, change an application's status). It runs only when the user confirms it; a new message cancels a pending one.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `conversation_id` | integer | FK → `chat_conversations.id`, not null, ON DELETE CASCADE, indexed |
| `tool` | varchar(50) | Not null, e.g. `set_application_status` |
| `arguments` | jsonb | Not null; checked again when the user confirms |
| `summary` | text | Not null; written by code, e.g. 'Move "Backend Developer" at Codesky from applied to interview' |
| `status` | varchar(20) | Not null: `pending`, `confirmed`, `cancelled` or `failed` |
| `result` | text | What happened, or why it failed |
| `created_at` | timestamp | |
| `resolved_at` | timestamp | When it was confirmed, cancelled or failed |

### `search_source_switches`
An admin's on/off switch for one search source, for every user at once. `SEARCH_SOURCES` in `.env` says which sources the server can use (they have API keys); this table says which of them are switched on right now. A source without a row is on.

| Column | Type | Notes |
|---|---|---|
| `name` | varchar(50) | Primary key, e.g. `tavily`, `jsearch` |
| `is_enabled` | boolean | Not null. False leaves the source out of every user's searches |
| `updated_by_id` | integer | FK → `users.id`, nullable, ON DELETE SET NULL. The admin who switched it last |
| `updated_at` | timestamp | |

## Relationships Summary

- `users.role_id` → `roles.id`
- `user_profiles.user_id` → `users.id` (1:1)
- `user_preferred_locations.user_id` → `users.id` (1:N)
- `user_preferred_employment_types.user_id` → `users.id` (1:N)
- `user_technologies` links `users` ↔ `technologies` (M:N)
- `job_offer_technologies` links `job_offers` ↔ `technologies` (M:N)
- `applications` links `users` ↔ `job_offers` (1 row per user–offer pair, saved offers included)
- `application_status_changes` belongs to `applications` (1:N)
- `search_runs.user_id` → `users.id` (1:N)
- `resumes.user_id` → `users.id` (1:N)
- `ai_analyses` links `users` ↔ `job_offers` (N rows per user–offer pair), optionally → `resumes`
- `users` → `chat_conversations` (1:N) → `chat_messages` and `chat_actions` (1:N each)
- `search_source_switches.updated_by_id` → `users.id` (the admin who flipped it; kept as null when that account is deleted)

Deleting a user deletes their profile, preferences, skills links, applications (with their status history), search runs, CVs, analyses and assistant conversations. Deleting a job offer deletes the applications to it and its analyses. Deleting a CV keeps the analyses made with it (`resume_id` becomes null). Deleting a user never deletes rows in `technologies`.

## Design Notes

- **No bulk scraping.** Offers are found through Tavily search or sent by the user (browser button, manual import), and only their basic facts are stored. This avoids copying job boards' content, which could conflict with their terms of use and database rights. The offer page is fetched only when the offer is analysed.
- **No `job_sources` table.** There are only three fixed ways an offer can arrive, so the `source_kind` enum on `job_offers` replaces a lookup table. The job board an offer comes from can be read from its `url` domain.
- **Deduplication of offers** relies on the `url` uniqueness constraint on `job_offers`. When an import finds an existing URL again, the row is updated (`last_seen_at`, `is_active`) rather than duplicated.
- **Saved offers are applications with status `saved`.** Saving is the first step of the same life cycle, so one table holds it and the board shows saved offers as its first column. `/saved-jobs` is a shortcut over these rows for the Save button. Every status change is also written to `application_status_changes`, so the funnel can count how far each application got even after it was rejected.
- **Location and preference matching** use free-text fields rather than a normalized `locations` table. Location strings vary significantly between job boards (e.g. "Warszawa" vs "Warsaw, PL" vs "Remote/Warsaw"), so normalization/geocoding is left as a possible future improvement.
- **Search results are not stored.** A search returns its results to the user and keeps only a `search_runs` row (who, when, how many results). A result is saved only when the user keeps it, as their private offer (`source = search`, `found_via` set). The daily limit counts `search_runs` rows since midnight UTC; an admin can give a user their own limit (`users.search_daily_limit`). Each user can choose which enabled sources their searches ask (`users.search_sources`); a choice that no longer matches any enabled source falls back to all of them. An admin can switch a source off for everyone (`search_source_switches`): it is then left out of every search, but users' own choices stay saved and work again once it is back on. If every source is off, search answers 503 and no search is counted.
- **CV text, not the file.** Only the text of a CV is kept, plus the AI's reading of it as JSON (`extracted`): a JSON column fits because the app always reads and writes it as one object and never filters by it. Nothing is copied into the profile until the user picks fields to apply; skills, locations and employment types are then added to the profile's, never replacing what the user typed. `applications.resume_id` is still a plain integer; it becomes a foreign key to `resumes` when applications start recording which CV was sent.
- **Analyses: the model reads, code scores.** The model only maps the offer's requirements to the user's skills and gives a 0-10 role fit, a summary, reasons and red flags; the score is computed by code from a fixed rubric and stored with its `breakdown`. `provider`, `model` and `prompt_version` are stored with every row, so a result can always be traced to what produced it. Lists are JSON columns because they are always read and written whole with the row and never filtered.
- **`technologies` and `roles`** are treated as lookup tables. `created_at` was intentionally omitted from `technologies` since no current feature depends on knowing when a technology entry was created.

## Planned Additions (Future Work)

The following will be added together with the features that need them:

- **AI assistant module (rest):** a table storing AI query history for the chat about an offer (per user, per job offer: prompt version, the anonymised context sent to the model and the validated response).
- Possible extensions to `job_offer_technologies` (e.g. required vs. nice-to-have flags) if AI-driven matching requires finer-grained weighting.
