"""Command line interface for LogiFlows operations and administration."""
import sys
import argparse
from sqlalchemy import text
from app.core.config import settings
from app.database.session import SessionLocal, engine
from app.database.init_db import init_db


def seed_demo_command() -> int:
    """Seed demo and baseline data into database (strictly prohibited in production)."""
    env = (settings.ENVIRONMENT or "").strip().lower()
    if env == "production":
        print("ERROR: Demo data seeding is strictly prohibited in PRODUCTION environment.", file=sys.stderr)
        return 1

    print(f"Seeding demo data for environment: {settings.ENVIRONMENT}...")
    db = SessionLocal()
    try:
        init_db(db)
        print("Demo data successfully seeded.")
        return 0
    except Exception as e:
        print(f"ERROR: Failed to seed demo data: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


def check_db_command() -> int:
    """Check database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database connectivity verified.")
        return 0
    except Exception as e:
        print(f"ERROR: Database check failed: {e}", file=sys.stderr)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="LogiFlows Courier Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("seed-demo", help="Seed demo and baseline data (non-production only)")
    subparsers.add_parser("check-db", help="Verify database connectivity")

    args = parser.parse_args()

    if args.command == "seed-demo":
        sys.exit(seed_demo_command())
    elif args.command == "check-db":
        sys.exit(check_db_command())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
