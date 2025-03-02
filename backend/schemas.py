from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class UserBase(BaseModel):
    username: str
    email: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int

    class Config:
        from_attributes = True


class FavoriteBase(BaseModel):
    brand_name: str
    domain_name: str
    domain_extension: str
    price: str
    total_score: int = 0
    length_score: int = 0
    dictionary_score: int = 0
    pronounceability_score: int = 0
    repetition_score: int = 0
    tld_score: int = 0


class FavoriteCreate(FavoriteBase):
    pass


class Favorite(FavoriteBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class WatchlistItemBase(BaseModel):
    domain_name: str
    domain_extension: str
    notify_when_available: bool = True


class WatchlistItemCreate(WatchlistItemBase):
    pass


class WatchlistItem(WatchlistItemBase):
    id: int
    user_id: int
    status: str
    created_at: datetime
    last_checked: datetime

    class Config:
        from_attributes = True


class WatchlistItemUpdate(BaseModel):
    notify_when_available: Optional[bool] = None
    status: Optional[str] = None
    last_checked: Optional[datetime] = None
