from datetime import datetime
import aiohttp
import asyncio
from typing import Optional, Dict


async def send_request_to_endpoint(api_url: str, payload: Dict) -> Optional[Dict]:
    try:
        connector = aiohttp.TCPConnector(ssl=False)

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10), connector=connector
        ) as session:
            async with session.get(api_url, json=payload) as response:
                if response.status != 200:
                    raise ValueError(
                        f"Failed to send request: {response.status}, {await response.text()}"
                    )
                return await response.json()

    except aiohttp.ClientError as e:
        raise ValueError(f"Network error occurred: {str(e)}")
    except Exception as e:
        raise ValueError(f"Unexpected error: {str(e)}")


async def main():
    print(1)
    api_url = "http://3.91.79.53:8000/מחשב-חזקת-שתי-ספרות"
    payload = {}

    try:
        print(3)
        for i in range(2, 100):
            payload["message"] = [2, i]
            a = await send_request_to_endpoint(api_url, payload)
            print(i)
            print(f"Response {i} ::: {a}")
    except ValueError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
