from app.ai.chains import get_llm
from app.schemas.extraction import ExtractionResult
from app.utils.logger import setup_logger

logger = setup_logger()


EXTRACTION_PROMPT = """You are a medical document analysis assistant. 
Carefully read the following medical document text and extract structured information.

Rules:
- Only extract information that is explicitly present in the text. Do not infer or hallucinate values.
- If a field is not mentioned, leave it empty/null rather than guessing.
- For lab values, only include tests that have an actual measured value in the text.
- Keep the summary to one plain-English sentence a non-medical person could understand.

Document text:
{document_text}
"""


def get_extraction_llm():
    """
    Returns a Gemini chat model bound to our ExtractionResult schema.
    temperature=0 because extraction should be deterministic and literal,
    unlike conversational QA which uses a higher temperature for natural phrasing.
    """
    llm = get_llm(temperature=0)
    return llm.with_structured_output(ExtractionResult)


def extract_structured_data(document_text: str) -> ExtractionResult:
    """
    Runs structured extraction on a document's raw text.
    Returns an ExtractionResult with diagnoses, medicines, lab_values, and a summary.
    """
    structured_llm = get_extraction_llm()
    prompt = EXTRACTION_PROMPT.format(document_text=document_text)

    try:
        result: ExtractionResult = structured_llm.invoke(prompt)
        logger.info(
            f"Extraction succeeded: {len(result.diagnoses)} diagnoses, "
            f"{len(result.medicines)} medicines, {len(result.lab_values)} lab values"
        )
        return result
    except Exception as e:
        logger.error(f"Structured extraction failed: {e}")
        raise