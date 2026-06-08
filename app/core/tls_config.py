import ssl
from pathlib import Path

def create_tls_context(cert_file: str, key_file: str) -> ssl.SSLContext:
    """
    Creates an SSLContext enforcing TLS 1.3 minimum.
    Used for local testing & production readiness.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3  # 🔒 Enforce TLS 1.3
    context.load_cert_chain(cert_file, key_file)
    context.set_ciphers("TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256")
    return context

def verify_tls_config():
    """Returns True if TLS files exist in project root."""
    cert = Path("server.crt")
    key = Path("server.key")
    return cert.exists() and key.exists()