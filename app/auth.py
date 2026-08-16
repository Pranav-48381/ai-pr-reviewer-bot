import os
import time
import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

def get_installation_access_token(installation_id: str) -> str:
    """
    Generates a dynamic access token using the GitHub App's .pem file.
    """
    # 1. Read the Private Key
    pem_path = os.getenv("GITHUB_PRIVATE_KEY_PATH")
    with open(pem_path, 'rb') as pem_file:
        private_key = pem_file.read()
        
    app_id = os.getenv("GITHUB_APP_ID")
    
    # 2. Create the JWT (expires in 10 minutes)
    time_now = int(time.time())
    payload = {
        "iat": time_now - 60,       # Issued at time (60 seconds in the past to handle clock drift)
        "exp": time_now + (10 * 60), # Expiration time
        "iss": app_id               # GitHub App ID
    }
    
    encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")
    
    # 3. Exchange the JWT for an Installation Token
    headers = {
        "Authorization": f"Bearer {encoded_jwt}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Request the token from GitHub's API
    token_url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    response = requests.post(token_url, headers=headers)
    response.raise_for_status()
    
    return response.json().get("token")