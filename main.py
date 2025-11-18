import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from bson import ObjectId
import hashlib
import secrets

from database import db, create_document, get_documents
from schemas import AuthUser, Session, ChatMessage

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "CollabCode Studio Backend is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


# Utility functions

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hashed = stored_hash.split("$")
        return hashlib.sha256((salt + password).encode()).hexdigest() == hashed
    except Exception:
        return False


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    session = Session(user_id=user_id, token=token, expires_at=expires)
    create_document("session", session)
    return token


def get_user_by_token(token: str) -> Optional[dict]:
    if db is None:
        return None
    sess = db["session"].find_one({"token": token, "expires_at": {"$gt": datetime.now(timezone.utc)}})
    if not sess:
        return None
    user = db["authuser"].find_one({"_id": ObjectId(sess["user_id"])}) if ObjectId.is_valid(sess["user_id"]) else None
    return user


# Request/Response models
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    token: str
    name: str
    email: EmailStr


class ChatPostRequest(BaseModel):
    content: str


class ChatMessageResponse(BaseModel):
    id: str
    user_name: str
    content: str
    created_at: datetime


# Auth endpoints
@app.post("/auth/register")
def register(payload: RegisterRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    existing = db["authuser"].find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = AuthUser(name=payload.name, email=payload.email, password_hash=hash_password(payload.password))
    user_id = create_document("authuser", user)
    token = create_session(user_id)
    return LoginResponse(token=token, name=user.name, email=user.email)


@app.post("/auth/login")
def login(payload: LoginRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    user = db["authuser"].find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_session(str(user["_id"]))
    return LoginResponse(token=token, name=user.get("name", ""), email=user.get("email", ""))


# Dependency to get current user

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


# Chat endpoints
@app.get("/chat", response_model=List[ChatMessageResponse])
def list_messages(user=Depends(get_current_user)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    msgs = db["chatmessage"].find().sort("created_at", -1).limit(50)
    result: List[ChatMessageResponse] = []
    for m in msgs:
        u = db["authuser"].find_one({"_id": ObjectId(m["user_id"])}) if ObjectId.is_valid(m["user_id"]) else None
        result.append(ChatMessageResponse(
            id=str(m.get("_id")),
            user_name=(u.get("name") if u else "Unknown"),
            content=m.get("content", ""),
            created_at=m.get("created_at", datetime.now(timezone.utc))
        ))
    return list(reversed(result))


@app.post("/chat", response_model=ChatMessageResponse)
def post_message(payload: ChatPostRequest, user=Depends(get_current_user)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    msg = ChatMessage(user_id=str(user["_id"]), content=payload.content)
    msg_id = create_document("chatmessage", msg)
    saved = db["chatmessage"].find_one({"_id": ObjectId(msg_id)})
    return ChatMessageResponse(
        id=msg_id,
        user_name=user.get("name", ""),
        content=saved.get("content", payload.content),
        created_at=saved.get("created_at", datetime.now(timezone.utc))
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
