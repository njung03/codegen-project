import json

from fastapi import HTTPException
from src.domain.models import schema
from src.infrastructure.services.github_service import (
    generate_full_diff_helper,
    get_repository_content,
)
from src.infrastructure.services.openai_service import (
    generate_primary_response,
    generate_reflection_response,
)
from src.infrastructure.repositories import crud
from sqlalchemy.orm import Session


def store_input_data(input_data: schema.InputDataCreate, generate_diff_db: Session):
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
        db_inputdata = crud.create_input_data(db=generate_diff_db, inputdata=input_data)
        return db_inputdata.id
    except Exception as e:
        # Rollback the transaction in case of an error
        generate_diff_db.rollback()
        print("Error in storing input data: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


# Store unified diff in the database
def store_unified_diff(diff: str, input_id: int, generate_diff_db: Session):
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
            db=generate_diff_db, outputdata=outputdiff_data, input_id=input_id
        )
    except Exception as e:
        # Rollback the transaction in case of an error
        generate_diff_db.rollback()
        print("Error in storing unified diff: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


def generate_diff(input_data: schema.InputDataCreate, db: Session):
    """
    Generate diff based on input data and store it in the database.

    Args:
        input_data (schema.InputDataCreate): The input data for generating the diff.
        generate_diff_db (Session): The database session.

    Returns:
         The final diff.
    """
    repository_content = get_repository_content(input_data.github_url)

    # generate primary response to the prompt
    primary_response = generate_primary_response(input_data.prompt, repository_content)

    # generate reflection response to prompt using primary response as input
    reflection_response = generate_reflection_response(
        input_data.prompt, primary_response, repository_content
    )

    reflection_response_json = json.loads(reflection_response)

    # Get unified diff using git diff
    final_unified_diff = generate_full_diff_helper(
        reflection_response_json, input_data.github_url
    )
    # Store input and unified diff in database
    id = store_input_data(input_data, db)
    store_unified_diff(final_unified_diff, id, db)
    return final_unified_diff
