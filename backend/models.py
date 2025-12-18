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
    batch_id: Optional[str] = None
    data: List[Dict[str, Any]]  # Array of row objects
    session_name: Optional[str] = None

class SynthesisUploadResponse(BaseModel):
    success: bool
    message: str
    summary: Optional[Dict[str, Any]] = None

# ============================================================================
# Batch Models
# ============================================================================

class BatchResolveRequest(BaseModel):
    batch_id: str
    orcid: str
    project: str

class BatchMatch(BaseModel):
    unique_id: str
    sample_name: str
    description: Optional[str] = None
    creation_date: Optional[str] = None

class BatchResolveResponse(BaseModel):
    status: str  # 'resolved', 'multiple_matches', 'not_found'
    batch_id: Optional[str] = None
    matches: Optional[List[BatchMatch]] = None
    input: Optional[str] = None
    message: Optional[str] = None

class BatchCreateRequest(BaseModel):
    batch_name: str
    batch_id: str
    batch_description: Optional[str] = None
    orcid: str
    project: str

class BatchCreateResponse(BaseModel):
    success: bool
    unique_id: str
    message: str
