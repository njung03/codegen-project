import gzip
import os
import shutil
import subprocess
import tempfile
from fastapi import HTTPException
import requests


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
