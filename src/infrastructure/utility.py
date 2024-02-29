from functools import wraps
import time
from fastapi import HTTPException

import requests


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
