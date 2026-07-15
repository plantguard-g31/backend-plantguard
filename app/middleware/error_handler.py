from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

logger = logging.getLogger("plantguard.errors")

# ─────────────────────────────────────────────────────────────
# MASTER DICTIONARY: ALL FARMER-FRIENDLY BILINGUAL MESSAGES
# ─────────────────────────────────────────────────────────────
# Every error in PlantGuard is mapped here.
# Format: {"error_code": "HTTP_CODE", "message_en": "...", "message_ne": "..."}
# 
# DESIGN PRINCIPLES:
# 1. Plain language - farmers are not developers
# 2. Actionable - tells them WHAT to do, not just what went wrong
# 3. Bilingual - English + Nepali (Devanagari)
# 4. Consistent format - Flutter app can parse easily
# ─────────────────────────────────────────────────────────────

ERROR_MESSAGES = {
    # ── AUTHENTICATION ERRORS ──
    "invalid_credentials": {
        "en": "Invalid email or password. Please check and try again.",
        "ne": "गलत इमेल वा पासवर्ड। कृपया जाँच गरेर फेरि प्रयास गर्नुहोस्।"
    },
    "account_deactivated": {
        "en": "Your account has been deactivated. Please contact support.",
        "ne": "तपाईंको खाता निष्क्रिय गरिएको छ। कृपया सहयोगको लागि सम्पर्क गर्नुहोस्।"
    },
    "token_expired": {
        "en": "Your session has expired. Please log in again.",
        "ne": "तपाईंको सत्र सकिएको छ। कृपया फेरि लगइन गर्नुहोस्।"
    },
    "invalid_token": {
        "en": "Invalid authentication token. Please log in again.",
        "ne": "अमान्य प्रमाणीकरण टोकन। कृपया फेरि लगइन गर्नुहोस्।"
    },
    "admin_required": {
        "en": "Admin access required. Please log in as an administrator.",
        "ne": "प्रशासक पहुँच आवश्यक छ। कृपया प्रशासकको रूपमा लगइन गर्नुहोस्।"
    },
    "forbidden": {
        "en": "You do not have permission to do this.",
        "ne": "तपाईंलाई यो गर्न अनुमति छैन।"
    },
    "cannot_delete_other": {
        "en": "You do not have permission to delete this record.",
        "ne": "तपाईंलाई यो रेकर्ड मेटाउन अनुमति छैन।"
    },
    "cannot_deactivate_admin": {
        "en": "Cannot deactivate an admin account.",
        "ne": "प्रशासक खाता निष्क्रिय गर्न सकिँदैन।"
    },

    # ── PASSWORD CHANGE ERRORS ──
    "password_mismatch": {
        "en": "Passwords do not match. Please make sure both passwords are the same.",
        "ne": "पासवर्ड मेल खाँदैन। कृपया दुवै पासवर्ड एउटै छ भनि सुनिश्चित गर्नुहोस्।"
    },
    "password_too_short": {
        "en": "Password must be at least 8 characters long.",
        "ne": "पासवर्ड कम्तिमा ८ अक्षरको हुनुपर्छ।"
    },
    "password_same_as_current": {
        "en": "New password must be different from your current password.",
        "ne": "नयाँ पासवर्ड तपाईंको हालको पासवर्डभन्दा फरक हुनुपर्छ।"
    },
    "invalid_current_password": {
        "en": "Current password is incorrect.",
        "ne": "हालको पासवर्ड गलत छ।"
    },

    # ── FILE UPLOAD ERRORS ──
    "file_too_large": {
        "en": "Photo is too large. Please select a photo smaller than 5 MB.",
        "ne": "फोटो धेरै ठूलो छ। कृपया ५ एमबी भन्दा सानो फोटो छान्नुहोस्।"
    },
    "invalid_magic_bytes": {
        "en": "This is not a valid photo. Please select a JPEG or PNG image.",
        "ne": "यो मान्य फोटो होइन। कृपया JPEG वा PNG छवि छान्नुहोस्।"
    },
    "invalid_file_type": {
        "en": "Invalid file type. Only JPEG and PNG images are allowed.",
        "ne": "अमान्य फाइल प्रकार। केवल JPEG र PNG छविहरू अनुमति छन्।"
    },
    "file_corrupted": {
        "en": "File is corrupted or not a valid image.",
        "ne": "फाइल बिग्रिएको छ वा मान्य छवि होइन।"
    },

    # ── IMAGE QUALITY ERRORS ──
    "low_resolution": {
        "en": "Photo is too small. Please take a photo from closer.",
        "ne": "फोटो धेरै सानो छ। कृपया नजिकबाट फोटो खिच्नुहोस्।"
    },
    "blurry_image": {
        "en": "Photo is blurry. Please hold your phone steady and try again.",
        "ne": "फोटो धमिलो छ। कृपया फोन स्थिर राखेर फेरि प्रयास गर्नुहोस्।"
    },
    "image_too_dark": {
        "en": "Photo is too dark. Please move to a brighter area and retake.",
        "ne": "फोटो धेरै अँध्यारो छ। कृपया उज्यालो ठाउँमा गएर फेरि खिच्नुहोस्।"
    },
    "image_too_bright": {
        "en": "Photo is too bright. Please avoid direct sunlight and retake.",
        "ne": "फोटो धेरै चम्किलो छ। कृपया सिधा घामबाट बचेर फेरि खिच्नुहोस्।"
    },
    "no_leaf_detected": {
        "en": "No plant leaf found. Please make sure the photo shows a leaf.",
        "ne": "बिरुवाको पात फेला परेन। कृपया फोटोमा पात देखिने गरी खिच्नुहोस्।"
    },
    "invalid_input": {
        "en": "We could not read this photo. Please try another one.",
        "ne": "यो फोटो पढ्न सकिएन। कृपया अर्को फोटो प्रयास गर्नुहोस्।"
    },

    # ── RATE LIMITING ──
    "rate_limit": {
        "en": "Too many requests. Please wait 60 seconds and try again.",
        "ne": "धेरै अनुरोधहरू। कृपया ६० सेकेन्ड कुर्नुहोस् र फेरि प्रयास गर्नुहोस्।"
    },

    # ── NOT FOUND ──
    "not_found": {
        "en": "We could not find what you are looking for.",
        "ne": "तपाईंले खोजेको कुरा फेला परेन।"
    },
    "history_not_found": {
        "en": "This diagnosis record was not found.",
        "ne": "यो निदान रेकर्ड फेला परेन।"
    },
    "treatment_not_found": {
        "en": "Treatment not found in database for this severity level.",
        "ne": "यो गम्भीरता स्तरको लागि डाटाबेसमा उपचार फेला परेन।"
    },
    "user_not_found": {
        "en": "User not found.",
        "ne": "प्रयोगकर्ता फेला परेन।"
    },

    # ── VALIDATION ERRORS ──
    "invalid_email": {
        "en": "Invalid email format. Please check and try again.",
        "ne": "अमान्य इमेल ढाँचा। कृपया जाँच गरेर फेरि प्रयास गर्नुहोस्।"
    },
    "invalid_language": {
        "en": "Invalid language. Must be 'en' or 'ne'.",
        "ne": "अमान्य भाषा। 'en' वा 'ne' हुनुपर्छ।"
    },
    "invalid_crop_type": {
        "en": "Invalid crop type. Must be tomato, potato, or bell_pepper.",
        "ne": "अमान्य बाली प्रकार। टमाटर, आलु, वा बेल पेपर हुनुपर्छ।"
    },
    "duplicate_email": {
        "en": "This email is already registered. Please log in instead.",
        "ne": "यो इमेल पहिले नै दर्ता भइसकेको छ। कृपया लगइन गर्नुहोस्।"
    },

    # ── SYSTEM ERRORS ──
    "server_error": {
        "en": "Something went wrong on our side. Please try again later.",
        "ne": "हाम्रो तर्फबाट केही गल्ती भयो। कृपया पछि फेरि प्रयास गर्नुहोस्।"
    },
    "ai_unavailable": {
        "en": "Our AI model is not available right now. Please try again in a moment.",
        "ne": "हाम्रो AI मोडल अहिले उपलब्ध छैन। कृपया केही समयमा फेरि प्रयास गर्नुहोस्।"
    },
    "database_error": {
        "en": "Database error. Please try again later.",
        "ne": "डाटाबेस त्रुटि। कृपया पछि फेरि प्रयास गर्नुहोस्।"
    }
}

# ─────────────────────────────────────────────────────────────
# SMART ERROR FORMATTER
# ─────────────────────────────────────────────────────────────
def _format_error(status_code: int, detail: str) -> dict:
    """
    Converts any error into farmer-friendly bilingual format.
    
    Args:
        status_code: HTTP status code (e.g., 422, 401, 500)
        detail: The error detail string (could be a key like "blurry_image" or a raw message)
    
    Returns:
        dict with error_code, message_en, message_ne
    """
    # Check if detail is a known error key
    if detail in ERROR_MESSAGES:
        messages = ERROR_MESSAGES[detail]
        return {
            "error_code": str(status_code),
            "message_en": messages["en"],
            "message_ne": messages["ne"]
        }
    
    # If detail is not a known key, use generic message for that status code
    generic_messages = {
        400: {"en": "Invalid request. Please check your input.", "ne": "अमान्य अनुरोध। कृपया तपाईंको इनपुट जाँच गर्नुहोस्।"},
        401: {"en": "Authentication required. Please log in.", "ne": "प्रमाणीकरण आवश्यक छ। कृपया लगइन गर्नुहोस्।"},
        403: {"en": "You do not have permission to do this.", "ne": "तपाईंलाई यो गर्न अनुमति छैन।"},
        404: {"en": "We could not find what you are looking for.", "ne": "तपाईंले खोजेको कुरा फेला परेन।"},
        409: {"en": "This already exists. Please use a different value.", "ne": "यो पहिले नै अवस्थित छ। कृपया फरक मान प्रयोग गर्नुहोस्।"},
        413: {"en": "File is too large.", "ne": "फाइल धेरै ठूलो छ।"},
        415: {"en": "Unsupported file type.", "ne": "असमर्थित फाइल प्रकार।"},
        422: {"en": "Invalid input. Please check your details.", "ne": "अमान्य इनपुट। कृपया तपाईंको विवरण जाँच गर्नुहोस्।"},
        429: {"en": "Too many requests. Please wait and try again.", "ne": "धेरै अनुरोधहरू। कृपया कुर्नुहोस् र फेरि प्रयास गर्नुहोस्।"},
        500: {"en": "Something went wrong. Please try again later.", "ne": "केही गल्ती भयो। कृपया पछि फेरि प्रयास गर्नुहोस्।"},
        503: {"en": "Service temporarily unavailable. Please try again later.", "ne": "सेवा अस्थायी रूपमा अनुपलब्ध छ। कृपया पछि फेरि प्रयास गर्नुहोस्।"}
    }
    
    messages = generic_messages.get(status_code, {"en": "An error occurred.", "ne": "त्रुटि भयो।"})
    
    return {
        "error_code": str(status_code),
        "message_en": messages["en"],
        "message_ne": messages["ne"]
    }

# ─────────────────────────────────────────────────────────────
# SMART PYDANTIC ERROR DETECTOR
# ─────────────────────────────────────────────────────────────
def _detect_pydantic_error_key(errors: list) -> str:
    """
    Analyzes Pydantic validation errors and returns the appropriate error key.
    
    This is the CRITICAL FIX: Instead of always returning "invalid_input" for all
    422 errors, we look at the actual error message to determine which feature
    the error came from.
    
    Args:
        errors: List of Pydantic error dicts from RequestValidationError
    
    Returns:
        Error key string (e.g., "password_mismatch", "invalid_email", "invalid_language")
    """
    if not errors:
        return "invalid_input"
    
    # Get the first error (most relevant)
    first_error = errors[0]
    error_msg = str(first_error.get("msg", "")).lower()
    error_loc = str(first_error.get("loc", [])).lower()
    
    # Password-related errors
    if "password" in error_loc or "password" in error_msg:
        if "match" in error_msg or "do not match" in error_msg:
            return "password_mismatch"
        elif "at least" in error_msg or "too short" in error_msg or "8 characters" in error_msg:
            return "password_too_short"
        else:
            return "password_too_short"
    
    # Email-related errors
    if "email" in error_loc or "email" in error_msg:
        if "invalid" in error_msg or "format" in error_msg:
            return "invalid_email"
        else:
            return "invalid_email"
    
    # Language-related errors
    if "language" in error_loc or "language" in error_msg or "lang" in error_loc:
        return "invalid_language"
    
    # Crop type errors
    if "crop" in error_loc or "crop" in error_msg:
        return "invalid_crop_type"
    
    # Name-related errors
    if "name" in error_loc and "length" in error_msg:
        return "invalid_input"  # Generic validation error
    
    # Default fallback
    return "invalid_input"

# ─────────────────────────────────────────────────────────────
# ERROR HANDLER REGISTRATION
# ─────────────────────────────────────────────────────────────
def register_error_handlers(app):
    """
    Registers global error handlers for the FastAPI app.
    Every error is converted to farmer-friendly bilingual format.
    """
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """
        Handles all HTTPException raised by endpoints.
        Converts technical errors to farmer-friendly messages.
        """
        error_response = _format_error(exc.status_code, str(exc.detail))
        
        # Log the error for debugging (never shown to farmer)
        logger.warning(f"HTTP {exc.status_code}: {exc.detail} | Path: {request.url.path}")
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """
        Handles Pydantic validation errors (e.g., invalid email format, passwords don't match).
        
        CRITICAL FIX: This now detects which feature the error came from and returns
        the appropriate message instead of always showing "We could not read this photo."
        """
        errors = exc.errors()
        
        # Detect the specific error type
        error_key = _detect_pydantic_error_key(errors)
        
        # Get the appropriate message
        error_response = _format_error(422, error_key)
        
        # Log the full validation error for debugging
        logger.warning(f"Validation Error: {errors} | Path: {request.url.path}")
        
        return JSONResponse(
            status_code=422,
            content=error_response
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """
        Catches ALL unexpected errors (database crashes, AI model failures, etc.)
        This is the LAST line of defense - prevents farmers from seeing raw Python tracebacks.
        """
        error_response = _format_error(500, "server_error")
        
        # Log the full error with traceback for debugging
        logger.error(f"UNHANDLED ERROR: {type(exc).__name__}: {str(exc)} | Path: {request.url.path}", exc_info=True)
        
        return JSONResponse(
            status_code=500,
            content=error_response
        )