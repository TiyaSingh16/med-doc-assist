# AI-Powered Medical Document Assistant

An intelligent system that lets users upload medical reports (PDFs) and
ask questions about them using a RAG (Retrieval-Augmented Generation)
pipeline. Automatically extracts diagnoses, medications, and lab values.

## Tech Stack
- **Backend:** FastAPI (Python), PostgreSQL, SQLAlchemy
- **AI Pipeline:** LangChain, OpenAI Embeddings, Pinecone
- **Frontend:** React + TailwindCSS
- **Deployment:** Railway (backend), Vercel (frontend)

## Status
🚧 Active development — Day 1 of 10

## Setup
cd backend
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload

## API Documentation
Auto-generated docs available at /docs when running locally.