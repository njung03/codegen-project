import gzip
from fastapi import FastAPI, HTTPException
import requests
from openai import OpenAI
from pydantic import BaseModel

class InputData(BaseModel):
    github_repo_url: str
    prompt: str

app = FastAPI()
client = OpenAI()
@app.post("/generate-diff")
async def generate_diff(input_data: InputData):
    # Validate input
    if not input_data.github_repo_url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Invalid GitHub repo URL")

    # Fetch content of the GitHub repository
    github_api_url = f"{input_data.github_repo_url.rstrip('/')}/archive/master.tar.gz"
    response = requests.get(github_api_url)
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="Failed to fetch GitHub repository content")
    
    # Extract content from the response
    content = response.content  # This would be the content of the repository
    decompressed_data = gzip.decompress(content)
    repository_content = decompressed_data.decode('utf-8')
    # Generate diff based on prompt and repository content
    print("repository_content:",repository_content)
    # file = generate_file(input_data.prompt, repository_content)
    # print("file: ", file)
    initial_response = generate_primary_response(input_data.prompt, repository_content)
    print("initial response:", initial_response)
    # new_response = generate_intermediate_reflection_response(input_data.prompt, repository_content, initial_response)
    # print("intermediate refleciton response: ", new_response)
    reflection_response = generate_relfection_response(input_data.prompt, initial_response, repository_content)
    final_response = generate_diff(input_data.prompt, repository_content, reflection_response)
    print("reflection response: ", reflection_response)
    # final_response = generate_response_with_reflection(input_data.prompt, initial_response)
    print("fianl_diff: ", final_response)
    return {"Final diff": final_response}
def generate_file(prompt, repository_content):
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
            "role": "user",
            "content": f"Prompt:{prompt} \n\nTask : Which file and function will you change to accomplish the task(could be multiple)? Please only give the file and function names.\n\nrepository: {repository_content}"
            }
        ],
        temperature=0.43,
        max_tokens=256,
        top_p=0.3,
        frequency_penalty=0,
        presence_penalty=0
        )
    return completion.choices[0].message.content
def generate_primary_response(prompt, repository_content, files=None):

    # completion = client.chat.completions.create(
    # model="gpt-3.5-turbo",
    # messages=[
    #     {
    #     "role": "user",
    #     "content": "Prompt: # The program doesn't output anything in windows 10\n\n(base) C:\\Users\\off99\\Documents\\Code\\>llm list files in current dir; windows\n/ Querying GPT-3200\n───────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────\n       │ File: temp.sh\n───────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────\n   1   │\n   2   │ dir\n   3   │ ```\n───────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────\n>> Do you want to run this program? [Y/n] y\n\nRunning...\n\n\n(base) C:\\Users\\off99\\Documents\\Code\\>\nNotice that there is no output. Is this supposed to work on Windows also?\nAlso it might be great if the script detects which OS or shell I'm using and try to use the appropriate command e.g. dir instead of ls because I don't want to be adding windows after every prompt. \n\nTask : Which file and function in the repository below will you change to accomplish the task? Please give only the file and function names as the final answer.\n\nrepository: \"\"\"\npax_global_header00006660000000000000000000000064145657210370014524gustar00rootroot0000000000000052 comment=59becfed4ee32f69997a23006956895c44a8420c\ntest-tinygen-main/000077500000000000000000000000001456572103700144445ustar00rootroot00000000000000test-tinygen-main/README.md000066400000000000000000000000161456572103700157200ustar00rootroot00000000000000# test-tinygentest-tinygen-main/src/000077500000000000000000000000001456572103700152335ustar00rootroot00000000000000test-tinygen-main/src/main.py000066400000000000000000000026231456572103700165340ustar00rootroot00000000000000import os\nimport sys\nfrom colorama import Fore\nfrom halo import Halo\nimport requests\n\nspinner = Halo(text='Querying GPT-3', spinner='dots')\n\n\ndef print_prompt(prompt: str):\n    \"\"\"Uses highlighting from your native cat; I use bat, a cat alternative\"\"\"\n    with open('temp.sh', 'w') as f:\n        f.write(prompt)\n    os.system('bat temp.sh')\n    os.remove('temp.sh')\n\n\ndef run_bash_file_from_string(s: str):\n    \"\"\"Runs a bash script from a string\"\"\"\n    with open('temp.sh', 'w') as f:\n        f.write(s)\n    os.system('bash temp.sh')\n    os.remove('temp.sh')\n\n\n@Halo(text='Querying GPT-3', spinner='dots')\ndef model_query(prompt: str) -> str:\n    data = {\n        \"input\": prompt\n    }\n    headers = {\"Authorization\": \"Basic clb76yfe1056trk1al1zq2h0w\"}\n    response = requests.post(\n        \"https://dashboard.scale.com/spellbook/api/app/8r493dlh\",\n        json=data,\n        headers=headers\n    )\n    print(response.status_code)\n    return response.json()['text']\n\n\ndef process():\n    prompt = ' '.join(sys.argv[1:])\n    result = model_query(prompt)\n    print_prompt(result)\n    response = input(Fore.RED + '>> Do you want to run this program? [Y/n] ')\n    if response == '' or response.lower() == 'y':\n        print(Fore.LIGHTBLACK_EX + '\\nRunning...\\n')\n        run_bash_file_from_string(result)\n    else:\n        print(Fore.LIGHTBLACK_EX + 'Aborted.')\n\n\ndef main():\n    process()\n\n\nif __name__ == '__main__':\n    process()\n\"\"\""
    #     }
    # ],
    # temperature=0.43,
    # max_tokens=256,
    # top_p=1,
    # frequency_penalty=0,
    # presence_penalty=0
    # )
    # completion = client.chat.completions.create(
    # model="gpt-3.5-turbo",
    # messages=[
        # {
        # "role": "system",
        # "content": "You will be provided with a prompt and a repository delimited by triple quotes. \
        #     There could be multiple files to change. For each modified file, provide a Git-style diff in the desired format indicating the differences between the original and modified.\
        #             \\n\nDesired format:\n###\diff --git a/file1.txt b/file1.txt\nindex abc123..def456 100644\n--- a/file1.txt\
        #             \n+++ b/file1.txt\n@@ -1,3 +1,3 @@\
        #             \n-This is line 1\n-This is line 2\n+This is the modified line 2\n+This is line 3\n###\ "
        # },
        # {
        # "role": "user",
        # "content": f"Prompt: {prompt} \n\n repository: \"\"\"\n{repository_content}\n\"\"\" \
        #     Accomplish the task in the prompt by changing the files in the repository. Please respond with updated files."
        # }
        # {
        #     "role": "user",
        #     "content": "Please provide a Git-style diff for each of the modified file. A diff compares two versions of files. In this case, the original \
        #         and modified version. The desired format is delimited by triple quotes \
        #             \n\nDesired fromat: \"\"\"\ndiff --git a/file1.txt b/file1.txt\nindex abc123..def456 100644\n--- a/file1.txt\
        #             \n+++ b/file1.txt\n@@ -1,3 +1,3 @@\
        #             \n-This is line 1\n-This is line 2\n+This is the modified line 2\n+This is line 3\n\"\"\""
        # }
    # ],
    # If changing the {files} accomplish the task, please change them. If not, change different files. 
    # temperature=0.4,
    # max_tokens=256,
    # top_p=1,
    # frequency_penalty=0,
    # presence_penalty=0
    # )
    # completion = client.chat.completions.create(
    # model="gpt-3.5-turbo",
    # messages=[
    #     {
    #     "role": "user",
    #     "content": f"Prompt: {prompt} \n\nGiven prompt, which files and functions in the repository provided below will you change?\n\nRepository: \"\"\"\n{repository_content}\n\"\"\""
    #     }
    # ],
    # temperature=0.43,
    # max_tokens=256,
    # top_p=1,
    # frequency_penalty=0,
    # presence_penalty=0
    # )
    completion = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {
        "role": "user",
        "content": f"prompt: {prompt}Ignore pax_global_header and README.md\n Change files in the repository to solve the task in the prompt. Also clearly state original and changed file names.\n\nrepository: \n\"\"\"{repository_content} \n\"\"\" "      }
    ],
    temperature=0,
    max_tokens=1024,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0
    )
    return completion.choices[0].message.content
def generate_relfection_response(initial_prompt, initial_response, repository_content):
    reflection_prompt = "Make sure to provide the actual solution to the user's prompt. First work out your own solution to the prompt with only content in the previosu diff.\
          Then compare to the user's solution and evaluate if your solution is correct or not.\
              Respond in your answer with either user's solution exactly or your solution to the prompt after evaluating."
    
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
        {
        "role": "system",
        "content": "provide solution to the user prompt"
        },
        {"role": "user",
        "content": f"prompt: {initial_prompt}Ignore pax_global_header and README.md\n Also clearly state original and changed file names.\
            \n\nrepository: \n\"\"\"{repository_content} \n\"\"\"" 
        },
        {"role": "assistant",
        "content": f"{initial_response}"
        },
        {
        "role": "user",
        "content": "Is the model sure about the changes made to accomplish the task in the prompt? \
            First work out your own solution to the prompt. Then compare to the model's solution \
                and evaluate if your solution is correct or not. Please provide the actual solution to the user prompt as your answer.\
                    Simply telling me that the model's solution is correct will not work for me."
        }
    ],
    temperature=0.8,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0
    )
    return completion.choices[0].message.content
def generate_diff(prompt, repository_content, prompt_response):
    completion = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
    {
      "role": "user",
      "content": f"prompt: {prompt}\nAlso clearly state original and changed file names.\n\nrepository: \n\"\"\"{repository_content} \n\"\"\" "  
    },
    {
        "role": "assistant",
        "content": f"{prompt_response}"
    },
    {
      "role": "user",
      "content": "Please provide a Git-stye unified diff(plus and minus signs) comparing the original and modified files. Please provide the diff for all modified files. \
        The diff should clearly indicate the difference between the original and modified files line by line."
    }
  ],
  temperature=0,
  max_tokens=1024,
  top_p=1,
  frequency_penalty=0,
  presence_penalty=0
)
    return completion.choices[0].message.content
# def generate_intermediate_reflection_response(prompt, repository_content, initial_response):

#     completion = client.chat.completions.create(
#     model="gpt-3.5-turbo",
#     messages=[
#         {
#         "role": "user",
#         "content": f"Prompt: {prompt} \n\nGiven prompt, which files and functions in the repository provided below will you change?\n\nRepository: \"\"\"\n{repository_content}\n\"\"\""
#         },
#         {"role": "assistant",
#          "content": f"{initial_response}"},
#         {
#         "role": "user",
#         "content": "Is the model sure about the previous response? \
#             If not, please try to solve on your own. As a final answer, you will provide a Git-style diff."
#     }
#     ],
#     temperature=0.8,
#     top_p=1,
#     frequency_penalty=0,
#     presence_penalty=0
    
#     )
#     # Extract diff from OpenAI API response
#     diff_text = completion.choices[0].message.content
#     if not diff_text:
#         raise HTTPException(status_code=404, detail="No diff generated")

#     return diff_text

def generate_response_with_reflection(initial_prompt, initial_response):
    
    reflection_prompt = "Is the model sure about the previous diff regarding the changes made to accomplish the task in the prompt? \
            First work out your own solution to the prompt with only content in the previosu diff. Then compare to the previous diff \
                and evaluate if your solution is correct or not. Don't decide if the previous diff is correct \
                    until you have done the problem yourself. Do not explain thought process. Your final answer will be a Git-style unified diff with the modified and origianl code."
    
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
        # {
        # "role": "system",
        # "content": "Please provide full unified diff containing the assistant's diff content." 
        # },
        {"role": "user",
        "content": f"prompt: {initial_prompt}\n Provide a unified Git-style diff comparing the modified and original code."
        },
        {"role": "assistant",
        "content": f"diff: {initial_response}"
        },
        {
        "role": "user",
        "content": "Please correct your response."
        }
    ],
    temperature=0.8,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0
    )
    return completion.choices[0].message.content

