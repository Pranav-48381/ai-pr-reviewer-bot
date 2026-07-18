import os
import json
from dotenv import load_dotenv
from google import genai

# Load the environment variables HERE, before the client initializes
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

async def analyze_code_diff(filename: str, diff_text: str) -> dict:
    prompt = f"""
    You are a senior engineer reviewing a file named '{filename}'.
    Analyze the following git diff and output your review STRICTLY in JSON format.
    
    The JSON must have this exact structure:
    {{
        "filename": "{filename}",
        "review_summary": "Overall summary.",
        "complexity_analysis": {{
            "time_complexity": "e.g., O(n)",
            "space_complexity": "e.g., O(1)"
        }},
        "issues": [
            {{
                "type": "Performance" | "Bug" | "Style",
                "description": "Clear explanation.",
                "suggestion": "Snippet of better code."
            }}
        ]
    }}
    
    Code Diff:
    {diff_text}
    """
    
    response = await client.aio.models.generate_content(
        model='gemini-3.5-flash',
        contents=prompt
    )
    
    raw_text = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(raw_text)