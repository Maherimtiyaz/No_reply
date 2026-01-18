#!/usr/bin/env python3
"""
Verification script for Prompt 2 - Database Setup
This script checks if all database components are working correctly
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test if all database modules can be imported"""
    print("1. Testing imports...")
    try:
        from src.db import Base, User, OAuthAccount, RawEmail, Transaction, ParsingLog
        from src.db import get_db, engine, SessionLocal
        from src.db.models import OAuthProvider, EmailStatus, TransactionType, ParsingStatus
        print("   ✅ All imports successful")
        return True
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        return False

def test_model_creation():
    """Test if models can be instantiated"""
    print("\n2. Testing model creation...")
    try:
        from src.db.models import User, OAuthProvider, EmailStatus, TransactionType, ParsingStatus
        from datetime import datetime
        
        # Create instances (not persisted)
        user = User(email="test@example.com", full_name="Test User")
        print(f"   ✅ User model created: {user.email}")
        
        # Check enum values
        assert OAuthProvider.GOOGLE == "google"
        assert EmailStatus.PENDING == "pending"
        assert TransactionType.DEBIT == "debit"
        assert ParsingStatus.SUCCESS == "success"
        print("   ✅ All enum types working")
        
        return True
    except Exception as e:
        print(f"   ❌ Model creation failed: {e}")
        return False

def test_alembic_setup():
    """Test if Alembic is properly configured"""
    print("\n3. Testing Alembic configuration...")
    try:
        from pathlib import Path
        
        # Check if alembic files exist
        alembic_ini = Path("alembic.ini")
        alembic_dir = Path("alembic")
        alembic_env = Path("alembic/env.py")
        migration_dir = Path("alembic/versions")
        initial_migration = Path("alembic/versions/001_initial_schema.py")
        
        checks = {
            "alembic.ini": alembic_ini.exists(),
            "alembic/ directory": alembic_dir.exists(),
            "alembic/env.py": alembic_env.exists(),
            "alembic/versions/": migration_dir.exists(),
            "Initial migration": initial_migration.exists()
        }
        
        all_passed = True
        for name, exists in checks.items():
            status = "✅" if exists else "❌"
            print(f"   {status} {name}")
            if not exists:
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"   ❌ Alembic check failed: {e}")
        return False

def test_session_factory():
    """Test if database session factory works"""
    print("\n4. Testing database session factory...")
    try:
        from src.db import SessionLocal, get_db
        
        # Test SessionLocal
        session = SessionLocal()
        session.close()
        print("   ✅ SessionLocal factory working")
        
        # Test get_db generator
        db_gen = get_db()
        db = next(db_gen)
        db.close()
        print("   ✅ get_db() dependency working")
        
        return True
    except Exception as e:
        print(f"   ❌ Session factory failed: {e}")
        return False

def test_in_memory_db():
    """Test creating tables in memory database"""
    print("\n5. Testing in-memory database creation...")
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from src.db.base import Base
        from src.db.models import User, OAuthAccount, RawEmail, Transaction, ParsingLog
        from datetime import datetime
        
        # Create in-memory SQLite database
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        print("   ✅ All tables created successfully")
        
        # Create a session and add test data
        TestSession = sessionmaker(bind=engine)
        session = TestSession()
        
        # Add a test user
        user = User(email="verify@test.com", full_name="Verify User")
        session.add(user)
        session.commit()
        
        # Query it back
        fetched = session.query(User).filter(User.email == "verify@test.com").first()
        assert fetched is not None
        assert fetched.full_name == "Verify User"
        print("   ✅ CRUD operations working")
        
        session.close()
        return True
    except Exception as e:
        print(f"   ❌ In-memory database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("Prompt 2 - Database Setup Verification")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Model Creation", test_model_creation()))
    results.append(("Alembic Setup", test_alembic_setup()))
    results.append(("Session Factory", test_session_factory()))
    results.append(("In-Memory DB", test_in_memory_db()))
    
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All verification checks passed!")
        print("✅ Prompt 2 is working correctly!")
        return 0
    else:
        print("\n⚠️  Some checks failed. Review the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
