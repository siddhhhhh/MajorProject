import asyncio
import importlib.util

import httpx

spec = importlib.util.spec_from_file_location("ev", "agents/evidence_retriever.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


async def main() -> None:
    async with httpx.AsyncClient() as session:
        text = await module.fetch_full_text("https://www.reuters.com/sustainability/", session)
        print("LEN", len(text))
        print(repr(text[:260]))


if __name__ == "__main__":
    asyncio.run(main())
