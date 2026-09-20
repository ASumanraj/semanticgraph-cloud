import sys
import asyncio

if sys.platform == "win32":
    # psycopg async requires SelectorEventLoop on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
