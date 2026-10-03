import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

engine = create_engine(os.environ["DATABASE_URL"])
SessionLocal = sessionmaker(bind=engine)


def get_db():
    """Give each request its own session, closed when the request ends."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
