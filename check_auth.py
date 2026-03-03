import requests
import sys

def list_supporting_creators(sessid):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Origin': 'https://www.fanbox.cc',
        'Cookie': f'FANBOXSESSID={sessid}'
    }
    
    url = "https://api.fanbox.cc/plan.listSupporting"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if 'body' in data:
            creators = data['body']
            if not creators:
                print("No supporting creators found.")
                return []
            
            print(f"Found {len(creators)} supporting creators:")
            for creator in creators:
                creator_info = creator.get('creatorId', 'Unknown')
                title = creator.get('title', 'No Title')
                # The structure might be different, let's inspect one if we can or just try to print likely fields
                # Usually it's inside 'creatorId' or similar
                print(f" - {creator_info}: {title}")
            return creators
        else:
            print("Error: 'body' not found in response.")
            print(data)
            return []
            
    except Exception as e:
        print(f"Error fetching supporting creators: {e}")
        return []

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sessid = sys.argv[1]
    else:
        sessid = input("Enter FANBOXSESSID: ").strip()
        
    list_supporting_creators(sessid)
