from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from app.config import settings
from app.utils.logger import setup_logger

logger = setup_logger()

CHROMA_PATH = "chroma_db"


def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )


def embed_document(text: str, document_id: str) -> bool:
    try:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", ".", " "]
        )
        chunks = splitter.split_text(text)
        logger.info(f"Split document {document_id} into {len(chunks)} chunks")

        metadatas = [
            {"document_id": document_id, "chunk_index": i}
            for i in range(len(chunks))
        ]

        embeddings = get_embeddings()
        vectorstore = Chroma(
            collection_name=f"doc_{document_id}",
            embedding_function=embeddings,
            persist_directory=CHROMA_PATH,
        )
        vectorstore.add_texts(texts=chunks, metadatas=metadatas)
        logger.info(f"Successfully embedded document {document_id}")
        return True

    except Exception as e:
        logger.error(f"Embedding failed for document {document_id}: {e}")
        return False


def get_vectorstore(document_id: str) -> Chroma:
    embeddings = get_embeddings()
    return Chroma(
        collection_name=f"doc_{document_id}",
        embedding_function=embeddings,
        persist_directory=CHROMA_PATH,
    )