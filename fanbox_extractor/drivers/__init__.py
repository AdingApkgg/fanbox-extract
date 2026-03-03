import os
import shutil
from .google_drive import GoogleDriveDriver
from .mega import MegaDriver

class DriverManager:
    def __init__(self):
        self.google_driver = GoogleDriveDriver()
        self.mega_driver = MegaDriver()

    def try_download(self, url, output_dir):
        """Try to download a URL using available drivers."""
        
        # Google Drive
        if self.google_driver.is_supported(url):
            try:
                print(f"Detected Google Drive link: {url}")
                # We let gdown infer filename by passing output=None first (downloads to cwd)
                # Or pass output_dir/filename if we knew.
                # Since we don't know the name, we let gdown figure it out.
                # BUT, gdown(output=None) returns the filename.
                
                # However, downloading to cwd and moving is safer.
                filename = self.google_driver.download(url, None)
                if filename and os.path.exists(filename):
                    final_path = os.path.join(output_dir, os.path.basename(filename))
                    shutil.move(filename, final_path)
                    print(f"Moved to {final_path}")
                    return final_path
            except Exception as e:
                print(f"Google Drive download error: {e}")
                return False
                
        # Mega
        elif self.mega_driver.is_supported(url):
            try:
                print(f"Detected Mega link: {url}")
                # Mega driver downloads to output_dir directly
                success = self.mega_driver.download(url, output_dir)
                return success
            except Exception as e:
                print(f"Mega download error: {e}")
                return False

        return False
