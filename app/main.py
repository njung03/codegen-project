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
import json
import tarfile
from io import BytesIO
import tempfile
import subprocess
import shutil
from urllib.parse import urlparse, parse_qs


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


# Function to handle API and non-API errors and retry
def handle_errors(func):
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
            except Exception as e:
                print("Unexpected non-API error occured:", e)
                retries += 1
                raise HTTPException(status_code=500, detail="Internal server error")
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


def get_repository_content(github_url):
    # Validate input
    if not github_url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Invalid GitHub repo URL")

    # Fetch content of the GitHub repository
    github_api_url = f"{github_url.rstrip('/')}/archive/master.tar.gz"
    response = requests.get(github_api_url)
    if response.status_code != 200:
        raise HTTPException(
            status_code=404, detail="Failed to fetch GitHub repository content"
        )

    # Extract content from the response
    content = response.content  # This would be the content of the repository
    decompressed_data = gzip.decompress(content)
    repository_content = decompressed_data.decode("utf-8")
    return repository_content


def get_basename(path):
    return "/".join(path.split("/")[1:])


def generate_full_diff_helper(file_mappings, repo_url):
    try:
        # Clone the repository
        repo_dir = tempfile.mkdtemp()
        subprocess.run(["git", "clone", repo_url, repo_dir], check=True)

        for original_file_path, mapping in file_mappings.items():
            modified_content = mapping["modified_content"]
            modified_file_path = mapping["modified_path"]

            # get base name
            modified_file_path = get_basename(modified_file_path)
            original_file_path = get_basename(original_file_path)
            # Write modified content to a temporary file
            modified_temp_file_path = os.path.join(
                tempfile.mkdtemp(), modified_file_path
            )
            with open(modified_temp_file_path, "w") as f:
                f.write(modified_content)

            # Rename the original file to match the modified file path
            original_file_abs_path = os.path.join(repo_dir, original_file_path)
            modified_file_abs_path = os.path.join(repo_dir, modified_file_path)
            os.rename(original_file_abs_path, modified_file_abs_path)

            # Overwrite the original file with modified content
            shutil.copyfile(modified_temp_file_path, modified_file_abs_path)

        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        diff_output = subprocess.check_output(
            ["git", "diff", "--unified=5", "--cached"],
            cwd=repo_dir,
            universal_newlines=True,
        )
        return diff_output
    except Exception as e:
        print("error in generating unified diff:", e)
    finally:
        # Check if the temporary directory exists and remove it if necessary
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir, ignore_errors=True)
            print("Temporary directory has been successfully removed.")
        else:
            print("Temporary directory does not exist.")


@app.post("/generate-diff")
@handle_errors
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
    id = store_input_data(input_data, generate_diff_db)
    store_unified_diff(final_unified_diff, id, generate_diff_db)
    return final_unified_diff


@handle_errors
def generate_primary_response(prompt, repository_content):
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": 'You will be provided with a prompt and repository \
                    Please modify the files to accomplish \
                    the issue or task in the prompt. Answer in JSON format as \
                    provided below.\
                    \nDesired format:\
                    \n{"src/main_original.py": \
                    {"modified_path": "src/main.py",\
                    "modified_content":"# Modified content of main.py"},\
                    "src/utils_original.py":\
                    {"modified_path": "src/utils.py",\
                    "modified_content": "# Modified content of utils.py"}\n}\n\n',
            },
            {
                "role": "user",
                "content": f"Prompt: {prompt}\n\nrepository: {repository_content}",
            },
        ],
        max_tokens=700,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    return completion.choices[0].message.content


@handle_errors
def generate_reflection_response(prompt, repository_content, primary_response):
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": 'First work out your own solution to the \
                    prompt and repository. The repository is in JSON format \
                    with the key as the file path and the value as the file content.\
                    Then compare your solution to the user\'s solution and \
                    evaluate if the user\'s solution is correct or not. \
                    Don\'t decide if the user\'s solution is correct until\
                    you have done the problem yourself. \
                    You will provide the final, correct answer in JSON format as provided below.\
                    \nDesired format:\
                    \n{"src/main_original.py": \
                    {"modified_path": "src/main.py",\
                    "modified_content":"# Modified content of main.py"},\
                    "src/utils_original.py":\
                    {"modified_path": "src/utils.py",\
                    "modified_content": "# Modified content of utils.py"}\n}\n\n',
            },
            {
                "role": "user",
                "content": f"Prompt: {prompt}\
                    \n\nrepository: {repository_content}\
                    \n\nuser's solution: {primary_response}",
            },
        ],
        max_tokens=700,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    return completion.choices[0].message.content
