from app.ai.chains import get_llm
from app.schemas.comparison import ComparisonResult
from app.schemas.extraction import ExtractionResult
from app.utils.logger import setup_logger

logger = setup_logger()


COMPARISON_PROMPT = """You are a medical document comparison assistant.
You are given two structured summaries extracted from a patient's medical documents,
taken at two different points in time. Document A is the earlier document, Document B is the later one.

Compare them and identify what changed between A and B:
- For lab values present in both, determine if the trend improved, worsened, or stayed unchanged
  (use clinical judgment: e.g. a lower fasting blood sugar is an improvement, a higher one is worse).
- For lab values only in one document, mark them as 'new' (only in B) or 'resolved' (only in A, no longer tracked).
- For medications, note anything added, removed, or with a changed dosage.
- For diagnoses, note anything new or resolved.
- Do not invent data that isn't present in either document.

Document A (earlier):
{document_a}

Document B (later):
{document_b}
"""


def get_comparison_llm():
    llm = get_llm(temperature=0)
    return llm.with_structured_output(ComparisonResult)


def compare_documents(extraction_a: ExtractionResult, extraction_b: ExtractionResult) -> ComparisonResult:
    """
    Compares two structured extraction results and returns what changed between them.
    """
    structured_llm = get_comparison_llm()
    prompt = COMPARISON_PROMPT.format(
        document_a=extraction_a.model_dump_json(indent=2),
        document_b=extraction_b.model_dump_json(indent=2),
    )

    try:
        result: ComparisonResult = structured_llm.invoke(prompt)
        logger.info(
            f"Comparison succeeded: {len(result.lab_value_changes)} lab changes, "
            f"{len(result.medication_changes)} medication changes, "
            f"{len(result.diagnosis_changes)} diagnosis changes"
        )
        return result
    except Exception as e:
        logger.error(f"Document comparison failed: {e}")
        raise