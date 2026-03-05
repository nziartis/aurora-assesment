from dotenv import load_dotenv

load_dotenv()

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

import messages
import qa

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await messages.refresh()
    except Exception as e:
        logger.warning("Failed to warm cache at startup: %s", e)
    yield


app = FastAPI(title="Member Q&A", lifespan=lifespan)


class Question(BaseModel):
    question: str = Field(..., min_length=1)


class Answer(BaseModel):
    answer: str


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index():
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Member Q&A</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, sans-serif; background: #0f0f0f; color: #e8e8e8; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 1rem; }
    .card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px; padding: 2rem; width: 100%; max-width: 600px; }
    h1 { font-size: 1.25rem; font-weight: 600; margin-bottom: 1.5rem; color: #fff; }
    textarea { width: 100%; background: #111; border: 1px solid #333; border-radius: 8px; color: #e8e8e8; font-size: 0.95rem; padding: 0.75rem; resize: vertical; min-height: 80px; outline: none; }
    textarea:focus { border-color: #555; }
    button { margin-top: 0.75rem; width: 100%; padding: 0.7rem; background: #2563eb; border: none; border-radius: 8px; color: #fff; font-size: 0.95rem; font-weight: 500; cursor: pointer; }
    button:hover { background: #1d4ed8; }
    button:disabled { background: #1e3a5f; color: #6b7280; cursor: not-allowed; }
    .answer { margin-top: 1.25rem; padding: 1rem; background: #111; border: 1px solid #2a2a2a; border-radius: 8px; font-size: 0.95rem; line-height: 1.6; display: none; }
    .answer.visible { display: block; }
    .error { color: #f87171; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Member Q&amp;A</h1>
    <textarea id="q" placeholder="Ask a question about a member&#10;e.g. When is Layla planning her trip to London?"></textarea>
    <button id="btn" onclick="ask()">Ask</button>
    <div class="answer" id="answer"></div>
  </div>
  <script>
    async function ask() {
      const q = document.getElementById('q').value.trim();
      if (!q) return;
      const btn = document.getElementById('btn');
      const out = document.getElementById('answer');
      btn.disabled = true;
      btn.textContent = 'Thinking...';
      out.className = 'answer';
      try {
        const res = await fetch('/ask', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({question: q}) });
        const data = await res.json();
        out.className = 'answer visible';
        out.textContent = res.ok ? data.answer : (data.detail || 'Something went wrong.');
        if (!res.ok) out.classList.add('error');
      } catch {
        out.className = 'answer visible error';
        out.textContent = 'Could not reach the server.';
      } finally {
        btn.disabled = false;
        btn.textContent = 'Ask';
      }
    }
    document.getElementById('q').addEventListener('keydown', e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) ask(); });
  </script>
</body>
</html>"""


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ask", response_model=Answer)
async def ask(body: Question):
    data = await messages.get_all()
    if not data:
        raise HTTPException(status_code=503, detail="Member data unavailable. Try again shortly.")

    member_messages = messages.find_user(body.question, data)
    if member_messages is None:
        return Answer(answer="I don't have data for any member matching that name.")

    answer_text = await qa.answer(body.question, member_messages)
    return Answer(answer=answer_text)
