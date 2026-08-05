from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.storage import build_r2_storage


class R2StorageSettingsTests(SimpleTestCase):
    def setUp(self):
        self.environment = {
            "R2_ENDPOINT_URL": "https://account.r2.cloudflarestorage.com/",
            "R2_ACCESS_KEY_ID": "access-key",
            "R2_SECRET_ACCESS_KEY": "secret-key",
            "R2_BUCKET_NAME": "events-media",
            "R2_CUSTOM_DOMAIN": "https://media.example.com/",
        }

    def test_complete_configuration_builds_s3_storage(self):
        storage = build_r2_storage(self.environment, required=True)

        self.assertEqual(storage["BACKEND"], "storages.backends.s3.S3Storage")
        self.assertEqual(storage["OPTIONS"]["endpoint_url"], "https://account.r2.cloudflarestorage.com")
        self.assertEqual(storage["OPTIONS"]["custom_domain"], "media.example.com")
        self.assertFalse(storage["OPTIONS"]["querystring_auth"])
        self.assertFalse(storage["OPTIONS"]["file_overwrite"])

    def test_optional_unconfigured_storage_uses_local_backend(self):
        self.assertIsNone(build_r2_storage({}, required=False))

    def test_required_configuration_reports_all_missing_values(self):
        with self.assertRaises(ImproperlyConfigured) as error:
            build_r2_storage({}, required=True)

        self.assertIn("R2_ENDPOINT_URL", str(error.exception))
        self.assertIn("R2_CUSTOM_DOMAIN", str(error.exception))

    def test_partial_configuration_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            build_r2_storage({"R2_BUCKET_NAME": "events-media"})

    def test_endpoint_must_be_https_and_have_no_path(self):
        self.environment["R2_ENDPOINT_URL"] = "http://example.com/path"

        with self.assertRaises(ImproperlyConfigured):
            build_r2_storage(self.environment, required=True)

    def test_custom_domain_must_not_contain_a_path(self):
        self.environment["R2_CUSTOM_DOMAIN"] = "media.example.com/private"

        with self.assertRaises(ImproperlyConfigured):
            build_r2_storage(self.environment, required=True)
