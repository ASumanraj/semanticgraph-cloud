import asyncio
import sys

if sys.platform == "win32":
    # psycopg async requires SelectorEventLoop on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import logging

import pytest


@pytest.fixture(autouse=True)
def _ensure_loggers_enabled():
    yield
    logging.getLogger("semanticgraph").disabled = False
