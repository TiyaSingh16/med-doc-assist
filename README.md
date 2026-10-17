# MedDocAssist — AI-Powered Medical Document Assistant

An AI-powered web app that lets users upload medical documents (lab reports, prescriptions, discharge summaries) and interact with them intelligently — chat with the document, extract structured data, and compare multiple reports over time to track health trends.

**🔗 Live demo:** [med-doc-assist.vercel.app](https://med-doc-assist.vercel.app)
**🔗 API docs:** [med-doc-assist-production.up.railway.app/docs](https://med-doc-assist-production.up.railway.app/docs)

<!-- Add screenshots here, e.g.:
![Dashboard](./screenshots/dashboard.png)
![Chat](./screenshots/chat.png)
![Comparison](./screenshots/compare.png)
-->

---

## Features

- 🔐 **JWT authentication** — secure user registration and login
- 📄 **PDF upload with smart extraction** — digital text extraction (PyMuPDF) with automatic OCR fallback (Tesseract) for scanned documents
- 💬 **RAG-powered chat with page citations**: ask questions about an uploaded document. Answers come only from its retrieved excerpts, cite pages like `[p. 2]`, and list their sources (page and excerpt) in the UI.
- ⚡ **Streaming responses** — answers stream token-by-token via Server-Sent Events, like ChatGPT
- 🗂️ **Structured data extraction** — automatically pulls diagnoses, medications, and lab values into clean, typed JSON using LLM structured output (Pydantic schemas)
- 📊 **Document comparison** — upload two reports from different dates and get an AI-generated diff: which lab values improved/worsened, medication changes, resolved/new diagnoses
- 📝 **Persistent chat history** — conversations are saved per document and survive page refreshes
- 🔒 **Private storage**: originals are stored privately in Cloudinary under a unique key per upload, and are never exposed by the API
- ♻️ **Self-healing vector index**: if the vector store is lost (for example on a redeploy), a document's vectors are rebuilt from its saved text the next time it is used
- ☁️ **Fully deployed**: live on Railway (backend + PostgreSQL) and Vercel (frontend)

---

## Tech Stack

**Backend**
- FastAPI, SQLAlchemy + Alembic, PostgreSQL
- JWT auth (python-jose, bcrypt)
- Google Gemini 2.5 Flash (LLM + structured output)
- LangChain (RAG chains, streaming), ChromaDB (vector store)
- HuggingFace `all-MiniLM-L6-v2` (embeddings)
- PyMuPDF + Tesseract OCR (document text extraction)
- Cloudinary (file storage)

**Frontend**
- React + Vite, Tailwind CSS
- React Router, Axios
- react-markdown (formatted chat responses)

**Deployment**
- Railway (backend + managed PostgreSQL)
- Vercel (frontend, static build)

---

## Architecture Overview

```
User → React (Vercel) → FastAPI (Railway) → PostgreSQL (Railway)
                              │
                              ├─→ Cloudinary (PDF storage)
                              ├─→ ChromaDB (vector embeddings)
                              └─→ Gemini 2.5 Flash (chat, extraction, comparison)
```

**Document flow:** Upload → smart text extraction (digital first, OCR fallback) → chunk + embed into ChromaDB → available for RAG chat, structured extraction, and comparison.

---

## Key Design Decisions

A few decisions worth highlighting (also covered in more depth in interviews):

- **Structured output over prompt-engineered JSON**: extraction and comparison use LLM structured output (Pydantic schema binding) rather than asking the model to "please respond in JSON" — this constrains generation at the decoding level for reliable, parseable output.
- **Cache-first extraction**: extracted structured data is cached in a JSONB column and only regenerated on explicit request, avoiding redundant LLM calls.
- **SSE over WebSockets for streaming**: chat is a one-directional stream (server → client), so Server-Sent Events were sufficient and simpler than a full WebSocket connection.
- **Comparing structured data, not raw text**: document comparison runs on two already-extracted `ExtractionResult` objects rather than raw PDF text, so the LLM's job is pure comparison, not simultaneous parsing-and-comparing.

---

## Reliability and Security

| Concern | What the code does |
|---|---|
| Medical files are sensitive | Uploaded PDFs are stored as **private** Cloudinary files under `medical_docs/<user>/<uuid>`, so they are unguessable and two users with the same filename can't overwrite each other. The API never returns a storage URL. Every document endpoint checks ownership and returns 404 for other users' documents. |
| Fake or huge uploads | Checked by content (`%PDF-` magic bytes), not just the extension. 10 MB cap, enforced without reading more than the limit. |
| Scanned PDFs | Digital text first, then Tesseract OCR. Tesseract is found via `TESSERACT_CMD` or `PATH` and installed on Railway via `railpack.json`. If no text can be extracted, the document is marked **failed with a reason** instead of "completed" with nothing in it. |
| Lost vectors | Chroma lives on the server's disk, which Railway replaces on redeploy. PostgreSQL keeps the extracted text, and `ensure_vectors()` rebuilds a document's index on first use. Embedding is idempotent (stable ids). |
| One slow LLM call blocking everyone | Routes that do blocking work (sync SQLAlchemy, Cloudinary, Gemini) are plain `def`, so FastAPI runs them in a thread pool. Streaming runs retrieval in a thread. Background processing uses its own DB session. |
| Token forgery | `SECRET_KEY` is required (min 16 chars; known placeholders rejected), so the app refuses to start without it. Login takes the same time for unknown emails. |
| Cost and abuse | Per-user rate limit (default 20/min) on chat, extraction and comparison; returns `429` with `Retry-After`. |
| Prompt injection from document text | The prompt fences excerpts inside `<document>` tags and tells the model to treat them as data. This is a mitigation, not a guarantee. |
| Leaking internals | Errors shown to users are written for users; details go to the logs. Logs don't contain email addresses. |

---

## Retrieval Evaluation

`backend/eval/` measures whether retrieval finds the excerpt that answers a question. It contains 3 fictional multi-page reports and 15 questions, each tagged with the page holding the answer and a keyword the retrieved chunk must contain. It reports **hit@k** (the right chunk is in the top k) and **MRR**, across chunk sizes, using the app's own chunking.

```bash
cd backend
python -m eval.run --retriever minilm     # production embedding model (downloads it on first use)
python -m eval.run --retriever keyword    # TF-IDF keyword baseline, no model needed
```

Measured keyword baseline (the bar the embedding model should beat):

| chunk size | hit@1 | hit@2 | hit@4 | MRR |
|---|---|---|---|---|
| 300 | 0.67 | 0.87 | 0.87 | 0.79 |
| 500 | 0.67 | 0.87 | 1.00 | 0.80 |
| 800 | 0.67 | 0.93 | 1.00 | 0.82 |

MiniLM results: *not recorded yet. Run the first command above and paste the table here.* The test set is small and synthetic, so it is useful for comparing settings, not as a benchmark.

---

## Testing and CI

```bash
cd backend
# needs a disposable PostgreSQL database; the tests apply the migrations and empty the tables
DATABASE_URL=postgresql://user:pass@localhost:5432/mda_test python -m pytest -q
```

There are 45 tests. They run against **real PostgreSQL** with the real Alembic migrations, real PyMuPDF and **Tesseract OCR**, and a real Chroma store with deterministic fake embeddings and a fake LLM, so no API keys are needed. They cover:
- private, unique storage keys;
- content-based PDF validation and size limits;
- OCR fallback, and failure when OCR is unavailable;
- one user unable to reach another's documents;
- vectors rebuilt after being wiped;
- page-numbered sources in normal and streaming answers;
- rate limiting, LLM failure handling, and the secret-key check.

GitHub Actions (`.github/workflows/ci.yml`) runs on every push:
- **Backend:** the test suite against a PostgreSQL 16 service, with Tesseract installed.
- **Frontend:** `npm ci`, lint, build, and `npm audit` of production dependencies.

---

## Running Locally

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL running locally
- Tesseract OCR (for scanned PDFs). On Windows, install it and set `TESSERACT_CMD` if it is not on `PATH`
- API keys: Google Gemini, Cloudinary

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt

# Copy .env.example to .env and fill it in (SECRET_KEY, DATABASE_URL,
# GOOGLE_API_KEY and the Cloudinary keys are required)

alembic upgrade head
uvicorn app.main:app --reload
```

Backend runs at `http://127.0.0.1:8000` — API docs at `/docs`.

### Frontend

```bash
cd frontend
npm install

# Create a .env file with:
# VITE_API_URL=http://127.0.0.1:8000

npm run dev
```

Frontend runs at `http://localhost:5173`.

---

## Project Structure

```
med-doc-assist/
├── backend/
│   ├── app/
│   │   ├── ai/            # LangChain chains, embeddings, prompts
│   │   ├── models/         # SQLAlchemy models
│   │   ├── routers/        # API endpoints
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic (extraction, comparison, PDF processing)
│   │   ├── utils/          # Auth dependency, rate limiter, logging
│   │   └── main.py
│   ├── alembic/            # Database migrations (applied on every deploy)
│   ├── eval/               # Retrieval evaluation (dataset + hit@k/MRR runner)
│   ├── tests/              # pytest suite (PostgreSQL, OCR, fakes for external APIs)
│   └── railpack.json       # Installs Tesseract on Railway
└── frontend/
    └── src/
        ├── api/             # API client functions
        ├── components/      # Reusable components
        └── pages/            # Route-level pages
```

---

### Login & Registration
![Login](./screenshots/login.png)
![Register](./screenshots/register.png)

### Document Upload
![Upload](./screenshots/upload.png)
![Uploaded documents](./screenshots/uploaded.png)

### Chat with your document
![Chat Q&A](./screenshots/qna.png)

### Document comparison
![Comparison step 1](./screenshots/compare1.png)
![Comparison results](./screenshots/compared.png)
![Comparison results continued](./screenshots/compared2.png)

---

## Limitations

- **Single-process rate limiting:** the limit is kept in memory, so with several instances each keeps its own count. A shared store (Redis) would fix that.
- **Extra work after a redeploy:** vectors stored on the container disk are rebuilt on first use, which costs a delay and embedding work. A managed or persistent vector store (pgvector, or a Railway volume) would avoid it.
- **The comparison is LLM-judged:** improved or worsened trends come from the model. Computing numeric changes in code (with unit checks) would be more reliable.
- **Prompt injection is mitigated, not solved.**
- **Old documents have no page numbers:** documents processed before page tracking cite excerpts instead of pages, until they are re-uploaded.
- **Small evaluation:** the retrieval evaluation is synthetic and small.

---

## Author

Built by Tiya Singh as a portfolio project demonstrating full-stack development, AI/ML integration, and cloud deployment.