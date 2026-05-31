# VerifyX Backend

**AI-powered digital safety and media literacy training — backend services**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00)](https://sqlalchemy.org)
[![Tests](https://img.shields.io/badge/Tests-672%20passing-22C55E)](./tests)

---

## What is VerifyX?

VerifyX trains instincts, not just awareness. Traditional digital literacy education is static — VerifyX generates fresh
AI challenges on demand, lets users verify suspicious content in real time, and builds a community around reporting
online harms.

The backend ships as a standalone FastAPI service designed to plug into any frontend or mobile application via a
documented REST API and swappable provider interfaces.

---

## Features

| Feature                      | Description                                                                                                                                |
|------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| 🎯 **AI Challenge Engine**   | Claude generates unique scenarios per user per session across 8 harm themes. Daily limit enforced. Answers AI-evaluated with full debrief. |
| 🛡️ **Content Verification** | Paste any suspicious URL or message — returns verdict, confidence score, and specific red flags.                                           |
| 🏆 **Multiplayer Rooms**     | Shared challenge sessions. Room lifecycle: waiting → in progress → completed.                                                              |
| 📊 **Leaderboard & XP**      | Streak tracking, difficulty-weighted XP with speed multiplier, badge awards.                                                               |
| 🚨 **Community Reporting**   | Users submit suspicious content. Admin review queue. Approved reports auto-publish as news posts.                                          |
| 📰 **News & Discussion**     | Threaded comments (2 levels), mutually exclusive upvote/downvote reactions.                                                                |
| 🔌 **Swappable Auth**        | `AuthProvider` interface — swap Supabase, Cognito, or implement your own in one file.                                                      |
| ⚡ **AI Fallback Chain**      | Claude primary → Groq automatic fallback. No manual intervention required.                                                                 |

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- An [Anthropic API key](https://console.anthropic.com) (Claude)
- A [Groq API key](https://console.groq.com) (free tier available — used as AI fallback)

### Quickstart

```bash
# 1. Clone the repository
git clone <repo-url>
cd verifyx-backend

# 2. Configure environment
cp .env.example .env.dev
# Edit .env.dev — at minimum, fill in:
#   DATABASE_URL, ANTHROPIC_API_KEY, GROQ_API_KEY, FRONTEND_URL

# 3. Start all services
docker compose --env-file .env.dev up --build

# 4. Verify the backend is healthy
curl http://localhost:8000/health
# → {"success": true}
```

The API is running at **`http://localhost:8000`**
Interactive docs at **`http://localhost:8000/docs`**

### Running Without Docker

```bash
# Install dependencies
pip install -r requirements.txt

# Export environment
export $(cat .env.dev | xargs)

# Run migrations (requires a running PostgreSQL instance)
flyway -url=$FLYWAY_URL -user=$FLYWAY_USER -password=$FLYWAY_PASSWORD migrate

# Start the server
fastapi run app/main.py --port 8000
```

---

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env.dev` to get started.

### Essential Variables

| Variable              | Required | Default    | Description                                            |
|-----------------------|----------|------------|--------------------------------------------------------|
| `DATABASE_URL`        | ✅        | —          | `postgresql+asyncpg://user:pass@host:5432/db`          |
| `ANTHROPIC_API_KEY`   | ✅        | —          | Claude API key                                         |
| `GROQ_API_KEY`        | ✅        | —          | Groq fallback key                                      |
| `FRONTEND_URL`        | ✅        | —          | CORS allowed origin(s), comma-separated                |
| `AUTH_PROVIDER`       | ✅        | `supabase` | `supabase` \| `cognito` \| `giggle`                    |
| `JWT_SIGNING_KEY`     | ✅        | —          | Public key for JWT verification                        |
| `AI_PLATFORM_CONTEXT` | ✅        | generic    | Platform description injected into all AI prompts      |
| `CHILD_SAFETY_MODE`   | ✅        | `True`     | Appends child safety instructions to scenario prompts  |
| `REDIS_URL`           | ❌        | —          | Absent → in-memory rate limiting (single process only) |
| `SCORING_ENGINE`      | ❌        | `default`  | `default` (pure Python) \| `kie` (Drools DMN)          |

See [INTEGRATION.md](./INTEGRATION.md) for the full variable reference.

---

## API Reference

All endpoints are prefixed `/api/v1`. Full interactive docs at `/docs`.

<details>
<summary><strong>Auth</strong> — <code>/api/v1/auth</code></summary>

| Method | Path                    | Description                     |
|--------|-------------------------|---------------------------------|
| `POST` | `/auth/signin`          | Sign in with email and password |
| `POST` | `/auth/signup`          | Register a new user             |
| `POST` | `/auth/logout`          | Revoke session                  |
| `POST` | `/auth/refresh`         | Refresh access token            |
| `POST` | `/auth/forget/password` | Send password reset email       |
| `PUT`  | `/auth/update/password` | Apply new password              |

</details>

<details>
<summary><strong>Challenges</strong> — <code>/api/v1/challenge</code></summary>

| Method | Path                     | Description                 |
|--------|--------------------------|-----------------------------|
| `POST` | `/challenge`             | Generate a new AI challenge |
| `POST` | `/challenge/{id}/submit` | Submit an answer            |
| `GET`  | `/challenge/history`     | Paginated attempt history   |
| `GET`  | `/challenge/{id}`        | Get a specific challenge    |

</details>

<details>
<summary><strong>Multiplayer</strong> — <code>/api/v1/room</code></summary>

| Method | Path                     | Description                     |
|--------|--------------------------|---------------------------------|
| `POST` | `/room`                  | Create a room (host auto-joins) |
| `POST` | `/room/join`             | Join by 6-character code        |
| `POST` | `/room/{id}/start`       | Start the session               |
| `GET`  | `/room/{id}`             | Room state (use for polling)    |
| `GET`  | `/room/{id}/challenge`   | Shared challenge for the room   |
| `GET`  | `/room/{id}/leaderboard` | Room results                    |

</details>

<details>
<summary><strong>Content Verification</strong> — <code>/api/v1/chatbot</code></summary>

| Method | Path              | Description                  |
|--------|-------------------|------------------------------|
| `POST` | `/chatbot/verify` | Verify a URL or message text |

**Response shape:**

```json
{
  "verdict": "scam",
  "confidence": 91,
  "is_low_confidence": false,
  "red_flags": [
    "urgency language",
    "unsolicited prize claim"
  ],
  "recommendation": "Do not click any links. Report and delete.",
  "disclaimer": "This assessment is generated by AI..."
}
```

Possible verdicts: `legitimate` | `suspicious` | `scam` | `misinformation` | `insufficient_information`

</details>

<details>
<summary><strong>Reporting & News</strong> — <code>/api/v1/report</code>, <code>/api/v1/news</code></summary>

| Method | Path                  | Description                        |
|--------|-----------------------|------------------------------------|
| `POST` | `/report`             | Submit a suspicious content report |
| `GET`  | `/report/me`          | Own report history                 |
| `GET`  | `/report/me/{id}`     | Report detail                      |
| `GET`  | `/news`               | Paginated news feed                |
| `GET`  | `/news/{id}`          | Post with threaded comments        |
| `POST` | `/news/{id}/comments` | Add a comment                      |
| `POST` | `/news/{id}/react`    | Upvote or downvote                 |

</details>

<details>
<summary><strong>Progress & Leaderboard</strong><code>/api/v1/progress</code>, <code>/api/v1/leaderboard</code></summary>

| Method | Path           | Description            |
|--------|----------------|------------------------|
| `GET`  | `/progress`    | Own XP, streak, badges |
| `GET`  | `/leaderboard` | Ranked scores          |

</details>

---

## Project Structure

```
app/
├── api/v1/                 # Route handlers (one file per domain)
├── ai/
│   ├── providers/          # ClaudeProvider, GroqProvider
│   ├── client.py           # generate_scenario, evaluate_response, generate_debrief
│   └── factory.py          # Provider selection via AI_PROVIDER env var
├── core/
│   ├── authentication/     # AuthProvider ABC + Supabase, Cognito, Giggle stubs
│   ├── cache/              # RateLimitStore ABC + RedisStore, InMemoryStore
│   ├── rules/              # ScoringEngine ABC + DefaultScoringEngine, KIEScoringEngine
│   └── exceptions/         # Exception classes and FastAPI handlers
├── services/               # Business logic (one file per domain)
├── repositories/           # Async SQLAlchemy database access
├── models/                 # ORM model definitions
├── dto/                    # Pydantic request/response schemas
├── enums/                  # Enum definitions
├── config.py               # All settings via environment variables
└── main.py                 # App entry point and lifespan
db-migration/               # Flyway-versioned SQL migration files
tests/
├── unit/                   # 672 tests, no external dependencies
└── integration/            # Requires running PostgreSQL
```

---

## Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Full suite with coverage
pytest
```

672 unit tests across AI providers, scoring engine, auth provider routing, cache store, rate limiting, all service layer
logic, enums, and exceptions.

---

## Architecture

**Swappable providers** — three interfaces let operators replace infrastructure without modifying application logic:

- **`AuthProvider`** (`app/core/authentication_provider.py`) — implement 8 methods to use any auth backend. Set
  `AUTH_PROVIDER=supabase|cognito`.
- **`RateLimitStore`** (`app/core/cache/registry.py`) — `REDIS_URL` present → Redis; absent → in-memory.
- **`ScoringEngine`** (`app/core/rules/scoring_engine.py`) — `SCORING_ENGINE=default` (pure Python, no deps) or `kie` (
  Drools DMN).

**AI fallback chain** — `complete_with_fallback()` in `app/ai/factory.py` calls Claude first; on any exception, retries
with Groq automatically. Both providers implement the same `AIProvider` ABC.

---

## Contributing

Contributions are welcome. Please open an issue before submitting a pull request for significant changes.

---
