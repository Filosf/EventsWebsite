from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.security import normalize_production_secret


class ProductionSecretTests(SimpleTestCase):
    def test_render_generated_secret_is_expanded_deterministically(self):
        value = "B0jrphAPOY7pg92AN0c9MN4yecczLMdwnx4OkA1KFUk="

        normalized = normalize_production_secret(value)

        self.assertEqual(len(normalized), 128)
        self.assertEqual(normalized, normalize_production_secret(value))
        self.assertNotEqual(normalized, value)

    def test_long_secret_is_unchanged(self):
        value = "release-secret-key-with-more-than-fifty-random-characters-93725184062"

        self.assertEqual(normalize_production_secret(value), value)

    def test_short_or_low_variety_secrets_are_rejected(self):
        for secret in ("dev-only-change-me", "short", "a" * 64):
            with self.subTest(secret=secret), self.assertRaises(ImproperlyConfigured):
                normalize_production_secret(secret)
