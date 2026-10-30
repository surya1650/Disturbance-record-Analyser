const assert=require('node:assert/strict');
const r=require('../src/dranalyser/application/static/inspection-readings.js');
const model=require('../src/dranalyser/application/static/inspection-model.js');
const result={channels:[{id:'A1',label:'VA',meaning:'VA',units:'V (CFG-declared, unverified)'},{id:'A2',label:'IA',meaning:'IA',units:'A (assumed CT ratio, unverified)'},{id:'A3',label:'Unknown',units:'raw counts'}],windows:[{index:0,start_index:10,stop_index:90,channels:{A1:{status:'model_consistent',rms:10,phasor:[0,10],centre_s:.05},A2:{status:'model_consistent',rms:5,phasor:[3,4],centre_s:.05},A3:{status:'withheld',reason:'Changing waveform.'}}}]};
assert.equal(typeof r.view,'function');
let v=r.view(result,50,'A1');
assert.equal(v.window.index,0);assert.equal(v.channels.get('A1').angle_deg,0);
assert.ok(Math.abs(v.channels.get('A2').angle_deg+36.86989764584402)<1e-12);
assert.equal(v.channels.get('A2').rms,5);assert.equal(v.channels.get('A3').rms,null);
assert.match(v.channels.get('A3').reason,/Changing/);
assert.equal(v.groups.voltage.length,1);assert.equal(v.groups.current.length,1);
assert.equal(r.view(result,9,'A1').window,null);assert.equal(r.view(result,90,'A1').window,null);
const other=structuredClone(result);other.windows[0].channels.A2.centre_s=.051;
assert.equal(r.view(other,50,'A1').channels.get('A2').angle_deg,null);
other.windows[0].channels.A2.centre_s=.05;other.windows[0].channels.A1.phasor=[0,0];other.windows[0].channels.A1.rms=0;
v=r.view(other,50,'A1');assert.equal(v.channels.get('A1').rms,0);assert.equal(v.channels.get('A1').angle_deg,null);assert.equal(v.channels.get('A2').angle_deg,null);
const html=r.readingMarkup({id:'A2',label:'IA',units:'raw counts'},[50,.05,123],r.view(result,50,'A1').channels.get('A2'),'A');
assert.ok(html.includes('123'));assert.ok(html.includes('raw counts'));assert.ok(html.includes('assumed CT'));assert.ok(html.includes('RMS'));assert.ok(html.includes('Angle'));
assert.ok(r.readingMarkup({id:'A3',label:'<img>',units:'counts'},[50,null,null],null,'hover').includes('Unknown'));
assert.ok(!r.vectorMarkup(r.view(result,50,'A1'),{A1:'#123456',A2:'#654321'}).includes('NaN'));
const s=model.create({file:'x',revision:1,sample_count:1000,channels:[]});s.view=[100,199];
assert.equal(s.follow(200),true);assert.deepEqual(s.view,[101,200]);assert.equal(s.follow(150),false);
s.follow(0);assert.deepEqual(s.view,[0,99]);s.follow(999);assert.deepEqual(s.view,[900,999]);
console.log('Electrical readings: exact-window support, relative angles, zero/missing values, unit separation and cursor-follow passed');
const digital=r.readingMarkup({id:'D1',label:'Trip',kind:'digital',units:'state'},[3,.003,0],null,'A');
assert.ok(digital.includes('State'));assert.ok(!digital.includes('RMS'));assert.ok(!digital.includes('Angle'));
const fallback=structuredClone(result);fallback.windows[0].channels.A1={status:'withheld',reason:'Changing voltage'};
assert.equal(r.view(fallback,50).reference,'A2');assert.equal(r.view(fallback,50).groups.current.length,1);
assert.equal(r.view(fallback,50,'A1').channels.get('A2').angle_deg,null,'explicit refused reference must stay explicit');

// Vectors identify the source channel, retaining the immutable request identity.
const named=r.vectorMarkup(r.view(result,50,'A1'));
assert.ok(named.includes('>VA (A1)</text>'));
assert.ok(named.includes('>IA (A2)</text>'));
assert.ok(named.includes('Angles relative to VA (A1)'));
assert.ok(!named.includes('>A1</text>'));
const malicious=structuredClone(result);malicious.channels[0].label='<img src=x onerror=alert(1)>';
const escaped=r.vectorMarkup(r.view(malicious,50,'A1'));
assert.ok(!escaped.includes('<img'));
assert.ok(escaped.includes('&lt;img src=x onerror=alert(1)&gt; (A1)'));
const unnamed=structuredClone(result);unnamed.channels[0].label='';delete unnamed.channels[0].meaning;
assert.ok(r.vectorMarkup(r.view(unnamed,50,'A1')).includes('>A1</text>'),'missing labels keep the source identity rather than inventing a name');

// Generic source names are not phase evidence. Only supplied display meanings
// can replace them, with original source label/identity retained in provenance.
const generic=structuredClone(result);generic.channels[0].label='CH1';generic.channels[1].label='Channel 2';
const namedGeneric=r.vectorMarkup(r.view(generic,50,'A1'));
assert.ok(namedGeneric.includes('>VA (A1)</text>'));
assert.ok(namedGeneric.includes('>IA (A2)</text>'));
assert.ok(namedGeneric.includes('original source label: CH1 · source ID: A1'));
const cursorSource={channels:{A1:{label:'CH1',units:'V',status:'observed',fundamental_rms:10,phasor:[0,10]},A2:{label:'CH2',units:'A',status:'observed',fundamental_rms:5,phasor:[3,4]}}};
const cursorNamed=r.vectorMarkup(r.cursorView(cursorSource,'A1',{A1:'VA',A2:'IA'}));
assert.ok(cursorNamed.includes('>VA (A1)</text>'));assert.ok(cursorNamed.includes('>IA (A2)</text>'));
assert.ok(cursorNamed.includes('Angles relative to VA (A1)'));
const cursorUnknown=r.vectorMarkup(r.cursorView(cursorSource,'A1'));
assert.ok(cursorUnknown.includes('>CH1 (A1)</text>'));
assert.ok(!cursorUnknown.includes('>VA (A1)</text>'),'CH1 position cannot invent phase A');
const informative=structuredClone(cursorSource);informative.channels.A1.label='Bus voltage measured';
assert.ok(r.vectorMarkup(r.cursorView(informative,'A1',{A1:'VA'})).includes('>Bus voltage measured (A1)</text>'));
assert.ok(r.vectorMarkup(r.cursorView(cursorSource,'A1',{A1:'ignore'})).includes('>CH1 (A1)</text>'),'ignored meaning cannot label a generic source');

assert.ok(r.vectorMarkup(r.cursorView(cursorSource,'A1',{A1:'IA'})).includes('>CH1 (A1)</text>'),'conflicting current meaning cannot relabel a voltage source');
