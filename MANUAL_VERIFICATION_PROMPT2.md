# Manual Verification Guide - Prompt 2

## ✅ Step-by-Step Manual Checks

### 1. Check Files Were Created

Open your file explorer or run:
```bash
# Check database models exist
ls backend/src/db/

# You should see:
# - __init__.py
# - base.py
# - models.py
# - session.py
```

```bash
# Check Alembic setup
ls backend/alembic/

# You should see:
# - env.py
# - script.py.mako
# - README
# - versions/ folder
```

```bash
# Check migration file
ls backend/alembic/versions/

# You should see:
# - 001_initial_schema.py
```

---

### 2. Verify Python Can Import Models

Open a Python terminal in the `backend` folder:

```bash
cd backend
python3
```

Then in the Python shell, type these commands one by one:

```python
# Test 1: Import base
from src.db.base import Base
print("✅ Base imported successfully")

# Test 2: Import models
from src.db.models import User, OAuthAccount, RawEmail, Transaction, ParsingLog
print("✅ All models imported successfully")

# Test 3: Import enums
from src.db.models import OAuthProvider, EmailStatus, TransactionType, ParsingStatus
print("✅ All enums imported successfully")

# Test 4: Check enum values
print(f"OAuth Providers: {[p.value for p in OAuthProvider]}")
print(f"Email Statuses: {[s.value for s in EmailStatus]}")
print("✅ Enums working correctly")

# Test 5: Create a User instance (in memory, not saved)
user = User(email="test@example.com", full_name="Test User")
print(f"✅ Created user: {user.email}")

# Exit Python
exit()
```

**Expected output:** All checks should show ✅

---

### 3. Run the Tests

This is the most important verification:

```bash
cd backend
python3 -m pytest tests/ -v
```

**Expected output:**
```
tests/test_database.py::TestUserModel::test_create_user PASSED
tests/test_database.py::TestUserModel::test_read_user PASSED
tests/test_database.py::TestUserModel::test_update_user PASSED
tests/test_database.py::TestUserModel::test_soft_delete_user PASSED
tests/test_database.py::TestOAuthAccountModel::test_create_oauth_account PASSED
tests/test_database.py::TestOAuthAccountModel::test_oauth_user_relationship PASSED
tests/test_database.py::TestRawEmailModel::test_create_raw_email PASSED
tests/test_database.py::TestRawEmailModel::test_email_status_update PASSED
tests/test_database.py::TestTransactionModel::test_create_transaction PASSED
tests/test_database.py::TestTransactionModel::test_transaction_relationships PASSED
tests/test_database.py::TestParsingLogModel::test_create_parsing_log PASSED
tests/test_database.py::TestParsingLogModel::test_parsing_log_with_error PASSED
tests/test_database.py::TestDatabaseSchema::test_user_email_unique PASSED
tests/test_database.py::TestDatabaseSchema::test_message_id_unique PASSED
tests/test_health.py::test_app_boots PASSED
tests/test_health.py::test_health_endpoint_returns_200 PASSED
tests/test_health.py::test_health_endpoint_response_format PASSED

======================= 17 passed =======================
```

**✅ If you see "17 passed" - Everything is working!**

---

### 4. Check Configuration

```bash
# View the config file
cat backend/config.py
```

Look for this line:
```python
DATABASE_URL: str = "postgresql://user:password@localhost:5432/noreply"
```

**✅ Should be present**

```bash
# View the .env.example
cat backend/.env.example
```

Should contain:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/finemail
```

**✅ Should be present**

---

### 5. Verify Database Models Structure

Open these files in your editor and check:

**backend/src/db/models.py** - Should contain:
- ✅ `class User(BaseModel)` - with email, full_name
- ✅ `class OAuthAccount(BaseModel)` - with provider, tokens
- ✅ `class RawEmail(BaseModel)` - with message_id, sender, body
- ✅ `class Transaction(BaseModel)` - with amount, merchant, type
- ✅ `class ParsingLog(BaseModel)` - with status, error_message

**backend/src/db/base.py** - Should contain:
- ✅ `Base = declarative_base()`
- ✅ `class BaseModel(Base)` with id, created_at, updated_at, deleted_at, is_deleted

**backend/src/db/session.py** - Should contain:
- ✅ `engine = create_engine(...)`
- ✅ `SessionLocal = sessionmaker(...)`
- ✅ `def get_db()` function

---

### 6. Check Alembic Configuration

```bash
# View alembic.ini
cat backend/alembic.ini
```

**✅ Should exist and contain `[alembic]` section**

```bash
# View migration file
cat backend/alembic/versions/001_initial_schema.py
```

**✅ Should contain `def upgrade()` and `def downgrade()` functions**

---

## 🎯 Quick Verification Checklist

Copy this checklist and check each item:

```
Prompt 2 Manual Verification Checklist

Files Created:
[ ] backend/src/db/__init__.py
[ ] backend/src/db/base.py
[ ] backend/src/db/models.py
[ ] backend/src/db/session.py
[ ] backend/alembic.ini
[ ] backend/alembic/env.py
[ ] backend/alembic/script.py.mako
[ ] backend/alembic/versions/001_initial_schema.py
[ ] backend/tests/test_database.py
[ ] PROMPT2_COMPLETED.md

Python Imports:
[ ] Can import Base from src.db.base
[ ] Can import all models from src.db.models
[ ] Can import enums (OAuthProvider, EmailStatus, etc.)
[ ] Can create model instances without errors

Tests:
[ ] All 17 tests pass (pytest tests/ -v)
[ ] 14 database tests pass
[ ] 3 health tests from prompt1 still pass

Configuration:
[ ] DATABASE_URL in config.py
[ ] DATABASE_URL example in .env.example

Models:
[ ] User model has email, full_name
[ ] OAuthAccount model has provider, tokens
[ ] RawEmail model has message_id, sender, body
[ ] Transaction model has amount, merchant, type
[ ] ParsingLog model has status, error_message

Features:
[ ] All models have UUID primary keys
[ ] All models have created_at, updated_at
[ ] All models have soft delete (is_deleted, deleted_at)
[ ] Relationships defined between models
[ ] Enums used for status fields
```

---

## 🚨 Common Issues & Solutions

### Issue 1: Import errors
```
ModuleNotFoundError: No module named 'sqlalchemy'
```
**Solution:**
```bash
cd backend
python3 -m pip install -r requirements.txt
```

### Issue 2: Tests fail
```
FAILED tests/test_database.py
```
**Solution:** Check the error message. Most common is missing dependencies.

### Issue 3: Can't find alembic
```
alembic: command not found
```
**Solution:** Use `python3 -m alembic` instead

---

## ✅ Success Criteria

**Prompt 2 is working correctly if:**
1. ✅ All 17 tests pass
2. ✅ You can import all models in Python
3. ✅ All files listed above exist
4. ✅ No import errors when running tests

**If all above are true, you're ready to push to Git!**
