from app.ai import analyze_code_diff
import httpx
import os
import hmac
import hashlib
from fastapi import FastAPI, Request, HTTPException, Header
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse

load_dotenv()

app = FastAPI()

GITHUB_SECRET = os.getenv("GITHUB_SECRET")
if not GITHUB_SECRET:
    raise ValueError("GITHUB_SECRET environment variable is missing!")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN environment variable is missing!")



@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <html>
        <head>
            <title>AI PR Reviewer</title>
            <style>
                body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #0d1117; color: #c9d1d9; margin: 0; }
                .card { background: #161b22; padding: 3rem; border-radius: 10px; border: 1px solid #30363d; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
                h1 { color: #58a6ff; margin-top: 0; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>🤖 AI PR Reviewer is Live!</h1>
                <p>The webhook server is actively monitoring GitHub for new Pull Requests.</p>
            </div>
        </body>
    </html>
    """
@app.post("/webhook")
async def github_webhook(
        request: Request,
        x_hub_signature_256: str = Header(None)):

    body = await request.body()
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing GitHub signature")

    expected_signature = "sha256=" + hmac.new(
        GITHUB_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature. Hacker blocked!")

    payload = await request.json()
    action = payload.get("action", "unknown action")
    print(f"=== SECURE WEBHOOK VERIFIED === PR Action: {action}")

    if action in ["opened", "reopened", "synchronize"]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            headers = {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            # 1. Fetch the list of files
            files_url = payload["pull_request"]["url"] + "/files"
            files_response = await client.get(files_url, headers=headers)

            if files_response.status_code == 200:
                files_data = files_response.json()
                all_feedback = []
                
                # 2. Analyze each file
                for file in files_data:
                    filename = file['filename']
                    diff = file.get('patch', '')
                    if diff:
                        print(f"🧠 Analyzing {filename}...")
                        feedback = await analyze_code_diff(filename, diff)
                        all_feedback.append(feedback)
                
                # 3. Build comprehensive Markdown
                markdown_body = "### 🤖 Multi-File AI Code Review\n\n"
                for review in all_feedback:
                    markdown_body += f"#### 📄 File: `{review['filename']}`\n"
                    markdown_body += f"**Summary:** {review['review_summary']}\n\n"
                    markdown_body += (f"⏱️ **Time:** {review['complexity_analysis']['time_complexity']} | "
                                      f"**Space:** {review['complexity_analysis']['space_complexity']}\n\n")
                    
                    if review['issues']:
                        markdown_body += "🚨 **Detected Issues:**\n"
                        for issue in review['issues']:
                            markdown_body += f"* **{issue['type']}**: {issue['description']}\n"
                            if issue.get('suggestion'):
                                markdown_body += f"  > *Suggestion:* `{issue['suggestion']}`\n"
                    markdown_body += "\n---\n"

                # 4. Post the aggregated review exactly once
                comments_url = payload["pull_request"]["comments_url"]
                post_response = await client.post(comments_url, headers=headers, json={"body": markdown_body})
                
                if post_response.status_code == 201:
                    print("✅ Successfully posted multi-file review to GitHub!")
                else:
                    print(f"❌ Failed to post comment: {post_response.text}")
    
    return {"status": "ok"}