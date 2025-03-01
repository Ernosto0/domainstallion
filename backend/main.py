from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import timedelta
from sqlalchemy.orm import Session

from .database import engine, get_db
from .models import Base, User, Favorite
from .auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from backend.services.brand_generator import BrandGenerator

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Brand Name Generator", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# Configure templates
templates = Jinja2Templates(directory="backend/templates")


# Pydantic models
class Token(BaseModel):
    access_token: str
    token_type: str


class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class FavoriteCreate(BaseModel):
    brand_name: str
    domain_name: str
    domain_extension: str
    price: str


class BrandRequest(BaseModel):
    keywords: str
    num_suggestions: int = Field(
        default=20, ge=5, le=50
    )  # Between 5 and 50 suggestions


class DomainInfo(BaseModel):
    domain: str
    available: bool
    price: str


class BrandResponse(BaseModel):
    name: str
    domains: Dict[str, DomainInfo]


# Authentication endpoints
@app.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = User.get_password_hash(user.password)
    db_user = User(
        username=user.username, email=user.email, hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": "User created successfully"}


# Favorites endpoints
@app.post("/favorites")
async def add_favorite(
    favorite: FavoriteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_favorite = Favorite(
        user_id=current_user.id,
        brand_name=favorite.brand_name,
        domain_name=favorite.domain_name,
        domain_extension=favorite.domain_extension,
        price=favorite.price,
    )
    db.add(db_favorite)
    db.commit()
    db.refresh(db_favorite)
    return {"message": "Favorite added successfully"}


@app.get("/favorites")
async def get_favorites(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    favorites = db.query(Favorite).filter(Favorite.user_id == current_user.id).all()
    return favorites


@app.delete("/favorites/{favorite_id}")
async def delete_favorite(
    favorite_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favorite = (
        db.query(Favorite)
        .filter(Favorite.id == favorite_id, Favorite.user_id == current_user.id)
        .first()
    )
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")

    db.delete(favorite)
    db.commit()
    return {"message": "Favorite deleted successfully"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request, "title": "Brand Name Generator"}
    )


@app.post("/api/generate", response_model=List[BrandResponse])
async def generate_names(request: BrandRequest):
    if not request.keywords:
        raise HTTPException(status_code=400, detail="Keywords are required")

    generator = BrandGenerator()
    results = await generator.generate_names(request.keywords, request.num_suggestions)

    if not results:
        raise HTTPException(status_code=500, detail="Failed to generate brand names")

    return results


@app.get("/user/profile")
async def get_user_profile(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "email": current_user.email}
