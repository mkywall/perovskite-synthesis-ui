from fastapi import APIRouter, HTTPException
from models import LoginRequest, LoginResponse, UserInfo
import logging
import secrets
import os
from dotenv import load_dotenv

from pycrucible import CrucibleClient
from pycrucible.models import BaseDataset
from pycrucible.utils import get_tz_isoformat


logger = logging.getLogger(__name__)
router = APIRouter()

# Simple in-memory session store (replace with Redis/DB for production)
sessions = {}

load_dotenv()
crucible_url = "https://crucible.lbl.gov/testapi"
admin_apikey = os.environ.get('ADMIN_APIKEY')
client = CrucibleClient(crucible_url, admin_apikey)
logger.info(f"Crucible client initialized with URL: {crucible_url}")

def lookup_user_by_email(email):
    """
    Lookup user information by email.

    Args:
        email: User's email address

    Returns:
        tuple: (orcid, name, projects_list)
        - orcid: str, user's ORCID identifier
        - name: str, user's full name
        - projects_list: list of str, available projects
    """
    logger.debug(f"Looking up user by email: {email}")
    user = client.get_user(email = email)
    if user:
        logger.debug(f"User found: {user}")
        orcid = user['orcid']
        full_name = f"{user['first_name']} {user['last_name']}"
        # TODO: this is actually wrong - should return projects based on ACL not ownership
        projects = client.list_projects(orcid = user['orcid'])
        logger.debug(f"Found {len(projects)} projects for user {orcid}")
        project_ids = [p['project_id'] for p in projects]
        project_ids.sort()
        return orcid, full_name, project_ids
    else:
        logger.warning(f"No user found for email: {email}")
        return None, None, []


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user by email and return user information.

    Flow:
    1. Receive email from frontend
    2. Call lookup_user_by_email()
    3. Generate session token
    4. Return user info + token
    """
    try:
        email = request.email.lower().strip()
        logger.info(f"Login attempt for email: {email}")

        # TODO: Call your actual function here
        orcid, name, projects = lookup_user_by_email(email)

        if not orcid or not name:
            logger.warning(f"No user found for email: {email}")
            return LoginResponse(
                success=False,
                message=f"No user found with email: {email}"
            )

        # Generate simple session token
        session_token = secrets.token_urlsafe(32)

        # Store session (in production, use Redis or database)
        sessions[session_token] = {
            "email": email,
            "orcid": orcid,
            "name": name
        }

        user_info = UserInfo(
            email=email,
            orcid=orcid,
            name=name,
            projects=projects
        )

        logger.info(f"Login successful for {name} ({email})")

        return LoginResponse(
            success=True,
            user=user_info,
            session_token=session_token,
            message="Login successful"
        )

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def logout(session_token: str):
    """
    Logout user and invalidate session token.
    """
    if session_token in sessions:
        del sessions[session_token]
        return {"success": True, "message": "Logged out successfully"}
    return {"success": False, "message": "Invalid session"}

@router.get("/session/{session_token}")
async def verify_session(session_token: str):
    """
    Verify if a session token is valid.
    """
    if session_token in sessions:
        return {"valid": True, "user": sessions[session_token]}
    return {"valid": False}
