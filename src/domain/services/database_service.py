from fastapi import Depends, HTTPException
from src.infrastructure.repositories import crud
from src.domain.models import schema

from src.infrastructure.session.database import get_db


class DatabaseService:
    def __init__(self):
        self.generate_diff_db = Depends(get_db())

    def store_input_data(self, input_data: schema.InputDataCreate):
        """
        Store input data in the database.

        Args:
            input_data (schema.InputDataCreate): The input data to be stored.
            generate_diff_db (Session): The database session.

        Returns:
            int: The ID of the stored input data.
        """
        try:
            # Create input data in the database
            db_inputdata = crud.create_input_data(
                db=self.generate_diff_db, inputdata=input_data
            )
            return db_inputdata.id
        except Exception as e:
            # Rollback the transaction in case of an error
            self.generate_diff_db.rollback()
            print("Error in storing input data: %s", e)
            raise HTTPException(status_code=500, detail="Internal server error")

    # Store unified diff in the database
    def store_unified_diff(self, diff: str, input_id: int):
        """
        Store unified diff in the database.

        Args:
            diff (str): The unified diff to be stored.
            input_id (int): The ID of the corresponding input data.
            generate_diff_db (Session): The database session.
        """
        try:
            # Create output data (diff) in the database and link it to the input data
            outputdiff_data = schema.OutputDiffCreate(diff=diff)
            _ = crud.create_output_data(
                db=self.generate_diff_db, outputdata=outputdiff_data, input_id=input_id
            )
        except Exception as e:
            # Rollback the transaction in case of an error
            self.generate_diff_db.rollback()
            print("Error in storing unified diff: %s", e)
            raise HTTPException(status_code=500, detail="Internal server error")
