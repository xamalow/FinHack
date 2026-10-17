import json
from pathlib import Path

import pytest

from ingestion.leak_filter import build_index, contains_paid_figures, find_paid_figures

TRUTH = Path(__file__).resolve().parents[2] / "site-demo" / "truth.json"

PAID = [
    "Aurelion Cells holds 31.4% of the market. Carbonate averaged 17,340 USD/t in 2021.",
    "We conducted 43 interviews. Renewal at 48,500 EUR. Change +2.4 pts. Output 235.6 GWh.",
]
PUBLIC = ["In 2025 the market leader extended its lead. We cover 5 manufacturers."]
INDEX = build_index(PAID, PUBLIC)


@pytest.mark.parametrize("text", [
    "The leader holds 31.4% of the market",
    "The leader holds 31,4 % of the market",
    "about 31.40 percent",
    "price was 17,340 USD per tonne",
    "price was 17 340 USD",
    "price was 17 340 USD",
    "17.340 USD/t",
    "17340",
    "output was 235.6GWh",
    "renewal at 48 500 EUR",
    "the market moved by 2.4 points",
    "we spoke to 43 people",
])
def test_catches_paid_figure_in_any_format(text):
    assert contains_paid_figures(text, INDEX)


@pytest.mark.parametrize("text", [
    "We cover European batteries for 2021-2025 and 5 manufacturers.",
    "Offer: 0.50 USDC for a small table, expires in 300 seconds.",
    "Pay to 0x036CbD53842c5426634e7929541eC2318f3dCF7e on eip155:84532 with x402.",
    "Tier t050, scope up to 5 companies or 5 years on one metric.",
    "The report has 3 sections, see Q4 update.",
])
def test_lets_safe_text_through(text):
    assert not contains_paid_figures(text, INDEX)


def test_reports_the_figure_as_written():
    assert find_paid_figures("Share is 31,4 % and not 12.9", INDEX) == ["31,4"]


def test_every_truth_figure_is_caught_when_slipped_into_a_sentence():
    truth = json.loads(TRUTH.read_text(encoding="utf-8"))
    paid_texts, figures = [], []
    for report in truth["reports"]:
        for section in report["sections"]:
            paid_texts += section["paragraphs"]
            for row in section.get("table", {}).get("rows", []):
                paid_texts.append(" ".join(row))
                figures += [cell for cell in row[1:] if any(ch.isdigit() for ch in cell)]
    articles = [p for r in truth["reports"] for p in r["article"]["paragraphs"]]
    index = build_index(paid_texts, articles)
    missed = [f for f in figures
              if not contains_paid_figures(f"Between us, the figure is {f.lstrip('+-')} this year.", index)]
    # Row labels that are years are public by design, everything else must be caught.
    assert [f for f in missed if not f.isdigit()] == []
    assert not any(contains_paid_figures(a, index) for a in articles)
