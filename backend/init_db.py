from .database import Base,engine
from . import models
if __name__=="__main__":
    if engine is None: raise SystemExit("Set DATABASE_URL to a MySQL database first.")
    Base.metadata.create_all(bind=engine)
    print("MySQL tables created.")
