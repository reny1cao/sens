import asyncio
import aiohttp
import json

async def test_query():
    session_id = "session-1748611713800-91hvkgwli"
    
    # First, let's try a simple query to see the data structure
    query = "Show me the first 5 rows from annual-enterprise-survey-2023-financial-year-provisional table"
    
    url = "http://localhost:8000/api/nl2sql/session/query"
    headers = {
        "Content-Type": "application/json",
        "X-Session-Id": session_id
    }
    
    data = {
        "question": query,
        "session_id": session_id
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as response:
            result = await response.json()
            print(f"Status: {response.status}")
            print(f"Result: {json.dumps(result, indent=2)}")

asyncio.run(test_query())
