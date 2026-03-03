import os
import shutil
import tempfile
import zipfile
import tarfile
import rarfile
from pypdf import PdfReader
from .utils import extract_links_from_text

class LinkExtractor:
    def extract_pdf_links(self, filepath):
        """Extract links from a PDF file."""
        links = set()
        try:
            reader = PdfReader(filepath)
            for page in reader.pages:
                # Method 1: Extract from Annotations
                if "/Annots" in page:
                    for annot in page["/Annots"]:
                        obj = annot.get_object()
                        if "/A" in obj and "/URI" in obj["/A"]:
                            uri = obj["/A"]["/URI"]
                            if isinstance(uri, str) and (uri.startswith("http") or uri.startswith("https")):
                                links.add(uri)
                
                # Method 2: Extract from Text
                text = page.extract_text()
                for link in extract_links_from_text(text):
                    links.add(link)

        except Exception as e:
            print(f"Error extracting links from PDF {os.path.basename(filepath)}: {e}")
        
        return sorted(list(links))

    def process_archive(self, filepath):
        """Extract links from text/PDF files inside archives (zip, rar, tar)."""
        links = set()
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Determine archive type and extract relevant files
            files_to_check = []
            
            if zipfile.is_zipfile(filepath):
                with zipfile.ZipFile(filepath, 'r') as zf:
                    for name in zf.namelist():
                        if name.lower().endswith(('.txt', '.url', '.webloc', '.pdf')):
                            zf.extract(name, temp_dir)
                            files_to_check.append(os.path.join(temp_dir, name))
            
            elif tarfile.is_tarfile(filepath):
                with tarfile.open(filepath, 'r') as tf:
                    for member in tf.getmembers():
                        if member.name.lower().endswith(('.txt', '.url', '.webloc', '.pdf')):
                            tf.extract(member, temp_dir)
                            files_to_check.append(os.path.join(temp_dir, member.name))
                            
            elif rarfile.is_rarfile(filepath):
                with rarfile.RarFile(filepath, 'r') as rf:
                     for name in rf.namelist():
                        if name.lower().endswith(('.txt', '.url', '.webloc', '.pdf')):
                            rf.extract(name, temp_dir)
                            files_to_check.append(os.path.join(temp_dir, name))

            # Process extracted files
            for fpath in files_to_check:
                try:
                    if fpath.lower().endswith('.pdf'):
                        links.update(self.extract_pdf_links(fpath))
                    else:
                        # Try reading as text
                        try:
                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                links.update(extract_links_from_text(content))
                        except Exception:
                            pass
                except Exception as e:
                    print(f"Error processing file inside archive {fpath}: {e}")

        except Exception as e:
            # print(f"Error processing archive {os.path.basename(filepath)}: {e}")
            pass
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            
        return sorted(list(links))
