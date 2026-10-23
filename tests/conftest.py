from datetime import date

import pytest

from raildata import pipeline

START, END = date(2026, 3, 2), date(2026, 3, 4)


@pytest.fixture(scope="session")
def pipeline_run(tmp_path_factory):
    """One small end-to-end run (3 delivery days) shared by integration tests."""
    data_dir = tmp_path_factory.mktemp("data")
    result = pipeline.run(START, END, data_dir, seed=7, full_refresh=True)
    return data_dir, result
