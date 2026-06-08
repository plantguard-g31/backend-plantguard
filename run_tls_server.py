import uvicorn
import ssl
import traceback
import sys
from pathlib import Path

def verify_tls_config():
    cert = Path("server.crt")
    key = Path("server.key")
    if not cert.exists():
        print(f"Missing: {cert.absolute()}")
    if not key.exists():
        print(f"Missing: {key.absolute()}")
    return cert.exists() and key.exists()

def create_tls_context(cert_file: str, key_file: str) -> ssl.SSLContext:
    """
    Creates an SSLContext enforcing TLS 1.3 minimum.
    Used for verification/testing only — production TLS is handled by Render.com.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.load_cert_chain(cert_file, key_file)
    return context

if __name__ == "__main__":
    print(" Starting TLS 1.3 server check...")
    if not verify_tls_config():
        print(" Aborting: Certificate files not found in project root.")
        sys.exit(1)
    
    try:
        #  Verify TLS 1.3 config works (for documentation/testing)
        print("🔒 Verifying TLS 1.3 context...")
        ctx = create_tls_context("server.crt", "server.key")
        print(f"TLS 1.3 context created. Minimum version: {ctx.minimum_version}")
        
        # Start Uvicorn with TLS using universally-supported parameters
        # Note: ssl_minimum_version is enforced at reverse proxy level in production
        print(" Starting Uvicorn on https://0.0.0.0:8000")
        print(" Connect via: https://localhost:8000 or https://127.0.0.1:8000")
        print(" Local testing: TLS version negotiated by client")
        print("   Production (Render.com): TLS 1.3 enforced automatically")
        
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",           # Listen on all interfaces
            port=8000,
            ssl_keyfile="server.key",      # Supported by all Uvicorn versions
            ssl_certfile="server.crt",     #Supported by all Uvicorn versions
        )
    except Exception as e:
        print("💥 CRASH DETAIL:")
        traceback.print_exc()
        sys.exit(1)