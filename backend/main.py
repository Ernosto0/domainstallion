from fastapi import FastAPI, Request, HTTPException, Depends, status, BackgroundTasks
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
import asyncio

# Enable insecure transport for development
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from .database import engine, get_db
from .models import (
    Base,
    User,
    Favorite,
    WatchlistItem as WatchlistItemModel,
    AlertHistory,
)
from .auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_password_hash,
)
from .google_auth import router as google_auth_router
from backend.services.brand_generator import BrandGenerator
from backend.schemas import WatchlistItemCreate, WatchlistItem
from .tasks import check_watchlist_domains

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
    style: str = Field(
        default="neutral",
        description="Style of brand names to generate: 'short', 'playful', 'serious', 'techy', or 'neutral'",
    )
    num_suggestions: int = Field(
        default=20, ge=5, le=50
    )  # Between 5 and 50 suggestions
    exclude_names: List[str] = Field(default_factory=list)  # List of names to exclude


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
        print(f"Processing favorites request for user: {current_user.username}")

        # Get user's favorites
        favorites = db.query(Favorite).filter(Favorite.user_id == current_user.id).all()
        print(f"Found {len(favorites)} favorites")

        # Get user's watchlist with debug info
        watchlist = (
            db.query(WatchlistItemModel)
            .filter(WatchlistItemModel.user_id == current_user.id)
            .all()
        )
        print(f"Found {len(watchlist)} watchlist items")

        # Debug print each watchlist item
        for item in watchlist:
            print(
                f"Watchlist item: {item.domain_name}.{item.domain_extension} (ID: {item.id}, Status: {item.status})"
            )

        # Format dates for both favorites and watchlist
        for favorite in favorites:
            favorite.formatted_date = favorite.created_at.strftime("%Y-%m-%d %H:%M")

        for item in watchlist:
            item.formatted_date = item.created_at.strftime("%Y-%m-%d %H:%M")
            item.last_checked_date = item.last_checked.strftime("%Y-%m-%d %H:%M")
            print(
                f"Formatted dates for {item.domain_name}: Created: {item.formatted_date}, Last checked: {item.last_checked_date}"
            )

        # Debug print template context
        template_context = {
            "request": request,
            "current_user": current_user,
            "favorites": favorites,
            "watchlist": watchlist,
        }
        print(f"Template context - watchlist length: {len(watchlist)}")

        # Check if it's an AJAX request
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            response = templates.TemplateResponse(
                "favorites.html",
                template_context,
            )
            print("Rendered AJAX response")
            return response
        else:
            response = templates.TemplateResponse(
                "favorites.html",
                template_context,
            )
            print("Rendered full page response")
            return response
    except Exception as e:
        print(f"Error in get_favorites: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            raise HTTPException(status_code=500, detail=str(e))
        return RedirectResponse(url="/")


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

    if request.style not in ["short", "playful", "serious", "techy", "neutral"]:
        raise HTTPException(status_code=400, detail="Invalid style specified")

    generator = BrandGenerator()

    # Generate more names than requested to account for exclusions
    extra_suggestions = len(request.exclude_names)
    total_suggestions = request.num_suggestions + extra_suggestions

    results = await generator.generate_names(
        request.keywords, request.style, total_suggestions
    )

    if not results:
        raise HTTPException(status_code=500, detail="Failed to generate brand names")

    # Filter out excluded names
    filtered_results = [
        result
        for result in results
        if result["name"].lower()
        not in [name.lower() for name in request.exclude_names]
    ][: request.num_suggestions]

    # Log the response data before returning
    logger = logging.getLogger(__name__)
    logger.debug(f"API Response Data: {filtered_results}")

    return filtered_results


@app.get("/user/profile")
async def get_user_profile(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "email": current_user.email}


@app.post("/watchlist", response_model=WatchlistItem)
async def add_to_watchlist(
    watchlist_item: WatchlistItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Check if domain is already in user's watchlist
    existing_item = (
        db.query(WatchlistItemModel)
        .filter(
            WatchlistItemModel.user_id == current_user.id,
            WatchlistItemModel.domain_name == watchlist_item.domain_name,
            WatchlistItemModel.domain_extension == watchlist_item.domain_extension,
        )
        .first()
    )

    if existing_item:
        raise HTTPException(
            status_code=400, detail="Domain is already in your watchlist"
        )

    # Create new watchlist item with alerts disabled by default
    db_item = WatchlistItemModel(
        user_id=current_user.id,
        domain_name=watchlist_item.domain_name,
        domain_extension=watchlist_item.domain_extension,
        status="taken",
        notify_when_available=False,  # Explicitly set to False
    )

    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    # Log the creation of the watchlist item
    logger = logging.getLogger(__name__)
    logger.info(
        f"Added domain {db_item.domain_name}.{db_item.domain_extension} to watchlist for user {current_user.username}"
    )

    return db_item


@app.delete("/watchlist/{watchlist_id}")
async def remove_from_watchlist(
    watchlist_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    watchlist_item = (
        db.query(WatchlistItemModel)
        .filter(
            WatchlistItemModel.id == watchlist_id,
            WatchlistItemModel.user_id == current_user.id,
        )
        .first()
    )

    if not watchlist_item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    db.delete(watchlist_item)
    db.commit()
    return {"message": "Domain removed from watchlist"}


class NotifyUpdate(BaseModel):
    notify_when_available: bool


@app.put("/watchlist/{watchlist_id}/notify")
async def update_watchlist_notification(
    watchlist_id: int,
    notify_update: NotifyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    watchlist_item = (
        db.query(WatchlistItemModel)
        .filter(
            WatchlistItemModel.id == watchlist_id,
            WatchlistItemModel.user_id == current_user.id,
        )
        .first()
    )

    if not watchlist_item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    # Track the change in alert settings
    was_enabled = watchlist_item.notify_when_available
    watchlist_item.notify_when_available = notify_update.notify_when_available

    # Create an alert history entry when alerts are enabled
    if not was_enabled and notify_update.notify_when_available:
        alert = AlertHistory(
            watchlist_item_id=watchlist_id,
            alert_type="alerts_enabled",
            message=f"Alerts enabled for domain {watchlist_item.domain_name}.{watchlist_item.domain_extension}",
            delivered=True,
        )
        db.add(alert)
        logger = logging.getLogger(__name__)
        logger.info(
            f"Alerts enabled for domain {watchlist_item.domain_name}.{watchlist_item.domain_extension}"
        )
    elif was_enabled and not notify_update.notify_when_available:
        alert = AlertHistory(
            watchlist_item_id=watchlist_id,
            alert_type="alerts_disabled",
            message=f"Alerts disabled for domain {watchlist_item.domain_name}.{watchlist_item.domain_extension}",
            delivered=True,
        )
        db.add(alert)
        logger = logging.getLogger(__name__)
        logger.info(
            f"Alerts disabled for domain {watchlist_item.domain_name}.{watchlist_item.domain_extension}"
        )

    db.commit()
    db.refresh(watchlist_item)
    return watchlist_item


@app.on_event("startup")
async def startup_event():
    # Start the background task
    asyncio.create_task(check_watchlist_domains())
