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
assert.ok(r.view(fallback,50,'A1').reasons.voltage.some(reason=>reason.includes('Changing voltage')));
assert.match(r.vectorMarkup(r.view(fallback,50,'A1')),/Why unavailable/);
const timeline={trigger_offset_s:.012,start_local:'2026-07-04T23:44:55.128000'};
assert.equal(model.milliseconds(0,timeline),'-12.000 ms');
assert.equal(model.milliseconds(.012,timeline),'0.000 ms');
assert.equal(model.milliseconds(.020,timeline),'+8.000 ms');
assert.match(model.relayTime(.020,timeline),/23:44:55.148/);
assert.match(model.relayTime(.0008,timeline),/23:44:55.128800/);
assert.match(model.relayTime(.0008,{start_local:'2026-07-04T23:59:59.999500'}),/2026-07-05 00:00:00.000300/);
assert.equal(model.milliseconds(null,timeline),'Time unavailable');
assert.match(model.milliseconds(.01,{}),/from first sample/);
const rms=structuredClone(result);rms.windows.push({...rms.windows[0],start_index:90,stop_index:170,channels:{A1:{status:'withheld',reason:'Transient'}}});
assert.deepEqual(model.rmsSeries(rms,'A1').map(p=>p[2]),[10,null]);
const record={file:'view.cfg',revision:1,sample_count:3,channels:[{id:'D1',kind:'digital',activity:{transition_count:0}},{id:'A1',kind:'analog'},{id:'D2',kind:'digital',activity:{transition_count:2}}]};
const state=model.create(record);assert.deepEqual(state.order,['A1','D2','D1']);assert.ok(state.visible('A1'));assert.ok(state.visible('D2'));assert.ok(!state.visible('D1'));
const scale=model.amplitudeScale([[0,0,100],[1,.001,101]],'analog','rms');
assert.equal(scale.ticks[0],0,'RMS scale must include zero rather than exaggerating small fluctuations');
assert.ok(scale.top>=101);
assert.equal(scale.y(0),92);
const bipolar=model.amplitudeScale([[0,0,-100],[1,.001,200]],'analog','waveform');
assert.ok(bipolar.ticks[0]<0&&bipolar.ticks.at(-1)>0);
assert.equal(model.amplitudeLabel(200000),'200k');
const graph=r.graphMarkup({id:'A1',kind:'analog',units:'V (CFG-declared, unverified)'},[20,.02,12],[20,.02,9],null,'rms','+8.000 ms');
assert.match(graph,/Instantaneous/);assert.match(graph,/12.0000 V/);assert.match(graph,/Sample RMS/);assert.match(graph,/9.00000 V/);assert.match(graph,/\+8.000 ms/);
assert.ok(!graph.includes('Fundamental RMS'));

const secondary={ok:true,blocked:true,flags:['[BLOCK RATIO-PS] IA secondary=0'],channel_inventory:[{id:'A1'}]};
assert.equal(model.assignmentPolicy(secondary,true).allowed,false);
assert.match(model.qualityMessage(secondary),/CT\/VT ratios/);
assert.ok(model.operationalGuidance(secondary).some(s=>s.startsWith('RATIO-PS:')));
assert.equal(model.assignmentPolicy({...secondary,flags:['[BLOCK TIME-DAT] invalid grid']},true).allowed,false);
assert.equal(model.assignmentPolicy({...secondary,flags:['[BLOCK UNKNOWN] inspect']},true).allowed,false);
const mapOnly={...secondary,flags:['[BLOCK CH-MISSING] missing IA']};
assert.equal(model.assignmentPolicy(mapOnly,true).allowed,true);
assert.equal(model.assignmentPolicy(mapOnly,true).requiresMapping,true);
assert.equal(model.assignmentPolicy(mapOnly,false).allowed,false);
assert.equal(model.assignmentPolicy({...secondary,blocked:false,flags:[]},true).allowed,true);

const questions=require('../src/dranalyser/application/static/instrument-review.js');
assert.deepEqual(questions.missingInstrumentRatings({channel_inventory:[
 {id:'A1',kind:'analog',unit:'A',ps:'S',primary:1,secondary:0},
 {id:'A2',kind:'analog',unit:'V',ps:'S',primary:220000,secondary:110},
 {id:'A3',kind:'analog',unit:'A',ps:'P',primary:1,secondary:0},
 {id:'D1',kind:'digital',unit:'state',ps:'S',primary:1,secondary:0}
]}).map(c=>c.id),['A1']);
