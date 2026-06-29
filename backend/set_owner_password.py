"""One-off maintenance: make the platform OWNER's login match the configured
SEED_ADMIN_* values (your KarimMichel123 credentials).

The normal seeding only creates the owner on a brand-new database; it never
changes an existing owner's password. Run this whenever you need to (re)set the
owner login. It is idempotent and safe to re-run.

    cd backend
    .venv/Scripts/python set_owner_password.py        # Windows
    python set_owner_password.py                       # elsewhere

It reads SEED_ADMIN_USERNAME / SEED_ADMIN_PASSWORD from the .env it loads, so it
acts on whichever database DATABASE_URL points to.
"""

from sqlalchemy import select

from app.auth import hash_password
from app.config import settings
from app.db import SessionLocal
from app.models import User


def main() -> None:
    username = settings.seed_admin_username
    password = settings.seed_admin_password
    db = SessionLocal()
    try:
        owner = db.execute(select(User).where(User.role == "owner")).scalars().first()
        if owner is None:
            owner = User(
                username=username,
                full_name="Platform Owner",
                password_hash=hash_password(password),
                role="owner",
                company_id=None,
                is_active=True,
            )
            db.add(owner)
            action = "Created"
        else:
            owner.username = username
            owner.password_hash = hash_password(password)
            owner.is_active = True
            action = "Updated"
        db.commit()
        print(f"{action} owner login -> username='{username}' (password set from SEED_ADMIN_PASSWORD).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
