"""GSC priority-pages upload parser (U1) — contract tests against the REAL
`priority_pages.json` shape (per the 2026-08-14 handoff plan §3).

The fixture mirrors an actual produced file (livingsystems.ca, monthly-2026-08-10):
bare-host `site`, per-page {url, path, clicks, impressions, avg_position,
top_queries:[str], inquiries}.
"""

from __future__ import annotations

import pytest

from api.services.gsc_priority import (
    PriorityUploadError,
    parse_priority_upload,
    seed_urls,
)

REAL = {
    "generated_for": "talkingtoad",
    "site": "livingsystems.ca",   # bare host (not a full origin) — as produced
    "source": ".../pages.csv",
    "count": 3,
    "pages": [
        {"url": "https://livingsystems.ca/", "path": "/", "clicks": 138,
         "impressions": 1494, "avg_position": 23.5,
         "top_queries": ["living systems counselling", "living systems"], "inquiries": 1},
        {"url": "https://livingsystems.ca/emotional-pain-and-suffering/", "path": "/e",
         "clicks": 20, "impressions": 900, "avg_position": 8.1,
         "top_queries": ["emotional pain"], "inquiries": 0},
        {"url": "https://livingsystems.ca/differentiation/", "path": "/d",
         "clicks": 5, "impressions": 300, "avg_position": 12.0,
         "top_queries": [], "inquiries": 0},
    ],
}
TARGET = "https://livingsystems.ca"


def test_u1_parses_real_shape_order_and_derived_fields():
    seed = parse_priority_upload(REAL, TARGET)
    assert seed["used"] == 3 and seed["total"] == 3
    # order preserved (file order == priority order)
    assert seed_urls(seed) == [
        "https://livingsystems.ca/",
        "https://livingsystems.ca/emotional-pain-and-suffering/",
        "https://livingsystems.ca/differentiation/",
    ]
    home = seed["pages"][0]
    assert home["clicks"] == 138 and home["impressions"] == 1494
    assert home["position"] == 23.5            # avg_position → position
    assert home["conversions"] == 1            # inquiries → conversions
    assert home["top_queries"] == ["living systems counselling", "living systems"]
    # ctr derived = 138/1494
    assert home["ctr"] == pytest.approx(138 / 1494)


def test_u1_zero_impressions_ctr_is_zero_not_crash():
    raw = {"pages": [{"url": "https://livingsystems.ca/x", "clicks": 0,
                      "impressions": 0, "avg_position": 0, "inquiries": 0}]}
    seed = parse_priority_upload(raw, TARGET)
    assert seed["pages"][0]["ctr"] == 0.0


def test_u1_off_domain_rows_held_out_and_announced():
    raw = {"pages": [
        {"url": "https://livingsystems.ca/keep", "clicks": 3, "impressions": 10},
        {"url": "https://evil.example.com/drop", "clicks": 99, "impressions": 100},
    ]}
    seed = parse_priority_upload(raw, TARGET)
    assert seed["used"] == 1
    assert seed["held_out_offdomain"] == 1
    assert seed_urls(seed) == ["https://livingsystems.ca/keep"]


def test_u1_blank_url_rows_skipped():
    raw = {"pages": [
        {"url": "", "clicks": 1}, {"clicks": 2}, "notadict",
        {"url": "https://livingsystems.ca/ok", "clicks": 3, "impressions": 6},
    ]}
    seed = parse_priority_upload(raw, TARGET)
    assert seed["used"] == 1 and seed["held_out_blank"] == 3


def test_u1_wrong_site_file_rejected():
    """Every page off-domain → the whole file is the wrong site's; reject clearly."""
    raw = {"pages": [{"url": "https://someothersite.org/a", "clicks": 5}]}
    with pytest.raises(PriorityUploadError, match="right"):
        parse_priority_upload(raw, TARGET)


def test_u1_malformed_no_pages_rejected():
    for bad in ({}, {"pages": []}, {"pages": "nope"}, "string"):
        with pytest.raises(PriorityUploadError):
            parse_priority_upload(bad, TARGET)


def test_u1_string_metrics_coerced():
    """GSC CSVs can yield stringy numbers; parser coerces without crashing."""
    raw = {"pages": [{"url": "https://livingsystems.ca/s", "clicks": "7",
                      "impressions": "20", "avg_position": "9.5", "inquiries": "2"}]}
    p = parse_priority_upload(raw, TARGET)["pages"][0]
    assert p["clicks"] == 7 and p["impressions"] == 20
    assert p["position"] == 9.5 and p["conversions"] == 2
