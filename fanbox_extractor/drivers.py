import os
import types
import asyncio
import mimetypes
import requests
from urllib.parse import urlparse, parse_qs, unquote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class DriverManager:
    def __init__(self):
        self.request_timeout = (10, 120)
        self.session = self._build_session()

    def _build_session(self):
        session = requests.Session()
        retry = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def try_download(self, url: str, output_dir: str) -> bool:
        success, _ = self.try_download_detail(url, output_dir)
        return success

    def try_download_detail(self, url: str, output_dir: str) -> tuple[bool, str]:
        host = (urlparse(url).netloc or "").lower()
        if "drive.google.com" in url:
            return self._download_gdrive(url, output_dir)
        if "mega.nz" in host:
            return self._download_mega(url, output_dir)
        if "dropbox.com" in host:
            return self._download_dropbox(url, output_dir)
        if "1drv.ms" in host or "onedrive.live.com" in host:
            return self._download_onedrive(url, output_dir)
        if "mediafire.com" in host:
            return self._download_mediafire(url, output_dir)
        return self._download_http(url, output_dir)

    def _download_gdrive(self, url: str, output_dir: str) -> tuple[bool, str]:
        try:
            import gdown
        except Exception:
            return False, "gdrive_dependency_missing"
        try:
            gdown.download(url, output=output_dir, quiet=True, fuzzy=True)
            return True, "downloaded"
        except Exception:
            return False, "gdrive_download_failed"

    def _download_mega(self, url: str, output_dir: str) -> tuple[bool, str]:
        try:
            if not hasattr(asyncio, "coroutine"):
                setattr(asyncio, "coroutine", types.coroutine)
            from mega import Mega
        except Exception:
            return False, "mega_dependency_missing"
        try:
            target = os.path.abspath(output_dir)
            os.makedirs(target, exist_ok=True)
            client = Mega().login()
            result = client.download_url(url, dest_path=target)
            if result:
                return True, "downloaded"
            return False, "mega_no_result"
        except Exception:
            return False, "mega_download_failed"

    def _download_dropbox(self, url: str, output_dir: str) -> tuple[bool, str]:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        query["dl"] = ["1"]
        rebuilt_query = "&".join(f"{k}={v[0]}" for k, v in query.items())
        final_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if rebuilt_query:
            final_url = f"{final_url}?{rebuilt_query}"
        success, reason = self._download_http(final_url, output_dir)
        if success:
            return success, reason
        return False, "dropbox_download_failed"

    def _download_onedrive(self, url: str, output_dir: str) -> tuple[bool, str]:
        success, reason = self._download_http(url, output_dir)
        if success:
            return success, reason
        return False, "onedrive_download_failed"

    def _download_mediafire(self, url: str, output_dir: str) -> tuple[bool, str]:
        try:
            response = self.session.get(url, timeout=self.request_timeout)
            response.raise_for_status()
            marker = 'href="https://download'
            idx = response.text.find(marker)
            if idx == -1:
                marker = 'href="http://download'
                idx = response.text.find(marker)
            if idx == -1:
                return False, "mediafire_link_not_found"
            start = idx + len('href="')
            end = response.text.find('"', start)
            if end == -1:
                return False, "mediafire_link_not_found"
            real_url = response.text[start:end]
            success, reason = self._download_http(real_url, output_dir)
            if success:
                return success, reason
            return False, "mediafire_download_failed"
        except Exception:
            return False, "mediafire_download_failed"

    def _guess_filename(self, url: str, response: requests.Response) -> str:
        content_disposition = response.headers.get("content-disposition", "")
        if "filename=" in content_disposition:
            name = content_disposition.split("filename=")[-1].strip().strip('"')
            name = unquote(name)
            if name:
                return name
        path_name = os.path.basename(urlparse(url).path)
        if path_name and "." in path_name:
            return unquote(path_name)
        content_type = (response.headers.get("content-type") or "").split(";")[0].strip()
        ext = mimetypes.guess_extension(content_type) or ""
        if not ext:
            ext = ".bin"
        return f"downloaded_file{ext}"

    def _download_http(self, url: str, output_dir: str) -> tuple[bool, str]:
        try:
            response = self.session.get(url, stream=True, timeout=self.request_timeout)
            response.raise_for_status()
            content_type = (response.headers.get("content-type") or "").lower()
            if "text/html" in content_type:
                return False, "direct_html_page"
            filename = self._guess_filename(url, response)
            target_dir = os.path.abspath(output_dir)
            os.makedirs(target_dir, exist_ok=True)
            target_path = os.path.join(target_dir, filename)
            if os.path.exists(target_path):
                return True, "downloaded"
            with open(target_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if not chunk:
                        continue
                    f.write(chunk)
            return True, "downloaded"
        except Exception:
            return False, "direct_download_failed"
