from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def migrate_db(bind_engine=None):
    """
    Safely migrates existing database schema to ensure multi-user isolation columns exist.
    Handles SQLite table alterations idempotently.
    """
    eng = bind_engine or engine
    Base.metadata.create_all(bind=eng)
    with eng.connect() as conn:
        for table in ["contracts", "executions", "audit_logs"]:
            try:
                result = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                columns = [row[1] for row in result]
                if columns and "user_id" not in columns:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN user_id VARCHAR"))
                    conn.commit()
            except Exception:
                pass

        try:
            users_res = conn.execute(text("SELECT id FROM users ORDER BY created_at ASC LIMIT 1")).fetchall()
            if users_res:
                first_uid = users_res[0][0]
                conn.execute(text("UPDATE contracts SET user_id = :uid WHERE user_id IS NULL"), {"uid": first_uid})
                conn.execute(text("UPDATE executions SET user_id = :uid WHERE user_id IS NULL"), {"uid": first_uid})
                conn.execute(text("UPDATE audit_logs SET user_id = :uid WHERE user_id IS NULL"), {"uid": first_uid})
                conn.commit()
        except Exception:
            pass

