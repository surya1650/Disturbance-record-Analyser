"""Display labels are optional and never substitute for physical end evidence."""
import copy

import pytest

from dranalyser.workbench import event_study as study
from tests import test_event_study as fixtures

model=fixtures.model


@pytest.mark.parametrize('value', [None,'','   '])
def test_missing_display_label_uses_filename_without_inventing_station(model,value):
    _,row=model
    chosen=fixtures.inputs()
    chosen['ends']['S']['substation']=value
    prepared,_=study.prepare_inputs('.',row,chosen)
    assert prepared['ends']['S']['substation']=='S/event.cfg'
    report=study.build_event_report('.',row,chosen)
    assert report['ends']['S']['substation']=='S/event.cfg'
    assert report['distance']['km_from_S'] is None
    assert report['authorizes_location'] is False
    del chosen['ends']['S']['substation']
    assert study.prepare_inputs('.',row,chosen)[0]['ends']['S']['substation']=='S/event.cfg'


def test_supplied_display_label_is_preserved(model):
    _,row=model
    chosen=fixtures.inputs()
    prepared,_=study.prepare_inputs('.',row,chosen)
    assert prepared['ends']['S']['substation']=='Sending SS'


@pytest.mark.parametrize('value',[False,0,{},'x'*121])
def test_invalid_display_label_remains_a_validation_error(model,value):
    _,row=model
    chosen=fixtures.inputs()
    chosen['ends']['S']['substation']=value
    with pytest.raises(ValueError):
        study.prepare_inputs('.',row,chosen)


def test_blank_labels_do_not_establish_pairing_or_allow_same_capture(model):
    _,row=model
    chosen=fixtures.inputs(pair=True)
    for end in chosen['ends'].values():
        end.pop('substation')
    no_confirmation=copy.deepcopy(chosen)
    no_confirmation['same_event_confirmed']=False
    with pytest.raises(ValueError,match='same event'):
        study.prepare_inputs('.',row,no_confirmation)
    chosen['ends']['R']['record']='S/event.cfg'
    with pytest.raises(ValueError,match='same capture'):
        study.prepare_inputs('.',row,chosen)


def test_generated_long_filename_label_roundtrips(model,monkeypatch):
    _,row=model
    original=study._source
    long_name='nested/'+'a'*130+'.cfg'
    monkeypatch.setattr(study,'_source',lambda root,revision,name: original(root,revision,'S/event.cfg' if name==long_name else name))
    chosen=fixtures.inputs()
    chosen['ends']['S'].update(record=long_name,substation='')
    prepared,_=study.prepare_inputs('.',row,chosen)
    assert prepared['ends']['S']['substation']==long_name[:120]
    reopened,_=study.prepare_inputs('.',row,prepared)
    assert reopened['ends']['S']['substation']==prepared['ends']['S']['substation']
