from dranalyser.workbench.record_names import record_display_name, saved_display_name


def test_specific_filename_names_take_precedence_over_generic_relay_headers():
    assert record_display_name('Substation_One.cfg', station='MiCOM') == 'Substation One'
    assert record_display_name('other/TerminalTwo.CFF', station='CSC999A') == 'TerminalTwo'
    assert record_display_name('TerminalTwo.cfg', explicit='Reviewed station') == 'Reviewed station'


def test_generic_filename_uses_folder_then_meaningful_header_without_assigning_end():
    assert record_display_name('North_station/event.cfg', station='Relay') == 'North station'
    assert record_display_name('event.cfg', station='Meaningful station') == 'Meaningful station'
    assert record_display_name('DR1.cfg', station='MiCOM') == 'DR1'


def test_saved_physical_label_matches_exact_record_only_and_explicit_display_wins():
    row = dict(metadata=dict(incident_line=dict(review=dict(ends={
        'R': dict(record='two.cfg', name='User station')}))))
    assert saved_display_name(row, 'two.cfg') == 'User station'
    assert saved_display_name(row, 'one.cfg') == 'one'
    assert saved_display_name(row, 'two.cfg', explicit='Observation label') == 'Observation label'
