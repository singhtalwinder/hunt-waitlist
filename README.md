# Hunt

> Real tech jobs early—directly from company career pages—matched to candidates based on who is actually a fit.

Hunt is a job discovery and matching system that:
- Surfaces **real tech jobs before they hit job boards**
- Matches candidates only to jobs they're **meaningfully qualified for**
- Explicitly shows **"no jobs found"** when appropriate

## Architecture

```
hunt-waitlist/
├── frontend/           # Next.js 16 + React 19 + Tailwind
│   ├── app/            # Pages (waitlist, dashboard, jobs, settings)
│   ├── components/     # React components
│   └── lib/            # API client, types, utilities
├── backend/            # Python + FastAPI
│   ├── app/
│   │   ├── api/        # REST endpoints
│   │   ├── db/         # SQLAlchemy models
│   │   ├── engines/    # Core business logic
│   │   │   ├── discovery/   # Company & ATS detection
│   │   │   ├── crawl/       # Web crawling
│   │   │   ├── render/      # JS rendering (Playwright)
│   │   │   ├── extract/     # Job extraction (ATS parsers + LLM)
│   │   │   ├── normalize/   # Role/seniority/location normalization
│   │   │   ├── match/       # Candidate matching
│   │   │   ├── feedback/    # Explanations & notifications
│   │   │   └── monitor/     # System health metrics
│   │   └── workers/    # Background tasks (Dramatiq)
│   └── tests/
├── infra/              # Docker & Fly.io configs
└── supabase-migration-hunt.sql
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Next.js 16, React 19, Tailwind CSS |
| Backend | Python 3.11, FastAPI, Pydantic |
| Database | PostgreSQL (Supabase) + pgvector |
| Caching | Redis (Upstash) |
| Browser | Playwright (Chromium) |
| NLP | spaCy, sentence-transformers |
| LLM | OpenAI GPT-4o-mini |
| Email | Resend |
| Hosting | Fly.io (backend), Vercel (frontend) |

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for local development)
- Supabase account
- Upstash Redis account

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browsers
playwright install chromium

# Download spaCy model
python -m spacy download en_core_web_sm

# Copy environment variables
cp .env.example .env
# Edit .env with your values

# Run migrations
# (Apply supabase-migration-hunt.sql to your Supabase project)

# Start the API
uvicorn app.main:app --reload

# In another terminal, start the worker
dramatiq app.workers.tasks
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy environment variables
cp .env.example .env.local
# Edit .env.local with your values

# Start development server
npm run dev
```

### Running with Docker

```bash
# Build images
docker build -f infra/docker/Dockerfile.api -t hunt-api .
docker build -f infra/docker/Dockerfile.worker -t hunt-worker .

# Run API
docker run -p 8000:8000 --env-file backend/.env hunt-api

# Run Worker
docker run --env-file backend/.env hunt-worker
```

## Database Schema

The main tables are:

- `companies` - Companies with career pages to crawl
- `crawl_snapshots` - Raw HTML from crawled pages
- `jobs_raw` - Extracted job data before normalization
- `jobs` - Canonical normalized jobs with embeddings
- `candidate_profiles` - User preferences for matching
- `matches` - Job-candidate match results with scores

Run `supabase-migration-hunt.sql` in your Supabase SQL Editor to create all tables.

## Engines

### 1. Discovery Engine
Identifies companies and their ATS types (Greenhouse, Lever, Ashby).

### 2. Crawl Engine
Fetches pages with rate limiting, robots.txt respect, and change detection.

### 3. Render Engine
Uses Playwright to render JavaScript-heavy pages when needed.

### 4. Extraction Engine
ATS-specific parsers with LLM fallback for unknown layouts.

### 5. Normalization Engine
Maps titles to role families, detects seniority, normalizes locations.

### 6. Matching Engine
Hard constraints + soft scoring for candidate-job matching.

### 7. Feedback Engine
Generates match explanations and weekly email digests.

### 8. Monitoring Engine
Tracks crawl success rates, job freshness, match yield.

## API Endpoints

### Public
- `GET /api/jobs` - List jobs with filters
- `GET /api/jobs/{id}` - Get job details
- `GET /api/candidates/{id}/matches` - Get matched jobs

### Admin
- `GET /api/admin/metrics` - System metrics
- `GET /api/admin/companies` - List companies
- `POST /api/admin/companies` - Add company

### Internal (Workers)
- `POST /api/internal/crawl/trigger` - Trigger crawl
- `POST /api/internal/match/trigger` - Trigger matching

## Deployment

### Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
flyctl auth login

# Create apps
flyctl apps create hunt-api
flyctl apps create hunt-worker

# Set secrets
flyctl secrets set DATABASE_URL=... REDIS_URL=... -a hunt-api
flyctl secrets set DATABASE_URL=... REDIS_URL=... -a hunt-worker

# Deploy
flyctl deploy --config infra/fly.api.toml
flyctl deploy --config infra/fly.worker.toml
```

### GitHub Actions

Set `FLY_API_TOKEN` secret in your repository, then push to `main` to trigger deployment.

## Environment Variables

### Backend (`.env`)

```bash
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=...
OPENAI_API_KEY=sk-...
RESEND_API_KEY=re_...
```

### Frontend (`.env.local`)

```bash
NEXT_PUBLIC_SUPABASE_URL=https://...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

Private - All rights reserved.
