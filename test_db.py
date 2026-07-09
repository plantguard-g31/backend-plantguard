from app.core.config import get_settings

settings = get_settings()

print("\n--- DATABASE CONNECTION TEST ---")
print(f"Is URL empty? {settings.DATABASE_URL == ''}")
print(f"Full URL loaded: {settings.DATABASE_URL}")
print("--------------------------------\n")