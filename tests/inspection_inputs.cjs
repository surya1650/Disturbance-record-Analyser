const assert=require('node:assert/strict');
const m=require('../src/dranalyser/application/static/inspection-inputs.js');
assert.equal(m.stable({b:2,a:{z:1,y:0}}),m.stable({a:{y:0,z:1},b:2}));
const options=m.options({voltageKv:'132',mappings:{A1:'VA',D1:''},assertedStates:{D1:'0'},lineMode:'__custom__',
  model:{length_km:'50',x1_ohm_per_km:'.4',r1_ohm_per_km:'.1',r0_ohm_per_km:'',x0_ohm_per_km:'',provenance:'Operator model'},faultLoop:'AB',projectionWindow:'0'});
assert.equal(options.voltage_kv,132);assert.equal(options.asserted_states.D1,0);assert.equal(options.line_model.length_km,50);
assert.equal(options.line_model.x0_ohm_per_km,null);assert.equal(options.projection_window,0);assert.equal(options.fault_loop,'AB');
assert.equal(options.mappings.D1,undefined);assert.equal(options.line_id,undefined);
const unknown=m.options({voltageKv:'0',mappings:{},assertedStates:{},lineMode:'__custom__',model:{length_km:'',x1_ohm_per_km:''},faultLoop:'',projectionWindow:''});
assert.equal(unknown.line_model.length_km,null);assert.equal(unknown.line_model.x1_ohm_per_km,null);assert.equal(unknown.fault_loop,undefined);
assert.throws(()=>m.options({voltageKv:'0',mappings:{},assertedStates:{},lineMode:'__custom__',model:{length_km:'not numeric'}}));
console.log('Source input choices preserve unknowns, explicit state0 and stable identities');
assert.throws(()=>m.catalogue({detail:'Line registry budget exceeded'},false),/budget exceeded/);
assert.throws(()=>m.catalogue({unexpected:true},true),/list/);
assert.deepEqual(m.catalogue({items:[{id:'EXPLICIT'}]},true),[{id:'EXPLICIT'}]);

const html=m.markup({line_model:{r0_ohm_per_km:.3,x0_ohm_per_km:1.2,provenance:'<unsafe>'}});
assert.ok(html.includes('<details class="source-zero-sequence">'));
assert.ok(!html.includes('<details class="source-zero-sequence" open'));
assert.ok(html.includes('Phase-loop projection and E5 do not need these fields'));
assert.ok(html.includes('data-line-field="r0_ohm_per_km"'));
assert.ok(html.includes('value="0.3"'));
assert.ok(html.includes('value="1.2"'));
assert.ok(!html.includes('<unsafe>'));
assert.ok(html.includes('&lt;unsafe&gt;'));
