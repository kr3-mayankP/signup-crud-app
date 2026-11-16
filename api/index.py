import os
from contextlib import asynccontextmanager
from argon2.exceptions import VerificationError
from argon2 import PasswordHasher
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, field_validator

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Uses Argon2id with OWASP-recommended defaults and automatic salting
ph = PasswordHasher()


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    accepted_terms BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        conn.commit()
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if DATABASE_URL:
        init_db()
    yield


app = FastAPI(title="Signup CRUD API (Argon2)", lifespan=lifespan)

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
def signup(payload: SignupRequest):
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

    # Ensures table exists even on serverless cold starts
    init_db()

    # Hash password using Argon2id (returns encoded string with algorithm, params, salt, and hash)
    hashed_pw = ph.hash(payload.password)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (first_name, last_name, email, password_hash, accepted_terms)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, first_name, last_name, email, created_at;
                """,
                (
                    payload.first_name,
                    payload.last_name,
                    payload.email.lower(),
                    hashed_pw,
                    payload.accepted_terms,
                ),
            )
            new_user = cur.fetchone()
        conn.commit()
        return {
            "message": "Account created successfully!",
            "user": new_user,
        }
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    finally:
        conn.close()
#------------------------------------------------------------------------

@app.post("/api/login")
def login(payload: LoginRequest):
    init_db()

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, first_name, last_name, email, password_hash
                FROM users
                WHERE email = %s;
                """,
                (str(payload.email).lower(),),
            )
            user = cur.fetchone()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        try:
            ph.verify(user["password_hash"], payload.password)
        except VerificationError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        return {
            "message": "Login successful.",
            "user": {
                "id": user["id"],
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "email": user["email"],
            },
        }
    finally:
        conn.close()

#------------------------------------------------------------------------------


@app.get("/api/users")
def list_users():
    init_db()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, first_name, last_name, email, created_at
                FROM users
                ORDER BY created_at DESC;
                """
            )
            users = cur.fetchall()
        return {"users": users}
    finally:
        conn.close()