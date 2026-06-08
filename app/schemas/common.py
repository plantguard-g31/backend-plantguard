from pydantic import BaseModel

class ErrorResponse(BaseModel):
    detail: str
    status: str = "error"
    code: int