import os
from argon2.exceptions import VerificationError
from argon2 import PasswordHasher
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    func,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.exc import IntegrityError
from collections.abc import Generator

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

#----------------------------------------------------

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set.")

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
    accepted_terms: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, server_default=func.now()
    )

#----------------------------------------------------

# Uses Argon2id with OWASP-recommended defaults and automatic salting
ph = PasswordHasher()


# def get_db_connection():
#     if not DATABASE_URL:
#         raise RuntimeError("DATABASE_URL environment variable is not set.")
#     return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


# def init_db():
#     conn = get_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 CREATE TABLE IF NOT EXISTS users (
#                     id SERIAL PRIMARY KEY,
#                     first_name VARCHAR(100) NOT NULL,
#                     last_name VARCHAR(100) NOT NULL,
#                     email VARCHAR(255) UNIQUE NOT NULL,
#                     password_hash TEXT NOT NULL,
#                     accepted_terms BOOLEAN NOT NULL DEFAULT TRUE,
#                     created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
#                 );
#                 """
#             )
#         conn.commit()
#     finally:
#         conn.close()


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     if DATABASE_URL:
#         init_db()
#     yield


#app = FastAPI(title="Signup CRUD API (Argon2)", lifespan=lifespan)

app = FastAPI(title="Signup CRUD API (Argon2)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

#------------------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

#------------------------------------------------------------------------------

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

    hashed_pw = ph.hash(payload.password)

    new_user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=str(payload.email).lower(),
        password_hash=hashed_pw,
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
        "message": "Account created successfully!",
        "user": {
            "id": new_user.id,
            "first_name": new_user.first_name,
            "last_name": new_user.last_name,
            "email": new_user.email,
            "created_at": new_user.created_at,
        },
    }

#------------------------------------------------------------------------

@app.post("/api/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
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

    return {
        "message": "Login successful.",
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
        },
    }

#------------------------------------------------------------------------------


@app.get("/api/users")
def list_users(db: Session = Depends(get_db)):
    users = db.execute(
        select(
            User.id,
            User.first_name,
            User.last_name,
            User.email,
            User.created_at,
        ).order_by(User.created_at.desc())
    ).all()

    return {
        "users": [
            {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "created_at": user.created_at,
            }
            for user in users
        ]
    }