"""`$why` proposition flattening — the data behind the WhyCards factors.

Plain pytest unit tests — no Aito calls.

A `$why` proposition arrives shaped differently on the two APIs, and
reading only one encoding fails SILENTLY: v1 groups ANDed propositions
under `$and` and wraps values in an operator (`$has`, `$numeric`); v2
(Rep2) groups under `$group` and encodes text matches as `$match`. Miss
`$group` and the factor renders with no conditions at all; miss a value
wrapper and the raw `{'$match': ...}` dict is printed into the UI. Both
are the demo-effect class that reached a partner meeting in the
accounting demo, where `$why` degraded to a bare base rate with no error.

This repo is on the v2 branch, so the v2 encoding is the live one.
"""

from __future__ import annotations

from src.predict_service import _iter_propositions


def test_v1_and_conjunction_with_has_wrapper():
    prop = {"$and": [
        {"title": {"$has": "rust"}},
        {"domain": {"$has": "github.com"}},
    ]}
    assert list(_iter_propositions(prop)) == [
        ("title", "rust"),
        ("domain", "github.com"),
    ]


def test_v2_group_conjunction_with_match_wrapper():
    """The live-path regression: `$group` + `$match` must flatten to the
    same pairs v1 produces — not an empty list, not a raw dict."""
    prop = {"$group": [
        {"title": {"$match": "rust"}},
        {"domain": "github.com"},
    ]}
    assert list(_iter_propositions(prop)) == [
        ("title", "rust"),
        ("domain", "github.com"),
    ]


def test_v1_and_v2_encodings_agree():
    v1 = {"$and": [{"title": {"$has": "rust"}}]}
    v2 = {"$group": [{"title": {"$match": "rust"}}]}
    assert list(_iter_propositions(v1)) == list(_iter_propositions(v2))


def test_numeric_envelope_is_coerced_to_int_when_whole():
    """Aito returns Int columns as floats; the UI should not show '9.0'."""
    assert list(_iter_propositions({"hour": {"$numeric": 9.0}})) == [("hour", 9)]


def test_unknown_single_operator_yields_its_value_not_a_raw_dict():
    """Guard against a future operator printing `{'$whatever': 'x'}` into
    the card — the reader must never see a serialised wrapper."""
    assert list(_iter_propositions({"title": {"$whatever": "rust"}})) == [
        ("title", "rust"),
    ]


def test_bare_value_passes_through():
    assert list(_iter_propositions({"domain": "github.com"})) == [
        ("domain", "github.com"),
    ]
