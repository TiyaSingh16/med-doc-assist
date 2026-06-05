from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from app.ai.embedder import get_vectorstore
from app.ai.prompts import MEDICAL_QA_PROMPT
from app.config import settings
from app.utils.logger import setup_logger

logger = setup_logger()


def get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.google_api_key,
        temperature=0.3,
    )


def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)


def ask_question(document_id: str, question: str) -> dict:
    try:
        vectorstore = get_vectorstore(document_id)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

        prompt = PromptTemplate(
            template=MEDICAL_QA_PROMPT,
            input_variables=["context", "question"]
        )

        llm = get_llm()

        chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )

        answer = chain.invoke(question)
        source_docs = retriever.invoke(question)
        chunks_used = len(source_docs)

        logger.info(f"Question answered for doc {document_id}, used {chunks_used} chunks")
        return {
            "answer": answer,
            "chunks_used": chunks_used,
        }

    except Exception as e:
        logger.error(f"QA chain failed: {e}")
        raise