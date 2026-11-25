"""Promote one existing signup to the initial super-admin account.

Run from the signup-crud-app directory:
    python scripts/bootstrap_super_admin.py admin@example.com
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT))

from api.index import User, engine


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/bootstrap_super_admin.py <existing-account-email>")
        return 2

    email = sys.argv[1].strip().lower()
    with Session(engine) as db:
        existing_super_admin = db.scalar(
            select(User.id).where(User.role == "super_admin").limit(1)
        )
        if existing_super_admin is not None:
            print("A super-admin account already exists; no changes were made.")
            return 1

        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print("No account with that email exists. Sign up first, then retry.")
            return 1

        confirmation = input(
            f"Promote {user.email} to the initial super admin? Type PROMOTE: "
        )
        if confirmation != "PROMOTE":
            print("Cancelled; no changes were made.")
            return 1

        user.role = "super_admin"
        user.approval_status = "approved"
        user.approved_at = datetime.now(timezone.utc)
        user.approved_by = None
        db.commit()

    print("Initial super-admin account is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
