# Git Conventions

This document defines the Git workflow and naming conventions used in the JobRadar AI project.

The goal of these conventions is to keep the repository history clean, readable and consistent without introducing unnecessary complexity.

## Branching Strategy

The project uses the `main` branch as the stable branch.

A separate `develop` branch is not used, because this is a single-developer engineering thesis project.

For small setup or documentation changes, commits may be made directly to `main`.

For larger features or changes, a separate branch should be created and later merged into `main`.

## Change Types

The same change types are used for branch names and commit messages.

```text
feat       new application feature
fix        bug fix
refactor   code restructuring without behavior changes
chore      project setup, configuration, dependencies or maintenance
ci         continuous integration workflow changes
docs       documentation changes
test       adding or improving tests
```

## Branch Naming

Branch names use lowercase letters and kebab-case.

Format:

```text
<type>/<short-description>
```

Examples:

```text
feat/auth
feat/job-offers
feat/ai-analysis
fix/login-validation
refactor/auth-service
chore/backend-setup
ci/backend-checks
docs/backend-setup
```

## Commit Messages

Commit messages follow a simplified Conventional Commits format.

Format:

```text
<type>: <short description>
```

The description should be written in English, use the imperative mood and start with a lowercase letter.

Examples:

```text
docs: add initial README
chore: add backend project structure
chore: configure ruff and mypy
ci: add backend quality workflow
feat: add health check endpoint
feat: add user registration endpoint
fix: handle invalid login credentials
test: add authentication tests
refactor: move auth logic to service layer
```

## Difference Between Branches and Commits

A branch describes a larger area of work.

Example:

```text
feat/auth
```

This means that the branch is used for authentication-related work.

A commit describes one specific change made inside that branch.

Examples:

```text
feat: add user model
feat: add user registration endpoint
feat: add login endpoint
test: add authentication tests
```

## Practical Rule

Small documentation or setup changes may be committed directly to `main`.

Larger changes should be developed on a separate branch and merged into `main` after review or local verification.

Examples:

```text
Small README update              -> commit directly to main
Git conventions document         -> commit directly to main
Backend setup                    -> chore/backend-setup
Authentication module            -> feat/auth
Job offer management             -> feat/job-offers
AI analysis module               -> feat/ai-analysis
GitHub Actions configuration     -> ci/backend-checks
```
