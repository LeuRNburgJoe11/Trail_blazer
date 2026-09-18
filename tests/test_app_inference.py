"""Optional raw-data integration checks: actual app button -> frozen inference."""
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "outputs/combined/merged-main"


@pytest.mark.parametrize("subsystem,relative", [
    ("door", "data/Door/Test.csv"),
    ("acv", "data/acv/Test/acv_test_case.xlsx"),
    ("rail", "data/Rail_Corrugation/Test/Test1.csv"),
    ("shm", "data/SHM/Test/test01.csv"),
])
def test_app_predictions_match_batch(subsystem, relative):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    path = ROOT / relative
    if not path.exists():
        pytest.skip("Run prepare_data.py to enable real-upload integration checks")
    payload = path.read_bytes()

    class Upload:
        name = path.name
        size = len(payload)

        def getvalue(self):
            return payload

    def uploader(*args, **kwargs):
        return [Upload()] if kwargs["accept_multiple_files"] else Upload()

    with patch("streamlit.file_uploader", side_effect=uploader):
        app = AppTest.from_file(str(ROOT / "app/main.py")).run()
        app.selectbox[0].select(subsystem).run()
        next(button for button in app.button if button.label == "Analyse").click().run(timeout=60)
    assert not app.exception
    assert not app.error
    actual = pd.read_csv(BytesIO(app.session_state["exports"][subsystem]))
    expected = pd.read_csv(RUN / f"{subsystem}_predictions.csv")
    if subsystem != "door":
        expected = expected[expected.file_id == path.name].reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected)
