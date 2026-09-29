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


def test_cemetery_by_name_is_excluded():
    assert _is_excluded({"primaryType": "park", "types": ["park"],
                         "displayName": {"text": "בית העלמין חוף הכרמל"}})


def test_blocklisted_id_is_excluded():
    assert _is_excluded({"id": "ChIJ6x8sJ_e7HRURYmDH38A6sIA", "primaryType": "park", "types": ["park"]})


def test_spring_is_nature():
    p = {"primaryType": "park", "types": ["park"], "displayName": {"text": "עין שיח"}}
    assert _category_for(p, "park") == "nature"
    p = {"primaryType": "park", "types": ["park"], "displayName": {"text": "Ein Kerem Spring"}}
    assert _category_for(p, "park") == "nature"


def test_park_named_like_town_stays_park():
    # "Ein" inside a word must not trigger; museums are never reclassified
    assert _category_for({"primaryType": "park", "types": ["park"], "displayName": {"text": "Gan Meir Park"}}, "park") == "park"
    assert _category_for({"primaryType": "museum", "types": ["museum"], "displayName": {"text": "מוזיאון עין הוד"}}, "museum") == "museum"


def test_clinic_named_maayan_is_not_nature():
    from server import _is_natural
    assert not _is_natural({"primaryType": "doctor", "types": ["doctor", "health"]})
    assert _is_natural({"primaryType": "park", "types": ["park"]})
    assert _is_natural({"primaryType": "tourist_attraction", "types": ["tourist_attraction", "natural_feature"]})
