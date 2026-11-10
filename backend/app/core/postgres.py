"""Per-process Postgres connections for the API and voice worker."""
from functools import lru_cache
import atexit
import os
import socket
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import dns.resolver
import certifi
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import get_settings


@lru_cache
def _environment_root_cert(pem: str) -> str:
    fd, path = tempfile.mkstemp(prefix="opencall-db-ca-", suffix=".crt")
    with os.fdopen(fd, "w") as output:
        output.write(pem)
    atexit.register(lambda: Path(path).unlink(missing_ok=True))
    return path


@lru_cache
def get_pool() -> ConnectionPool:
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    conninfo = url.get_secret_value()
    host = urlsplit(conninfo).hostname
    if not host:
        raise RuntimeError("Invalid DATABASE_URL")
    # Explicit resolution avoids libpq's AI_ADDRCONFIG filtering of IPv6-only hosts.
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        address = next((entry[4][0] for entry in addresses if entry[0] == socket.AF_INET), addresses[0][4][0])
    except socket.gaierror:
        address = str(dns.resolver.resolve(host, "AAAA", lifetime=5)[0])
    root_cert = get_settings().database_ssl_root_cert
    pem = get_settings().database_ssl_root_cert_pem
    if pem:
        root_cert = _environment_root_cert(pem.get_secret_value())
    local_cert = Path(__file__).resolve().parents[2] / "prod-ca-2021.crt"
    if root_cert is None and local_cert.is_file():
        root_cert = local_cert
    return ConnectionPool(conninfo, min_size=0, max_size=4, timeout=10, open=True,
                          kwargs={"hostaddr": address, "connect_timeout": 8, "sslmode": "verify-full", "sslrootcert": str(root_cert) if root_cert else certifi.where(),
                                  "row_factory": dict_row, "prepare_threshold": None})
