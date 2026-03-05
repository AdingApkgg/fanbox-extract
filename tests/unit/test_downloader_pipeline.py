import os
import tempfile
import unittest
from unittest.mock import patch

from fanbox_extractor.downloader import FanboxDownloader


class _FakeDetailResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "body": {
                "body": {
                    "text": "",
                },
                "tags": [],
                "feeRequired": 0,
                "isRestricted": False,
            }
        }


class _FakeSession:
    def get(self, url, timeout=None, stream=False):
        return _FakeDetailResponse()


class _FakeExtractor:
    def __init__(self):
        self.downloaded_archive = False
        self.archive_dir_emitted = False
        self.extract_call_count = 0

    def extract_text_links(self, text):
        return []

    def extract_archives_recursively(self, root_dir, skip_existing=True, should_stop=None):
        self.extract_call_count += 1
        if self.downloaded_archive and not self.archive_dir_emitted:
            self.archive_dir_emitted = True
            archive_dir = os.path.join(root_dir, "net_archive_extracted")
            os.makedirs(archive_dir, exist_ok=True)
            return [archive_dir]
        return []

    def collect_resource_files(self, root_dir):
        if self.downloaded_archive:
            return ["first.pdf", "net_archive_extracted/second.pdf"], []
        return ["first.pdf"], []

    def extract_pdf_links(self, file_path):
        if file_path.endswith("first.pdf"):
            return [("https://example.com/net.zip", "abcd")]
        return []

    def process_archive(self, file_path):
        return []


class _FakeDriverManager:
    def __init__(self, extractor):
        self.extractor = extractor
        self.download_calls = 0

    def try_download_detail(self, url, output_dir):
        self.download_calls += 1
        self.extractor.downloaded_archive = True
        return True, "downloaded"


class DownloaderPipelineTest(unittest.TestCase):
    def test_downloaded_archive_is_extracted_in_following_round(self):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                downloader = FanboxDownloader("fake_sessid", "creator")
                fake_extractor = _FakeExtractor()
                downloader.extractor = fake_extractor
                downloader.driver_manager = _FakeDriverManager(fake_extractor)
                downloader.session = _FakeSession()

                markdown_payload = {}

                with patch(
                    "fanbox_extractor.downloader.write_bilingual_readmes",
                    lambda post_dir, markdown_text, callback=None: markdown_payload.setdefault("md", markdown_text),
                ):
                    downloader.process_post(
                        {
                            "id": "123",
                            "title": "Post",
                            "publishedDatetime": "2025-01-01T00:00:00+00:00",
                        },
                        skip_existing=True,
                        extract_archives=True,
                        auto_extract_archives=True,
                    )

                rendered = markdown_payload.get("md", "")
                self.assertIn("## Extracted Archives", rendered)
                self.assertIn("net_archive_extracted", rendered)
                self.assertIn("https://example.com/net.zip", rendered)
                self.assertGreaterEqual(fake_extractor.extract_call_count, 2)
                self.assertEqual(downloader.driver_manager.download_calls, 1)
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
