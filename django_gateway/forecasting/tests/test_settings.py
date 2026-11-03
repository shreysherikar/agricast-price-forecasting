"""
Unit tests for safe production defaults in Django gateway settings:
- Missing DJANGO_SECRET_KEY in production mode (DEBUG=False) raises ImproperlyConfigured.
- Dev secret key allowed when DEBUG=True.
- DJANGO_ALLOWED_HOSTS defaults to ['localhost', '127.0.0.1'].
- CORS_ALLOW_ALL_ORIGINS defaults to False.
- CORS_ALLOWED_ORIGINS defaults to localhost:3000, localhost:3001, localhost:5173.
- Security headers (SECURE_CONTENT_TYPE_NOSNIFF, X_FRAME_OPTIONS) set when DEBUG=False.
"""
import os
import sys
import importlib
from unittest import TestCase
from django.core.exceptions import ImproperlyConfigured


class GatewaySettingsTests(TestCase):
    def setUp(self):
        self._orig_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)
        # Reload settings with original env restored so subsequent tests are clean
        if "gateway.settings" in sys.modules:
            importlib.reload(sys.modules["gateway.settings"])

    def test_missing_secret_key_in_production_raises(self):
        """When DEBUG is False and DJANGO_SECRET_KEY is unset, ImproperlyConfigured must be raised."""
        os.environ["DJANGO_DEBUG"] = "False"
        os.environ.pop("DJANGO_SECRET_KEY", None)

        with self.assertRaises(ImproperlyConfigured):
            import gateway.settings
            importlib.reload(gateway.settings)

    def test_dev_secret_key_allowed_when_debug_true(self):
        """When DEBUG is True and DJANGO_SECRET_KEY is unset, a dev fallback key is permitted."""
        os.environ["DJANGO_DEBUG"] = "True"
        os.environ.pop("DJANGO_SECRET_KEY", None)

        import gateway.settings
        importlib.reload(gateway.settings)

        self.assertTrue(gateway.settings.DEBUG)
        self.assertTrue(len(gateway.settings.SECRET_KEY) > 0)
        self.assertIn("dev", gateway.settings.SECRET_KEY.lower())

    def test_default_allowed_hosts(self):
        """DJANGO_ALLOWED_HOSTS defaults to localhost and 127.0.0.1."""
        os.environ["DJANGO_DEBUG"] = "True"
        os.environ.pop("DJANGO_ALLOWED_HOSTS", None)

        import gateway.settings
        importlib.reload(gateway.settings)

        self.assertEqual(gateway.settings.ALLOWED_HOSTS, ["localhost", "127.0.0.1"])

    def test_custom_allowed_hosts_override(self):
        """DJANGO_ALLOWED_HOSTS accepts a comma-separated list of hosts."""
        os.environ["DJANGO_DEBUG"] = "True"
        os.environ["DJANGO_ALLOWED_HOSTS"] = "api.myapp.com, web.myapp.com"

        import gateway.settings
        importlib.reload(gateway.settings)

        self.assertEqual(gateway.settings.ALLOWED_HOSTS, ["api.myapp.com", "web.myapp.com"])

    def test_cors_defaults(self):
        """CORS defaults to safe non-wildcard with specific local origins."""
        os.environ["DJANGO_DEBUG"] = "True"
        os.environ.pop("CORS_ALLOW_ALL", None)
        os.environ.pop("CORS_ALLOWED_ORIGINS", None)

        import gateway.settings
        importlib.reload(gateway.settings)

        self.assertFalse(gateway.settings.CORS_ALLOW_ALL_ORIGINS)
        expected_origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:5173",
        ]
        self.assertEqual(gateway.settings.CORS_ALLOWED_ORIGINS, expected_origins)

    def test_cors_custom_origins_override(self):
        """CORS_ALLOWED_ORIGINS can be overridden via comma-separated environment variable."""
        os.environ["DJANGO_DEBUG"] = "True"
        os.environ["CORS_ALLOWED_ORIGINS"] = "https://forecasting-dashboard.vercel.app, https://preview.vercel.app"

        import gateway.settings
        importlib.reload(gateway.settings)

        self.assertFalse(gateway.settings.CORS_ALLOW_ALL_ORIGINS)
        self.assertEqual(
            gateway.settings.CORS_ALLOWED_ORIGINS,
            ["https://forecasting-dashboard.vercel.app", "https://preview.vercel.app"],
        )

    def test_production_security_headers(self):
        """When DEBUG is False, SECURE_CONTENT_TYPE_NOSNIFF and X_FRAME_OPTIONS must be set."""
        os.environ["DJANGO_DEBUG"] = "False"
        os.environ["DJANGO_SECRET_KEY"] = "prod-test-secret-key-1234567890"

        import gateway.settings
        importlib.reload(gateway.settings)

        self.assertFalse(gateway.settings.DEBUG)
        self.assertTrue(getattr(gateway.settings, "SECURE_CONTENT_TYPE_NOSNIFF", False))
        self.assertEqual(getattr(gateway.settings, "X_FRAME_OPTIONS", None), "DENY")
