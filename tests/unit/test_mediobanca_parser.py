"""Unit tests for the Mediobanca Premier parser.

All tests run against the anonymised fixture file — no DB, no network.
"""

from pathlib import Path

FIXTURE = Path("tests/fixtures/MediobancaPremier_anonimized.xlsx")
NOT_A_MEDIOBANCA_FILE = Path("tests/fixtures/.gitkeep")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_parser():
    from bilancio.parsers.mediobanca_premier import MediobancaPremierParser

    return MediobancaPremierParser()


# ---------------------------------------------------------------------------
# detect()
# ---------------------------------------------------------------------------


def test_detect_returns_true_for_mediobanca_fixture():
    assert _make_parser().detect(FIXTURE) is True


def test_detect_returns_false_for_non_xlsx():
    assert _make_parser().detect(NOT_A_MEDIOBANCA_FILE) is False


def test_detect_returns_false_for_missing_file():
    assert _make_parser().detect(Path("does_not_exist.xlsx")) is False


# ---------------------------------------------------------------------------
# parse() — basic shape
# ---------------------------------------------------------------------------


def test_parse_returns_list_of_transactions():
    txs = _make_parser().parse(FIXTURE, account_id=1)
    assert isinstance(txs, list)
    assert len(txs) > 0


def test_parse_skips_header_and_footer_rows():
    txs = _make_parser().parse(FIXTURE, account_id=1)
    # The fixture has 501 rows: 15 header + N data + 3 footer. We must get only data rows.
    assert len(txs) < 490  # well under raw row count
    assert len(txs) > 400  # but still a lot of real transactions


def test_parse_all_transactions_carry_account_id():
    txs = _make_parser().parse(FIXTURE, account_id=42)
    assert all(t.account_id == 42 for t in txs)


def test_parse_source_file_is_recorded():
    txs = _make_parser().parse(FIXTURE, account_id=1)
    assert all(t.source_file == str(FIXTURE) for t in txs)


def test_parse_source_row_is_recorded():
    txs = _make_parser().parse(FIXTURE, account_id=1)
    # source_row should reflect the 1-based spreadsheet row number
    assert all(isinstance(t.source_row, int) and t.source_row > 15 for t in txs)


# ---------------------------------------------------------------------------
# parse() — amounts
# ---------------------------------------------------------------------------


def test_parse_uscite_produces_negative_amount():
    """Row 16: POS -48.0 EUR should come out as a negative amount."""
    txs = _make_parser().parse(FIXTURE, account_id=1)
    first = txs[0]
    assert first.amount < 0


def test_parse_entrate_produces_positive_amount():
    """There should be at least one positive transaction (e.g. salary)."""
    txs = _make_parser().parse(FIXTURE, account_id=1)
    positives = [t for t in txs if t.amount > 0]
    assert len(positives) > 0


def test_parse_no_zero_amounts():
    txs = _make_parser().parse(FIXTURE, account_id=1)
    assert all(t.amount != 0 for t in txs)


# ---------------------------------------------------------------------------
# parse() — dates
# ---------------------------------------------------------------------------


def test_parse_value_date_is_datetime():
    from datetime import datetime

    txs = _make_parser().parse(FIXTURE, account_id=1)
    assert all(isinstance(t.value_date, datetime) for t in txs)


def test_parse_booking_date_is_none_or_datetime():
    from datetime import datetime

    txs = _make_parser().parse(FIXTURE, account_id=1)
    assert all(
        t.booking_date is None or isinstance(t.booking_date, datetime) for t in txs
    )


def test_parse_first_transaction_value_date():
    """Row 16 has value_date 11/04/2026."""
    from datetime import date

    txs = _make_parser().parse(FIXTURE, account_id=1)
    assert txs[0].value_date.date() == date(2026, 4, 11)


# ---------------------------------------------------------------------------
# parse() — currency
# ---------------------------------------------------------------------------


def test_parse_currency_is_eur():
    txs = _make_parser().parse(FIXTURE, account_id=1)
    assert all(t.currency == "EUR" for t in txs)


# ---------------------------------------------------------------------------
# parse() — description & transaction type
# ---------------------------------------------------------------------------


def test_parse_description_raw_is_set():
    txs = _make_parser().parse(FIXTURE, account_id=1)
    assert all(t.description_raw for t in txs)


def test_parse_transaction_type_is_set():
    txs = _make_parser().parse(FIXTURE, account_id=1)
    assert all(t.transaction_type for t in txs)


def test_parse_pos_transaction_type():
    txs = _make_parser().parse(FIXTURE, account_id=1)
    pagam_pos = [t for t in txs if t.transaction_type == "Pagam. POS"]
    assert len(pagam_pos) > 100  # most transactions are card payments


def test_parse_salary_transaction_type():
    txs = _make_parser().parse(FIXTURE, account_id=1)
    salaries = [t for t in txs if t.transaction_type == "Stipendio"]
    assert len(salaries) > 0
    assert all(t.amount > 0 for t in salaries)


# ---------------------------------------------------------------------------
# parse() — merchant_clean
# ---------------------------------------------------------------------------


def test_parse_pagam_pos_merchant_extracted():
    """'Pagam. POS - PAGAMENTO POS ... A (ITA) TRENITALIA - PT WL  CARTA...' → 'TRENITALIA - PT WL'"""
    txs = _make_parser().parse(FIXTURE, account_id=1)
    trenitalia = [
        t for t in txs if t.merchant_clean and "TRENITALIA" in t.merchant_clean
    ]
    assert len(trenitalia) > 0


def test_parse_sdd_merchant_extracted():
    """'Addebito SDD - ILIAD               -...' → 'ILIAD'"""
    txs = _make_parser().parse(FIXTURE, account_id=1)
    iliad = [t for t in txs if t.merchant_clean and "ILIAD" in t.merchant_clean]
    assert len(iliad) > 0


def test_parse_stipendio_merchant_is_employer():
    """Salary transactions should have the employer as merchant_clean."""
    txs = _make_parser().parse(FIXTURE, account_id=1)
    salaries = [t for t in txs if t.transaction_type == "Stipendio"]
    assert all(t.merchant_clean for t in salaries)


def test_parse_disposizione_merchant_is_beneficiary():
    """'Disposizione - RIF:...BEN. Immobiliare Riva Di Reno...' → beneficiary name."""
    txs = _make_parser().parse(FIXTURE, account_id=1)
    disposizioni = [t for t in txs if t.transaction_type == "Disposizione"]
    assert all(t.merchant_clean for t in disposizioni)


# ---------------------------------------------------------------------------
# parse() — dedup hash
# ---------------------------------------------------------------------------


def test_parse_hash_is_sha256_hex():
    txs = _make_parser().parse(FIXTURE, account_id=1)
    assert all(len(t.hash) == 64 for t in txs)
    assert all(all(c in "0123456789abcdef" for c in t.hash) for t in txs)


def test_parse_hashes_are_unique_within_file():
    txs = _make_parser().parse(FIXTURE, account_id=1)
    hashes = [t.hash for t in txs]
    assert len(hashes) == len(set(hashes)), (
        "Duplicate hashes found within a single import"
    )


def test_parse_is_idempotent():
    """Parsing the same file twice must produce identical hashes in the same order."""
    p = _make_parser()
    first = [t.hash for t in p.parse(FIXTURE, account_id=1)]
    second = [t.hash for t in p.parse(FIXTURE, account_id=1)]
    assert first == second


# ---------------------------------------------------------------------------
# BankParser Protocol conformance
# ---------------------------------------------------------------------------


def test_parser_implements_protocol():
    from bilancio.parsers.base import BankParser

    assert isinstance(_make_parser(), BankParser)


def test_bank_name():
    assert _make_parser().bank_name == "Mediobanca Premier"
