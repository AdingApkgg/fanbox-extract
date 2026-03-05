import sys
import json
import os
import io
from contextlib import redirect_stdout

# Redirect stdout to stderr to avoid corrupting JSON output
sys.stdout = sys.stderr

# Ensure we can import from fanbox_extractor package even if running from root
sys.path.append(os.getcwd())

try:
    from fanbox_extractor.downloader import FanboxDownloader
    from fanbox_extractor.web_ui_core import build_tree_nodes, resolve_download_root
except ImportError:
    # Fallback for direct execution if sys.path setup failed
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from fanbox_extractor.downloader import FanboxDownloader
    from fanbox_extractor.web_ui_core import build_tree_nodes, resolve_download_root

def handle_command(command, payload):
    if command == "list_creators":
        sessid = payload.get("sessid")
        if not sessid:
            return {"error": "Missing sessid"}
        
        try:
            f = io.StringIO()
            with redirect_stdout(f):
                downloader = FanboxDownloader(sessid)
                creators = downloader.fetch_supporting_creators()
            return {"success": True, "creators": creators}
        except Exception as e:
            return {"success": False, "error": str(e)}

    elif command == "start_download":
        sessid = payload.get("sessid")
        creator_id = payload.get("creator_id")
        if not sessid or not creator_id:
            return {"error": "Missing sessid or creator_id"}
            
        try:
            f = io.StringIO()
            with redirect_stdout(f):
                downloader = FanboxDownloader(sessid)
                # Just verifying we can init - actual download is spawned separately
            return {"success": True, "message": "Downloader initialized"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    elif command == "get_files":
        path = payload.get("path", "")
        # Use current working directory to resolve downloads folder
        # This assumes the script is run from project root
        root = resolve_download_root(os.getcwd())
        
        target_path = root
        if path:
            target_path = os.path.join(root, path)
            
        # Security check to prevent directory traversal
        try:
            abs_root = os.path.abspath(root)
            abs_target = os.path.abspath(target_path)
            if not abs_target.startswith(abs_root):
                 return {"error": "Access denied", "files": []}
            
            # Ensure root exists
            if not os.path.exists(abs_target):
                os.makedirs(abs_target, exist_ok=True)
                
            files = build_tree_nodes(abs_target)
            return {"success": True, "files": files}
        except Exception as e:
            return {"success": False, "error": str(e), "files": []}

    elif command == "test":
        return {"success": True, "message": "Bridge is working", "payload_received": payload}

    return {"error": f"Unknown command: {command}"}

if __name__ == "__main__":
    original_stdout = sys.__stdout__
    
    try:
        if len(sys.argv) < 2:
            print(json.dumps({"error": "No command provided"}), file=original_stdout)
            sys.exit(1)
            
        command = sys.argv[1]
        payload = {}
        if len(sys.argv) > 2:
            try:
                payload = json.loads(sys.argv[2])
            except json.JSONDecodeError:
                print(json.dumps({"error": "Invalid JSON payload"}), file=original_stdout)
                sys.exit(1)
                
        result = handle_command(command, payload)
        print(json.dumps(result), file=original_stdout)
        
    except Exception as e:
        print(json.dumps({"error": f"Bridge error: {str(e)}"}), file=original_stdout)
        sys.exit(1)
