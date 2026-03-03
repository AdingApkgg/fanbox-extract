import os
import re
import sys

# Monkey patch tenacity.asyncio for Python 3.11+ compatibility
if sys.version_info >= (3, 11):
    import asyncio
    if not hasattr(asyncio, 'coroutine'):
        # Simple shim for the removed decorator
        def coroutine(func):
            return func
        asyncio.coroutine = coroutine
        # Also need to ensure it's available before tenacity imports it
        sys.modules['asyncio'].coroutine = coroutine

from mega import Mega

class MegaDriver:
    def __init__(self):
        try:
            self.mega = Mega()
            # Anonymous login is enough for public links
            self.m = self.mega.login()
        except Exception:
            print("Mega anonymous login failed. Some downloads might not work.")
            self.m = None

    @staticmethod
    def is_supported(url):
        return "mega.nz" in url or "mega.co.nz" in url

    def download(self, url, output_dir):
        if not self.m:
            return False
            
        try:
            print(f"Downloading from Mega: {url}")
            # Mega download usually downloads to current dir, need to handle output_path
            # mega.py download_url(url, dest_path=None, dest_filename=None)
            
            # Extract key/id from url might be needed if direct url fails, but library handles it
            self.m.download_url(url, dest_path=output_dir)
            return True
        except Exception as e:
            # Check if it's the specific tenacity/asyncio error and ignore it if possible, 
            # or handle it gracefully.
            # The error 'AttributeError: module 'asyncio' has no attribute 'coroutine'' 
            # comes from old tenacity version used by mega.py interacting with new python 3.11+.
            # We can't easily fix the library, but we can catch the error.
            print(f"Mega download failed: {e}")
            return False
