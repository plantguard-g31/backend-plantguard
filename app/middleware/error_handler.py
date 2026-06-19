from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# Master Dictionary of all Bilingual Errors (SRS FR-21)
ERROR_MESSAGES = {
    # --- Status Code Fallbacks ---
    400: {"en": "Invalid request. Please check your input.", "ne": "अमान्य अनुरोध। कृपया तपाईंको इनपुट जाँच गर्नुहोस्।"},
    401: {"en": "Your session has ended. Please log in again.", "ne": "तपाईंको सेसन सकिएको छ। कृपया फेरि लगिन गर्नुहोस्।"},
    403: {"en": "You do not have permission to perform this action.", "ne": "तपाईंलाई यो कार्य गर्ने अनुमति छैन।"},
    404: {"en": "Resource not found.", "ne": "स्रोत भेटिएन।"},
    409: {"en": "This email is already registered.", "ne": "यो इमेल पहिले नै दर्ता भइसकेको छ।"},
    413: {"en": "Photo is too large. Please select a photo under 5 MB.", "ne": "फोटो धेरै ठूलो छ। कृपया ५ एमबी भन्दा कम फोटो छान्नुहोस्।"},
    415: {"en": "This file is not a photo. Please select a JPEG or PNG image.", "ne": "यो फाइल फोटो होइन। कृपया JPEG वा PNG छवि छान्नुहोस्।"},
    422: {"en": "Photo quality not good enough. Please retake in better lighting.", "ne": "फोटोको गुणस्तर पर्याप्त छैन। कृपया राम्रो प्रकाशमा फेरि खिच्नुहोस्।"},
    429: {"en": "Too many requests. Please wait 60 seconds and try again.", "ne": "धेरै अनुरोधहरू। कृपया ६ सेकेन्ड कुर्नुहोस् र फेरि प्रयास गर्नुहोस्।"},
    500: {"en": "Internal server error. Please try again later.", "ne": "आन्तरिक सर्भर त्रुटि। कृपया पछि फेरि प्रयास गर्नुहोस्।"},

    # --- Specific Auth Errors ---
    "invalid_credentials": {"en": "Invalid email or password.", "ne": "अमान्य इमेल वा पासवर्ड।"},
    "account_deactivated": {"en": "Your account has been deactivated. Please contact support.", "ne": "तपाईंको खाता निष्क्रिय गरिएको छ। कृपया सहयोगको लागि सम्पर्क गर्नुहोस्।"},
    "password_mismatch": {"en": "Passwords do not match.", "ne": "पासवर्ड मेल खाँदैन।"},
    "duplicate_email": {"en": "This email is already registered.", "ne": "यो इमेल पहिले नै दर्ता भइसकेको छ।"},
    
    # --- Upload & Quality Errors ---
    "file_too_large": {"en": "Photo is too large. Please select a photo under 5 MB.", "ne": "फोटो धेरै ठूलो छ। कृपया ५ एमबी भन्दा कम फोटो छान्नुहोस्।"},
    "invalid_magic_bytes": {"en": "This file is not a photo. Please select a JPEG or PNG image.", "ne": "यो फाइल फोटो होइन। कृपया JPEG वा PNG छवि छान्नुहोस्।"},
    "invalid_input": {"en": "Invalid input format. Please check your details.", "ne": "अमान्य इनपुट ढाँचा। कृपया तपाईंको विवरण जाँच गर्नुहोस्।"},
    "low_resolution": {"en": "Photo resolution is too low. Please take a clearer photo.", "ne": "फोटोको रिजोल्युसन धेरै कम छ। कृपया स्पष्ट फोटो खिच्नुहोस्।"},
    "blurry_image": {"en": "Photo is too blurry. Please hold the camera steady.", "ne": "फोटो धमिलो छ। कृपया क्यामेरा स्थिर राख्नुहोस्।"},
    "image_too_dark": {"en": "Photo is too dark. Please use better lighting.", "ne": "फोटो धेरै अँध्यारो छ। कृपया राम्रो प्रकाश प्रयोग गर्नुहोस्।"},
    "image_too_bright": {"en": "Photo is overexposed. Please avoid direct sunlight.", "ne": "फोटो धेरै चम्किलो छ। कृपया प्रत्यक्ष घामबाट बच्नुहोस्।"},
    "no_leaf_detected": {"en": "No plant leaf detected. Please ensure the photo shows a leaf.", "ne": "कुनै बिरुवाको पात फेला परेन। कृपया फोटोमा पात छ भनि सुनिश्चित गर्नुहोस्।"},
}

def _format_error(status_code: int, detail: str, request: Request) -> dict:
    """
    Smart Error Formatter:
    1. Checks if 'detail' is a specific error key (e.g., 'invalid_credentials').
    2. If yes, returns the specific bilingual message.
    3. If no, falls back to the generic status code message.
    """
    # Check for specific key first
    if detail in ERROR_MESSAGES:
        messages = ERROR_MESSAGES[detail]
    else:
        # Fallback to generic status code message
        messages = ERROR_MESSAGES.get(status_code, ERROR_MESSAGES[500])
        
    return {
        "error_code": str(status_code),
        "message_en": messages["en"],
        "message_ne": messages["ne"]
    }

def register_error_handlers(app):
    @app.exception_handler(HTTPException)
    async def custom_http_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_format_error(exc.status_code, str(exc.detail), request)
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        # Handles Pydantic validation errors (e.g., invalid email format 'notaemail')
        # ALWAYS returns 'invalid_input', never the photo quality message.
        return JSONResponse(
            status_code=422,
            content=_format_error(422, "invalid_input", request)
        )