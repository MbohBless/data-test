# LLM-Powered Analytical Intelligence Engine

**MVP Implementation**: FastAPI + LangChain + PostgreSQL + Groq LLMs

Automatically analyze structured data using natural language queries. The system generates SQL, executes queries safely, and returns verified human-readable insights.

---

## 🎯 Overview

This is a production-ready MVP skeleton for an LLM-driven analytical engine that:

- **Accepts natural language queries** → "Show total revenue per month"
- **Generates optimized SQL** using Groq LLMs via LangChain
- **Executes queries safely** with read-only PostgreSQL access
- **Self-evaluates results** and regenerates if needed
- **Returns insights** with visualization recommendations

### Key Features

✅ **Modular Architecture** - MCP-ready components
✅ **Safe Execution** - Read-only SQL with validation
✅ **Self-Correcting** - LLM evaluation and regeneration loop
✅ **Observable** - Structured logging with request tracing
✅ **Scalable** - Async operations with connection pooling
✅ **Type-Safe** - Full type hints and Pydantic validation

---

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│         FastAPI Application             │
│  ┌─────────────────────────────────┐   │
│  │     POST /api/v1/analyze        │   │
│  └──────────────┬──────────────────┘   │
└─────────────────┼──────────────────────┘
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
┌──────────┐ ┌────────┐ ┌────────┐
│ Schema   │ │  LLM   │ │ Exec   │
│ Manager  │ │Pipeline│ │ utor   │
└────┬─────┘ └───┬────┘ └───┬────┘
     │           │            │
     ▼           ▼            ▼
┌─────────┐ ┌────────┐ ┌──────────┐
│  Redis  │ │ Groq   │ │Postgres  │
│  Cache  │ │  API   │ │    DB    │
└─────────┘ └────────┘ └──────────┘
```

### Component Workflow

1. **Schema Manager** → Fetches and caches database schema
2. **LLM Pipeline** → Generates SQL from natural language
3. **SQL Verifier** → Validates query safety and correctness
4. **Executor** → Executes read-only SQL
5. **Evaluator** → Checks if results answer the request
6. **Insight Generator** → Creates human-readable summary

---

## 📁 Project Structure

```
.
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── analyze.py          # API endpoints (analyze, schema)
│   ├── core/
│   │   ├── cache.py                # Redis caching layer
│   │   ├── config.py               # Settings management
│   │   ├── evaluator.py            # Query evaluation & regeneration
│   │   ├── llm_pipeline.py         # LangChain LLM workflows
│   │   ├── schema_manager.py       # Database schema extraction
│   │   └── executor/
│   │       └── postgres_executor.py # Safe SQL execution
│   ├── models/
│   │   └── schemas.py              # Pydantic request/response models
│   └── main.py                     # FastAPI application entrypoint
├── tests/
│   ├── unit/                       # Unit tests
│   ├── integration/                # Integration tests
│   └── conftest.py                 # Pytest fixtures
├── docker-compose.yml              # Local development stack
├── Dockerfile                      # Container definition
├── requirements.txt                # Python dependencies
├── pyproject.toml                  # Project configuration
├── .env.example                    # Environment template
└── README.md                       # This file
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Groq API Key ([get one here](https://console.groq.com))

### 1. Clone and Setup

```bash
# Clone repository
git clone <repository-url>
cd llm-analytical-engine

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your Groq API key
# GROQ_API_KEY=your_api_key_here
```

### 3. Start Services

```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Wait for services to be healthy
docker-compose ps

# Run migrations (if any)
# (Future: alembic upgrade head)
```

### 4. Run Application

```bash
# Development mode with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Docker Compose (full stack)
docker-compose up
```

### 5. Test API

```bash
# Health check
curl http://localhost:8000/health

# Get database schema
curl http://localhost:8000/api/v1/schema

# Submit analysis request
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Show total revenue per month",
    "include_raw_data": true
  }'
```

### 6. View Documentation

Open browser to:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🔧 Configuration

All configuration is managed via environment variables. See `.env.example` for full list.

### Key Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql://...` |
| `REDIS_URL` | Redis connection | `redis://...` |
| `GROQ_API_KEY` | Groq API key | *required* |
| `GROQ_MODEL_NAME` | Model identifier | `mixtral-8x7b-32768` |
| `GROQ_TEMPERATURE` | LLM temperature | `0.1` |
| `MAX_RETRY_ATTEMPTS` | SQL regeneration limit | `2` |
| `READ_ONLY_MODE` | Enforce read-only SQL | `true` |

---

## 🧪 Testing

### Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test file
pytest tests/unit/test_executor.py

# Integration tests only
pytest tests/integration/
```

### Code Quality

```bash
# Format code
black app/ tests/

# Lint code
ruff check app/ tests/

# Type checking
mypy app/
```

---

## 📊 API Reference

### POST /api/v1/analyze

Submit natural language analytical query.

**Request:**
```json
{
  "request": "Show total revenue per month",
  "context": {},
  "force_refresh_schema": false,
  "include_raw_data": true
}
```

**Response:**
```json
{
  "insight": "Revenue increased steadily, peaking in July.",
  "key_findings": [
    "Monthly revenue grew 22% on average",
    "July had highest revenue at $142k"
  ],
  "data": [...],
  "visualization_type": "line_chart",
  "sql": "SELECT date_trunc('month', date) AS month, ...",
  "execution_time_ms": 45.2,
  "row_count": 12,
  "evaluation": {...},
  "attempts": 1
}
```

### GET /api/v1/schema

Get database schema summary.

**Response:**
```json
{
  "tables": [...],
  "total_tables": 5,
  "database_name": "analytics",
  "fetched_at": "2024-07-22T10:30:00Z",
  "cached": true
}
```

---

## 🔒 Security

### SQL Execution Safety

- ✅ **Read-only mode** enforced at connection level
- ✅ **Command whitelist** (SELECT, WITH, EXPLAIN only)
- ✅ **SQL injection prevention** via regex and validation
- ✅ **Query timeout** limits execution time
- ✅ **Table name sanitization** prevents path traversal

### Best Practices

1. Always run in `READ_ONLY_MODE=true`
2. Use dedicated read-only database user
3. Limit Groq API key permissions
4. Enable query logging for audit
5. Set appropriate rate limits

---

## 🎯 Development Roadmap

### ✅ Phase 1: MVP Skeleton (Current)

- [x] FastAPI skeleton
- [x] PostgreSQL executor with safety
- [x] LangChain integration (stubs)
- [x] Schema caching
- [x] API endpoints
- [x] Docker setup

### 🚧 Phase 2: Implementation (Next 4 weeks)

- [ ] Complete LLM pipeline (SQL generation)
- [ ] Implement evaluation chain
- [ ] Add insight generation
- [ ] Complete test coverage
- [ ] Add logging & observability

### 📅 Phase 3: MCP Integration (Weeks 7-10)

- [ ] Refactor to MCP DataSource Provider
- [ ] Implement MCP Executor interface
- [ ] Add MCP Model Provider wrapper
- [ ] Create MCP Feedback Repository

### 🎉 Phase 4: Production (Weeks 11-12)

- [ ] Performance optimization
- [ ] Security hardening
- [ ] Monitoring & alerting
- [ ] Load testing
- [ ] Deployment automation

---

## 🤝 Contributing

### Code Standards

- Follow PEP 8 style guide
- Add type hints to all functions
- Write docstrings for public APIs
- Maintain test coverage >80%
- Use structured logging

### Commit Messages

```
feat: Add SQL generation chain
fix: Handle NULL values in summary
docs: Update API reference
test: Add executor validation tests
refactor: Extract prompt templates
```

---

## 📝 Implementation Notes

### Function Stubs

Many functions are marked with `raise NotImplementedError()`. These are intentional placeholders for MVP skeleton. Implementation order:

1. **Schema Manager** - `_fetch_schema_from_database()`, `get_sample_rows()`
2. **LLM Pipeline** - All chain methods with actual Groq calls
3. **Evaluator** - `_parse_evaluation_output()`, regeneration logic
4. **Tests** - Complete all `pass` placeholders

### MCP-Ready Design

All core modules expose MCP-compatible interfaces:

- **SchemaManager** → MCP DataSource Provider
- **PostgresExecutor** → MCP Executor
- **LLMPipeline** → MCP Model Provider
- **CacheManager** → MCP Feedback Repository

When migrating to MCP, swap implementations without changing business logic.

---

## 🐛 Troubleshooting

### Database Connection Failed

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check connection string
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

### Redis Connection Failed

```bash
# Check Redis is running
docker-compose ps redis

# Test connection
redis-cli -u $REDIS_URL ping
```

### LLM API Errors

```bash
# Verify API key
echo $GROQ_API_KEY

# Check API status
curl -H "Authorization: Bearer $GROQ_API_KEY" \
  https://api.groq.com/v1/models
```

---

## 📧 Contact

For questions or issues, open a GitHub issue.

---

**Built with ❤️ for data-driven teams**
