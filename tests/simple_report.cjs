'use strict';
const assert=require('node:assert/strict');
const report=require('../src/dranalyser/application/static/simple-report.js');
const conditions=require('../src/dranalyser/application/static/inspection-conditions.js');
function fixture(){
  const result={file:'S/event.cfg',incident_id:'incident-1',revision:3,sample_count:30,
    channels:[{id:'A1',label:'VA',meaning:'VA',units:'V (CFG-declared, unverified)'},{id:'A2',label:'IA',meaning:'IA',units:'A'}],
    windows:[{start_index:0,stop_index:10,channels:{A1:{status:'model_consistent',rms:100},A2:{status:'model_consistent',rms:5}}},
      {start_index:10,stop_index:20,channels:{A1:{status:'model_consistent',rms:40},A2:{status:'model_consistent',rms:20}}},
      {start_index:20,stop_index:30,channels:{A1:{status:'model_consistent',rms:0},A2:{status:'withheld',reason:'No stable support'}}}],
    snapshot:{line:{length_km:100,terminals:{S:'Substation Alpha',R:'Substation Beta'}},
      selected_projection:{status:'Conditional model projection',distance_km:42,method:'Selected phase-loop reactance projection on supplied positive-X1 sections',
        window_index:1,assumptions:['User-selected AB loop'],authorizes_location:false,basis:'Conditional model; not verified.'}},
    digital_evidence:[{id:'D1',label:'TRIP A',meanings:['TRIP_A'],active_samples:4,unknown_samples:0,first_active_index:0,
      first_active_source_s:0,asserted_state:0,assertion_source:'source-analysis choice',interpretation_available:true},
      {id:'D2',label:'AR BLOCK',meanings:['AR_BLOCK'],active_samples:3,unknown_samples:1,first_active_index:8,
        first_active_source_s:null,asserted_state:1,assertion_source:'assumed high state',interpretation_available:false},
      {id:'D3',label:'Spare',meanings:[],active_samples:2,unknown_samples:0,first_active_index:4,first_active_source_s:.004,
        asserted_state:1,interpretation_available:true}],
    trip:{text:'Trip assertion recorded under stated polarity.'},ar:{text:'AR blocking needs polarity review.'},
    assumptions:[{channel_id:'A2',ratio_text:'600/1',source:'user voltage-level default',basis:'Unverified CT ratio'}],scaling_notes:['Source scaling is unverified.']};
  result.operator_conditions=conditions.build(result,{start:10,end:20,start_s:.01,end_s:.02});
  return result;
}
const source=fixture(),before=JSON.stringify(source),model=report.build(source),html=report.markup(model);
assert.equal(JSON.stringify(source),before,'report build must not mutate source analysis or applied regions');
assert.equal(model.conditions.rows.length,2);
assert.deepEqual([model.conditions.rows[0].pre.value,model.conditions.rows[0].fault.value,model.conditions.rows[0].post.value],[100,40,0]);
assert.equal(model.conditions.rows[1].post.value,null,'unavailable post-fault fit remains null rather than zero');
assert.ok(model.conditions.rows[1].post.reason);
assert.equal(model.conditions.rows[0].units,'V (CFG-declared, unverified)');
assert.ok(html.indexOf('Pre-fault, fault and post-fault conditions')<html.indexOf('Approximate line-model projection'));
assert.ok(html.includes('[10, 20)'));assert.ok(html.includes('local s'));assert.ok(html.includes('B starts post-fault'));
assert.ok(html.includes('Median')||html.includes('median'));
assert.ok(html.includes('600/1'));assert.ok(html.includes('Unverified CT ratio'));
assert.equal(model.distance.kind,'projection');assert.equal(model.distance.distance_km,42);assert.equal(model.distance.authorizes_location,false);
assert.ok(html.includes('not a verified physical fault location'));
assert.ok(html.includes('fitted RMS lower'));assert.ok(html.includes('fitted RMS higher'));
assert.equal(model.digital.rows[0].asserted_state,0,'active-low polarity must survive');
assert.equal(model.digital.rows[0].first_active_index,0);assert.equal(model.digital.rows[0].first_active_source_s,0);
assert.equal(model.digital.rows[1].interpretable,false);assert.ok(model.digital.rows[1].interpretation.includes('Review asserted-state polarity'));
assert.equal(model.digital.rows[2].interpretable,false);assert.ok(model.digital.rows[2].interpretation.includes('Meaning not assigned'));
assert.ok(html.includes('time unavailable'));assert.ok(html.includes('does not prove breaker opening'));
assert.ok(!html.includes('opening time: 0'));assert.ok(!html.includes('AR failure confirmed'));
assert.equal(model.digital.unresolved,2);
const invalidPolarity=fixture();delete invalidPolarity.digital_evidence[0].asserted_state;
assert.equal(report.build(invalidPolarity).digital.rows[0].interpretable,false);
assert.equal(report.build(invalidPolarity).digital.unresolved,3);
assert.doesNotThrow(()=>JSON.stringify(model));

// Stale numerical region rows may not leak into a report without an applied selection.
const noSelection=fixture();noSelection.operator_conditions.selection=null;
const blank=report.build(noSelection);
assert.ok(blank.conditions.rows.every(r=>[r.pre,r.fault,r.post].every(c=>c.value===null)));
assert.deepEqual(blank.analog.interpretations,[]);assert.ok(blank.next_steps.some(s=>s.includes('place A')));
assert.ok(report.markup(blank).includes('Fault interval not selected'));
const invalid=fixture();invalid.operator_conditions.selection={start:20,end:10};
assert.equal(report.build(invalid).conditions.selection,null);
const mismatch=fixture();mismatch.operator_conditions.regions[1].channels[0].units='kV';
assert.equal(report.build(mismatch).conditions.rows[0].fault.value,null);
assert.ok(report.build(mismatch).conditions.rows[0].fault.reason.includes('units'));

// Preserve method, reference, selected record scope and exact stored incident text.
const operational={location_text:'41.988 km from Substation Alpha by E5 (two-ended)',used:{S:'S/event.cfg',R:'R/event.cfg'}};
const incident=report.build(fixture(),operational),incidentHtml=report.markup(incident);
assert.equal(incident.distance.kind,'incident');assert.equal(incident.distance.method,'E5');assert.equal(incident.distance.distance_km,41.988);
assert.equal(incident.distance.selected_source_used,true);assert.ok(incidentHtml.includes(operational.location_text));
assert.ok(incidentHtml.includes('Incident distance calculation'));assert.ok(incidentHtml.includes('Approximate line-model projection'));
assert.equal(incident.distance.length_km,null,'a selected custom source line length is not an incident line fact');
const excluded=report.build({...fixture(),file:'excluded.cfg'},operational);
assert.equal(excluded.distance.selected_source_used,false);assert.ok(report.markup(excluded).includes('not listed as driving'));
const refused=report.build(fixture(),{location_text:'refused - channel scaling unresolved',used:{}});
assert.equal(refused.incident_distance.distance_km,null);assert.equal(refused.distance.kind,'projection');
const zeroIncident=report.build(fixture(),{location_text:'0.000 km from Alpha by E5 (two-ended)',used:{}});
assert.equal(zeroIncident.distance.distance_km,0);assert.equal(zeroIncident.distance.reference,'Alpha');

// Never clip an outside-line projection or present a number without its method.
for(const distance of [-12,0,140]){
  const out=fixture();out.snapshot.selected_projection.distance_km=distance;out.snapshot.selected_projection.status=distance<0||distance>100?'Outside supplied line':'Conditional model projection';
  const data=report.build(out);assert.equal(data.distance.distance_km,distance);assert.equal(data.distance.authorizes_location,false);
  assert.ok(report.markup(data).includes('Method: Selected phase-loop'));
}
const unlabelled=fixture();delete unlabelled.snapshot.selected_projection.method;
assert.equal(report.build(unlabelled).distance.distance_km,null);assert.ok(report.build(unlabelled).distance.reason.includes('method'));

const refusedProjection=fixture();refusedProjection.snapshot.selected_projection.status='Not available';
assert.equal(report.build(refusedProjection).distance.distance_km,null);

// Partial source evidence stays usable and untrusted source text is always escaped.
for(const input of [undefined,null,{}, {channels:null,digital_evidence:'bad',snapshot:{}}]){
  const data=report.build(input);assert.doesNotThrow(()=>report.markup(data));assert.equal(data.conditions.rows.length,0);
  assert.equal(data.distance.distance_km,null);
}
const hostile=fixture();hostile.file='<script>alert(1)</script>';hostile.channels[0].label='<img src=x onerror=alert(1)>';
hostile.operator_conditions=conditions.build(hostile,{start:10,end:20});hostile.digital_evidence[0].label='<svg/onload=alert(1)>';
hostile.snapshot.selected_projection.method='<script>method</script>';
const safe=report.markup(report.build(hostile));assert.ok(!safe.includes('<script>'));assert.ok(!safe.includes('<img src=x'));assert.ok(safe.includes('&lt;script&gt;'));assert.ok(safe.includes('&lt;img'));

// Detailed digital edges never inflate the concise report; disclose omitted rows.
const large=fixture();large.digital_evidence=Array.from({length:256},(_,i)=>({...large.digital_evidence[0],id:'D'+(i+1),rising_edges:Array(512).fill({index:1})}));
const bounded=report.build(large);assert.equal(bounded.digital.rows.length,12);assert.equal(bounded.digital.total,256);assert.equal(bounded.digital.omitted,244);
assert.ok(!JSON.stringify(bounded).includes('rising_edges'));assert.ok(report.markup(bounded).includes('Additional indications remain'));
console.log('Simple report: applied region RMS/unknowns, incident/projection distinction, safe digital interpretation, bounded evidence and escaping passed');
