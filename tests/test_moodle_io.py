import pandas as pd

from scoring.moodle_io import load_column_map, read_moodle_export


def test_english_headers_and_filters(tmp_path):
    df = pd.DataFrame({
        "Surname": ["Smith", "Doe", "Overall average"], "First name": ["Ann", "John", ""],
        "Email address": ["a@x.org", "j@x.org", ""], "State": ["Finished", "In progress", ""],
        "IP address": ["1.2.3.4", "5.6.7.8", ""],
        "Response 1": ["<p>Labelled data&nbsp;is used</p>", "x", ""], "Response 2": ["-", "y", ""],
    })
    p = tmp_path / "e.xlsx"
    df.to_excel(p, index=False)
    recs = read_moodle_export(p, load_column_map())
    assert len(recs) == 2                      # devam eden deneme ve ortalama satırı atıldı
    assert recs[0].text == "Labelled data is used"
    assert recs[1].is_empty and recs[1].text == ""
    assert "IP address" not in str(recs[0].__dict__)
