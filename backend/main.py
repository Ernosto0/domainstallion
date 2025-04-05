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
import time
from .services.stats_service import StatsService




app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="backend/static"), name="static")


# Environment settings
ENV = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENV == "production"

# Configure logging
logging_level = logging.INFO if IS_PRODUCTION else logging.DEBUG
logging.basicConfig(
    level=logging_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Configure rate limits based on environment
# Higher limits in production to handle legitimate traffic
if IS_PRODUCTION:
    RATE_LIMIT_TOKEN = {"calls": 10, "period": 300}  # 10 requests per 5 minutes
    RATE_LIMIT_API = {"calls": 40, "period": 60}     # 40 requests per minute
    RATE_LIMIT_DOMAIN = {"calls": 200, "period": 3600}  # 200 requests per hour 
    RATE_LIMIT_SOCIAL = {"calls": 40, "period": 3600}   # 40 requests per hour
    RATE_LIMIT_USER = {"calls": 2000, "period": 3600}   # 2000 requests per hour, per user
    RATE_LIMIT_EXTENSIONS = {"calls": 60, "period": 3600}  # 60 requests per hour
else:
    # Development limits
    RATE_LIMIT_TOKEN = {"calls": 5, "period": 300}       # 5 requests per 5 minutes
    RATE_LIMIT_API = {"calls": 20, "period": 60}         # 20 requests per minute
    RATE_LIMIT_DOMAIN = {"calls": 100, "period": 3600}   # 100 requests per hour
    RATE_LIMIT_SOCIAL = {"calls": 20, "period": 3600}    # 20 requests per hour
    RATE_LIMIT_USER = {"calls": 1000, "period": 3600}    # 1000 requests per hour, per user
    RATE_LIMIT_EXTENSIONS = {"calls": 30, "period": 3600}  # 30 requests per hour

# Only enable insecure transport in development
if not IS_PRODUCTION:
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    logging.warning("Insecure OAuth transport enabled for development")
else:
    logging.info("Running in production mode")

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
from backend.services.social_media_checker import check_social_media
from backend.schemas import WatchlistItemCreate, WatchlistItem
from .tasks import check_watchlist_domains
from .rate_limiter import (
    limiter,
    _rate_limit_exceeded_handler,
    rate_limit,
    RateLimitExceeded,
)
from backend.services.check_more_extension import check_more_extensions

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Brand Name Generator", version="1.0.0")

# Add rate limiter to the application
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not IS_PRODUCTION else ["https://yourdomain.com"], # TODO: change to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# Configure templates
templates = Jinja2Templates(directory="backend/templates")


# Add debug middleware in development mode only
if not IS_PRODUCTION:
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
else:
    # Simpler middleware for production that just handles redirects
    @app.middleware("http")
    async def production_middleware(request: Request, call_next):
        # Only redirect if it's a browser request to /favorites without auth
        if (request.url.path == "/favorites" and 
            request.method == "GET" and 
            not request.headers.get("Authorization")):
            accepts = request.headers.get("accept", "")
            if "text/html" in accepts.lower():
                return RedirectResponse(url="/", status_code=302)
        
        response = await call_next(request)
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
    min_length: int = Field(default=3, ge=3, le=15)  # Minimum name length
    max_length: int = Field(default=15, ge=3, le=15)  # Maximum name length
    include_word: Optional[str] = None  # Optional word to include in generated names
    similar_to: Optional[str] = None  # Optional domain name to generate similar alternatives
    extensions: List[str] = Field(default_factory=list)  # List of domain extensions to check


class DomainInfo(BaseModel):
    domain: str
    available: bool
    price: str
    score: Dict[
        str, Any
    ]  # Add score field to match what we're sending from the backend
    providers: Optional[Dict[str, Any]] = (
        None  # Add providers field to include provider pricing
    )


class BrandResponse(BaseModel):
    name: str
    domains: Dict[str, DomainInfo]


# Authentication endpoints
@app.post("/token", response_model=Token)
@rate_limit(calls=RATE_LIMIT_TOKEN["calls"], period=RATE_LIMIT_TOKEN["period"])
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
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

        # Get user's watchlist
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


@app.get("/api/stats/domains-generated")
async def get_domains_generated(db: Session = Depends(get_db)):
    stats_service = StatsService(db)
    total_count = await stats_service.get_counter_value("domains_generated")
    return {"total_domains_generated": total_count}


@app.post("/api/generate", response_model=List[BrandResponse])
async def generate_names(request: BrandRequest, db: Session = Depends(get_db)):
    logger = logging.getLogger(__name__)
    logger.debug(f"Received generate request with keywords: {request.keywords}")

    if not request.keywords:
        raise HTTPException(status_code=400, detail="Keywords are required")

    if request.style not in ["short", "playful", "serious", "techy", "neutral", "creative"]:
        raise HTTPException(status_code=400, detail="Invalid style specified")

    if request.min_length > request.max_length:
        raise HTTPException(
            status_code=400,
            detail="Minimum length cannot be greater than maximum length",
        )
        
    # Validate at least one extension is provided
    if not request.extensions:
        logger.debug("No extensions provided, will use defaults")
    else:
        logger.debug(f"Using custom extensions: {request.extensions}")

    try:
        generator = BrandGenerator()
        logger.debug("BrandGenerator initialized")

        # Generate more names than requested to account for exclusions
        extra_suggestions = len(request.exclude_names)
        total_suggestions = request.num_suggestions + extra_suggestions

        logger.debug(f"Generating {total_suggestions} names...")
        results = await generator.generate_names(
            request.keywords,
            request.style,
            total_suggestions,
            min_length=request.min_length,
            max_length=request.max_length,
            include_word=request.include_word,
            similar_to=request.similar_to,
            extensions=request.extensions,
        )
        logger.debug(f"Generated {len(results)} names")

        if not results:
            logger.error("No results returned from generator")
            raise HTTPException(
                status_code=500, detail="Failed to generate brand names"
            )

        # Filter out excluded names
        filtered_results = [
            result
            for result in results
            if result["name"].lower()
            not in [name.lower() for name in request.exclude_names]
        ][: request.num_suggestions]

        # Log a sample of the results to check provider information
        if filtered_results:
            sample_result = filtered_results[0]
            logger.info(f"Sample result being returned to frontend: {sample_result}")

            # Check if any domains have provider information
            for domain_ext, domain_info in sample_result.get("domains", {}).items():
                providers = domain_info.get("providers", {})
                logger.info(
                    f"Providers for {sample_result['name']}.{domain_ext}: {providers}"
                )

            # Increment the domains generated counter
            stats_service = StatsService(db)
            # Count how many domains were generated by multiplying names by extensions
            domains_checked = 0
            for result in filtered_results:
                domains_checked += len(result.get("domains", {}))
                
            await stats_service.increment_counter("domains_generated", domains_checked)
            logger.info(f"Incremented domains generated counter by {domains_checked}")

        logger.debug(f"Returning {len(filtered_results)} filtered results")
        return filtered_results
    except Exception as e:
        logger.error(f"Error in generate_names: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating names: {str(e)}")


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
    # Set higher log level for domain checker to reduce verbosity
    logging.getLogger("backend.services.domain_checker").setLevel(logging.INFO)

    # Start the background task
    asyncio.create_task(check_watchlist_domains())
    logging.info("Started watchlist domain checking background task")

    # Preload common domains into cache
    from backend.services.domain_checker import preload_common_domains

    asyncio.create_task(preload_common_domains())
    logging.info("Started preloading common domains")


@app.on_event("shutdown")
async def shutdown_event():
    # Clean up resources
    from backend.services.domain_checker import cleanup_resources

    await cleanup_resources()
    logging.info("Cleaned up resources on shutdown")


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy(request: Request):
    return templates.TemplateResponse(
        "privacy.html",
        {"request": request, "title": "Privacy Policy - Brand Generator"},
    )


@app.get("/terms", response_class=HTMLResponse)
async def terms_of_service(request: Request):
    return templates.TemplateResponse(
        "terms.html",
        {"request": request, "title": "Terms of Service - Brand Generator"},
    )


# Example of applying rate limits to endpoints
@app.post("/generate-domain")
@rate_limit(calls=RATE_LIMIT_API["calls"], period=RATE_LIMIT_API["period"])  # API-intensive endpoint
async def generate_domain(request: Request):
    # Your existing code here
    pass


@app.get("/check-availability/{domain}")
@rate_limit(calls=RATE_LIMIT_DOMAIN["calls"], period=RATE_LIMIT_DOMAIN["period"])  # Domain checking endpoint
async def check_availability(request: Request, domain: str):
    # Your existing code here
    pass


@app.get("/watchlist")
@rate_limit(
    calls=RATE_LIMIT_USER["calls"], 
    period=RATE_LIMIT_USER["period"], 
    user_specific=True
)  # User-specific rate limit
async def get_watchlist(
    request: Request, current_user: User = Depends(get_current_user)
):
    # Your existing code here
    pass

@app.get("/check-social-media/{username}")
@rate_limit(
    calls=RATE_LIMIT_SOCIAL["calls"], 
    period=RATE_LIMIT_SOCIAL["period"]
)  # Social media checking endpoint
async def check_social_media_endpoint(request: Request, username: str):
    try:
        result = await check_social_media(username)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/check-more-extensions/{domain_name}")
@rate_limit(calls=RATE_LIMIT_EXTENSIONS["calls"], period=RATE_LIMIT_EXTENSIONS["period"])  # Extensions checking endpoint
async def check_more_extensions_endpoint(
    request: Request, 
    domain_name: str, 
    checked_extensions: str
):
    """
    Check additional domain extensions for a given domain name.
    
    Args:
        domain_name: Base domain name (without extension)
        checked_extensions: Comma-separated list of already checked extensions
    
    Returns:
        Dictionary mapping full domain names to availability information
    """
    try:
        # Parse the already checked extensions
        already_checked = checked_extensions.split(",") if checked_extensions else []
        
        # Ensure domain_name doesn't have any extensions in it
        if "." in domain_name:
            base_name = domain_name.split(".")[0]
        else:
            base_name = domain_name
        
        # Call the service to check additional extensions
        logger = logging.getLogger(__name__)
        logger.info(f"Checking more extensions for domain: {base_name}")
        logger.info(f"Already checked extensions: {already_checked}")
        
        results = await check_more_extensions(base_name, already_checked)
        return results
    except Exception as e:
        logger.error(f"Error checking more extensions for {domain_name}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error checking more extensions: {str(e)}"
        )

