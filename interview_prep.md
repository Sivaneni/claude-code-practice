# CI/CD Pipeline — Interview Prep

## What I Built

I implemented a CI/CD quality gate pipeline for a Python FastAPI project using **GitHub Actions** and **pre-commit hooks**. The goal was to automate code quality checks so that no broken, poorly formatted, or insecure code ever reaches the main branch.

---

## The Problem It Solves

In team environments, developers write code in different styles, forget to run linters, and occasionally push secrets or vulnerable code. A CI pipeline enforces standards automatically — without relying on human discipline.

---

## Two Layers of Defense

### Layer 1 — Pre-commit Hooks (Local)
Before a developer can even commit code, hooks run automatically on their machine:

- **Black** — enforces consistent code formatting
- **Ruff** — catches linting issues and fixes import ordering
- **Bandit** — scans for common Python security vulnerabilities
- **Built-in hooks** — detect private keys, large files, merge conflicts, and trailing whitespace

This catches issues at the earliest possible point — before they ever leave the developer's machine.

### Layer 2 — GitHub Actions (Remote)
When code is pushed or a pull request is opened, the same checks run again in the cloud. The pipeline has two sequential jobs:

**Job 1: Lint & Security**
- Checks out the code on a clean Ubuntu runner
- Sets up Python 3.12 with pip caching for speed
- Runs Black (format check), Ruff (lint), and Bandit (security scan)

**Job 2: Tests** *(runs only if Job 1 passes)*
- Uses `needs: lint-and-security` to enforce sequential execution
- Runs pytest with a placeholder API key (real secrets never enter CI)
- Gracefully skips if no test files exist yet

This `needs` dependency means bad code is rejected early — tests don't waste compute time if formatting or security checks already failed.

---

## Key DevOps Decisions

| Decision | Reason |
|---|---|
| Two-layer checks (local + remote) | Fail fast locally, enforce remotely |
| `needs:` between jobs | Don't run tests on already-broken code |
| pip caching | Faster CI runs, lower cost |
| Placeholder API key in CI | Never expose real secrets in workflows |
| `--exit-zero` on Bandit | Reports findings without blocking; used for visibility |
| `pyproject.toml` for config | Single source of truth for all tool configs |

---

## What I Would Add Next

- Separate `deploy` job triggered only on merge to `master`
- Test coverage reporting with `pytest-cov`
- Dependabot for automated dependency updates
- Branch protection rules requiring CI to pass before merge

---

## CI Failure & Root Cause Analysis

### Incident
The GitHub Actions `test` job failed with:
```
ModuleNotFoundError: No module named 'fastapi'
```

### Root Cause
`requirements-dev.txt` was missing the `-r requirements.txt` include line. A linter/formatter hook silently stripped it during an earlier commit. As a result, the CI runner installed only dev tools (Black, Ruff, pytest, etc.) but **never installed the production dependencies** (fastapi, httpx, python-dotenv). When pytest tried to collect `test_weather_api.py`, the import `from fastapi.testclient import TestClient` failed immediately.

### Fix Applied
Restored `-r requirements.txt` as the first line of `requirements-dev.txt`:
```
-r requirements.txt   ← re-added this line
black>=24.0.0
ruff>=0.4.0
...
```

### Lesson Learned
Always verify that `requirements-dev.txt` explicitly includes production dependencies via `-r requirements.txt`. A CI environment is a clean slate — it installs only what you tell it to. Never assume dependencies are pre-installed.

---

## One-liner Summary for Interviews

> "I set up a two-layer CI pipeline — pre-commit hooks catch issues locally before commit, and GitHub Actions re-enforces the same checks on every push and PR, with sequential jobs so tests only run on clean code."
