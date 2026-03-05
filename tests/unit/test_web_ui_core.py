import os
import tempfile
import unittest
from fanbox_extractor.web_ui_core import auth_enabled
from fanbox_extractor.web_ui_core import requires_auth
from fanbox_extractor.web_ui_core import build_download_url
from fanbox_extractor.web_ui_core import rewrite_markdown_links
from fanbox_extractor.web_ui_core import format_size


class WebUiCoreUnitTest(unittest.TestCase):
    def test_auth_enabled(self):
        self.assertTrue(auth_enabled("secret"))
        self.assertFalse(auth_enabled(""))
        self.assertFalse(auth_enabled("   "))

    def test_requires_auth(self):
        self.assertTrue(requires_auth("/"))
        self.assertTrue(requires_auth("/downloads/a.png"))
        self.assertFalse(requires_auth("/login"))
        self.assertFalse(requires_auth("/health"))

    def test_build_download_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloads = os.path.join(tmp, "downloads")
            os.makedirs(downloads, exist_ok=True)
            nested = os.path.join(downloads, "creator", "a b.txt")
            os.makedirs(os.path.dirname(nested), exist_ok=True)
            with open(nested, "w", encoding="utf-8") as f:
                f.write("x")
            url = build_download_url(nested, downloads)
            self.assertEqual(url, "/downloads/creator/a%20b.txt")
            outside = os.path.join(tmp, "outside.txt")
            with open(outside, "w", encoding="utf-8") as f:
                f.write("x")
            self.assertIsNone(build_download_url(outside, downloads))

    def test_rewrite_markdown_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloads = os.path.join(tmp, "downloads")
            post_dir = os.path.join(downloads, "creator", "post")
            os.makedirs(post_dir, exist_ok=True)
            markdown_path = os.path.join(post_dir, "README.md")
            image_path = os.path.join(post_dir, "image.png")
            with open(image_path, "w", encoding="utf-8") as f:
                f.write("x")
            content = "![img](image.png)\n[web](https://example.com)"
            rewritten = rewrite_markdown_links(content, markdown_path, downloads)
            self.assertIn("![]", rewritten.replace("[img]", "[]"))
            self.assertIn("/downloads/creator/post/image.png", rewritten)
            self.assertIn("(https://example.com)", rewritten)

    def test_format_size(self):
        self.assertEqual(format_size(512), "512.00 B")
        self.assertEqual(format_size(1024), "1.00 KB")


if __name__ == "__main__":
    unittest.main()
