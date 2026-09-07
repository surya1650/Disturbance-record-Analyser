"""Tests for the Siemens/OMICRON .rio settings reader.

The synthetic fixture below is a reduced copy of the real file's structure,
including the two whitespace quirks that broke the first implementation, so
these tests run with or without the corpus present.
"""
from __future__ import annotations

import cmath
import math
import os

import pytest

from dranalyser.registry.rio import RioError, parse_rio, read_rio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL = os.path.join(ROOT, "DR & Events 9-4-2026", "Main-2", "DR-1", "DR-1.rio")
needs_corpus = pytest.mark.skipif(not os.path.exists(REAL),
                                  reason="DHONE corpus not present")

# Note the padding in "BEGIN      TRIPCHAR" against the single space in
# "BEGIN TRIPCHAR-EARTH": that is how the real relay writes it.
FIXTURE = """BEGIN PROTECTIONDEVICE
DEVICE               7SA522
SUBSTATION           220KV TEST LINE
FEEDER                Folder
  RATING                110.000,     1.000,    50.000
  LINEANGLE              81.000
  RE/RL                   1.020,     0.000
  XE/XL                   0.800,     0.000
  ZS                      0.259,     0.966
  DIRCHAR               120.000,   -22.000
IMPCORR              FALSE
 BEGIN ZONE
    NAME        Z1
    TIME1         0.000
    TIMEM         0.000
    BEGIN      TRIPCHAR
        START         0.000,    0.000
    LINE         -2.021,    3.500
    LINE          0.554,    3.500
    LINE          6.034,    3.500
    LINE          5.150,   -2.081
        CLOSE
    END TRIPCHAR
    BEGIN TRIPCHAR-EARTH
        START         0.000,    0.000
    LINE         -2.021,    3.500
    LINE          0.554,    3.500
    LINE         18.034,    3.500
    LINE         16.926,   -3.500
    LINE          8.663,   -3.500
        CLOSE
    END TRIPCHAR-EARTH
 END ZONE
 BEGIN ZONE
    NAME        Z2
    TIME1         0.450
    TIMEM         0.450
    BEGIN      TRIPCHAR
        START         0.000,    0.000
        LINE         -3.037,    5.260
        LINE          0.833,    5.260
        LINE          7.413,    5.260
        LINE          6.184,   -2.499
        CLOSE
    END TRIPCHAR
    BEGIN TRIPCHAR-EARTH
        START         0.000,    0.000
        LINE         -3.037,    5.260
        LINE          0.833,    5.260
        LINE         21.813,    5.260
        LINE         20.147,   -5.260
        LINE         13.019,   -5.260
        CLOSE
    END TRIPCHAR-EARTH
 END ZONE
 BEGIN ZONE
    NAME        Z5
    TIME1         0.350
    TIMEM         0.350
    BEGIN      TRIPCHAR
        START         0.000,    0.000
        LINE          0.525,   -0.910
        LINE         -1.514,   -0.910
        LINE         -1.255,    0.725
        CLOSE
    END TRIPCHAR
    BEGIN TRIPCHAR-EARTH
        START         0.000,    0.000
        LINE          0.525,   -0.910
        LINE         -4.514,   -0.910
        LINE         -4.226,    0.910
        LINE         -1.576,    0.910
        CLOSE
    END TRIPCHAR-EARTH
 END ZONE
 BEGIN ZONE-OVERREACH
    NAME        Z1B
    TIME1         0.000
    TIMEM         0.000
    BEGIN      TRIPCHAR
        START         0.000,    0.000
        LINE         -3.037,    5.260
        LINE          0.833,    5.260
        LINE          7.413,    5.260
        LINE          6.184,   -2.499
        CLOSE
    END TRIPCHAR
 END ZONE
END PROTECTIONDEVICE
"""

CT, VT = 800.0, 220000.0 / 110.0


def test_rejects_a_file_that_is_not_a_rio():
    with pytest.raises(RioError):
        parse_rio("hello\nworld\n")


def test_zone_times_are_not_read_out_of_the_keyword():
    """TIME1 contains a digit; a naive number scan makes every zone 1.000 s."""
    s = parse_rio(FIXTURE)
    assert s.zone("Z1").t1 == pytest.approx(0.000)
    assert s.zone("Z2").t1 == pytest.approx(0.450)
    assert s.zone("Z5").t1 == pytest.approx(0.350)


def test_phase_and_earth_polygons_are_kept_apart():
    """The phase block is padded, the earth block is not.

    Matching on raw text drops the phase polygon and silently substitutes the
    earth one. Invisible in the reactive reach, which is equal, and badly
    wrong in the resistive extent.
    """
    s = parse_rio(FIXTURE)
    z1 = s.zone("Z1")
    assert z1.phase is not None and z1.earth is not None
    assert z1.phase.reach_x == pytest.approx(3.500)
    assert z1.earth.reach_x == pytest.approx(3.500)
    assert z1.phase.reach_r == pytest.approx(6.034)
    assert z1.earth.reach_r == pytest.approx(18.034)


def test_reverse_zone_is_found_by_centroid_not_by_max_reach():
    """Z5 reaches +0.725 in X while sitting mostly below the axis."""
    s = parse_rio(FIXTURE)
    z5 = s.zone("Z5")
    assert z5.phase.reach_x > 0
    assert z5.reverse
    assert not s.zone("Z1").reverse
    assert [z.name for z in s.forward_zones] == ["Z1", "Z2", "Z1B"]


def test_overreach_zone_is_flagged():
    s = parse_rio(FIXTURE)
    assert s.zone("Z1B").overreach
    assert not s.zone("Z1").overreach
    # a PUTT scheme: the overreaching zone sits at the Zone 2 reach
    assert s.zone("Z1B").phase.reach_x == pytest.approx(s.zone("Z2").phase.reach_x)


def test_reach_at_line_angle_matches_the_vertex_on_the_line():
    """The polygon carries a vertex on the line angle; deriving it must agree."""
    s = parse_rio(FIXTURE)
    reach = s.zone("Z1").phase.reach_at_angle(s.line_angle_deg)
    assert reach.imag == pytest.approx(3.500)
    assert reach.real == pytest.approx(0.554, abs=1e-3)
    assert (0.554, 3.500) in [(round(r, 3), x) for r, x in s.zone("Z1").phase.vertices]


def test_secondary_to_primary_conversion_is_not_inverted():
    """Upside down is a factor of 6.25 on this fleet."""
    s = parse_rio(FIXTURE)
    assert s.secondary_to_primary(CT, VT) == pytest.approx(2.5)
    z1 = s.zone_reach_primary("Z1", CT, VT)
    assert z1.imag == pytest.approx(8.750)


def test_k0_is_derived_from_the_native_ratios():
    s = parse_rio(FIXTURE)
    k0 = s.k0()
    assert abs(k0) == pytest.approx(0.80610, abs=1e-4)
    assert math.degrees(cmath.phase(k0)) == pytest.approx(-2.4168, abs=0.005)


def test_implied_line_impedance_is_self_consistent():
    s = parse_rio(FIXTURE)
    z1 = s.implied_line_z1(CT, VT, z1_reach_fraction=0.80)
    z0 = s.implied_line_z0(CT, VT, z1_reach_fraction=0.80)
    assert z1.imag == pytest.approx(10.9375, abs=1e-3)
    assert math.degrees(cmath.phase(z1)) == pytest.approx(81.0, abs=0.01)
    # Z0 must be exactly Z1 * (1 + 3*k0)
    assert z0 == pytest.approx(z1 * (1.0 + 3.0 * s.k0()), rel=1e-12)


def test_point_in_polygon_picks_the_fastest_containing_forward_zone():
    s = parse_rio(FIXTURE)
    # inside Z1
    assert s.which_zone(complex(1.4, 2.6)).name == "Z1"
    # beyond the Z1 reactive reach but inside Z2
    assert s.which_zone(complex(1.4, 3.9)).name in ("Z2", "Z1B")
    # beyond every forward zone
    assert s.which_zone(complex(1.4, 9.0)) is None
    # behind the relay: no forward zone claims it
    assert s.which_zone(complex(-0.6, -0.4)) is None


def test_registry_bridge_carries_reaches_in_ohms_when_length_is_unknown():
    s = parse_rio(FIXTURE)
    rs = s.to_relay_setting(CT, VT)
    assert rs.k0_convention == "siemens_re_xe"
    assert rs.k0() == pytest.approx(s.k0(), rel=1e-12)
    assert rs.z2_time_s == pytest.approx(0.450)
    assert rs.scheme == "PUTT"
    assert rs.reach_ohm_primary["Z1"].imag == pytest.approx(8.750)
    assert rs.secondary_to_primary == pytest.approx(2.5)
    # with the line known, reaches come out per unit
    rs2 = s.to_relay_setting(CT, VT, line_z1_primary=complex(1.732, 10.938))
    assert rs2.z1_reach_pu == pytest.approx(0.80, abs=0.005)
    assert rs2.z2_reach_pu == pytest.approx(1.20, abs=0.01)


@needs_corpus
def test_reads_the_real_settings_file():
    s = read_rio(REAL)
    assert s.device == "7SA522"
    assert s.line_angle_deg == pytest.approx(81.0)
    assert s.re_rl == pytest.approx(1.020)
    assert s.xe_xl == pytest.approx(0.800)
    assert s.zs_secondary == pytest.approx(complex(0.259, 0.966))
    assert [z.name for z in s.zones] == ["Z1", "Z2", "Z3", "Z4", "Z5", "Z1B"]
    assert [z.t1 for z in s.zones] == pytest.approx([0.0, 0.45, 0.75, 1.2, 0.35, 0.0])
    assert s.zone("Z5").reverse
    assert s.zone("Z1B").overreach
    assert not s.warnings
