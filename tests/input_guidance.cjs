const assert=require('node:assert/strict');
const guidance=require('../src/dranalyser/application/static/input-guidance.js');
const record={blocked:true,flags:['[BLOCK RATIO-P/S] IA 1/0','[BLOCK TIME-DAT] gap','[BLOCK SCALE-CF] VA amplitude']};
const before=JSON.stringify(record),state=guidance.assess(record),html=guidance.markup(record);
assert.equal(state.ratio,true);assert.equal(state.items.length,3);
assert.ok(html.includes('actual primary and secondary'));assert.ok(html.includes('ratio correction does not settle'));
assert.ok(html.includes('Recoverable waveforms can be inspected'));
assert.ok(!html.includes('Waveforms are available.'));
assert.ok(html.includes('data-go-feature="inputs"'));assert.equal(JSON.stringify(record),before);
assert.equal(guidance.markup({blocked:false,flags:[]}), '');
assert.ok(!guidance.markup({blocked:true,flags:['[BLOCK X] <script>x</script>']}).includes('<script>'));

assert.equal(guidance.assess({blocked:true,flags:['[BLOCK RATIO-PS] IA 1/0']}).ratio,true);

const original={name:'original.cfg'},derived={name:'reviewed-ratios-abc123/reviewed.cfg'};
assert.equal(guidance.preferredRecording({metadata:{assignments:{'original.cfg':{role:'excluded'}}}},[original,derived]),derived.name);
assert.equal(guidance.preferredRecording({metadata:{}},[original,derived]),original.name);

// Source inspection/comparison is a separate step from optional physics inputs.
const anonymous={bundle:{files:[{name:'local.cfg',kind:'comtrade',blocked:true},{name:'remote.cfg',kind:'comtrade',blocked:true},{name:'duplicate.cfg',kind:'comtrade',duplicate_of:'local.cfg'}]}};
const source={file:'local.cfg',sample_count:1200};
const steps=guidance.workflow(anonymous,source),copy=JSON.stringify(anonymous);
assert.deepEqual(steps.map(step=>step.destination),['waveforms','compare','report']);
assert.equal(steps[0].state,'Ready');assert.equal(steps[1].state,'Ready');
assert.match(steps[1].note,/1 other recording is attached/);
assert.match(steps[1].note,/no line, end confirmation or CT\/VT review is required/);
assert.match(steps[2].note,/without a line model/);assert.match(steps[2].note,/optional fault location/);
assert.deepEqual(guidance.workflow({...anonymous,metadata:{line_id:'DECLARED',assignments:{'local.cfg':{end:'S',role:'primary'}}}},source),steps,'physical declarations must not alter availability of raw inspection or comparison');
assert.equal(JSON.stringify(anonymous),copy,'guidance must not mutate frozen source metadata');
assert.equal(guidance.workflow({bundle:{files:[{name:'local.cfg',kind:'comtrade'}]}},source)[1].state,'Attach another capture');
assert.equal(guidance.workflow({}, {sample_count:0})[0].state,'Check source');
const workflow=guidance.workflowMarkup(anonymous,source);
assert.equal((workflow.match(/data-go-feature=/g)||[]).length,3);
assert.match(workflow,/aria-label="Steps for this recording"/);
assert.ok(html.indexOf('Input review for optional physical calculations')<html.indexOf('Missing CT/VT ratings'));
assert.ok(!html.includes('<details open'),'optional physical findings stay collapsed without hiding waveforms');
assert.match(html,/Inspect and compare the recorded values now/);
