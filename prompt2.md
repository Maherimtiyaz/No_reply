# Prompt 2 – Database Design & Migrations

## 1. Project Context
NoReply is a fintech SaaS that converts transactional emails into a structured financial ledger.

---

## 2. What We Are Building in This Step
Database schema and migrations.

---

## 3. Technical Requirements
- PostgreSQL
- SQLAlchemy
- Alembic
- UUID PKs
- Soft deletes

Tables:
- users
- oauth_accounts
- raw_emails
- transactions
- parsing_logs

---

## 4. Folder Structure
backend/src/db/
backend/alembic/

---

## 5. Tests Required
- Migration applies
- CRUD works

---

## 6. Actual Prompt
Design and implement PostgreSQL schema using SQLAlchemy and Alembic.
