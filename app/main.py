import os
import hmac
import hashlib
import httpx
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

from app.ai import analyze_code_diff
from app.auth import get_installation_access_token

load_dotenv()

app = FastAPI()

GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
if not GITHUB_WEBHOOK_SECRET:
    raise ValueError("GITHUB_WEBHOOK_SECRET environment variable is missing!")


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


async def process_pr_review(payload: dict):
    """Background worker to fetch PR diffs, run AI analysis, and post comments."""
    action = payload.get("action", "unknown action")
    if action not in ["opened", "reopened", "synchronize"]:
        return

    # Extract installation ID and generate a dynamic App token
    installation_id = str(payload.get("installation", {}).get("id"))
    if not installation_id:
        print("❌ No installation ID found in payload.")
        return

    token = get_installation_access_token(installation_id)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }

        # 1. Fetch changed files
        files_url = payload["pull_request"]["url"] + "/files"
        files_response = await client.get(files_url, headers=headers)

        if files_response.status_code != 200:
            print(f"❌ Failed to fetch PR files: {files_response.status_code} - {files_response.text}")
            return

        files_data = files_response.json()
        all_feedback = []

        # 2. Analyze each file with AI
        for file in files_data:
            filename = file.get("filename")
            diff = file.get("patch", "")
            if diff:
                print(f"🧠 Analyzing {filename}...")
                try:
                    feedback = await analyze_code_diff(filename, diff)
                    all_feedback.append(feedback)
                except Exception as e:
                    print(f"⚠️ Error analyzing {filename}: {e}")

        if not all_feedback:
            print("ℹ️ No feedback generated or no diffs found.")
            return

        # 3. Build Markdown body
        markdown_body = "### 🤖 Multi-File AI Code Review\n\n"
        for review in all_feedback:
            markdown_body += f"#### 📄 File: `{review.get('filename', 'Unknown')}`\n"
            markdown_body += f"**Summary:** {review.get('review_summary', '')}\n\n"

            complexity = review.get("complexity_analysis", {})
            if complexity:
                time_comp = complexity.get("time_complexity", "N/A")
                space_comp = complexity.get("space_complexity", "N/A")
                markdown_body += f"⏱️ **Time:** {time_comp} | **Space:** {space_comp}\n\n"

            issues = review.get("issues", [])
            if issues:
                markdown_body += "🚨 **Detected Issues:**\n"
                for issue in issues:
                    markdown_body += f"* **{issue.get('type', 'Issue')}**: {issue.get('description', '')}\n"
                    if issue.get("suggestion"):
                        markdown_body += f"  > *Suggestion:* `{issue['suggestion']}`\n"
            markdown_body += "\n---\n"

        # 4. Post the review comment to the PR
        comments_url = payload["pull_request"]["comments_url"]
        post_response = await client.post(comments_url, headers=headers, json={"body": markdown_body})

        if post_response.status_code == 201:
            print("✅ Successfully posted multi-file review to GitHub!")
        else:
            print(f"❌ Failed to post comment: {post_response.status_code} - {post_response.text}")


@app.post("/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None)
):
    body = await request.body()
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing GitHub signature")

    # Verify HMAC signature
    expected_signature = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature. Hacker blocked!")

    payload = await request.json()
    action = payload.get("action", "unknown action")
    print(f"=== SECURE WEBHOOK VERIFIED === PR Action: {action}")

    # Queue review process in background to ensure immediate 200 response to GitHub
    if action in ["opened", "reopened", "synchronize"]:
        background_tasks.add_task(process_pr_review, payload)

    return {"status": "ok"}