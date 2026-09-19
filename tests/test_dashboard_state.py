"""Dashboard state must not retain stale healthy-looking results after failures."""
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]


def make_app():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(str(ROOT / "app/main.py"))


def test_rejected_batch_persists_and_does_not_export():
    class Upload:
        name, size = "bad.csv", 12

        def getvalue(self):
            return b"bad_header\n1\n"

    with patch("streamlit.file_uploader", return_value=Upload()):
        app = make_app().run()
        next(button for button in app.button if button.label == "Analyse").click().run()
        assert not app.exception
        assert app.error
        assert not app.session_state["exports"]
        assert not app.session_state["decisions"]
        app.run()
        assert app.error
        assert app.session_state["failures"]["door"]["status"] == "rejected"


def test_changing_bundle_immediately_clears_stale_session_outputs():
    app = make_app().run()
    app.session_state["exports"] = {"door": b"stale"}
    app.session_state["decisions"] = {"door": {"old.csv": []}}
    app.sidebar.text_input[0].set_value("/nonexistent/model/bundle").run()
    assert not app.exception
    assert not app.session_state["exports"]
    assert not app.session_state["decisions"]


def test_clear_session_removes_rejections_and_predictions():
    app = make_app().run()
    app.session_state["failures"] = {"door": {"status": "rejected", "error": "bad input"}}
    next(button for button in app.button if button.label == "Clear session predictions").click().run()
    assert not app.session_state["failures"]
