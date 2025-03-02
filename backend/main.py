from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import timedelta
from sqlalchemy.orm import Session
import os
import logging

# Enable insecure transport for development
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from .database import engine, get_db
from .models import Base, User, Favorite
from .auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_password_hash,
)
from .google_auth import router as google_auth_router
from backend.services.brand_generator import BrandGenerator

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Brand Name Generator", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# Configure templates
templates = Jinja2Templates(directory="backend/templates")


# Add debug middleware
@app.middleware("http")
async def debug_middleware(request: Request, call_next):
    print(f"Incoming request: {request.method} {request.url.path}")

    # Check for auth header in request
    auth_header = request.headers.get("Authorization")
    print(f"Headers: {request.headers}")

    if auth_header:
        print(f"Auth header found: {auth_header}")
    else:
        print("No auth header found")
        # Only redirect if it's a browser request (not an API call)
        if request.url.path == "/favorites" and request.method == "GET":
            accepts = request.headers.get("accept", "")
            if "text/html" in accepts.lower():
                return RedirectResponse(url="/", status_code=302)

    response = await call_next(request)
    print(f"Response status: {response.status_code}")
    return response


# Include Google OAuth routes at the root level
app.include_router(google_auth_router)


# Error handler for 404 Not Found
@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: HTTPException):
    print(f"404 error for path: {request.url.path}")
    if request.url.path.startswith("/auth/google"):
        print("Forwarding Google OAuth request...")
        if request.url.path == "/auth/google/login":
            return await google_auth_router.google_login(request)
        elif request.url.path == "/auth/google/callback":
            db = next(get_db())
            return await google_auth_router.google_callback(request, db)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Brand Name Generator",
            "error": "Page not found. Please try again.",
        },
        status_code=404,
    )


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
    total_score: int
    length_score: int
    dictionary_score: int
    pronounceability_score: int
    repetition_score: int
    tld_score: int


class BrandRequest(BaseModel):
    keywords: str
    num_suggestions: int = Field(
        default=20, ge=5, le=50
    )  # Between 5 and 50 suggestions


class DomainInfo(BaseModel):
    domain: str
    available: bool
    price: str
    score: Dict[
        str, Any
    ]  # Add score field to match what we're sending from the backend


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

    hashed_password = get_password_hash(user.password)
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
        total_score=favorite.total_score,
        length_score=favorite.length_score,
        dictionary_score=favorite.dictionary_score,
        pronounceability_score=favorite.pronounceability_score,
        repetition_score=favorite.repetition_score,
        tld_score=favorite.tld_score,
    )
    db.add(db_favorite)
    db.commit()
    db.refresh(db_favorite)
    return {"message": "Favorite added successfully"}


@app.get("/favorites", response_class=HTMLResponse)
async def get_favorites(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        print(
            f"Processing favorites request for user: {current_user.username if current_user else 'None'}"
        )
        print(f"Request headers: {dict(request.headers)}")

        # Check if user is authenticated
        if not current_user:
            print("No authenticated user found")
            # Check if this is an AJAX request
            is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
            if is_ajax:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )
            else:
                print("Redirecting to home page")
                return RedirectResponse(url="/", status_code=302)

        print(f"User authenticated: {current_user.username}")

        # Query favorites
        try:
            favorites = (
                db.query(Favorite).filter(Favorite.user_id == current_user.id).all()
            )
            print(f"Found {len(favorites)} favorites for user {current_user.username}")

            # Debug print each favorite
            for fav in favorites:
                print(
                    f"Favorite ID: {fav.id}, Domain: {fav.domain_name}, Created: {fav.created_at}"
                )

        except Exception as db_error:
            print(f"Database error: {str(db_error)}")
            print(f"Database error type: {type(db_error)}")
            import traceback

            print(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500, detail=f"Database error: {str(db_error)}"
            )

        # Format the dates for each favorite
        for favorite in favorites:
            try:
                favorite.formatted_date = (
                    favorite.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if favorite.created_at
                    else ""
                )
                print(
                    f"Formatted date for favorite {favorite.id}: {favorite.formatted_date}"
                )
            except Exception as date_error:
                print(
                    f"Error formatting date for favorite {favorite.id}: {str(date_error)}"
                )
                print(f"Date error type: {type(date_error)}")
                print(f"Traceback: {traceback.format_exc()}")
                favorite.formatted_date = ""

        # Render template
        try:
            print("Attempting to render favorites template")
            response = templates.TemplateResponse(
                "favorites.html",
                {
                    "request": request,
                    "favorites": favorites,
                    "current_user": current_user,
                    "title": "My Favorites - Brand Generator",
                },
            )
            print("Successfully rendered favorites template")
            return response
        except Exception as template_error:
            print(f"Template error: {str(template_error)}")
            print(f"Template error type: {type(template_error)}")
            print(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500, detail=f"Template error: {str(template_error)}"
            )

    except HTTPException as http_error:
        print(f"HTTP Exception: {str(http_error)}")
        raise http_error
    except Exception as e:
        print(f"Unexpected error in get_favorites: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "title": "Brand Name Generator",
                "error": f"An unexpected error occurred: {str(e)}",
            },
            status_code=500,
        )


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

    # Log the response data before returning
    logger = logging.getLogger(__name__)
    logger.debug(f"API Response Data: {results}")

    return results


@app.get("/user/profile")
async def get_user_profile(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "email": current_user.email}
