import json
from src.domain.models import schema
from src.domain.services.database_service import DatabaseService
from src.infrastructure.services.github_service import (
    generate_full_diff_helper,
    get_repository_content,
)
from src.infrastructure.services.openai_service import OpenAISerivce


def generate_diff(input_data: schema.InputDataCreate):
    """
    Generate diff based on input data and store it in the database.

    Args:
        input_data (schema.InputDataCreate): The input data for generating the diff.
        generate_diff_db (Session): The database session.

    Returns:
         The final diff.
    """
    repository_content = get_repository_content(input_data.github_url)

    openai_client = OpenAISerivce()
    # generate primary response to the prompt
    primary_response = openai_client.generate_primary_response(
        input_data.prompt, repository_content
    )

    # generate reflection response to prompt using primary response as input
    reflection_response = openai_client.generate_reflection_response(
        input_data.prompt, primary_response, repository_content
    )

    reflection_response_json = json.loads(reflection_response)

    # Get unified diff using git diff
    final_unified_diff = generate_full_diff_helper(
        reflection_response_json, input_data.github_url
    )

    db = DatabaseService()
    # Store input and unified diff in database
    id = db.store_input_data(input_data)
    db.store_unified_diff(final_unified_diff, id)
    return final_unified_diff
