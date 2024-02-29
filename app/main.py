from fastapi import Depends, FastAPI
from src.core.services.diff_service import generate_diff
from src.domain.models import models, schema
from src.infrastructure.db.database import SessionLocal, engine
from src.infrastructure.utility import handle_errors
from sqlalchemy.orm import Session

models.Base.metadata.create_all(bind=engine)
app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/generate-diff")
@handle_errors
def generate_diff_endpoint(
    input_data: schema.InputDataCreate, generate_diff_db: Session = Depends(get_db)
):
    return generate_diff(input_data, generate_diff_db)
