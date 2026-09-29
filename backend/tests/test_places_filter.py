"""Unit tests for Google Places result filtering (no network)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import _is_excluded, _category_for  # noqa: E402


def test_cemetery_tagged_park_is_excluded():
    assert _is_excluded({"primaryType": "cemetery", "types": ["cemetery", "park", "point_of_interest"]})


def test_synagogue_tagged_museum_is_excluded():
    assert _is_excluded({"primaryType": "synagogue", "types": ["synagogue", "place_of_worship", "museum"]})


def test_hotel_is_excluded():
    assert _is_excluded({"primaryType": "hotel", "types": ["hotel", "lodging", "park"]})


def test_real_park_kept_and_categorised():
    p = {"primaryType": "park", "types": ["park", "tourist_attraction"]}
    assert not _is_excluded(p)
    assert _category_for(p, "museum") == "park"


def test_beach_kept():
    p = {"primaryType": "beach", "types": ["beach", "natural_feature"]}
    assert not _is_excluded(p)
    assert _category_for(p, "park") == "beach"
