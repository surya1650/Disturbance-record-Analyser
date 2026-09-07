"""The vendor-neutral settings model and the importer sniffing.

The RIO parser itself is covered by tests/test_rio.py; what is new here is
that the analyser no longer names a vendor type, that a characteristic can be
something other than a polygon, and that an ambiguous file is refused.
"""
from __future__ import annotations

import cmath
import math
import os

import pytest

from dranalyser.registry.settings import (MhoChar, PolygonChar,
                                          ProtectionSettings, SettingsError,
                                          Zone, quad_char)
from dranalyser.registry.settings_io import load_settings, sniff
from dranalyser.registry.settings_io import rio as rio_importer

RIO_FIXTURE = """DEVICE 7SA522
SUBSTATION TESTSTN
RATING 110.0 1.0 50.0
LINEANGLE 80.0
RE/RL 1.020
XE/XL 0.800
BEGIN ZONE
NAME Z1
TIME1 0.000
BEGIN TRIPCHAR
START 0.000, 0.000
LINE 6.034, 0.000
LINE 6.034, 3.500
LINE 0.617, 3.500
CLOSE
END TRIPCHAR
END ZONE
"""


# --------------------------------------------------------------------------
# characteristics
# --------------------------------------------------------------------------
def test_a_mho_circle_passes_through_the_origin_and_its_diameter():
    """Standard mho geometry, not inferred from any vendor file."""
    ch = MhoChar(kind="phase", diameter=cmath.rect(10.0, math.radians(75.0)))
    assert ch.contains(0j)                      # the origin is on the circle
    assert ch.contains(ch.diameter)             # so is the far end
    assert ch.contains(ch.diameter * 0.5)       # the centre is well inside
    assert not ch.contains(ch.diameter * 1.2)   # beyond the reach
    assert abs(ch.radius - 5.0) < 1e-9


def test_a_mho_reach_along_a_ray_follows_the_cosine_law():
    """For a circle through the origin, reach at angle a is |D|cos(a - theta)."""
    theta = 75.0
    ch = MhoChar(diameter=cmath.rect(10.0, math.radians(theta)))
    on_axis = ch.reach_at_angle(theta)
    assert abs(on_axis) == pytest.approx(10.0)
    off = ch.reach_at_angle(theta - 60.0)
    assert abs(off) == pytest.approx(10.0 * math.cos(math.radians(60.0)))
    # a load point 90 degrees off the characteristic angle is not seen at all
    assert not ch.contains(cmath.rect(8.0, math.radians(theta - 90.0)))


def test_a_quadrilateral_is_built_as_the_polygon_it_is():
    ch = quad_char(reach_x=5.0, r_right=3.0, r_left=1.0, tilt_deg=0.0)
    assert isinstance(ch, PolygonChar)
    assert ch.reach_x == pytest.approx(5.0)
    assert ch.contains(complex(1.0, 2.0))
    assert not ch.contains(complex(4.0, 2.0))     # outside the right blinder
    assert not ch.contains(complex(1.0, 6.0))     # beyond the reach


def test_a_drooping_reactance_line_shortens_the_resistive_corner():
    """Tilt is what stops a quad overreaching on a resistive fault."""
    flat = quad_char(reach_x=5.0, r_right=4.0, r_left=1.0, tilt_deg=0.0)
    drooped = quad_char(reach_x=5.0, r_right=4.0, r_left=1.0, tilt_deg=15.0)
    probe = complex(3.5, 4.6)
    assert flat.contains(probe)
    assert not drooped.contains(probe)


def test_a_reverse_zone_is_found_from_the_centroid_for_any_shape():
    fwd = Zone("Z1", phase=MhoChar(diameter=complex(1.0, 6.0)))
    rev = Zone("Z5", phase=MhoChar(diameter=complex(-0.5, -3.0)))
    assert not fwd.reverse and rev.reverse


# --------------------------------------------------------------------------
# k0 comes from the vendor's native form, never typed in
# --------------------------------------------------------------------------
def test_k0_is_derived_from_whichever_convention_the_importer_recorded():
    siemens = ProtectionSettings(line_angle_deg=81.0,
                                 k0_convention="siemens_re_xe",
                                 k0_params={"re_rl": 1.02, "xe_xl": 0.80})
    abb = ProtectionSettings(k0_convention="abb_kn",
                             k0_params={"kn_mag": 0.806, "kn_ang_deg": -2.41})
    assert siemens.k0() is not None
    assert abs(siemens.k0()) == pytest.approx(0.806, abs=0.01)
    assert abs(abb.k0()) == pytest.approx(0.806, abs=0.001)


def test_an_unknown_or_incomplete_convention_yields_no_k0_rather_than_a_guess():
    assert ProtectionSettings().k0() is None
    half = ProtectionSettings(k0_convention="siemens_re_xe",
                              k0_params={"re_rl": 1.02})
    assert half.k0() is None


# --------------------------------------------------------------------------
# importer selection
# --------------------------------------------------------------------------
def test_the_rio_importer_recognises_a_rio_and_not_a_stranger(tmp_path):
    good = tmp_path / "a.rio"
    good.write_text(RIO_FIXTURE, encoding="latin-1")
    assert rio_importer.confidence(RIO_FIXTURE, str(good)) > 0.8
    assert rio_importer.confidence("<?xml version='1.0'?><SCL/>", "b.xml") == 0.0


def test_load_settings_records_which_importer_read_the_file(tmp_path):
    p = tmp_path / "relay.rio"
    p.write_text(RIO_FIXTURE, encoding="latin-1")
    s = load_settings(str(p))
    assert s.provenance.fmt == "rio"
    assert s.vendor == "Siemens"
    assert len(s.provenance.sha256) == 64
    assert s.zone("Z1") is not None
    # the file is evidence: what was read stays visible
    assert "LINEANGLE" in s.raw


def test_an_unrecognised_file_is_refused_not_guessed_at(tmp_path):
    p = tmp_path / "mystery.xml"
    p.write_text("<?xml version='1.0'?><SCL><IED name='x'/></SCL>", encoding="latin-1")
    with pytest.raises(SettingsError, match="no importer recognises"):
        load_settings(str(p))


def test_two_importers_that_tie_are_refused_rather_than_resolved(tmp_path):
    """Never guess a format. A settings file read as the wrong vendor gives
    zone reaches that look plausible and are wrong."""
    class Fake:
        FORMAT = "fake"
        EXTENSIONS = (".rio",)

        @staticmethod
        def confidence(text, path=""):
            return 0.95

        @staticmethod
        def load(path):
            raise AssertionError("must never be reached")

    p = tmp_path / "relay.rio"
    p.write_text(RIO_FIXTURE, encoding="latin-1")
    with pytest.raises(SettingsError, match="cannot tell which format"):
        load_settings(str(p), importers=(rio_importer, Fake))


def test_a_missing_file_says_so(tmp_path):
    with pytest.raises(SettingsError, match="no such settings file"):
        load_settings(str(tmp_path / "nope.rio"))


def test_sniff_orders_the_candidates_best_first(tmp_path):
    p = tmp_path / "relay.rio"
    p.write_text(RIO_FIXTURE, encoding="latin-1")
    scored = sniff(str(p))
    assert scored[0][1] is rio_importer
    assert scored[0][0] > 0.8
