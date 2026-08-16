import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def analyze_code_diff(diff_text: str) -> str:
    """
    Synchronously analyzes a git diff and returns a formatted Markdown review.
    """
    prompt = f"""
    You are a senior engineer reviewing a GitHub Pull Request.
    Analyze the following git diff and output your review. 
    Focus on code quality, security vulnerabilities, edge cases, and performance.
    
    You MUST output your response matching this exact JSON structure:
    {{
        "review_summary": "Overall summary of the changes.",
        "issues": [
            {{
                "file": "name of the file",
                "type": "Performance" | "Bug" | "Security" | "Style",
                "description": "Clear explanation of the issue.",
                "suggestion": "How to fix it or improve it."
            }}
        ]
    }}
    
    Code Diff:
    {diff_text}
    """
    
    # 1. Use the synchronous client with Native JSON generation
    response = client.models.generate_content(
        model='gemini-2.5-flash', # Or whichever model you prefer
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    
    # 2. Parse the guaranteed JSON
    review_data = json.loads(response.text)
    
    # 3. Format it into a clean Markdown string for the GitHub comment
    markdown_comment = f"## 🤖 AI Code Review\n\n**Summary:** {review_data.get('review_summary', 'No summary provided.')}\n\n"
    
    issues = review_data.get("issues", [])
    if not issues:
        markdown_comment += "✅ Everything looks great! No major issues found."
    else:
        markdown_comment += "### Suggestions & Feedback:\n"
        for issue in issues:
            markdown_comment += f"* **[{issue['type']}] - `{issue['file']}`**: {issue['description']}\n"
            markdown_comment += f"  * *Suggestion*: {issue['suggestion']}\n\n"
            
    return markdown_comment