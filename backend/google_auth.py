from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from google.oauth2 import id_token
from google.auth.transport import requests
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session
import json
import os
from pathlib import Path
from urllib.parse import urljoin

# Enable insecure transport for development
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from .database import get_db
from .models import User
from .auth import create_access_token, get_password_hash

router = APIRouter()
templates = Jinja2Templates(directory="backend/templates")

# These should be moved to your .env file
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
)

print(f"Google OAuth Configuration:")
print(f"Client ID: {GOOGLE_CLIENT_ID}")
print(f"Client Secret: {GOOGLE_CLIENT_SECRET}")
print(f"Redirect URI: {GOOGLE_REDIRECT_URI}")


def create_flow():
    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_REDIRECT_URI],
            "javascript_origins": ["http://localhost:8000"],
        }
    }

    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid",
        ],
    )
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    return flow



@router.get("/auth/google/login")
async def google_login(request: Request):
    """Initiates the Google OAuth2 login flow"""
    flow = create_flow()
    try:
        print("Starting Google login flow...")
        authorization_url, state = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        print(f"Generated authorization URL: {authorization_url}")
        return RedirectResponse(url=authorization_url)
    except Exception as e:
        print(f"Error in google_login: {str(e)}")
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "error": f"Failed to initiate Google login: {str(e)}"},
            status_code=400,
        )


@router.get("/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Handles the Google OAuth2 callback"""
    flow = create_flow()
    try:
        print("Received callback request")
        print(f"Request URL: {request.url}")
        print(f"Request query params: {request.query_params}")

        # Get the authorization response URL
        base_url = str(request.base_url)
        path = str(request.url.path)
        query = str(request.url.query)
        authorization_response = f"{base_url.rstrip('/')}{path}?{query}"

        print(f"Authorization response URL: {authorization_response}")

        try:
            # Fetch the token
            flow.fetch_token(authorization_response=authorization_response)
        except Exception as token_error:
            print(f"Error fetching token: {str(token_error)}")
            raise

        try:
            # Get the ID token from Google
            credentials = flow.credentials
            id_info = id_token.verify_oauth2_token(
                credentials.id_token, requests.Request(), GOOGLE_CLIENT_ID
            )
            print(f"Received user info from Google: {json.dumps(id_info, indent=2)}")
        except Exception as token_verify_error:
            print(f"Error verifying token: {str(token_verify_error)}")
            raise

        # Extract user information
        email = id_info.get("email")
        name = id_info.get("name")
        google_id = id_info.get("sub")

        if not email:
            raise ValueError("Could not get email from Google")

        # Check if user exists
        user = db.query(User).filter(User.email == email).first()

        if not user:
            print(f"Creating new user for email: {email}")
            # Create new user
            username = name or email.split("@")[0]
            # Make sure username is unique
            base_username = username
            counter = 1
            while db.query(User).filter(User.username == username).first():
                username = f"{base_username}{counter}"
                counter += 1

            user = User(
                email=email,
                username=username,
                hashed_password=get_password_hash("GOOGLE_OAUTH_USER"),
                is_google_user=True,
                google_user_id=google_id,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            print(f"Found existing user: {user.username}")

        # Create access token
        access_token = create_access_token(data={"sub": user.username})

        print("Authentication successful, returning to main page")
        print(f"Created token for user: {user.username}")

        # Return HTML with JavaScript to store token and close window
        return HTMLResponse(
            content=f"""
            <html>
                <body>
                    <script>
                        window.localStorage.setItem('authToken', '{access_token}');
                        window.localStorage.setItem('username', '{user.username}');
                        window.location.href = '/';
                    </script>
                </body>
            </html>
        """
        )

    except Exception as e:
        print(f"Error in google_callback: {str(e)}")
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "error": f"Authentication failed: {str(e)}"},
            status_code=400,
        )
