from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    Table,
    DateTime,
    Float,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from passlib.context import CryptContext
from datetime import datetime
from .database import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_google_user = Column(Boolean, default=False)
    google_user_id = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    favorites = relationship("Favorite", back_populates="user")
    watchlist = relationship("WatchlistItem", back_populates="user")

    def verify_password(self, password: str) -> bool:
        # For Google users, we'll skip password verification
        if self.is_google_user:
            return True
        return pwd_context.verify(password, self.hashed_password)


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    brand_name = Column(String)
    domain_name = Column(String)
    domain_extension = Column(String)
    price = Column(String)
    total_score = Column(Integer, default=0)
    length_score = Column(Integer, default=0)
    dictionary_score = Column(Integer, default=0)
    pronounceability_score = Column(Integer, default=0)
    repetition_score = Column(Integer, default=0)
    tld_score = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="favorites")


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    domain_name = Column(String)
    domain_extension = Column(String)
    status = Column(String, default="taken")  # "taken" or "available"
    created_at = Column(DateTime, default=datetime.utcnow)
    last_checked = Column(DateTime, default=datetime.utcnow)
    notify_when_available = Column(Boolean, default=True)
    user = relationship("User", back_populates="watchlist")
