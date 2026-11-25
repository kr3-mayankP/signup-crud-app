import os
import secrets
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    func,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)
from sqlalchemy.pool import NullPool
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set.")

APP_ENV = os.getenv(
    "APP_ENV", "production" if os.getenv("VERCEL") else "development"
)
SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    if APP_ENV == "production":
        raise RuntimeError("SESSION_SECRET environment variable is not set.")
    # Local-only fallback. Set a stable SESSION_SECRET in .env to keep sessions
    # valid across local API restarts.
    SESSION_SECRET = secrets.token_urlsafe(48)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg2://", 1
    )

if APP_ENV == "production":
    engine = create_engine(DATABASE_URL, poolclass=NullPool)
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user", server_default=text("'user'")
    )
    approval_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_terms: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, server_default=func.now()
    )


def initialize_database_schema() -> None:
    """Create the users table and add approval columns on API startup."""
    with engine.begin() as connection:
        # Serialize startup migrations if multiple Vercel instances cold-start
        # at the same time.
        connection.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": 73482190517},
        )

        # Creates the table when the database is empty. For an existing table,
        # create_all leaves it alone, so the ALTER statements below handle it.
        Base.metadata.create_all(bind=connection)

        connection.execute(
            text(
                """
                ALTER TABLE users
                    ADD COLUMN IF NOT EXISTS role VARCHAR(20),
                    ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20),
                    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ NULL,
                    ADD COLUMN IF NOT EXISTS approved_by INTEGER NULL
                """
            )
        )

        # Existing accounts keep access. Future accounts default to pending.
        connection.execute(
            text("UPDATE users SET role = 'user' WHERE role IS NULL")
        )
        connection.execute(
            text(
                "UPDATE users SET approval_status = 'approved' "
                "WHERE approval_status IS NULL"
            )
        )
        connection.execute(
            text(
                """
                ALTER TABLE users
                    ALTER COLUMN role SET DEFAULT 'user',
                    ALTER COLUMN role SET NOT NULL,
                    ALTER COLUMN approval_status SET DEFAULT 'pending',
                    ALTER COLUMN approval_status SET NOT NULL
                """
            )
        )

        # Add the self-reference only if approved_by does not already have one.
        connection.execute(
            text(
                """
                DO $migration$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint AS constraint_info
                        JOIN pg_attribute AS column_info
                          ON column_info.attrelid = constraint_info.conrelid
                         AND column_info.attnum = ANY(constraint_info.conkey)
                        WHERE constraint_info.conrelid = 'users'::regclass
                          AND constraint_info.contype = 'f'
                          AND column_info.attname = 'approved_by'
                    ) THEN
                        ALTER TABLE users
                            ADD CONSTRAINT fk_users_approved_by
                            FOREIGN KEY (approved_by)
                            REFERENCES users(id)
                            ON DELETE SET NULL;
                    END IF;
                EXCEPTION WHEN duplicate_object THEN
                    NULL;
                END
                $migration$
                """
            )
        )

initialize_database_schema()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please log in.",
        )

    user = db.get(User, user_id)
    if user is None or user.approval_status != "approved":
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account cannot access the application.",
        )

    return user


def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role not in {"admin", "super_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is required.",
        )
    return current_user


def get_current_super_admin(
    current_admin: User = Depends(get_current_admin),
) -> User:
    if current_admin.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-admin access is required.",
        )
    return current_admin

app = FastAPI(title="Signup CRUD API (Argon2)")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="signup_session",
    max_age=60 * 60 * 8,
    same_site="lax",
    https_only=APP_ENV == "production",
)

ph = PasswordHasher()


class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    confirm_password: str
    accepted_terms: bool

    @field_validator("first_name", "last_name")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty.")
        return cleaned

    @field_validator("password")
    @classmethod
    def password_min_length(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ApprovalDecision(BaseModel):
    role: Literal["user", "admin"] = "user"


class SuperAdminAccountUpdate(BaseModel):
    role: Literal["user", "admin", "super_admin"] | None = None
    approval_status: Literal["approved", "revoked"] | None = None


@app.get("/api/health")
def health_check():
    return {"status": "ok", "hasher": "argon2id"}


@app.post("/api/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if not payload.accepted_terms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must accept the Terms of Use & Privacy Policy.",
        )

    if payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match.",
        )

    new_user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=str(payload.email).lower(),
        password_hash=ph.hash(payload.password),
        role="user",
        approval_status="pending",
        approved_at=None,
        approved_by=None,
        accepted_terms=payload.accepted_terms,
    )
    db.add(new_user)

    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError as error:
        db.rollback()
        if getattr(error.orig, "pgcode", None) == "23505":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            ) from error
        raise

    return {
        "message": "Account created. Your request is waiting for approval.",
        "user": {
            "id": new_user.id,
            "first_name": new_user.first_name,
            "last_name": new_user.last_name,
            "email": new_user.email,
            "approval_status": new_user.approval_status,
            "created_at": new_user.created_at,
        },
    }


@app.post("/api/login")
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    email = str(payload.email).lower()
    user = db.scalar(select(User).where(User.email == email))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    try:
        ph.verify(user.password_hash, payload.password)
    except VerificationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if user.approval_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is awaiting approval.",
        )
    if user.approval_status == "revoked":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this account has been revoked.",
        )
    if user.approval_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has not been approved.",
        )

    request.session.clear()
    request.session["user_id"] = user.id
    return {
        "message": "Login successful.",
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role": user.role,
        },
    }


@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out."}


@app.get("/api/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "user": {
            "id": current_user.id,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "email": current_user.email,
            "role": current_user.role,
        }
    }


@app.get("/api/admin/approval-requests")
def list_approval_requests(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    pending_users = db.scalars(
        select(User)
        .where(User.approval_status == "pending")
        .order_by(User.created_at.asc())
    ).all()

    return {
        "requests": [
            {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "created_at": user.created_at,
            }
            for user in pending_users
        ]
    }


@app.post("/api/admin/users/{user_id}/approve")
def approve_user(
    user_id: int,
    decision: ApprovalDecision,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    target_user = db.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if target_user.approval_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is not pending approval.",
        )
    if decision.role == "admin" and current_admin.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a super admin can grant admin access.",
        )

    target_user.role = decision.role
    target_user.approval_status = "approved"
    target_user.approved_at = datetime.now(timezone.utc)
    target_user.approved_by = current_admin.id
    db.commit()

    return {"message": "User approved.", "role": target_user.role}


@app.post("/api/admin/users/{user_id}/reject")
def reject_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    target_user = db.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if target_user.approval_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is not pending approval.",
        )

    target_user.approval_status = "rejected"
    target_user.approved_at = None
    target_user.approved_by = None
    db.commit()

    return {"message": "User rejected."}


@app.get("/api/super-admin/accounts")
def list_all_accounts(
    db: Session = Depends(get_db),
    current_super_admin: User = Depends(get_current_super_admin),
):
    accounts = db.scalars(
        select(User).order_by(User.created_at.desc(), User.id.desc())
    ).all()

    return {
        "accounts": [
            {
                "id": account.id,
                "first_name": account.first_name,
                "last_name": account.last_name,
                "email": account.email,
                "role": account.role,
                "approval_status": account.approval_status,
                "created_at": account.created_at,
                "approved_at": account.approved_at,
                "approved_by": account.approved_by,
            }
            for account in accounts
        ]
    }


@app.post("/api/admin/users/{user_id}/revoke")
def revoke_user_access(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    target_user = db.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if target_user.role != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins can revoke access only for user accounts.",
        )
    if target_user.approval_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user does not currently have active access.",
        )

    target_user.approval_status = "revoked"
    db.commit()

    return {"message": "User access revoked."}


@app.patch("/api/super-admin/accounts/{user_id}")
def update_account(
    user_id: int,
    payload: SuperAdminAccountUpdate,
    db: Session = Depends(get_db),
    current_super_admin: User = Depends(get_current_super_admin),
):
    if payload.role is None and payload.approval_status is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a role or access-status change.",
        )

    target_user = db.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    new_role = payload.role or target_user.role
    new_status = payload.approval_status or target_user.approval_status

    if target_user.id == current_super_admin.id and (
        new_role != "super_admin" or new_status != "approved"
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot remove your own active super-admin access.",
        )

    removing_active_super_admin = (
        target_user.role == "super_admin"
        and target_user.approval_status == "approved"
        and (new_role != "super_admin" or new_status != "approved")
    )
    if removing_active_super_admin:
        other_super_admins = db.scalar(
            select(func.count(User.id)).where(
                User.role == "super_admin",
                User.approval_status == "approved",
                User.id != target_user.id,
            )
        )
        if not other_super_admins:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The last active super admin cannot lose access or be demoted.",
            )

    target_user.role = new_role
    if payload.approval_status is not None:
        target_user.approval_status = payload.approval_status
        if payload.approval_status == "approved":
            target_user.approved_at = datetime.now(timezone.utc)
            target_user.approved_by = current_super_admin.id

    db.commit()
    db.refresh(target_user)

    return {
        "message": "Account updated.",
        "account": {
            "id": target_user.id,
            "role": target_user.role,
            "approval_status": target_user.approval_status,
            "approved_at": target_user.approved_at,
            "approved_by": target_user.approved_by,
        },
    }


@app.get("/api/users")
def list_users(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    users = db.execute(
        select(
            User.id,
            User.first_name,
            User.last_name,
            User.email,
            User.approval_status,
            User.created_at,
            User.approved_at,
            User.approved_by,
        )
        .where(User.role == "user")
        .order_by(User.created_at.desc())
    ).all()

    return {
        "users": [
            {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "approval_status": user.approval_status,
                "created_at": user.created_at,
                "approved_at": user.approved_at,
                "approved_by": user.approved_by,
            }
            for user in users
        ]
    }
