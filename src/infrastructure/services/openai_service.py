import os
from openai import OpenAI

from src.infrastructure.utility import handle_errors


class OpenAISerivce:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @handle_errors
    def generate_primary_response(self, prompt, repository_content):
        completion = self.client.chat.completions.create(
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
    def generate_reflection_response(
        self, prompt, repository_content, primary_response
    ):
        completion = self.client.chat.completions.create(
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

    # Function to handle API and non-API errors and retry
