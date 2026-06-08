from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.config import get_settings

settings = get_settings()

# Farmer-friendly bilingual error messages
ERROR_MESSAGES = {
    400: {"en": "Invalid request. Please check your input.", "ne": "अमान्य अनुरोध। कृपया तपाईंको इनपुट जाँच गर्नुहोस्।"},
    401: {"en": "Session expired. Please login again.", "ne": "सेसन सकियो। कृपया फेरि लगिन गर्नुहोस्।"},
    403: {"en": "Access denied. Insufficient permissions.", "ne": "प्रवेश अस्वीकृत। अनुमति पर्याप्त छैन।"},
    404: {"en": "Resource not found.", "ne": "स्रोत भेटिएन।"},
    413: {"en": "Photo too large. Maximum size is 5MB.", "ne": "फोटो धेरै ठूलो छ। अधिकतम आकार 5MB हो।"},
    415: {"en": "Invalid file format. Please upload a JPEG or PNG image.", "ne": "अमान्य फाइल ढाँचा। कृपया JPEG वा PNG छवि अपलोड गर्नुहोस्।"},
    422: {"en": "Photo quality not good enough. Please retake in better lighting.", "ne": "फोटोको गुणस्तर पर्याप्त छैन। कृपया राम्रो प्रकाशमा फेरि खिच्नुहोस्।"},
    429: {"en": "Too many requests. Please wait 60 seconds.", "ne": "धेरै अनुरोधहरू। कृपया ६० सेकेन्ड कुर्नुहोस्।"},
    500: {"en": "Internal server error. Please try again later.", "ne": "आन्तरिक सर्भर त्रुटि। कृपया पछि फेरि प्रयास गर्नुहोस्।"},
}

def _get_language(request: Request) -> str:
    """Extracts language preference from query param (?lang=ne) or defaults to English."""
    lang = request.query_params.get("lang", "en")
    return lang if lang in ["en", "ne"] else "en"

def _format_error(status_code: int, detail: str, request: Request) -> dict:
    lang = _get_language(request)
    # Map technical detail to farmer-friendly message
    if status_code in ERROR_MESSAGES:
        msg = ERROR_MESSAGES[status_code].get(lang, ERROR_MESSAGES[status_code]["en"])
    else:
        msg = ERROR_MESSAGES[500].get(lang, detail)
    
    return {"detail": msg, "status": "error", "code": status_code}

def register_error_handlers(app):
    """Attaches custom exception handlers to the FastAPI app."""
    
    @app.exception_handler(HTTPException)
    async def custom_http_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_format_error(exc.status_code, exc.detail, request)
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_format_error(422, "validation_error", request)
        )