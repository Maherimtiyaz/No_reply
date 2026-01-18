# Prompt 1 – Project Context, Architecture & Repo Scaffold

## 1. Project Context
NoReply is a fintech SaaS platform that ingests transactional emails (bank alerts, broker notifications, crypto exchange emails) and converts them into a clean, structured financial ledger.

The product is built for individuals who want automated, private, and accurate tracking of their financial activity without manual entry.

Core problem solved:
- Financial data is scattered across emails
- No unified ledger for transactions
- Manual tracking is error-prone

Tech stack constraints (must follow exactly):
- Backend: FastAPI (Python)
- Auth: OAuth (Gmail first)
- Database: PostgreSQL
- ORM: SQLAlchemy
- Migrations: Alembic
- Frontend: Minimal Next.js or simple React
- AI: OpenAI-compatible LLM abstraction (not used yet)
- Tests: Pytest

---

## 2. What We Are Building in This Step
This step sets up the project foundation only.

We are building:
- Backend and frontend repository scaffolding
- Environment configuration structure
- Health check endpoint
- Testing infrastructure

Out of scope:
- Business logic
- Database models
- OAuth
- AI parsing
- Email ingestion

---

## 3. Technical Requirements
Backend:
- FastAPI app bootstrap
- `/health` endpoint returning status OK
- Config loaded via environment variables

Frontend:
- Minimal scaffold only

Database:
- No database logic yet

Auth:
- None

Error Handling:
- Centralized exception handler scaffold

---

## 4. Folder & File Structure (MANDATORY)
root/
├── backend/
├── frontend/
├── README.md

---

## 5. Tests Required
- App boots
- `/health` returns 200

---

## 6. Actual Prompt
You are a senior backend architect. Design and scaffold a production-grade SaaS repository called NoReply using FastAPI. Do NOT implement business logic yet.
