# Git Workflow Guide - Pushing Prompt 2 Changes

## Current Status
- ✅ Prompt 1 already pushed
- 🔄 Prompt 2 completed and needs to be pushed

---

## Option 1: Push Prompt 2 on Main Branch (Simple)

If you're working solo and want to keep it simple:

```bash
# 1. Check current status
git status

# 2. Add all Prompt 2 changes
git add .

# 3. Commit with descriptive message
git commit -m "feat: Implement database models and migrations (Prompt 2)

- Add SQLAlchemy models: User, OAuthAccount, RawEmail, Transaction, ParsingLog
- Set up Alembic migrations with initial schema
- Implement database session management
- Add 14 comprehensive database tests
- Update configuration for database URL
- All tests passing (17/17)
"

# 4. Push to main branch
git push origin main
```

---

## Option 2: Feature Branch Workflow (Recommended for Teams)

Better for collaboration and code reviews:

```bash
# 1. Create a new branch for Prompt 2
git checkout -b feature/prompt2-database-setup

# 2. Check what files changed
git status

# 3. Add all changes
git add .

# 4. Commit with detailed message
git commit -m "feat: Implement database models and migrations (Prompt 2)

Database Setup:
- Create SQLAlchemy models (User, OAuthAccount, RawEmail, Transaction, ParsingLog)
- Implement soft delete pattern with is_deleted and deleted_at
- Add UUID primary keys for all tables
- Set up Alembic for database migrations

Testing:
- Add 14 comprehensive database tests
- Test CRUD operations for all models
- Verify relationships and constraints
- All 17 tests passing

Files:
- backend/src/db/ (base.py, models.py, session.py)
- backend/alembic/ (configuration and initial migration)
- backend/tests/test_database.py
"

# 5. Push the feature branch
git push origin feature/prompt2-database-setup

# 6. Create a Pull Request on GitHub/GitLab
# Then merge after review

# 7. After merge, switch back to main and pull
git checkout main
git pull origin main
```

---

## Option 3: Separate Commits for Each Component

More granular history:

```bash
# 1. Stage and commit database models
git add backend/src/db/
git commit -m "feat(db): Add SQLAlchemy models and base classes"

# 2. Stage and commit Alembic setup
git add backend/alembic* backend/alembic/
git commit -m "feat(db): Set up Alembic migrations with initial schema"

# 3. Stage and commit tests
git add backend/tests/test_database.py
git commit -m "test(db): Add comprehensive database model tests"

# 4. Stage and commit config changes
git add backend/config.py backend/.env.example
git commit -m "config: Add database URL configuration"

# 5. Stage and commit documentation
git add PROMPT2_COMPLETED.md
git commit -m "docs: Add Prompt 2 completion documentation"

# 6. Push all commits
git push origin main
```

---

## Quick Reference - Git Commands

### Check Status
```bash
git status                    # See what changed
git diff                      # See line-by-line changes
git log --oneline -5          # See last 5 commits
```

### Undo Changes (Before Commit)
```bash
git checkout -- <file>        # Discard changes to a file
git reset HEAD <file>         # Unstage a file
git reset --hard              # Discard all changes (careful!)
```

### View Changes
```bash
git diff HEAD                 # All uncommitted changes
git diff --staged             # Only staged changes
git show                      # Show last commit
```

### Branches
```bash
git branch                    # List branches
git branch <name>             # Create branch
git checkout <name>           # Switch branch
git checkout -b <name>        # Create and switch
git branch -d <name>          # Delete branch
```

---

## Recommended Workflow for This Project

Since you're working through prompts sequentially:

```bash
# For each prompt:
git checkout -b feature/prompt<N>-<description>
# ... work on prompt ...
# ... run tests ...
git add .
git commit -m "feat: Implement <prompt description>"
git push origin feature/prompt<N>-<description>
# Create PR, review, merge
git checkout main
git pull origin main

# Then move to next prompt
```

---

## Verifying Before Push

Always verify before pushing:

```bash
# 1. Run all tests
cd backend
python3 -m pytest tests/ -v

# 2. Check what will be committed
git status
git diff --staged

# 3. Verify the build works
cd backend
python3 -c "from src.db import Base, User; print('✅ Imports work')"

# 4. Run verification script
python3 tmp_rovodev_verify_db.py
```

---

## Example: Complete Workflow for Prompt 2

```bash
# Create feature branch
git checkout -b feature/prompt2-database

# Verify everything works
cd backend
python3 -m pytest tests/ -v
python3 tmp_rovodev_verify_db.py

# Stage all changes
git add .

# Check what's staged
git status

# Commit with descriptive message
git commit -m "feat: Complete Prompt 2 - Database setup with SQLAlchemy

Implementation:
- 5 SQLAlchemy models with relationships
- Alembic migration setup
- Database session management
- UUID primary keys with soft delete
- 14 comprehensive tests (all passing)

Tests: 17/17 passing ✅
"

# Push to remote
git push origin feature/prompt2-database

# After review/approval, merge to main
git checkout main
git merge feature/prompt2-database
git push origin main

# Clean up feature branch (optional)
git branch -d feature/prompt2-database
git push origin --delete feature/prompt2-database
```

---

## What to Include in Commit Message

Good commit message structure:

```
<type>: <short summary> (max 50 chars)

<detailed description>
- What was implemented
- Why it was implemented
- Any important decisions

Tests: X/X passing
Breaking changes: None
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `test:` - Tests
- `refactor:` - Code refactoring
- `style:` - Formatting
- `chore:` - Maintenance

---

## Need Help?

Run these commands to check your repository:

```bash
git status                    # Current state
git log --oneline -10         # Recent commits
git remote -v                 # Remote repositories
git branch -a                 # All branches
```
