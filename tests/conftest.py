import os
import pytest
from viralpulse.db import get_conn, init_db

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", os.environ.get("DATABASE_URL", ""))

@pytest.fixture
def db():
    """Provide a test DB connection with clean tables."""
    if not TEST_DB_URL:
        pytest.skip("No DATABASE_URL set")
    init_db(TEST_DB_URL)
    conn = get_conn(TEST_DB_URL)
    conn.execute("DELETE FROM crawl_runs")
    conn.execute("DELETE FROM scores")
    conn.execute("DELETE FROM engagement")
    conn.execute("DELETE FROM posts")
    conn.execute("DELETE FROM topics")
    conn.commit()
    yield conn
    conn.close()
