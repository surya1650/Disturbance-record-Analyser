const assert=require('node:assert/strict');
const ui=require('../src/dranalyser/application/static/incident-layout.js');
const source={snapshot:{line:{terminals:{S:'Frozen S',R:'Frozen R'},length_km:100},selected_projection:{distance_km:25,eligible_overlay:true,status:'Conditional model projection',reason:''}}};
const original=JSON.stringify(source);
const row={presentation:{names:{S:'Named S',R:'Named R'},record_ends:{capture:'S'},record_end_sources:{capture:'user label'}}};
const labelOnly=ui.sourceDisplay(row,'capture',source);
assert.equal(labelOnly.snapshot.selected_projection.eligible_overlay,false);
assert.match(labelOnly.snapshot.selected_projection.reason,/reference is not established/);
assert.equal(labelOnly.snapshot.line.terminals.S,'Named S');
row.presentation.record_end_sources.capture='operational assignment';
assert.equal(ui.sourceDisplay(row,'capture',source).snapshot.selected_projection.eligible_overlay,true);
row.presentation.record_ends.capture='R';
const receiving=ui.sourceDisplay(row,'capture',source);
assert.equal(receiving.snapshot.selected_projection.eligible_overlay,false);
assert.equal(receiving.snapshot.selected_projection.distance_km,25); // never silently mirror a mixed-section coordinate
assert.equal(JSON.stringify(source),original);
assert.equal(ui.recordLabel(row,'capture'),'Receiving end · Named R · capture');
console.log('Display names cannot authorize or mirror a sending-end model coordinate.');
