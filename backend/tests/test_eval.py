from eval import run
from eval.dataset import QUESTIONS, REPORTS


def test_dataset_questions_point_at_real_pages_and_keywords():
    for report, _question, page, keyword in QUESTIONS:
        assert keyword.lower() in REPORTS[report][page - 1].lower()


def test_keyword_baseline_runs_and_reports_valid_metrics():
    hits, mrr = run.evaluate(run.KeywordRetriever, chunk_size=500, ks=[1, 4])
    assert 0 <= hits[1] <= hits[4] <= 1
    assert 0 <= mrr <= 1
