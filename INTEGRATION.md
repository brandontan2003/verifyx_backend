# VerifyX — Integration Guide

Last updated: May 2026

> This is the integration document. Read it before touching any code. Without completing the steps in this guide, the backend will not start.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quickstart](#quickstart)
- [Environment Variables](#environment-variables)
- [Step 1 — Database Setup](#step-1--database-setup)
- [Step 2 — Auth Provider](#step-2--auth-provider)
- [Step 3 — AI Configuration](#step-3--ai-configuration)
- [Step 4 — Scoring Engine](#step-4--scoring-engine)
- [Step 5 — Rate Limiting](#step-5--rate-limiting)
- [Known Limitations](#known-limitations)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)

---

## Prerequisites

| Requirement       | Version | Notes                                                              |
|-------------------|---------|--------------------------------------------------------------------|
| Python            | 3.12+   |                                                                    |
| PostgreSQL        | 14+     | No extensions required                                             |
| Docker + Compose  | Latest  | Recommended for local setup                                        |
| Anthropic API key | —       | [console.anthropic.com](https://console.anthropic.com)             |
| Groq API key      | —       | [console.groq.com](https://console.groq.com) — free tier available |
| Redis             | 7+      | Optional — see [Rate Limiting](#step-5--rate-limiting)             |

---

## Quickstart

```bash
# 1. Copy and fill in the environment template
cp .env.example .env.dev

# 2. Start all services (Postgres, Redis, Flyway migrations, backend)
docker compose --env-file .env.dev up --build

# 3. Confirm healthy
curl http://localhost:8000/health

# 4. Run unit tests
docker compose exec verifyx-backend-service pytest tests/unit/
```

API docs: `http://localhost:8000/docs`

---

## Environment Variables

### Core — Required

| Variable                  | Example                                                      | Description                                                                 |
|---------------------------|--------------------------------------------------------------|-----------------------------------------------------------------------------|
| `DATABASE_URL`            | `postgresql+asyncpg://user:pass@verifyx-postgres:5432/appdb` | Must use the `asyncpg` driver. Do not use `psycopg2` — the engine is async. |
| `FRONTEND_URL`            | `http://localhost:5173`                                      | CORS allowed origin. Comma-separated for multiple origins.                  |
| `RESET_PASSWORD_ENDPOINT` | `/reset-password`                                            | Injected into password reset emails as the redirect URL.                    |

### Authentication — Required

| Variable          | Example                         | Description                                                             |
|-------------------|---------------------------------|-------------------------------------------------------------------------|
| `AUTH_PROVIDER`   | `supabase`                      | Selects the auth implementation. Options: `supabase`, `cognito`         |
| `JWT_SIGNING_KEY` | `-----BEGIN PUBLIC KEY-----...` | Public key to verify incoming JWTs. Supports RS256 and HS256.           |
| `JWT_AUDIENCE`    | `authenticated`                 | Expected `aud` claim in the JWT. Must match what your auth server sets. |

### AI — Required

| Variable              | Example                                                                                      | Description                                                                                                                                                  |
|-----------------------|----------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `ANTHROPIC_API_KEY`   | `sk-ant-...`                                                                                 | Claude API key. Required when `AI_PROVIDER=claude`.                                                                                                          |
| `GROQ_API_KEY`        | `gsk_...`                                                                                    | Groq API key. Used as automatic fallback when Claude fails.                                                                                                  |
| `AI_PROVIDER`         | `claude`                                                                                     | Primary AI provider. Options: `claude`, `groq`. Default: `claude`.                                                                                           |
| `CLAUDE_MODEL`        | `claude-sonnet-4-6`                                                                          | Claude model string.                                                                                                                                         |
| `GROQ_MODEL`          | `llama-3.3-70b-versatile`                                                                    | Groq model string.                                                                                                                                           |
| `AI_PLATFORM_CONTEXT` | `a free, global K-12 digital literacy education platform serving students in grades 8 to 12` | Injected into every AI system prompt as the platform description. **Change this from the default** — the default references Singapore.                       |
| `CHILD_SAFETY_MODE`   | `True`                                                                                       | Appends explicit age-appropriate content instructions to all scenario generation prompts. **Must be `True` for Giggle Academy deployment.** Default: `True`. |

### Rate Limiting — Optional but Recommended

| Variable                | Example                | Default    | Description                                                                                                |
|-------------------------|------------------------|------------|------------------------------------------------------------------------------------------------------------|
| `REDIS_URL`             | `redis://redis:6379/0` | *(absent)* | Absent → in-memory store. **In-memory is single-process only.** Do not run multiple workers without Redis. |
| `RATE_LIMIT_AI`         | `10`                   | `0`        | Max AI requests per minute per IP.                                                                         |
| `RATE_LIMIT_AUTH`       | `10`                   | `0`        | Max auth requests per minute per IP.                                                                       |
| `RATE_LIMIT_ROOM`       | `20`                   | `0`        | Max room requests per minute per IP.                                                                       |
| `RATE_LIMIT_READ`       | `60`                   | `0`        | Max GET requests per minute per IP.                                                                        |
| `RATE_LIMIT_SUBMIT`     | `60`                   | `0`        | Max POST/PUT requests per minute per IP.                                                                   |
| `DAILY_CHALLENGE_LIMIT` | `1`                    | `1`        | New challenges a user can generate per calendar day. Re-attempts are unlimited.                            |

### Scoring Engine — Optional

| Variable               | Example                               | Default   | Description                                                                         |
|------------------------|---------------------------------------|-----------|-------------------------------------------------------------------------------------|
| `SCORING_ENGINE`       | `default`                             | `default` | `default` = pure-Python rule-based, no external dep. `kie` = KIE/Drools DMN server. |
| `XP_TABLE`             | `{1: 10, 2: 20, 3: 35, 4: 50, 5: 75}` | as shown  | Base XP per difficulty level. Read by `DefaultScoringEngine` only.                  |
| `RULE_SERVER_URL`      | `http://kie:8080`                     | —         | Required only when `SCORING_ENGINE=kie`.                                            |
| `RULE_SERVER_USER`     | `kieserver`                           | —         | KIE server username. Required only when `SCORING_ENGINE=kie`.                       |
| `RULE_SERVER_PASSWORD` | `kieserver1!`                         | —         | KIE server password. Required only when `SCORING_ENGINE=kie`.                       |

### Database Migration (Flyway)

| Variable            | Example                                         | Description                                                 |
|---------------------|-------------------------------------------------|-------------------------------------------------------------|
| `FLYWAY_URL`        | `jdbc:postgresql://verifyx-postgres:5432/appdb` | Flyway JDBC connection string.                              |
| `FLYWAY_USER`       | `postgres`                                      | Database user for Flyway.                                   |
| `FLYWAY_PASSWORD`   | `postgres`                                      | Database password for Flyway.                               |
| `FLYWAY_SCHEMAS`    | `public`                                        | Schema Flyway manages.                                      |
| `POSTGRES_USER`     | `postgres`                                      | PostgreSQL superuser (used by the Docker postgres service). |
| `POSTGRES_PASSWORD` | `postgres`                                      | PostgreSQL password.                                        |
| `POSTGRES_DB`       | `appdb`                                         | Database name.                                              |

### Logging

| Variable        | Example | Default | Description                                               |
|-----------------|---------|---------|-----------------------------------------------------------|
| `LOGGING_LEVEL` | `INFO`  | `INFO`  | Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |

---

## Step 1 — Database Setup

### Option A — Docker Compose (Recommended)

Flyway runs automatically before the backend starts. SQL migration files live in `db-migration/`. No manual steps required.

### Option B — Run Flyway Manually

```bash
docker run --rm \
  -e FLYWAY_URL=jdbc:postgresql://<host>:5432/<dbname> \
  -e FLYWAY_USER=<user> \
  -e FLYWAY_PASSWORD=<password> \
  -v $(pwd)/db-migration:/flyway/sql \
  flyway/flyway:12.7.0 migrate
```

### Option C — Run SQL Directly

```bash
psql -h <host> -U <user> -d <dbname> -f db-migration/V1__initial_schema.sql
```

### Schema Notes

- **`users.user_id`** has no auto-generated default. Your `GiggleAuthProvider.sign_up()` must supply the user ID from your auth system (UUID string).
- Integer columns (`xp`, `streak`, `challenges_completed`, `perfect_scores`) default to `0` at the DB level.
- `news_reactions` enforces one reaction per user per post via `UNIQUE (news_id, user_id)`. Swapping between up/downvote is handled at the service layer.
- Comment depth max is 1 (top-level + one reply). Enforced at service layer only, not DB constraint.
- Report terminal states (`approved`, `rejected`) cannot be changed after transition. Enforced at service layer — returns 409 on any attempt to modify.

### Enum Strategy

The schema uses PostgreSQL `ENUM` types for **stable lifecycle fields** (challenge status, room status, report status, question type, reaction type).

Fields that are likely to grow over time (harm types, content types, badge types, role names, scope names) use `VARCHAR` with named `CHECK` constraints. Adding a new value to these fields:

```sql
-- Example: adding a new harm type
ALTER TABLE reports DROP CONSTRAINT reports_harm_type_check;
ALTER TABLE reports ADD CONSTRAINT reports_harm_type_check
    CHECK (harm_type IN (
        'misinformation', 'scam', 'phishing', 'deepfake',
        'cyberbullying', 'other', 'ransomware'  -- new value
    ));
```

Update the corresponding Python enum in `app/enums/` to match.

---

## Step 2 — Auth Provider

This is the most critical integration step. Three implementations ship out of the box — pick the one that matches your infrastructure, or implement your own.

### Option A — Supabase (default)

The original VerifyX auth backend. Use this if you already have a Supabase project.

```bash
AUTH_PROVIDER=supabase
JWT_SIGNING_KEY=<your Supabase JWT public key>   # Project Settings → API → JWT Secret
JWT_AUDIENCE=authenticated
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_KEY=<service_role key>           # Project Settings → API → service_role
RESET_PASSWORD_ENDPOINT=/reset-password          # appended to the Origin header for redirect
```

**How it works:** JWTs are verified locally against `JWT_SIGNING_KEY` using RS256/ES256. Sessions are validated live against `SUPABASE_URL/auth/v1/user`. Password reset sends a one-time link via Supabase; the frontend forwards the token in the request body as `request.token`.

Reference implementation: `app/core/authentication/supabase.py`
Tests: `pytest tests/unit/core/authentication/test_supabase_provider.py -v`

---

### Option B — AWS Cognito

Use this if you are deploying on AWS and already have a Cognito User Pool.

```bash
AUTH_PROVIDER=cognito
JWT_SIGNING_KEY=<Cognito JWKS public key>         # from your User Pool's JWKS endpoint
JWT_AUDIENCE=<your App Client ID>
COGNITO_REGION=ap-southeast-1
COGNITO_CLIENT_ID=<App Client ID>
COGNITO_USER_POOL_ID=<User Pool ID>
```

**How it works:** JWTs are verified locally against `JWT_SIGNING_KEY` using RS256. Sessions are validated live via `cognito-idp.get_user()`. Sign-up auto-confirms users (no email verification step). Password reset sends a 6-digit confirmation code via Cognito; the frontend forwards it as `request.confirmation_code`. Refresh tokens are not rotated by Cognito — the original refresh token is returned as-is.

Reference implementation: `app/core/authentication/cognito.py`
Tests: `pytest tests/unit/core/authentication/test_cognito_provider.py -v`

---

### Adding a new provider

Implement `AuthProvider` (`app/core/authentication_provider.py`), add a routing branch in `app/dependencies.py`, and set your new value in `AUTH_PROVIDER`. No other files need to change.

---


## Step 3 — AI Configuration

The backend uses Claude (primary) → Groq (automatic fallback). Both keys are required.

### Set the platform context

```bash
AI_PLATFORM_CONTEXT=a free, global K-12 digital literacy education platform serving students in grades 8 to 12
CHILD_SAFETY_MODE=True
```

`AI_PLATFORM_CONTEXT` is injected into every AI system prompt. Set it to an accurate description of your deployment — the AI uses this to frame its responses appropriately.

`CHILD_SAFETY_MODE=True` appends the following to all scenario generation prompts:

> This platform is used by learners aged 13–18. All generated content MUST be age-appropriate and free of graphic violence, explicit language, or adult themes. Frame scenarios around critical thinking and media literacy, not fear or distress.

**Do not disable this for Giggle Academy deployment.**

### Challenge themes

Available themes (hardcoded in `app/enums/ThemeEnum.py`):

`misinformation` | `scam` | `phishing` | `crisis` | `data_privacy` | `deepfake` | `AI_awareness`

---

## Step 4 — Scoring Engine

Use `SCORING_ENGINE=default` for Giggle Academy. This requires no external dependencies.

```bash
SCORING_ENGINE=default
XP_TABLE={1: 10, 2: 20, 3: 35, 4: 50, 5: 75}
```

**XP formula:**

```
base_xp    = XP_TABLE[difficulty]
multiplier = 2.0   if answered in < 25% of time limit
           = 1.5   if answered in < 50% of time limit
           = 1.2   if answered in < 75% of time limit
           = 1.0   otherwise
xp_earned  = round(base_xp × multiplier)
```

The `kie` engine delegates to a KIE/Drools DMN server and is the original VerifyX infrastructure. It falls back to `default` on any KIE failure. Only use it if you have an existing KIE/Drools deployment.

---

## Step 5 — Rate Limiting

With Redis (recommended for production):

```bash
REDIS_URL=redis://redis:6379/0
RATE_LIMIT_AI=10
RATE_LIMIT_AUTH=10
RATE_LIMIT_ROOM=20
RATE_LIMIT_READ=60
RATE_LIMIT_SUBMIT=60
DAILY_CHALLENGE_LIMIT=1
```

Without Redis, the backend starts with an in-process `InMemoryStore`. This is safe for:
- Single-process deployments
- Local development
- Integration testing

It is **not safe** for multi-worker deployments — each worker maintains its own counters and rate limits will not be shared across processes.

---

## Known Limitations

| Limitation | Detail |
|---|---|
| No WebSocket | Multiplayer rooms and leaderboards use client polling. Reconnect logic is not implemented. |
| No unpublish | Approved news posts are permanent. There is no endpoint to retract a published post. |
| Report terminal state | `approved`/`rejected` reports cannot be modified. Returns 409 on any attempt. |
| Comment depth | Maximum 2 levels (top-level + one reply). Enforced at service layer only. |
| In-memory rate limit | Not shared across workers. Use Redis for any multi-process deployment. |
| No Prometheus metrics | `/metrics` endpoint is not implemented. |
| Multiplayer polling | No WebSocket — clients must poll `/room/{id}` for state updates. |

---

## Support

For integration questions, open an issue in this repository. Reference the relevant section of this document and include your `AUTH_PROVIDER`, `SCORING_ENGINE`, and `AI_PROVIDER` settings in your report.
