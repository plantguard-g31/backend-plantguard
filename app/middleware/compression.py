from starlette.middleware.gzip import GZipMiddleware
from fastapi import FastAPI

def add_compression_middleware(app: FastAPI):
    """
    Enables GZip compression for all responses (60-80% reduction).
    """
    app.add_middleware(GZipMiddleware, minimum_size=500)  # Compress if >500 bytes