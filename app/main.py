import fastapi
from src.core.services.diff_service import generate_diff
from src.domain.models import models, schema
from src.infrastructure.session.database import engine
from src.infrastructure.utility import handle_errors

models.Base.metadata.create_all(bind=engine)
app = fastapi()


@app.post("/generate-diff")
@handle_errors
def generate_diff_endpoint(input_data: schema.InputDataCreate):
    return generate_diff(input_data)
