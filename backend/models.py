from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any

# ============================================================================
# Authentication Models
# ============================================================================

class LoginRequest(BaseModel):
    email: EmailStr

class UserInfo(BaseModel):
    email: str
    orcid: str
    name: str
    projects: List[str]

class LoginResponse(BaseModel):
    success: bool
    user: Optional[UserInfo] = None
    message: Optional[str] = None
    session_token: Optional[str] = None

# ============================================================================
# Synthesis Models
# ============================================================================

class SynthesisFieldsResponse(BaseModel):
    fields: Dict[str, List[str]]

class SynthesisUploadRequest(BaseModel):
    email: str
    orcid: str
    user_name: str
    project: str
    synthesis_type: str
    data: List[Dict[str, Any]]
    session_name: Optional[str] = None

class SynthesisUploadResponse(BaseModel):
    success: bool
    message: str
    summary: Optional[Dict[str, Any]] = None
