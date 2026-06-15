import os
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""

import asyncio
import uvicorn

async def main():
    config = uvicorn.Config("server:app", host="127.0.0.1", port=8001, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

asyncio.run(main())
