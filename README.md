
# TinyGen

This project is a trivial service that takes in a public GitHub repository and a code prompt, such as "convert it to Typescript," and returns the code diff that accomplishes this task.

## Setup

### Prerequisites

- Python 3.x
- pip (Python package manager)

### Installation

1. Clone this repository to your local machine using a virtualenv e.g.3.11.6:

   ```bash
   git clone https://github.com/njung03/codegen-project.git
   ```

2. Navigate to the project directory:

   ```bash
   cd codegen-project
   ```

3. Install the required Python packages using pip:

   ```bash
   pip install -r requirements.txt
   ```

### Setting Environment Variables

Before running the application, you need to set up environment variables for your OpenAI API key and your Supabase database URI. 

3. After setting the environment variables, make sure to restart your application for the changes to take effect.

### Running the Application

Once you have set up the environment variables, you can run the application using the following command:

```bash
uvicorn app.main:app --reload
```

### Accessing the API Documentation

You can access the API documentation by navigating to the `/docs` endpoint in your web browser after starting the application. This documentation provides detailed information about the available endpoints and how to interact with them. If you're using vscode
Thunder Client is an option.

Example input: {
  "github_url": "https://github.com/njung03/test-python-conversion",
  "prompt": "Convert python files to typescript"
}
Note: The quality of the output to this input is variable.
