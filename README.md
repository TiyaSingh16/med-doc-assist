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
- 💬 **RAG-powered chat** — ask natural-language questions about any uploaded document, answered using retrieval-augmented generation over the document's actual content (not general knowledge), with source-chunk grounding
- ⚡ **Streaming responses** — answers stream token-by-token via Server-Sent Events, like ChatGPT
- 🗂️ **Structured data extraction** — automatically pulls diagnoses, medications, and lab values into clean, typed JSON using LLM structured output (Pydantic schemas)
- 📊 **Document comparison** — upload two reports from different dates and get an AI-generated diff: which lab values improved/worsened, medication changes, resolved/new diagnoses
- 📝 **Persistent chat history** — conversations are saved per document and survive page refreshes
- ☁️ **Fully deployed** — live on Railway (backend + PostgreSQL) and Vercel (frontend)

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

## Running Locally

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL running locally
- API keys: Google Gemini, Cloudinary

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt

# Create a .env file with:
# database_url=postgresql://user:password@localhost:5432/medicaldocs
# secret_key=your-secret-key
# google_api_key=your-gemini-key
# cloudinary_cloud_name=your-cloud-name
# cloudinary_api_key=your-api-key
# cloudinary_api_secret=your-api-secret

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
│   │   └── main.py
│   └── alembic/             # Database migrations
└── frontend/
    └── src/
        ├── api/             # API client functions
        ├── components/      # Reusable components
        └── pages/            # Route-level pages
```

---

## Author

Built by Tiya Singh as a portfolio project demonstrating full-stack development, AI/ML integration, and cloud deployment.