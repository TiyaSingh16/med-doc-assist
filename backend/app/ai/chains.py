from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from app.ai.embedder import get_vectorstore
from app.ai.prompts import MEDICAL_QA_PROMPT
from app.config import settings
from app.utils.logger import setup_logger

logger = setup_logger()


def get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=settings.google_api_key,
        temperature=0.3,
    )


def get_qa_chain(document_id: str) -> RetrievalQA:
    vectorstore = get_vectorstore(document_id)
    retriever = vectorstore.as_retriever(
        search_kwargs={"k": 4}
    )

    prompt = PromptTemplate(
        template=MEDICAL_QA_PROMPT,
        input_variables=["context", "question"]
    )

    llm = get_llm()

    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True,
    )

    return chain


def ask_question(document_id: str, question: str) -> dict:
    try:
        chain = get_qa_chain(document_id)
        result = chain.invoke({"query": question})
        answer = result["result"]
        source_docs = result.get("source_documents", [])
        chunks_used = len(source_docs)
        logger.info(f"Question answered for doc {document_id}, used {chunks_used} chunks")
        return {
            "answer": answer,
            "chunks_used": chunks_used,
        }
    except Exception as e:
        logger.error(f"QA chain failed: {e}")
        raise