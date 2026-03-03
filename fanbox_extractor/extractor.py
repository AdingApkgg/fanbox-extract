import os
import re
import gzip
import bz2
import lzma
import zipfile
import tarfile
from urllib.parse import urlparse


class LinkExtractor:
    _URL_PATTERN = re.compile(r"(https?://[^\s<>\"]+)")
    _ACCESS_CODE_PATTERN = re.compile(
        r"(?:提取码|提取碼|访问码|存取码|密码|密碼|passcode|password|code)\s*[:：]?\s*([A-Za-z0-9]{3,12})",
        re.IGNORECASE,
    )
    _IGNORED_HOST_KEYWORDS = (
        "w3.org",
        "purl.org",
        "ns.adobe.com",
    )

    def extract_pdf_links(self, file_path: str) -> list[tuple[str, str | None]]:
        try:
            from pypdf import PdfReader
        except Exception:
            return []
        links: list[tuple[str, str | None]] = []
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                text = page.extract_text() or ""
                links.extend(self._extract_links_from_text(text))
        except Exception:
            return []
        return self._dedup(self._filter_links(links))

    def process_archive(self, file_path: str) -> list[tuple[str, str | None]]:
        lower_path = file_path.lower()
        if lower_path.endswith(".zip"):
            return self._process_zip(file_path)
        if lower_path.endswith(".rar"):
            return self._process_rar(file_path)
        if lower_path.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")):
            return self._process_tar(file_path)
        if lower_path.endswith(".7z"):
            return self._process_7z(file_path)
        if lower_path.endswith((".gz", ".bz2", ".xz")):
            return self._process_single_compressed(file_path)
        return []

    def _process_zip(self, file_path: str) -> list[tuple[str, str | None]]:
        links: list[tuple[str, str | None]] = []
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    data = zf.read(info.filename)
                    links.extend(self._extract_links_from_bytes(data, info.filename))
        except Exception:
            return []
        return self._dedup(self._filter_links(links))

    def _process_tar(self, file_path: str) -> list[tuple[str, str | None]]:
        links: list[tuple[str, str | None]] = []
        try:
            with tarfile.open(file_path, "r:*") as tf:
                for member in tf.getmembers():
                    if not member.isfile():
                        continue
                    handle = tf.extractfile(member)
                    if handle is None:
                        continue
                    data = handle.read()
                    links.extend(self._extract_links_from_bytes(data, member.name))
        except Exception:
            return []
        return self._dedup(self._filter_links(links))

    def _process_rar(self, file_path: str) -> list[tuple[str, str | None]]:
        try:
            import rarfile
        except Exception:
            return []
        links: list[tuple[str, str | None]] = []
        try:
            with rarfile.RarFile(file_path) as rf:
                for info in rf.infolist():
                    if info.is_dir():
                        continue
                    with rf.open(info) as handle:
                        data = handle.read()
                        links.extend(self._extract_links_from_bytes(data, info.filename))
        except Exception:
            return []
        return self._dedup(self._filter_links(links))

    def _process_7z(self, file_path: str) -> list[tuple[str, str | None]]:
        try:
            import py7zr
        except Exception:
            return []
        links: list[tuple[str, str | None]] = []
        try:
            with py7zr.SevenZipFile(file_path, mode="r") as archive:
                all_files = archive.readall()
                for filename, handle in all_files.items():
                    try:
                        data = handle.read()
                    except Exception:
                        continue
                    links.extend(self._extract_links_from_bytes(data, filename))
        except Exception:
            return []
        return self._dedup(self._filter_links(links))

    def _process_single_compressed(self, file_path: str) -> list[tuple[str, str | None]]:
        lower_path = file_path.lower()
        try:
            if lower_path.endswith(".gz"):
                with gzip.open(file_path, "rb") as f:
                    data = f.read()
            elif lower_path.endswith(".bz2"):
                with bz2.open(file_path, "rb") as f:
                    data = f.read()
            elif lower_path.endswith(".xz"):
                with lzma.open(file_path, "rb") as f:
                    data = f.read()
            else:
                return []
        except Exception:
            return []
        return self._dedup(self._filter_links(self._extract_links_from_bytes(data, os.path.basename(file_path))))

    def _extract_links_from_bytes(self, data: bytes, name: str) -> list[tuple[str, str | None]]:
        if name.lower().endswith(".pdf"):
            pdf_links = self._extract_pdf_links_from_bytes(data)
            if pdf_links:
                return pdf_links
        text = data.decode("utf-8", errors="ignore")
        return self._extract_links_from_text(text)

    def _extract_pdf_links_from_bytes(self, data: bytes) -> list[tuple[str, str | None]]:
        try:
            from io import BytesIO
            from pypdf import PdfReader
        except Exception:
            return []
        links: list[tuple[str, str | None]] = []
        try:
            reader = PdfReader(BytesIO(data))
            for page in reader.pages:
                text = page.extract_text() or ""
                links.extend(self._extract_links_from_text(text))
        except Exception:
            return []
        return links

    def _extract_links_from_text(self, text: str) -> list[tuple[str, str | None]]:
        links: list[tuple[str, str | None]] = []
        fallback_code = self._extract_access_code(text)
        for line in text.splitlines():
            line_links = self._URL_PATTERN.findall(line)
            if not line_links:
                continue
            access_code = self._extract_access_code(line) or fallback_code
            for link in line_links:
                links.append((link, access_code))
        if links:
            return links
        for link in self._URL_PATTERN.findall(text):
            links.append((link, fallback_code))
        return links

    def _extract_access_code(self, text: str) -> str | None:
        match = self._ACCESS_CODE_PATTERN.search(text)
        if not match:
            return None
        return match.group(1)

    def _filter_links(self, links: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
        filtered: list[tuple[str, str | None]] = []
        for link, access_code in links:
            host = (urlparse(link).netloc or "").lower()
            if any(keyword in host for keyword in self._IGNORED_HOST_KEYWORDS):
                continue
            filtered.append((link, access_code))
        return filtered

    def _dedup(self, links: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
        ordered_urls: list[str] = []
        merged_codes: dict[str, str | None] = {}
        for link, access_code in links:
            if link not in merged_codes:
                ordered_urls.append(link)
                merged_codes[link] = access_code
                continue
            if merged_codes[link] is None and access_code:
                merged_codes[link] = access_code
        return [(url, merged_codes[url]) for url in ordered_urls]
