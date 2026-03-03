import os
import sys
from fanbox_extractor.downloader import FanboxDownloader

if __name__ == "__main__":
    if len(sys.argv) > 1:
        SESSID = sys.argv[1]
    else:
        # Default or prompt
        SESSID = os.environ.get("FANBOXSESSID")
        if not SESSID:
             SESSID = input("Enter FANBOXSESSID: ").strip()

    try:
        downloader = FanboxDownloader(SESSID)
        downloader.run()
    except Exception as e:
        print(f"Error: {e}")
