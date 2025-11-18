"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime

# Core app schemas for authentication and chat

class AuthUser(BaseModel):
    """
    Users collection schema
    Collection name: "authuser"
    """
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Unique email address")
    password_hash: str = Field(..., description="Password hash with salt")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Session(BaseModel):
    """
    Sessions collection schema
    Collection name: "session"
    """
    user_id: str = Field(..., description="User ObjectId as string")
    token: str = Field(..., description="Session token")
    expires_at: datetime = Field(..., description="Expiry timestamp (UTC)")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ChatMessage(BaseModel):
    """
    Chat messages collection schema
    Collection name: "chatmessage"
    """
    user_id: str = Field(..., description="User ObjectId as string")
    content: str = Field(..., min_length=1, max_length=2000, description="Message text")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# Example schemas left for reference (not used by the app)
class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = Field(None, ge=0, le=120)
    is_active: bool = True

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    category: str
    in_stock: bool = True
