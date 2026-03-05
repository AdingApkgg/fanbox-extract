import os
import re
import requests
import threading
import concurrent.futures
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from xml.etree import ElementTree as ET
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .utils import sanitize_filename
from .extractor import LinkExtractor
from .drivers import DriverManager
from .markdown_i18n import write_bilingual_readmes


class _PatreonHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        attrs_dict = dict(attrs)
        href = (attrs_dict.get("href") or "").strip()
        if href:
            self.links.append(href)

    def handle_data(self, data):
        if data:
            self.text_parts.append(data)


class PatreonDownloader:
    def __init__(self, rss_url, creator_id="patreon", creator_name=None):
        self.rss_url = (rss_url or "").strip()
        self.creator_id = sanitize_filename(creator_id or "patreon")
        self.creator_name = creator_name or self.creator_id
        self.base_dir = os.path.join(os.getcwd(), "downloads", self.creator_id)
        os.makedirs(self.base_dir, exist_ok=True)
        self.extractor = LinkExtractor()
        self.driver_manager = DriverManager()
        self.request_timeout = (10, 120)
        self._stop_event = threading.Event()
        self.session = self._build_session()
        self._url_pattern = re.compile(r"(https?://[^\s<>\"]+)")

    def _build_session(self):
        session = requests.Session()
        retry = Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=50, pool_maxsize=50)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def request_stop(self):
        self._stop_event.set()

    def clear_stop(self):
        self._stop_event.clear()

    def set_creator(self, creator_id):
        self.creator_id = sanitize_filename(creator_id or "patreon")
        self.base_dir = os.path.join(os.getcwd(), "downloads", self.creator_id)
        os.makedirs(self.base_dir, exist_ok=True)

    def fetch_supporting_creators(self):
        return []

    def _extract_links_from_html(self, raw_html):
        if not raw_html:
            return []
        parser = _PatreonHTMLParser()
        try:
            parser.feed(raw_html)
            parser.close()
        except Exception:
            parser = _PatreonHTMLParser()
        text_links = self.extractor.extract_text_links(" ".join(parser.text_parts))
        html_links = parser.links + self._url_pattern.findall(raw_html)
        ordered_urls = []
        merged_codes = {}
        for link, access_code in text_links:
            if link not in merged_codes:
                ordered_urls.append(link)
                merged_codes[link] = access_code
                continue
            if merged_codes[link] is None and access_code:
                merged_codes[link] = access_code
        for link in html_links:
            normalized = self.extractor.normalize_url(link)
            if not normalized:
                continue
            if normalized in merged_codes:
                continue
            ordered_urls.append(normalized)
            merged_codes[normalized] = None
        return [(url, merged_codes[url]) for url in ordered_urls]

    def get_posts(self):
        if not self.rss_url:
            return []
        try:
            response = self.session.get(self.rss_url, timeout=self.request_timeout)
            response.raise_for_status()
        except Exception:
            return []

        try:
            root = ET.fromstring(response.text)
        except Exception:
            return []

        channel = root.find("channel")
        if channel is None:
            return []
        items = channel.findall("item")
        posts = []
        for item in items:
            title = (item.findtext("title") or "Untitled").strip()
            guid = (item.findtext("guid") or item.findtext("link") or title).strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            description = item.findtext("description") or ""
            content_encoded = ""
            for child in item:
                if child.tag.endswith("encoded") and child.text:
                    content_encoded = child.text
                    break
            body_html = content_encoded or description
            enclosures = []
            for enclosure in item.findall("enclosure"):
                url = (enclosure.attrib.get("url") or "").strip()
                if url:
                    enclosures.append(url)
            published = ""
            if pub_date:
                try:
                    published = parsedate_to_datetime(pub_date).isoformat()
                except Exception:
                    published = pub_date
            posts.append(
                {
                    "id": guid,
                    "title": title,
                    "url": link,
                    "publishedDatetime": published,
                    "body_html": body_html,
                    "enclosures": enclosures,
                    "links": self._extract_links_from_html(body_html),
                }
            )
        return posts

    def download_file(self, url, filepath, skip_existing=True):
        if skip_existing and os.path.exists(filepath):
            return filepath
        if self._stop_event.is_set():
            return None
        try:
            response = self.session.get(url, stream=True, timeout=self.request_timeout)
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            with open(filepath, "wb") as f, tqdm(
                desc=os.path.basename(filepath),
                total=total_size,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for data in response.iter_content(chunk_size=1024 * 64):
                    if self._stop_event.is_set():
                        return None
                    size = f.write(data)
                    bar.update(size)
            return filepath
        except Exception:
            return None

    def _merge_link_entries(self, merged_links, links):
        for link, access_code in links:
            if link not in merged_links:
                merged_links[link] = access_code
                continue
            if merged_links[link] is None and access_code:
                merged_links[link] = access_code

    def process_post(
        self,
        post,
        callback=None,
        skip_existing=True,
        extract_archives=True,
        auto_extract_archives=True,
    ):
        if self._stop_event.is_set():
            return
        post_id = sanitize_filename(post.get("id", "unknown"))
        title = post.get("title", "No Title")
        published_date = post.get("publishedDatetime", "")
        if callback:
            callback(f"Processing: {title} ({post_id})")
        date_str = "unknown_date"
        if published_date:
            try:
                date_str = datetime.fromisoformat(published_date).strftime("%Y-%m-%d")
            except Exception:
                date_str = published_date[:10] if len(published_date) >= 10 else "unknown_date"
        folder_name = f"{date_str}_{sanitize_filename(title)}_{post_id}"
        post_dir = os.path.join(self.base_dir, folder_name)
        os.makedirs(post_dir, exist_ok=True)

        md_content = []
        md_content.append(f"# {title}")
        md_content.append(f"**ID:** {post_id}  ")
        md_content.append(f"**Date:** {published_date}  ")
        md_content.append(f"**Source:** {post.get('url', '')}  ")
        md_content.append("")

        for i, link in enumerate(post.get("enclosures", [])):
            if self._stop_event.is_set():
                return
            file_name = f"{post_id}_enclosure_{i}"
            local_path = os.path.join(post_dir, file_name)
            result = self.download_file(link, local_path, skip_existing=skip_existing)
            if result:
                md_content.append(f"- [Enclosure {i + 1}]({os.path.basename(result)})")
            else:
                md_content.append(f"- {link}")

        extracted_links = {}
        links = post.get("links", [])
        if links:
            extracted_links["Post Content"] = links

        download_candidates = {}
        self._merge_link_entries(download_candidates, extracted_links.get("Post Content", []))
        download_results = {}
        processed_resource_files = set()
        extracted_archive_dirs = set()

        while True:
            if self._stop_event.is_set():
                return

            if auto_extract_archives:
                new_dirs = self.extractor.extract_archives_recursively(
                    post_dir,
                    skip_existing=skip_existing,
                    should_stop=self._stop_event.is_set,
                )
                extracted_archive_dirs.update(new_dirs)

            new_resource_scanned = False
            if extract_archives:
                pdf_files, archive_files = self.extractor.collect_resource_files(post_dir)
                for pdf_file in pdf_files:
                    if self._stop_event.is_set():
                        return
                    if pdf_file in processed_resource_files:
                        continue
                    processed_resource_files.add(pdf_file)
                    new_resource_scanned = True
                    links_from_pdf = self.extractor.extract_pdf_links(os.path.join(post_dir, pdf_file))
                    if links_from_pdf:
                        extracted_links[pdf_file] = links_from_pdf
                        self._merge_link_entries(download_candidates, links_from_pdf)
                for archive_file in archive_files:
                    if self._stop_event.is_set():
                        return
                    if archive_file in processed_resource_files:
                        continue
                    processed_resource_files.add(archive_file)
                    new_resource_scanned = True
                    links_from_archive = self.extractor.process_archive(os.path.join(post_dir, archive_file))
                    if links_from_archive:
                        extracted_links[archive_file] = links_from_archive
                        self._merge_link_entries(download_candidates, links_from_archive)

            new_download_count = 0
            for link, access_code in list(download_candidates.items()):
                if self._stop_event.is_set():
                    return
                if link in download_results:
                    continue
                downloaded, reason = self.driver_manager.try_download_detail(link, post_dir)
                download_results[link] = (downloaded, reason, access_code)
                if downloaded:
                    new_download_count += 1

            if not extract_archives:
                break
            if new_download_count == 0 and not new_resource_scanned:
                break

        if extracted_archive_dirs:
            md_content.append("\n## Extracted Archives")
            for directory in sorted({os.path.relpath(d, post_dir) for d in extracted_archive_dirs}):
                md_content.append(f"- `{directory}`")

        if extracted_links:
            md_content.append("\n## Extracted Resources")
            for source_file, links_list in sorted(extracted_links.items()):
                md_content.append(f"\n### From `{source_file}`")
                for link, access_code in links_list:
                    downloaded, reason, final_access_code = download_results.get(
                        link,
                        (False, "not_attempted", access_code),
                    )
                    access_code_to_show = final_access_code if final_access_code is not None else access_code
                    if downloaded:
                        if access_code_to_show:
                            md_content.append(f"- [{link}]({link}) (提取码: {access_code_to_show}) (Downloaded)")
                        else:
                            md_content.append(f"- [{link}]({link}) (Downloaded)")
                    else:
                        if access_code_to_show:
                            md_content.append(f"- [{link}]({link}) (提取码: {access_code_to_show}) (Not downloaded: {reason})")
                        else:
                            md_content.append(f"- [{link}]({link}) (Not downloaded: {reason})")

        write_bilingual_readmes(
            post_dir=post_dir,
            markdown_text="\n".join(md_content),
            callback=callback,
        )

    def run(
        self,
        progress_callback=None,
        status_callback=None,
        max_workers=5,
        skip_existing=True,
        extract_archives=True,
        auto_extract_archives=True,
    ):
        self.clear_stop()
        posts = self.get_posts()
        total = len(posts)
        if status_callback:
            status_callback(f"Found {total} posts. Starting download...")
        if total == 0:
            if progress_callback:
                progress_callback(1.0)
            if status_callback:
                status_callback("No posts found. Check Patreon RSS URL.")
            return

        completed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_post = {
                executor.submit(
                    self.process_post,
                    post,
                    callback=status_callback,
                    skip_existing=skip_existing,
                    extract_archives=extract_archives,
                    auto_extract_archives=auto_extract_archives,
                ): post
                for post in posts
            }
            for future in concurrent.futures.as_completed(future_to_post):
                if self._stop_event.is_set():
                    for pending in future_to_post:
                        pending.cancel()
                    if status_callback:
                        status_callback("Download stopped by user.")
                    break
                try:
                    future.result()
                except Exception as e:
                    if status_callback:
                        status_callback(f"Error processing Patreon post: {e}")
                finally:
                    completed += 1
                    if progress_callback:
                        progress_callback(completed / total)

        if not self._stop_event.is_set():
            if progress_callback:
                progress_callback(1.0)
            if status_callback:
                status_callback("Download complete!")
