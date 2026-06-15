import os
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

import asyncio
import uvicorn

async def main():
    config = uvicorn.Config("server:app", host="127.0.0.1", port=8002, log_level="info")
    server = uvicorn.Server(config)
    print("Starting server on 8002...")
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
