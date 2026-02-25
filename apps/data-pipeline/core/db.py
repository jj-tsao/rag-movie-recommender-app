from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url

from core.config import DATABASE_URL


def get_engine() -> Engine:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set")
    url = make_url(DATABASE_URL)
    # Prefer psycopg (v3, self-contained wheels) to avoid local libpq issues
    if url.drivername in ("postgresql", "postgresql+psycopg2"):
        url = url.set(drivername="postgresql+psycopg")
    return create_engine(url)