import gzip
import requests
from openai import OpenAI
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from supafast import crud, models, schema
from supafast.database import SessionLocal, engine
import os
import time
from functools import wraps


# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create tables if they do not exist
models.Base.metadata.create_all(bind=engine)

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# Function to handle API errors and retry
def handle_api_errors(func):
    """
    A decorator function to handle API errors and retry requests.

    Args:
        func (function): The function to be decorated.

    Returns:
        function: The wrapped function.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        retries = 0
        while retries < max_retries:
            try:
                return func(*args, **kwargs)
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                if status_code == 401:
                    raise HTTPException(
                        status_code=401, detail="Invalid Authentication"
                    )
                elif status_code == 429:
                    if "Rate limit reached" in e.response.text:
                        time.sleep(60)  # Wait for 60 seconds before retrying
                    else:
                        time.sleep(5)  # Wait for 5 seconds before retrying
                elif status_code == 500 or status_code == 503:
                    time.sleep(10)  # Wait for 10 seconds before retrying
                else:
                    print("An unexpected API error occurred: %s", e)
                    raise HTTPException(status_code=500, detail="Internal server error")
                retries += 1
        raise HTTPException(
            status_code=500, detail="Max retries reached. Unable to process request."
        )

    return wrapper


# Store input data in the database
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


@app.post("/generate-diff")
@handle_api_errors
def generate_diff(
    input_data: schema.InputDataCreate, generate_diff_db: Session = Depends(get_db)
):
    """
    Generate diff based on input data and store it in the database.

    Args:
        input_data (schema.InputDataCreate): The input data for generating the diff.
        generate_diff_db (Session): The database session.

    Returns:
         The final diff.
    """
    # Validate input
    if not input_data.github_url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Invalid GitHub repo URL")

    # Fetch content of the GitHub repository
    github_api_url = f"{input_data.github_url.rstrip('/')}/archive/master.tar.gz"
    response = requests.get(github_api_url)
    if response.status_code != 200:
        raise HTTPException(
            status_code=404, detail="Failed to fetch GitHub repository content"
        )

    # Extract content from the response
    content = response.content  # This would be the content of the repository
    decompressed_data = gzip.decompress(content)
    repository_content = decompressed_data.decode("utf-8")

    # generate primary response to the prompt
    primary_response = generate_primary_response(input_data.prompt, repository_content)

    # generate reflection response to prompt using primary response as input
    reflection_response = generate_relfection_response(
        input_data.prompt, primary_response, repository_content
    )

    # genereate primary diff to the final/reflection response
    primary_diff = generate_primary_diff(
        input_data.prompt, repository_content, reflection_response
    )

    # generate final diff with reflection on the primary diff
    final_diff = generate_final_diff(
        input_data.prompt, repository_content, primary_diff
    )

    # Store input(prompt and github url) and unified diff in supabase DB
    input_id = store_input_data(input_data, generate_diff_db)
    store_unified_diff(final_diff, input_id, generate_diff_db)

    return final_diff


@handle_api_errors
def generate_primary_response(prompt, repository_content):
    """
    Generate the primary response to a given prompt and repository content.

    Args:
        prompt (str): The prompt for the model.
        repository_content (str): The content of the repository.

    Returns:
        str: The generated primary response.
    """

    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You must provide modified files\
                    as a solution to the user's prompt. Provide full solution.",
            },
            {
                "role": "user",
                "content": f'prompt: {prompt}Ignore pax_global_header \
                    and README.md\n Change files in the repository to solve\
                    the task in the prompt. Also clearly state original and\
                    changed file names.\
                    \n\nrepository: \n"""{repository_content} \n""" ',
            },
        ],
        temperature=0,
        max_tokens=1024,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    return completion.choices[0].message.content


@handle_api_errors
def generate_relfection_response(initial_prompt, initial_response, repository_content):
    """
    Generate the reflection response based on initial prompt, initial response,
    and repository content.

    Args:
        initial_prompt (str): The initial prompt.
        initial_response (str): The initial response generated by the model.
        repository_content (str): The content of the repository.

    Returns:
        str: The generated reflection response.
    """
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "The assistant must provide modified files\
                      as solution to the user's first prompt which is delimited\
                        by triple quotes. Simply responding that you verified it\
                        or suggesting instructions does not work. \
                        Provide full solution.",
            },
            {
                "role": "user",
                "content": f'prompt:\
                      """\n{initial_prompt}\
                        Ignore pax_global_header and README.md\
                        \n Also clearly state original and changed file names.\
                        \n"""\
                        \n\nrepository: \n{repository_content}',
            },
            {"role": "assistant", "content": f"{initial_response}"},
            {
                "role": "user",
                "content": "Please provide the correct solution after evaluating\
                            the model's response. First work out your own solution \
                            to the prompt. Then compare to the previous model's\
                            solution. Please provide the actual solution to the user's \
                            prompt as your answer. Simply telling me that the \
                            model's solution is correct will not work for me.",
            },
        ],
        temperature=0.8,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    return completion.choices[0].message.content


@handle_api_errors
def generate_primary_diff(prompt, repository_content, prompt_response):
    """
    Generate the primary unified diff based on prompt, repository content,
    and final response to prompt after reflection.

    Args:
        prompt (str): The prompt for the model.
        repository_content (str): The content of the repository.
        prompt_response (str): The response generated by the model to the prompt.

    Returns:
        str: The generated primary diff.
    """
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "user",
                "content": f'prompt: {prompt}\
                    \nAlso clearly state original and changed file names.\
                    \n\nrepository: \n"""{repository_content} \n""" ',
            },
            {"role": "assistant", "content": f"{prompt_response}"},
            {
                "role": "user",
                "content": "Using the modified files provided above,\
                    please generate a unified diff (plus and minus signs) \
                    in the traditional format where each line of the original file \
                    from the repository delimited in triple quotes \
                        above is followed by the corresponding\
                    modified line from the files in the model's response.\
                    Make sure each file in the the diff contains \
                    the correct original repository code.",
            },
        ],
        temperature=0,
        max_tokens=1024,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    return completion.choices[0].message.content


@handle_api_errors
def generate_final_diff(prompt, repository_content, primary_diff):
    """
    Generate the final diff based on prompt, repository content, and primary diff.

    Args:
        prompt (str): The prompt for the model.
        repository_content (str): The content of the repository.
        primary_diff (str): The primary diff generated by the model.

    Returns:
        str: The generated final diff.
    """
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You must provide only the final diff. \
                    The diff in your response should contain the original \
                        repository code followed by modified code line by line.",
            },
            {
                "role": "user",
                "content": f'prompt:\
                      """\n{prompt}\n"""\
                        \n\nrepository: \n{repository_content} \
                        Task: Please generate a unified diff \
                    (plus and minus signs) for all the modified files in the\
                    traditional format where each line of the original file \
                    from the repository above is followed by the corresponding\
                    modified line. Make sure each file in the the diff contains \
                    the original repository code.',
            },
            {"role": "assistant", "content": f"{primary_diff}"},
            {
                "role": "user",
                "content": "Are you sure about the model's diff? \
                Please check that each of the different files in the \
                model's diff is comparing the original code from the \
                repository provided above and the modified code in the\
                model's diff. Please provide the final, correct diff as your response. \
                Simply verifying the previous model's diff is not enough.",
            },
        ],
        temperature=0,
        max_tokens=1024,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    return completion.choices[0].message.content
