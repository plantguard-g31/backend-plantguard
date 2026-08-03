import ssl
import sys
import traceback
from pathlib import Path

import uvicorn


def verify_tls_config():
    """
    Verify that the certificate and private key exist.
    """
    cert = Path("server.crt")
    key = Path("server.key")

    if not cert.exists():
        print(f"❌ Missing certificate: {cert.absolute()}")

    if not key.exists():
        print(f"❌ Missing private key: {key.absolute()}")

    return cert.exists() and key.exists()


def create_tls_context() -> ssl.SSLContext:
    """
    Create an SSL context that ONLY allows TLS 1.3.
    """

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # Enforce TLS 1.3 ONLY
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3

    # Load certificate
    context.load_cert_chain(
        certfile="server.crt",
        keyfile="server.key",
    )

    return context


def ssl_context_factory(config, default_factory):
    """
    Uvicorn calls this to obtain the SSL context.
    """
    print("🔒 Creating TLS 1.3 ONLY SSL Context...")
    return create_tls_context()


if __name__ == "__main__":

    print("=" * 60)
    print("PlantGuard Backend TLS 1.3 Verification Server")
    print("=" * 60)

    if not verify_tls_config():
        print("\n❌ Certificate files not found.")
        sys.exit(1)

    try:

        # Verify SSL Context
        ctx = create_tls_context()

        print("\n✅ SSL Context Created Successfully")
        print(f"Minimum TLS : {ctx.minimum_version.name}")
        print(f"Maximum TLS : {ctx.maximum_version.name}")

        print("\nStarting HTTPS server...")
        print("URL: https://localhost:8000")
        print("URL: https://127.0.0.1:8000")
        print("\nTLS Policy:")
        print("  ✔ TLS 1.3 : Allowed")
        print("  ✘ TLS 1.2 : Blocked")
        print("  ✘ TLS 1.1 : Blocked")
        print("  ✘ TLS 1.0 : Blocked")
        print("=" * 60)

        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            ssl_context_factory=ssl_context_factory,
        )

    except Exception:
        print("\n💥 Server failed to start:\n")
        traceback.print_exc()
        sys.exit(1)