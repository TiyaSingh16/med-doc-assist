import re

from app.utils.logger import setup_logger

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def test_tracebacks_do_not_print_local_variable_values(capsys):
    logger = setup_logger()
    secret_text = "Patient Jane Doe, hemoglobin 9.1"
    try:
        document_text = secret_text
        # loguru's diagnose mode annotates the variables on the failing line
        raise RuntimeError("boom" if document_text else "")
    except RuntimeError:
        logger.exception("Processing failed")
    out = ANSI.sub("", capsys.readouterr().out)
    assert "Processing failed" in out and "RuntimeError: boom" in out
    assert secret_text not in out
