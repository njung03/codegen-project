from sqlalchemy.orm import Session

from ...domain.models import models
from ...domain.models import schema


def create_input_data(db: Session, inputdata: schema.InputDataCreate):
    try:
        db_inputdata = models.InputData(**inputdata.model_dump())
        db.add(db_inputdata)
        db.commit()
        db.refresh(db_inputdata)
        return db_inputdata
    except Exception as e:
        raise ("failed to insert input: ", e)


def create_output_data(db: Session, outputdata: schema.OutputDiffCreate, input_id: int):
    try:
        db_outputdata = models.OutputDiff(
            **outputdata.model_dump(), input_data_id=input_id
        )
        db.add(db_outputdata)
        db.commit()
        db.refresh(db_outputdata)
        return db_outputdata
    except Exception as e:
        raise ("failed to insert output diff: ", e)
