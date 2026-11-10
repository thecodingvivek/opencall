import socket
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import SecretStr

from app.core import postgres


class PostgresConfigTests(unittest.TestCase):
    def tearDown(self):
        postgres.get_pool.cache_clear()
        postgres._environment_root_cert.cache_clear()

    def test_pool_prefers_ipv4_and_uses_configured_certificate(self):
        settings = SimpleNamespace(
            database_url=SecretStr("postgresql://user:password@database.example/db"),
            database_ssl_root_cert=None,
            database_ssl_root_cert_pem=SecretStr("certificate contents"),
        )
        addresses = [(socket.AF_INET6, None, None, None, ("::1", 0, 0, 0)),
                     (socket.AF_INET, None, None, None, ("192.0.2.1", 0))]
        with patch("app.core.postgres.get_settings", return_value=settings), \
             patch("app.core.postgres.socket.getaddrinfo", return_value=addresses), \
             patch("app.core.postgres.ConnectionPool") as pool:
            postgres.get_pool()
            kwargs = pool.call_args.kwargs["kwargs"]
            self.assertEqual(kwargs["hostaddr"], "192.0.2.1")
            self.assertEqual(kwargs["sslmode"], "verify-full")
            self.assertEqual(Path(kwargs["sslrootcert"]).read_text(), "certificate contents")
