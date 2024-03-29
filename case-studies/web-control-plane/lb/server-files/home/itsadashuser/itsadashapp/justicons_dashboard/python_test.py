import asyncio
import time

import aiohttp


async def fetch(session, url):
    async with session.get(url) as response:
        return await response.json()


async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, "http://justicons.org/json") for _ in range(1000)]
        results = await asyncio.gather(*tasks)
        # If you want to print all results, uncomment the next line
        print(results)


if __name__ == "__main__":
    start = time.time()
    asyncio.run(main())
    end = time.time()
    print(f"Time taken: {end - start} seconds")
