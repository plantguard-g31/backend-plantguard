import logging
import json
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for easy parsing and audit trails."""
    
    def format(self, record):
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        # Add extra fields if present
        if hasattr(record, "user_id"):
            log_obj["user_id"] = record.user_id
        if hasattr(record, "ip_address"):
            log_obj["ip_address"] = record.ip_address
        if hasattr(record, "endpoint"):
            log_obj["endpoint"] = record.endpoint
        return json.dumps(log_obj)

def setup_logging() -> logging.Logger:
    """Creates and configures the plantguard logger."""
    logger = logging.getLogger("plantguard")
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False  # Don't bubble to root logger
    
    return logger

# Export a ready-to-use logger instance
security_logger = setup_logging()