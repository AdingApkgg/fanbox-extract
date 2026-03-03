import gdown
import os

class GoogleDriveDriver:
    @staticmethod
    def is_supported(url):
        return "drive.google.com" in url or "docs.google.com" in url

    @staticmethod
    def download(url, output_path):
        try:
            print(f"Downloading from Google Drive: {url}")
            # gdown handles file IDs and large files automatically
            # output=None allows gdown to extract name from metadata
            filename = gdown.download(url, output_path, quiet=False, fuzzy=True)
            return filename
        except Exception as e:
            print(f"Google Drive download failed: {e}")
            return None
