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


# def get_branch_from_github_url(github_url):
#     # Parse the URL
#     parsed_url = urlparse(github_url)
#     # Extract the query parameters
#     query_params = parse_qs(parsed_url.query)
#     # Extract the branch from the query parameters
#     branch = query_params.get("branch", ["main"])[0]
#     return branch


def organize_repository_content(github_url):
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
    # result = {}
    # # Open the content as a tar file
    # with tarfile.open(fileobj=BytesIO(content), mode="r:gz") as tar:
    #     # Iterate over each file in the archive
    #     for member in tar.getmembers():
    #         file_path = member.name
    #         file_content = tar.extractfile(file_path)
    #         if file_content:
    #             file_content = file_content.read().decode("utf-8")
    #             result[file_path] = file_content
    return repository_content


def get_basename(path):
    return "/".join(path.split("/")[1:])


def generate_full_diff_helper(file_mappings, repo_url):
    print(file_mappings)
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


#     """
#     Generate the full unified diff for all modified files.

#     Args:
#         original_files_json (dict): JSON object with original file paths and contents.
#         modified_files_json (dict): JSON object with modified file paths and contents.

#     Returns:
#         str: The full unified diff output.
#     """
#     # Initialize an empty string to accumulate the diff output
#     full_diff_output = ""
#     # print("original repository contet: ", original_files_json)
#     # print("modified files: ", modified_files_json)
#     # Iterate over modified files
#     for original_path, modified_data in modified_files_json.items():
#         modified_path = modified_data["modified_path"]
#         modified_content = modified_data["modified_content"]
#         print(original_path, modified_content)
#         # Write original content to temporary file
#         with tempfile.NamedTemporaryFile(mode="w", delete=False) as original_file:
#             original_content = original_files_json.get(original_path)
#             print("repository: ", original_files_json)
#             print("original content fetched:", original_content, "\n\n", original_path)
#             original_file.write(original_content)
#             original_file_path = original_file.name

#         # Write modified content to temporary file
#         with tempfile.NamedTemporaryFile(mode="w", delete=False) as modified_file:
#             modified_file.write(modified_content)
#             modified_file_path = modified_file.name

#         # Generate unified diff using git diff command
#         diff_output = subprocess.check_output(
#             ["git", "diff", "--unified", original_file_path, modified_file_path],
#             text=True,
#         )

#         # Append diff output to the full diff
#         full_diff_output += f"Unified diff for {modified_path}:\n{diff_output}\n\n"

#         # Cleanup temporary files
#         subprocess.run(["rm", original_file_path])
#         subprocess.run(["rm", modified_file_path])

#     # Return the full diff output
#     return full_diff_output


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
    # organize repository content in json format.
    # key as file path and value as file content
    repository_content = organize_repository_content(input_data.github_url)
    # repository_content = json.dumps(repository_content, indent=4)
    #   Print the organized content in JSON format
    # print("repository organized in json: ", repository_content)

    # generate primary response to the prompt
    primary_response = generate_primary_json(input_data.prompt, repository_content)
    # print("primary reponse in json: ", primary_response)

    # generate reflection response to prompt using primary response as input
    reflection_response = generate_reflection_json(
        input_data.prompt, primary_response, repository_content
    )
    # print("reflection to primary json: ", reflection_response)
    reflection_response_json = json.loads(reflection_response)
    print("reflection response json:", reflection_response_json)
    final_unified_diff = generate_full_diff_helper(
        reflection_response_json, input_data.github_url
    )
    return final_unified_diff

    # # genereate primary diff to the final/reflection response
    # primary_diff = generate_primary_diff(
    #     input_data.prompt, repository_content, reflection_response
    # )

    # # generate final diff with reflection on the primary diff
    # final_diff = generate_final_diff(
    #     input_data.prompt, repository_content, primary_diff
    # )

    # Store input(prompt and github url) and unified diff in supabase DB
    # input_id = store_input_data(input_data, generate_diff_db)
    # store_unified_diff(final_diff, input_id, generate_diff_db)

    # return final_diff


@handle_api_errors
def generate_primary_json(prompt, repository_content):
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
    # completion = client.chat.completions.create(
    #     model="gpt-3.5-turbo",
    # messages=[
    #     {
    #         "role": "system",
    #     "content": 'You will be provided with a prompt and repository. \
    # Please modify files to accomplish issue or task in the prompt. \
    #     \nDesired format:\
    #     \n{"modified_files":"path": "src/main.py", \
    #     "content": "# Modified content of main.py"}, \
    #     {"path": "src/utils.py","content": "# Modified content of utils.py"}]}',
    # },
    #     {
    #         "role": "user",
    #         "content": f"Prompt: {prompt}\n\nrepository: {repository_content}",
    #     },
    # ],
    #     max_tokens=256,
    #     top_p=1,
    #     frequency_penalty=0,
    #     presence_penalty=0,
    # )
    return completion.choices[0].message.content


@handle_api_errors
def generate_reflection_json(prompt, repository_content, primary_json):
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
                    \n\nuser's solution: {primary_json}",
            },
        ],
        max_tokens=700,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    return completion.choices[0].message.content


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
