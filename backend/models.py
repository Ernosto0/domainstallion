from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table, DateTime
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from passlib.context import CryptContext
from datetime import datetime

Base = declarative_base()
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
    total_score = Column(Integer)  # Store the total score
    length_score = Column(Integer)  # Store individual scores
    dictionary_score = Column(Integer)
    pronounceability_score = Column(Integer)
    repetition_score = Column(Integer)
    tld_score = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="favorites")
