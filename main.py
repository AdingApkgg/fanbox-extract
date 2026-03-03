import os
import sys
from dotenv import load_dotenv
from fanbox_extractor.downloader import FanboxDownloader
from fanbox_extractor.patreon_downloader import PatreonDownloader

if __name__ == "__main__":
    try:
        load_dotenv()
        args = sys.argv[1:]
        if args and args[0].lower() in {"fanbox", "patreon"}:
            platform = args[0].lower()
            args = args[1:]
        else:
            platform = "fanbox"

        if platform == "patreon":
            rss_url = args[0] if args else os.environ.get("PATREON_RSS_URL", "")
            if not rss_url:
                rss_url = input("Enter Patreon RSS URL: ").strip()
            creator_id = args[1] if len(args) > 1 else "patreon"
            downloader = PatreonDownloader(rss_url=rss_url, creator_id=creator_id)
            downloader.run()
            sys.exit(0)

        if args:
            sessid = args[0]
        else:
            sessid = os.environ.get("FANBOXSESSID")
            if not sessid:
                sessid = input("Enter FANBOXSESSID: ").strip()
        downloader = FanboxDownloader(sessid)
        creator_id = args[1] if len(args) > 1 else None
        if not creator_id:
            creator_id = downloader.select_creator()
        if not creator_id:
            print("No creator selected. Exit.")
            sys.exit(1)
        downloader.set_creator(creator_id)
        downloader.run()
    except Exception as e:
        print(f"Error: {e}")
