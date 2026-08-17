from core.edit_fx_vocabulary import speed_ramp_jsx


def test_speed_ramp_uses_composition_time_offset():
    jsx = speed_ramp_jsx(
        "layer20",
        source_dur=15.0,
        ramps=[{"t": 0.0, "v": 1.0}, {"t": 1.0, "v": 0.5}],
        offset=7.35,
        source_in=5.55,
    )
    assert 'setValueAtTime(7.350, 5.550)' in jsx
    assert 'setValueAtTime(8.350, 6.050)' in jsx
    assert 'setValueAtTime(0.000, 5.550)' not in jsx


def test_speed_ramp_default_offset_remains_zero():
    jsx = speed_ramp_jsx(
        "layer0",
        source_dur=10.0,
        ramps=[{"t": 0.0, "v": 1.0}],
        source_in=2.0,
    )
    assert 'setValueAtTime(0.000, 2.000)' in jsx
