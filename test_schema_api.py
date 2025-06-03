import requests
import traceback

try:
    response = requests.get('http://localhost:8000/api/schema/visualize')
    print(f"Status Code: {response.status_code}")
    print(f"Content Type: {response.headers.get('content-type')}")
    print(f"Raw Response: {response.text[:500]}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Tables found: {len(data.get('entities', []))}")
    else:
        print(f"Error response: {response.text}")
except Exception as e:
    print(f"Exception: {type(e).__name__}: {e}")
    traceback.print_exc()