import logging
from supabase import create_client, Client
from app.core.config import get_settings

# Setup logger
logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize Supabase Client
supabase: Client = create_client(
    settings.SUPABASE_URL, 
    settings.SUPABASE_KEY
)

async def upload_profile_photo(file_bytes: bytes, user_id: str, file_extension: str) -> str:
    """
    Uploads a profile photo to Supabase Storage.
    Returns the public URL of the uploaded image.
    """
    file_name = f"{user_id}.{file_extension}"
    file_path = f"{user_id}/{file_name}"
    
    try:
        supabase.storage.from_("profile_photos").upload(
            file_path,
            file_bytes,
            {"upsert": "true"}
        )
        
        public_url = supabase.storage.from_("profile_photos").get_public_url(file_path)
        logger.info(f"Successfully uploaded photo to Supabase: {file_path}")
        
        return public_url
        
    except Exception as e:
        logger.error(f"Supabase Storage Upload Failed for user {user_id}: {str(e)}")
        raise Exception(f"Failed to upload image to cloud storage: {str(e)}")