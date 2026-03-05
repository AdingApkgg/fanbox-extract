import os
import re
import html
import gzip
import bz2
import lzma
import zipfile
import tarfile
from urllib.parse import urlparse, urlunparse


class LinkExtractor:
    _URL_PATTERN = re.compile(r"(https?://[^\s<>\"]+)")
    _URL_BYTES_PATTERN = re.compile(br"https?://[^\s<>\"]+")
    _MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\((https?://[^)\s]+)\)")
    _TRAILING_URL_CHARS = ".,;:!?)>]}\"'，。；：！？）】》」』"
    _LEADING_URL_CHARS = "([{<\"'（【《「『"
    _ARCHIVE_SUFFIXES = (
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".tar.gz",
        ".tgz",
        ".tar.bz2",
        ".tbz2",
        ".tar.xz",
        ".txz",
        ".gz",
        ".bz2",
        ".xz",
    )
    _ACCESS_CODE_PATTERN = re.compile(
        r"(?:提取码|提取碼|访问码|存取码|密码|密碼|passcode|password|code|pwd|MEGA Password)\s*[:：]?\s*([A-Za-z0-9\-_]{3,20})",
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
        
        # Method 1: PyPDF Analysis (Text + Annotations)
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                text = page.extract_text() or ""
                # 1. Text links
                links.extend(self._extract_links_from_text(text))
                
                # 2. Annotation links
                fallback_code = self._extract_access_code(text)
                annot_urls = self._extract_pdf_annotations(page)
                for url in annot_urls:
                    normalized = self._normalize_url(url)
                    if normalized:
                        links.append((normalized, fallback_code))
        except Exception as e:
            print(f"PyPDF extraction error for {file_path}: {e}")
            pass

        # Method 2: Raw Bytes Scanning (Fallback for corrupted/weird PDFs)
        try:
            with open(file_path, "rb") as f:
                data = f.read()
                # Use bytes pattern to find raw URLs in the file stream
                for raw in self._URL_BYTES_PATTERN.findall(data):
                    try:
                        candidate = raw.decode("utf-8", errors="ignore")
                        normalized = self._normalize_url(candidate)
                        if normalized:
                            # Try to find access code nearby in the raw text (simple scan)
                            # This is less accurate but better than nothing
                            links.append((normalized, None))
                    except Exception:
                        continue
        except Exception as e:
            print(f"Raw bytes extraction error for {file_path}: {e}")
            pass

        return self._dedup(self._filter_links(links))

    def _extract_pdf_annotations(self, page) -> list[str]:
        urls = []
        try:
            if "/Annots" not in page:
                return []
            annots = page["/Annots"]
            # annots can be an IndirectObject
            if hasattr(annots, "get_object"):
                annots = annots.get_object()
            
            if not isinstance(annots, (list, tuple)):
                return []

            for annot in annots:
                try:
                    obj = annot.get_object()
                    # Type 1: /A (Action)
                    if "/A" in obj:
                        action = obj["/A"]
                        if hasattr(action, "get_object"):
                            action = action.get_object()
                        
                        # Subtype: URI
                        if "/URI" in action:
                            urls.append(action["/URI"])
                        
                        # Subtype: Launch
                        elif "/F" in action:
                            f_val = action["/F"]
                            if hasattr(f_val, "startswith") and f_val.startswith("http"):
                                urls.append(f_val)
                    
                    # Type 2: Direct URI
                    elif "/URI" in obj:
                        urls.append(obj["/URI"])
                except Exception:
                    continue
        except Exception:
            pass
        return urls

    def extract_text_links(self, text: str) -> list[tuple[str, str | None]]:
        return self._dedup(self._filter_links(self._extract_links_from_text(text)))

    def normalize_url(self, url: str) -> str | None:
        return self._normalize_url(url)

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

    def is_archive_file(self, path: str) -> bool:
        return path.lower().endswith(self._ARCHIVE_SUFFIXES)

    def extract_archive_to_dir(
        self,
        file_path: str,
        output_root_dir: str,
        skip_existing: bool = True,
    ) -> tuple[bool, str | None]:
        if not self.is_archive_file(file_path):
            return False, None
        target_dir = os.path.join(
            output_root_dir,
            f"{self._strip_archive_suffix(os.path.basename(file_path))}_extracted",
        )
        if skip_existing and os.path.isdir(target_dir) and os.listdir(target_dir):
            return True, target_dir
        os.makedirs(target_dir, exist_ok=True)
        try:
            lower_path = file_path.lower()
            if lower_path.endswith(".zip"):
                self._extract_zip(file_path, target_dir)
            elif lower_path.endswith(".rar"):
                self._extract_rar(file_path, target_dir)
            elif lower_path.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")):
                self._extract_tar(file_path, target_dir)
            elif lower_path.endswith(".7z"):
                self._extract_7z(file_path, target_dir)
            elif lower_path.endswith((".gz", ".bz2", ".xz")):
                self._extract_single_compressed(file_path, target_dir)
            else:
                return False, None
        except Exception:
            return False, None
        if not os.listdir(target_dir):
            return False, None
        return True, target_dir

    def extract_archives_recursively(
        self,
        root_dir: str,
        skip_existing: bool = True,
        should_stop=None,
    ) -> list[str]:
        processed_archives: set[str] = set()
        extracted_dirs: list[str] = []
        while True:
            extracted_any = False
            for file_path in self._iter_files_recursive(root_dir):
                if should_stop and should_stop():
                    return extracted_dirs
                if not self.is_archive_file(file_path):
                    continue
                archive_path = os.path.realpath(file_path)
                if archive_path in processed_archives:
                    continue
                processed_archives.add(archive_path)
                extracted, extract_dir = self.extract_archive_to_dir(
                    archive_path,
                    os.path.dirname(archive_path),
                    skip_existing=skip_existing,
                )
                if extracted and extract_dir:
                    extracted_dirs.append(extract_dir)
                    extracted_any = True
            if not extracted_any:
                break
        return extracted_dirs

    def collect_resource_files(self, root_dir: str) -> tuple[list[str], list[str]]:
        pdf_files: list[str] = []
        archive_files: list[str] = []
        for file_path in self._iter_files_recursive(root_dir):
            rel_path = os.path.relpath(file_path, root_dir)
            if rel_path.lower().endswith(".pdf"):
                pdf_files.append(rel_path)
            if self.is_archive_file(file_path):
                archive_files.append(rel_path)
        return sorted(set(pdf_files)), sorted(set(archive_files))

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

    def _extract_zip(self, file_path: str, output_dir: str) -> None:
        with zipfile.ZipFile(file_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                target_path = self._safe_target_path(output_dir, info.filename)
                if not target_path:
                    continue
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with zf.open(info) as src, open(target_path, "wb") as dst:
                    dst.write(src.read())

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

    def _extract_tar(self, file_path: str, output_dir: str) -> None:
        with tarfile.open(file_path, "r:*") as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                target_path = self._safe_target_path(output_dir, member.name)
                if not target_path:
                    continue
                handle = tf.extractfile(member)
                if handle is None:
                    continue
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "wb") as dst:
                    dst.write(handle.read())

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

    def _extract_rar(self, file_path: str, output_dir: str) -> None:
        import rarfile

        with rarfile.RarFile(file_path) as rf:
            for info in rf.infolist():
                if info.is_dir():
                    continue
                target_path = self._safe_target_path(output_dir, info.filename)
                if not target_path:
                    continue
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with rf.open(info) as src, open(target_path, "wb") as dst:
                    dst.write(src.read())

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

    def _extract_7z(self, file_path: str, output_dir: str) -> None:
        import py7zr

        with py7zr.SevenZipFile(file_path, mode="r") as archive:
            all_files = archive.readall()
            for filename, handle in all_files.items():
                target_path = self._safe_target_path(output_dir, filename)
                if not target_path:
                    continue
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "wb") as dst:
                    dst.write(handle.read())

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

    def _extract_single_compressed(self, file_path: str, output_dir: str) -> None:
        lower_path = file_path.lower()
        output_name = self._strip_archive_suffix(os.path.basename(file_path))
        output_path = os.path.join(output_dir, output_name or "extracted_file")
        if lower_path.endswith(".gz"):
            with gzip.open(file_path, "rb") as src, open(output_path, "wb") as dst:
                dst.write(src.read())
            return
        if lower_path.endswith(".bz2"):
            with bz2.open(file_path, "rb") as src, open(output_path, "wb") as dst:
                dst.write(src.read())
            return
        if lower_path.endswith(".xz"):
            with lzma.open(file_path, "rb") as src, open(output_path, "wb") as dst:
                dst.write(src.read())

    def _strip_archive_suffix(self, filename: str) -> str:
        lower_name = filename.lower()
        for suffix in sorted(self._ARCHIVE_SUFFIXES, key=len, reverse=True):
            if lower_name.endswith(suffix):
                return filename[: -len(suffix)] or filename
        return filename

    def _iter_files_recursive(self, root_dir: str):
        for current_root, _, files in os.walk(root_dir):
            for name in files:
                yield os.path.join(current_root, name)

    def _safe_target_path(self, output_dir: str, member_name: str) -> str | None:
        normalized = member_name.replace("\\", "/")
        normalized = normalized.lstrip("/")
        if not normalized:
            return None
        target_path = os.path.realpath(os.path.join(output_dir, normalized))
        output_root = os.path.realpath(output_dir)
        if target_path != output_root and not target_path.startswith(output_root + os.sep):
            return None
        return target_path

    def _extract_links_from_bytes(self, data: bytes, name: str) -> list[tuple[str, str | None]]:
        links: list[tuple[str, str | None]] = []
        if name.lower().endswith(".pdf"):
            pdf_links = self._extract_pdf_links_from_bytes(data)
            if pdf_links:
                links.extend(pdf_links)
        text = data.decode("utf-8", errors="ignore")
        links.extend(self._extract_links_from_text(text))
        for raw in self._URL_BYTES_PATTERN.findall(data):
            try:
                candidate = raw.decode("utf-8", errors="ignore")
            except Exception:
                continue
            normalized = self._normalize_url(candidate)
            if normalized:
                links.append((normalized, self._extract_access_code(text)))
        return links

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
                # 1. Text links
                links.extend(self._extract_links_from_text(text))
                
                # 2. Annotation links
                fallback_code = self._extract_access_code(text)
                annot_urls = self._extract_pdf_annotations(page)
                for url in annot_urls:
                    normalized = self._normalize_url(url)
                    if normalized:
                        links.append((normalized, fallback_code))
        except Exception:
            return []
        return links

    def _extract_links_from_text(self, text: str) -> list[tuple[str, str | None]]:
        text = self._normalize_text(text)
        links: list[tuple[str, str | None]] = []
        fallback_code = self._extract_access_code(text)
        for link in self._MARKDOWN_LINK_PATTERN.findall(text):
            normalized = self._normalize_url(link)
            if normalized:
                links.append((normalized, fallback_code))
        for line in text.splitlines():
            line_links = self._URL_PATTERN.findall(line)
            if not line_links:
                continue
            access_code = self._extract_access_code(line) or fallback_code
            for link in line_links:
                normalized = self._normalize_url(link)
                if normalized:
                    links.append((normalized, access_code))
        if links:
            return links
        for link in self._URL_PATTERN.findall(text):
            normalized = self._normalize_url(link)
            if normalized:
                links.append((normalized, fallback_code))
        return links

    def _normalize_text(self, text: str) -> str:
        normalized = html.unescape(text or "")
        normalized = normalized.replace("：", ":").replace("／", "/").replace("．", ".")
        
        # 1. Fix broken URLs where 'mega.nz' or 'drive.google.com' might be split by spaces or newlines
        # Example: "https://mega. nz/..." -> "https://mega.nz/..."
        # We target specific known domains to avoid false positives
        normalized = re.sub(r"(https?://(?:mega|drive|pan|1drv|dropbox|mediafire))[\s\n]+(\.[a-z]+)", r"\1\2", normalized, flags=re.IGNORECASE)
        
        # 2. General URL cleanup (existing logic)
        normalized = re.sub(r"hxxps?://", lambda m: "https://" if m.group(0).lower().startswith("hxxps") else "http://", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\[\.\]|\(\.\)|\{\.\}", ".", normalized)
        
        # 3. Handle cases where the URL itself is split across lines in PDF text extraction
        # e.g. "https://mega.nz/fo\nlder/xxx" -> "https://mega.nz/folder/xxx"
        # We look for a pattern that looks like the start of a URL followed by a newline and more non-whitespace chars
        normalized = re.sub(r"(https?://[^\s\n]+)[\n\r]+([^\s\n]+)", r"\1\2", normalized)
        
        return normalized

    def _normalize_url(self, url: str) -> str | None:
        candidate = (url or "").strip()
        if not candidate:
            return None
        candidate = candidate.strip(self._LEADING_URL_CHARS)
        candidate = candidate.rstrip(self._TRAILING_URL_CHARS)
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        normalized_path = parsed.path or ""
        normalized_query = parsed.query or ""
        normalized_fragment = parsed.fragment or ""
        return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), normalized_path, parsed.params, normalized_query, normalized_fragment))

    def _extract_access_code(self, text: str) -> str | None:
        # First try to find explicit MEGA/GDrive password pattern
        mega_pattern = re.search(r"MEGA\s*Password\s*[:：]?\s*([A-Za-z0-9\-_]+)", text, re.IGNORECASE)
        if mega_pattern:
            return mega_pattern.group(1).strip()
            
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
