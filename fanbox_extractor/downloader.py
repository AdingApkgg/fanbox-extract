import os
import requests
import concurrent.futures
import threading
from datetime import datetime
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .utils import sanitize_filename
from .extractor import LinkExtractor
from .drivers import DriverManager
from .markdown_i18n import write_bilingual_readmes

class FanboxDownloader:
    def __init__(self, sessid, creator_id=None):
        self.sessid = sessid
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Origin': 'https://www.fanbox.cc',
            'Cookie': f'FANBOXSESSID={sessid}'
        }
        self.api_url = "https://api.fanbox.cc"
        self.extractor = LinkExtractor()
        self.driver_manager = DriverManager()
        self.request_timeout = (10, 120)
        self._stop_event = threading.Event()
        self.session = self._build_session()
        
        if creator_id:
            self.creator_id = creator_id
        else:
            self.creator_id = None
            
        if self.creator_id:
            self.base_dir = os.path.join(os.getcwd(), 'downloads', self.creator_id)
            os.makedirs(self.base_dir, exist_ok=True)
            print(f"Download directory: {self.base_dir}")

    def _build_session(self):
        session = requests.Session()
        session.headers.update(self.headers)
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

    def fetch_supporting_creators(self):
        """Fetch supporting creators list."""
        url = f"{self.api_url}/plan.listSupporting"
        try:
            response = self.session.get(url, timeout=self.request_timeout)
            response.raise_for_status()
            data = response.json()
            return data.get('body', [])
        except Exception as e:
            print(f"Error fetching creators: {e}")
            return []

    def set_creator(self, creator_id):
        """Set the current creator and initialize download directory."""
        self.creator_id = creator_id
        self.base_dir = os.path.join(os.getcwd(), 'downloads', self.creator_id)
        os.makedirs(self.base_dir, exist_ok=True)
        print(f"Selected creator: {creator_id}")
        print(f"Download directory: {self.base_dir}")

    def select_creator(self):
        """Fetch supporting creators and ask user to select one."""
        url = f"{self.api_url}/plan.listSupporting"
        try:
            response = self.session.get(url, timeout=self.request_timeout)
            response.raise_for_status()
            data = response.json()
            
            creators = data.get('body', [])
            if not creators:
                print("No supporting creators found automatically.")
                return input("Please enter the Creator ID manually: ").strip()
            
            print(f"\nFound {len(creators)} supporting creators:")
            for i, creator in enumerate(creators):
                print(f"{i + 1}. {creator.get('creatorId')} ({creator.get('title', 'No Title')})")
            
            if len(creators) == 1:
                choice = input(f"\nSelect {creators[0]['creatorId']}? [Y/n]: ").lower()
                if choice in ('', 'y', 'yes'):
                    return creators[0]['creatorId']
            
            while True:
                try:
                    selection = input("\nEnter the number of the creator to download (or 'q' to quit): ")
                    if selection.lower() == 'q':
                        return None
                    idx = int(selection) - 1
                    if 0 <= idx < len(creators):
                        return creators[idx]['creatorId']
                except ValueError:
                    pass
                print("Invalid selection. Please try again.")
                
        except Exception as e:
            print(f"Error fetching creators: {e}")
            return input("Please enter the Creator ID manually: ").strip()

    def get_posts(self):
        """Fetch all posts from the creator."""
        posts = []
        
        # Step 1: Get pagination URLs
        paginate_url = f"{self.api_url}/post.paginateCreator?creatorId={self.creator_id}"
        print(f"Fetching pagination info from {paginate_url}")
        
        page_urls = []
        try:
            response = self.session.get(paginate_url, timeout=self.request_timeout)
            response.raise_for_status()
            data = response.json()
            page_urls = data.get('body', [])
        except Exception as e:
            print(f"Error fetching pagination: {e}")

        if not page_urls:
            print("No pagination URLs found. Switching to manual pagination.")
            next_url = f"{self.api_url}/post.listCreator?creatorId={self.creator_id}&limit=50"
            seen_post_ids = set()
            
            while next_url:
                if self._stop_event.is_set():
                    break
                print(f"Fetching list: {next_url}")
                try:
                    response = self.session.get(next_url, timeout=self.request_timeout)
                    response.raise_for_status()
                    data = response.json()
                    items = data.get('body', [])
                    
                    if not items:
                        break
                    
                    new_items = [p for p in items if p['id'] not in seen_post_ids]
                    if not new_items:
                        break
                        
                    posts.extend(new_items)
                    for p in new_items:
                        seen_post_ids.add(p['id'])
                    
                    last_post = items[-1]
                    last_date = last_post.get('publishedDatetime')
                    
                    if not last_date:
                        break
                    
                    next_url = f"{self.api_url}/post.listCreator?creatorId={self.creator_id}&limit=50&maxPublishedDatetime={last_date}"
                    
                except Exception as e:
                    print(f"Error in manual pagination: {e}")
                    break
            
            print(f"Manually found {len(posts)} posts.")
            # Sort posts by date (newest first)
            posts.sort(key=lambda x: x.get('publishedDatetime', ''), reverse=True)
            return posts

        print(f"Found {len(page_urls)} pages.")
        
        # Step 2: Fetch posts from each page concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(self._fetch_page, url): url for url in page_urls}
            
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    items = future.result()
                    if items:
                        posts.extend(items)
                except Exception as e:
                    print(f"Error fetching page {url}: {e}")
                    
        # Sort posts by date (newest first) to maintain order after concurrent fetch
        posts.sort(key=lambda x: x.get('publishedDatetime', ''), reverse=True)
                
        return posts

    def _fetch_page(self, url):
        """Helper to fetch a single page of posts."""
        try:
            response = self.session.get(url, timeout=self.request_timeout)
            response.raise_for_status()
            data = response.json()
            items = data.get('body', [])
            if not items: return []
            return items
        except Exception as e:
            # print(f"Error fetching page {url}: {e}")
            return []

    def download_file(self, url, filepath, skip_existing=True):
        """Download a single file."""
        if skip_existing and os.path.exists(filepath):
            return filepath

        try:
            if self._stop_event.is_set():
                return None
            response = self.session.get(url, stream=True, timeout=self.request_timeout)
            response.raise_for_status()
            
            if not os.path.splitext(filepath)[1]:
                content_type = response.headers.get('content-type', '')
                if 'video/mp4' in content_type:
                    filepath += '.mp4'
                elif 'image/jpeg' in content_type:
                    filepath += '.jpg'
                elif 'image/png' in content_type:
                    filepath += '.png'
                elif 'application/zip' in content_type:
                    filepath += '.zip'
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(filepath, 'wb') as f, tqdm(
                desc=os.path.basename(filepath),
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for data in response.iter_content(chunk_size=1024 * 64):
                    if self._stop_event.is_set():
                        return None
                    size = f.write(data)
                    bar.update(size)
                    
        except Exception as e:
            print(f"Failed to download {url}: {e}")
            return None
        
        return filepath

    def _merge_link_entries(self, merged_links, links):
        for link, access_code in links:
            if link not in merged_links:
                merged_links[link] = access_code
                continue
            if merged_links[link] is None and access_code:
                merged_links[link] = access_code

    def process_post(
        self,
        post_summary,
        callback=None,
        skip_existing=True,
        extract_archives=True,
        auto_extract_archives=True,
    ):
        """Extract content from a post by fetching its details first."""
        if self._stop_event.is_set():
            return
        post_id = post_summary.get('id')
        title = post_summary.get('title', 'No Title')
        
        published_date = post_summary.get('publishedDatetime', '')
        
        # Parse date for folder name
        date_str = "unknown_date"
        if published_date:
            try:
                dt = datetime.fromisoformat(published_date)
                date_str = dt.strftime('%Y-%m-%d')
            except ValueError:
                pass

        # Create Post Directory
        folder_name = f"{date_str}_{sanitize_filename(title)}_{post_id}"
        post_dir = os.path.join(self.base_dir, folder_name)
        os.makedirs(post_dir, exist_ok=True)

        msg = f"正在处理: {title} ({post_id})"
        if callback: callback(msg)
        else: print(msg)

        # Fetch detailed post info
        detail_url = f"{self.api_url}/post.info?postId={post_id}"
        try:
            response = self.session.get(detail_url, timeout=self.request_timeout)
            
            # Handle 403 specifically
            if response.status_code == 403:
                print(f"Skipping restricted post {post_id} (Access Denied/Forbidden)")
                # Optionally remove empty directory if created
                try:
                    os.rmdir(post_dir)
                except OSError:
                    pass # Directory not empty or other error
                return
            
            response.raise_for_status()
            data = response.json()
            post = data.get('body', {})
            if not post:
                print(f"No body found for post {post_id}")
                return
            
            # Check if body is None (e.g. restricted posts)
            if post.get('body') is None: 
                if post.get('isRestricted'):
                     print(f"Skipping restricted post {post_id} (Access Denied)")
                     try:
                        os.rmdir(post_dir)
                     except OSError:
                        pass
                return

            body = post.get('body', {}) # Now we know body is not None
            
        except Exception as e:
            print(f"Error fetching details for post {post_id}: {e}")
            return

        # --- Markdown Content Preparation ---
        md_content = []
        content_links = []
        md_content.append(f"# {title}")
        md_content.append(f"**ID:** {post_id}  ")
        md_content.append(f"**Date:** {published_date}  ")
        md_content.append(f"**Fee:** {post.get('feeRequired', 0)} Yen  ")
        md_content.append(f"**Tags:** {', '.join(post.get('tags', []))}\n")
        
        # Add Text Body
        if 'text' in body and body['text']:
            md_content.append("## Description")
            md_content.append(body['text'])
            md_content.append("\n")
            content_links.extend(self.extractor.extract_text_links(body['text']))

        # Handle different post types and collect downloads
        md_content.append("## Gallery")
        
        # Images
        if 'images' in body:
            for i, img in enumerate(body['images']):
                if self._stop_event.is_set():
                    return
                url = img.get('originalUrl')
                ext = os.path.splitext(url)[1]
                filename = f"{post_id}_img_{i}{ext}"
                filepath = os.path.join(post_dir, filename)
                final_path = self.download_file(url, filepath, skip_existing=skip_existing)
                if final_path:
                    final_name = os.path.basename(final_path)
                    md_content.append(f"![{final_name}]({final_name})")

        # Files (sometimes in 'files' or 'fileMap')
        if 'files' in body:
            md_content.append("\n## Files")
            for file in body['files']:
                if self._stop_event.is_set():
                    return
                url = file.get('url')
                name = file.get('name')
                ext = os.path.splitext(name)[1]
                filename = f"{post_id}_file_{name}"
                filepath = os.path.join(post_dir, filename)
                final_path = self.download_file(url, filepath, skip_existing=skip_existing)
                if final_path:
                    final_name = os.path.basename(final_path)
                    md_content.append(f"- [{name}]({final_name})")
        
        # File Map
        if 'fileMap' in body:
             md_content.append("\n## Files (Map)")
             for file_id, file in body['fileMap'].items():
                if self._stop_event.is_set():
                    return
                url = file.get('url')
                name = file.get('name')
                ext = os.path.splitext(name)[1]
                filename = f"{post_id}_file_{name}"
                filepath = os.path.join(post_dir, filename)
                final_path = self.download_file(url, filepath, skip_existing=skip_existing)
                if final_path:
                    final_name = os.path.basename(final_path)
                    md_content.append(f"- [{name}]({final_name})")
        
        # Blocks (Article type)
        if 'blocks' in body:
            md_content.append("\n## Article Content")
            for block in body['blocks']:
                if self._stop_event.is_set():
                    return
                btype = block.get('type')
                if btype == 'p':
                    text_value = block.get('text', '')
                    md_content.append(text_value)
                    content_links.extend(self.extractor.extract_text_links(text_value))
                    md_content.append("") # Newline
                elif btype == 'header':
                    text_value = block.get('text', '')
                    md_content.append(f"### {text_value}")
                    content_links.extend(self.extractor.extract_text_links(text_value))
                elif btype == 'quote':
                    text_value = block.get('text', '')
                    md_content.append(f"> {text_value}")
                    content_links.extend(self.extractor.extract_text_links(text_value))
                elif btype == 'image':
                    image_id = block.get('imageId')
                    if image_id and 'imageMap' in body and image_id in body['imageMap']:
                        img = body['imageMap'][image_id]
                        url = img.get('originalUrl')
                        ext = os.path.splitext(url)[1]
                        filename = f"{post_id}_block_{image_id}{ext}"
                        filepath = os.path.join(post_dir, filename)
                        final_path = self.download_file(url, filepath, skip_existing=skip_existing)
                        if final_path:
                            final_name = os.path.basename(final_path)
                            md_content.append(f"![{final_name}]({final_name})")
                elif btype == 'file':
                     file_id = block.get('fileId')
                     if file_id and 'fileMap' in body and file_id in body['fileMap']:
                        file = body['fileMap'][file_id]
                        url = file.get('url')
                        name = file.get('name')
                        ext = os.path.splitext(name)[1]
                        filename = f"{post_id}_block_{name}"
                        filepath = os.path.join(post_dir, filename)
                        final_path = self.download_file(url, filepath, skip_existing=skip_existing)
                        if final_path:
                            final_name = os.path.basename(final_path)
                            md_content.append(f"- [{name}]({final_name})")
                elif btype == 'embed': # Tweets etc
                    embed_id = block.get('embedId')
                    if embed_id and 'embedMap' in body and embed_id in body['embedMap']:
                        embed = body['embedMap'][embed_id]
                        embed_url = embed.get('contentUrl')
                        md_content.append(f"> **Embed:** [{embed.get('serviceProvider')}]({embed_url})")
                        normalized = self.extractor.normalize_url(embed_url or "")
                        if normalized:
                            content_links.append((normalized, None))
                elif btype == 'url_embed':
                    url_embed_id = block.get('urlEmbedId')
                    if url_embed_id and 'urlEmbedMap' in body and url_embed_id in body['urlEmbedMap']:
                        url_embed = body['urlEmbedMap'][url_embed_id]
                        embed_url = url_embed.get('url') or url_embed.get('contentUrl')
                        normalized = self.extractor.normalize_url(embed_url or "")
                        if normalized:
                            md_content.append(f"> **URL Embed:** [{normalized}]({normalized})")
                            content_links.append((normalized, None))
                elif btype == 'video':
                    video_id = block.get('videoId')
                    if video_id and 'videoMap' in body and video_id in body['videoMap']:
                        video = body['videoMap'][video_id]
                        video_url = video.get('url') or video.get('sourceUrl') or video.get('embedUrl')
                        normalized = self.extractor.normalize_url(video_url or "")
                        if normalized:
                            md_content.append(f"> **Video:** [{normalized}]({normalized})")
                            content_links.append((normalized, None))
                elif block.get('text'):
                    text_value = block.get('text', '')
                    md_content.append(text_value)
                    content_links.extend(self.extractor.extract_text_links(text_value))

        extracted_links = {}
        merged_content_codes = {}
        ordered_content_urls = []
        for link, access_code in content_links:
            if link not in merged_content_codes:
                ordered_content_urls.append(link)
            self._merge_link_entries(merged_content_codes, [(link, access_code)])
        if ordered_content_urls:
            extracted_links["Post Content"] = [(url, merged_content_codes[url]) for url in ordered_content_urls]

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
                if new_dirs:
                    msg = f"  -> 解压了 {len(new_dirs)} 个归档文件"
                    if callback: callback(msg)
                    else: print(msg)
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
                    filepath = os.path.join(post_dir, pdf_file)
                    
                    msg = f"  -> 正在扫描 PDF: {os.path.basename(pdf_file)}"
                    if callback: callback(msg)
                    else: print(msg)
                    
                    links = self.extractor.extract_pdf_links(filepath)
                    if links:
                        msg = f"     发现 {len(links)} 个链接"
                        if callback: callback(msg)
                        else: print(msg)
                        extracted_links[pdf_file] = links
                        self._merge_link_entries(download_candidates, links)

                for archive_file in archive_files:
                    if self._stop_event.is_set():
                        return
                    if archive_file in processed_resource_files:
                        continue
                    processed_resource_files.add(archive_file)
                    new_resource_scanned = True
                    filepath = os.path.join(post_dir, archive_file)
                    
                    msg = f"  -> 正在扫描压缩包: {os.path.basename(archive_file)}"
                    if callback: callback(msg)
                    else: print(msg)
                    
                    links = self.extractor.process_archive(filepath)
                    if links:
                        msg = f"     发现 {len(links)} 个链接"
                        if callback: callback(msg)
                        else: print(msg)
                        extracted_links[archive_file] = links
                        self._merge_link_entries(download_candidates, links)

            new_download_count = 0
            for link, access_code in list(download_candidates.items()):
                if self._stop_event.is_set():
                    return
                if link in download_results:
                    continue
                
                msg = f"  -> 尝试下载外部链接: {link}"
                if callback: callback(msg)
                else: print(msg)
                
                downloaded, reason = self.driver_manager.try_download_detail(link, post_dir)
                download_results[link] = (downloaded, reason, access_code)
                if downloaded:
                    msg = f"     下载成功"
                    if callback: callback(msg)
                    else: print(msg)
                    new_download_count += 1
                else:
                    # Optional: Log failure reason if needed, but keep it clean for now
                    pass

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
            for source_file, links in sorted(extracted_links.items()):
                if self._stop_event.is_set():
                    return
                md_content.append(f"\n### From `{source_file}`")
                for link, access_code in links:
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
            
        # Clean up processed archives if links were extracted (Optional, commented out for safety)
        # for archive_file in extracted_links.keys():
        #     try:
        #         os.remove(os.path.join(post_dir, archive_file))
        #     except OSError:
        #         pass

    def run(
        self,
        progress_callback=None,
        status_callback=None,
        max_workers=5,
        skip_existing=True,
        extract_archives=True,
        auto_extract_archives=True,
    ):
        if not self.creator_id:
            print("No creator selected.")
            return

        self.clear_stop()
        posts = self.get_posts()
        print(f"找到 {len(posts)} 篇帖子。")
        if status_callback: status_callback(f"找到 {len(posts)} 篇帖子。开始下载...")
        
        total = len(posts)
        if total == 0:
            if progress_callback: progress_callback(1.0)
            if status_callback: status_callback("没有找到帖子。")
            return
        completed = 0
        
        # Process posts sequentially to ensure full resource extraction for each
        for i, post in enumerate(posts):
            if self._stop_event.is_set():
                if status_callback: status_callback("用户停止下载。")
                break
                
            try:
                self.process_post(
                    post,
                    callback=status_callback,
                    skip_existing=skip_existing,
                    extract_archives=extract_archives,
                    auto_extract_archives=auto_extract_archives,
                )
            except Exception as e:
                msg = f"处理帖子 {post.get('id')} 时出错: {e}"
                print(msg)
                if status_callback: status_callback(msg)
            finally:
                completed += 1
                if progress_callback: progress_callback(completed / total)
        
        if not self._stop_event.is_set():
            if progress_callback: progress_callback(1.0)
            if status_callback: status_callback("下载完成！")
