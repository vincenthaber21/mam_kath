from tempfile import TemporaryDirectory

from django.test import Client, SimpleTestCase, override_settings


class StaticAssetDeliveryTests(SimpleTestCase):
    def test_bundled_design_is_served_without_collectstatic_in_production(self):
        with TemporaryDirectory() as static_root:
            with override_settings(
                DEBUG=False,
                STATIC_ROOT=static_root,
                ALLOWED_HOSTS=["testserver"],
                STORAGES={
                    "default": {
                        "BACKEND": "django.core.files.storage.FileSystemStorage",
                    },
                    "staticfiles": {
                        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
                    },
                },
            ):
                client = Client()
                self.assertEqual(client.get("/").status_code, 200)
                self.assertEqual(client.get("/login/").status_code, 200)
                for path, mime in (
                    ("/static/css/site.css", {"text/css"}),
                    ("/static/js/site.js", {"text/javascript", "application/javascript"}),
                    ("/static/vendor/chart.umd.min.js", {"text/javascript", "application/javascript"}),
                ):
                    with self.subTest(path=path):
                        response = client.get(path)
                        self.assertEqual(response.status_code, 200)
                        self.assertIn(response["Content-Type"].split(";")[0], mime)
                        self.assertGreater(len(b"".join(response.streaming_content)), 100)
                        response.close()