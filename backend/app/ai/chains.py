from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from app.ai.embedder import get_vectorstore
from app.ai.prompts import MEDICAL_QA_PROMPT
from app.config import settings
from app.utils.logger import setup_logger

logger = setup_logger()


def get_llm(temperature: float = 0.3):
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.google_api_key,
        temperature=temperature,
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
async def ask_question_stream(document_id: str, question: str):
    """
    Same RAG logic as ask_question, but yields answer tokens as they're generated
    instead of returning the full string at once.
    """
    vectorstore = get_vectorstore(document_id)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    source_docs = retriever.invoke(question)
    context = format_docs(source_docs)
    chunks_used = len(source_docs)

    prompt = PromptTemplate(
        template=MEDICAL_QA_PROMPT,
        input_variables=["context", "question"]
    ).format(context=context, question=question)

    llm = get_llm()

    full_answer = ""
    async for chunk in llm.astream(prompt):
        token = chunk.content
        full_answer += token
        yield {"type": "token", "content": token}

    yield {"type": "done", "chunks_used": chunks_used, "full_answer": full_answer}