from typing import Optional, Dict, Any
from pydantic import BaseModel # Or just use a dataclass/regular class

class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None # The successful response body (dict, list, etc.)
    error: Optional[Dict[str, Any]] = None # Structured error details
    status_code: Optional[int] = None # HTTP status from the external API
    message: Optional[str] = None # A human-readable message
