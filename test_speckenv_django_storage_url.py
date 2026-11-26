from importlib.util import find_spec
from pathlib import Path
from unittest import TestCase, skipUnless

from speckenv_django import django_storage_url


class DjangoStorageURLTest(TestCase):
    maxDiff = None

    def test_parse_storage_url(self):
        url = "file:/test/media/"
        self.assertEqual(
            django_storage_url(url),
            {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
                "OPTIONS": {
                    "base_url": None,
                    "location": Path("/test/media/"),
                },
            },
        )

    def test_parse_storage_url_with_url(self):
        url = "file:/test/media/?base_url=/media/"
        self.assertEqual(
            django_storage_url(url),
            {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
                "OPTIONS": {
                    "base_url": "/media/",
                    "location": Path("/test/media/"),
                },
            },
        )

    def test_parse_relative_url(self):
        cwd = Path("/hello/world/")
        url = "file:./relative/"
        self.assertEqual(
            django_storage_url(url, base_dir=cwd),
            {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
                "OPTIONS": {
                    "base_url": None,
                    "location": Path("/hello/world/relative/"),
                },
            },
        )

    def test_s3_without_botocore_isnt_tested(self):
        # The S3 tests below need botocore (django-storages' dependency)
        if find_spec("botocore") is None:
            self.skipTest("botocore isn't installed")


S3 = "storages.backends.s3.S3Storage"


@skipUnless(find_spec("botocore"), "botocore isn't installed")
class DjangoS3StorageURLTest(TestCase):
    maxDiff = None

    def options(self, url):
        storage = django_storage_url(url)
        self.assertEqual(storage["BACKEND"], S3)
        options = dict(storage["OPTIONS"])
        config = options.pop("client_config")
        if options.get("file_overwrite") is False:
            del options["file_overwrite"]
        # botocore 1.36 and later add a CRC32 checksum to every upload, sent
        # chunked; S3-compatible services which don't know it refuse uploads
        self.assertEqual(config.request_checksum_calculation, "when_required")
        self.assertEqual(config.response_checksum_validation, "when_required")
        return options

    def test_parse_s3_vhost(self):
        url = "s3://access-key-id:secret-access-key@bucket.name.s3.eu-central-1.amazonaws.com/media/"
        self.assertEqual(
            self.options(url),
            {
                "region_name": "eu-central-1",
                "access_key": "access-key-id",
                "secret_key": "secret-access-key",
                "bucket_name": "bucket.name",
                "location": "media",
            },
        )

    def test_parse_s3_path(self):
        url = "s3://access-key-id:secret-access-key@s3.eu-central-1.amazonaws.com/bucket-name/media/"
        self.assertEqual(
            self.options(url),
            {
                "region_name": "eu-central-1",
                "access_key": "access-key-id",
                "secret_key": "secret-access-key",
                "bucket_name": "bucket-name",
                "location": "media",
            },
        )

    def test_other_s3_nine(self):
        # https://docs.nine.ch/docs/object-storage/object-storage-client-tools
        url = "s3://6aaf50b17357446bb:fcf1c9c6bc5c43@cz42.objectstorage.nineapis.ch/bucket-etj4mwc/thing/?region_name=nine-cz42&custom_domain=cz42.objectstorage.nineapis.ch/v1/AUTH_7209e15171e/bucket-etj4mwc"
        self.assertEqual(
            self.options(url),
            {
                "endpoint_url": "https://cz42.objectstorage.nineapis.ch",
                "region_name": "nine-cz42",
                "access_key": "6aaf50b17357446bb",
                "secret_key": "fcf1c9c6bc5c43",
                "bucket_name": "bucket-etj4mwc",
                "custom_domain": "cz42.objectstorage.nineapis.ch/v1/AUTH_7209e15171e/bucket-etj4mwc",
                "location": "thing",
            },
        )

    def test_other_s3_digitalocean(self):
        # https://docs.digitalocean.com/reference/api/spaces-api/
        url = "s3://access-key:secret-key@nyc3.digitaloceanspaces.com/example-space-name/key-prefix/?region_name=nyc3"
        self.assertEqual(
            self.options(url),
            {
                "access_key": "access-key",
                "secret_key": "secret-key",
                "region_name": "nyc3",
                "location": "key-prefix",
                "endpoint_url": "https://nyc3.digitaloceanspaces.com",
                "bucket_name": "example-space-name",
            },
        )

    def test_s3_parameters(self):
        url = "s3://access-key-id:secret-access-key@bucket-name.s3.eu-central-1.amazonaws.com/media/?querystring_auth=False&gzip=True&querystring_expire=120"
        self.assertEqual(
            self.options(url),
            {
                "region_name": "eu-central-1",
                "access_key": "access-key-id",
                "secret_key": "secret-access-key",
                "bucket_name": "bucket-name",
                "location": "media",
                # Types!
                "querystring_auth": False,
                "gzip": True,
                "querystring_expire": 120,
            },
        )

    def test_django_s3_storage_parameters(self):
        # speckenv 6 configured django-s3-storage: its names keep working
        url = (
            "s3://key:secret@s3.eu-central-1.amazonaws.com/bucket/"
            "?aws_s3_bucket_auth=False&aws_s3_max_age_seconds=600&aws_s3_gzip=False"
            "&aws_s3_public_url=https://cdn.example.org/media/"
            "&aws_s3_reduced_redundancy=True&aws_s3_encrypt_key=True"
            "&aws_s3_signature_version=s3v4&aws_s3_addressing_style=path"
            "&aws_s3_file_overwrite=True&aws_s3_use_threads=False"
        )
        self.assertEqual(
            self.options(url),
            {
                "region_name": "eu-central-1",
                "access_key": "key",
                "secret_key": "secret",
                "bucket_name": "bucket",
                "location": "",
                # Public: no presigned URLs, a public ACL
                "querystring_auth": False,
                "default_acl": "public-read",
                "querystring_expire": 600,
                "gzip": False,
                "custom_domain": "cdn.example.org/media",
                "url_protocol": "https:",
                "object_parameters": {
                    "CacheControl": "public, max-age=600",
                    "StorageClass": "REDUCED_REDUNDANCY",
                    "ServerSideEncryption": "AES256",
                },
                "file_overwrite": True,
                "use_threads": False,
            },
        )

    def test_client_config_options(self):
        # django-storages ignores them as options when it gets a client config
        config = django_storage_url(
            "s3://key:secret@objects.example.org/bucket/"
            "?aws_s3_signature_version=s3&aws_s3_addressing_style=path"
        )["OPTIONS"]["client_config"]
        self.assertEqual(config.signature_version, "s3")
        self.assertEqual(config.s3, {"addressing_style": "path"})

        # SigV4 as with django-s3-storage, botocore presigns with SigV2
        config = django_storage_url("s3://key:secret@objects.example.org/bucket/")[
            "OPTIONS"
        ]["client_config"]
        self.assertEqual(config.signature_version, "s3v4")
        self.assertIsNone(config.s3)

    def test_files_arent_overwritten_by_default(self):
        # As with django-s3-storage; django-storages' default overwrites
        storage = django_storage_url("s3://key:secret@s3.eu-central-1.amazonaws.com/b/")
        self.assertFalse(storage["OPTIONS"]["file_overwrite"])

    def test_django_s3_storage_connection_settings(self):
        storage = django_storage_url(
            "s3://key:secret@objects.example.org/bucket/"
            "?aws_s3_connect_timeout=5&aws_s3_max_pool_connections=3"
        )
        config = storage["OPTIONS"]["client_config"]
        self.assertEqual(config.connect_timeout, 5)
        self.assertEqual(config.max_pool_connections, 3)
        self.assertEqual(config.request_checksum_calculation, "when_required")

    def test_django_s3_storage_parameters_without_a_counterpart(self):
        url = "s3://key:secret@s3.eu-central-1.amazonaws.com/bucket/?aws_s3_metadata=x"
        with self.assertRaisesRegex(ValueError, "aws_s3_metadata"):
            django_storage_url(url)
