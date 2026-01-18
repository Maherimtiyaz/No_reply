# NoReply

NoReply is a fintech SaaS platform that ingests transactional emails (bank alerts, broker notifications, crypto exchange emails) and converts them into a clean, structured financial ledger.

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: Next.js (React)
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Migrations**: Alembic
- **Auth**: OAuth (Gmail)
- **AI**: OpenAI-compatible LLM abstraction
- **Tests**: Pytest

## Project Structure

```
root/
├── backend/          # FastAPI backend application
│   ├── main.py      # Application entry point
│   ├── config.py    # Configuration management
│   ├── exceptions.py # Exception handlers
│   └── tests/       # Backend tests
├── frontend/         # Next.js frontend application
└── README.md
```

## Getting Started

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy environment variables:
```bash
cp .env.example .env
```

4. Run the application:
```bash
uvicorn main:app --reload
```

5. Run tests:
```bash
pytest
```

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Run development server:
```bash
npm run dev
```

## API Endpoints

- `GET /health` - Health check endpoint

## Development Status

- [x] Project scaffold
- [ ] Database schema
- [ ] OAuth authentication
- [ ] Email ingestion
- [ ] AI parsing engine
- [ ] Ledger API
- [ ] Production hardening
