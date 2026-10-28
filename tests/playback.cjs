const assert=require('node:assert/strict');
const M=require('../src/dranalyser/application/static/playback-model.js');
const T=require('../src/dranalyser/application/static/inspection-transport.js');
const s=(runs,active=1)=>({status:'available',runs,active});
const r={trigger_s:.1,offset_ms:20,capture_s:[0,1],signals:{open:s([[0,.2,0],[.2,.5,1],[.8,1,0]]),closed:s([[0,.1,1],[.1,1,0]])}};
assert.equal(M.breaker(r,.05),'closed indication');
assert.equal(M.breaker(r,.15),'unknown'); // inactive open does not prove closed, nor inactive closed prove open
assert.equal(M.breaker(r,.3),'open indication');
assert.equal(M.stateAt(r.signals.open,.7),null); // gap
assert.equal(M.stateAt(s([[0,1,1]],0),.2),false);
r.signals.closed=s([[0,1,1]]);assert.equal(M.breaker(r,.3),'conflict');
assert.equal(M.local(r,120),.2);assert.equal(M.shared(r,.2),120);
assert.deepEqual(M.range([r]),[-80,920]);
assert.deepEqual(M.advance(90,20,1,[0,100]),{time:100,ended:true});
assert.deepEqual(M.advance(90,20,1,[0,100],true),{time:10,ended:false});
assert.throws(()=>M.advance(0,NaN,1,[0,100]));
assert.equal(M.pointAt([[0,1,2],[1,null,null],[2,3,4]],1.1),null);
assert.equal(M.pointAt([[0,1,2],[1,2,3]],10),null);
assert.deepEqual(M.pointAt([[0,1,2]],0),[0,1,2]);
(async()=>{let running=0,peak=0;const result=await T.mapLimit([...Array(32).keys()],4,async i=>{running++;peak=Math.max(peak,running);await new Promise(resolve=>setTimeout(resolve,1));running--;return i*2;});assert.equal(peak,4);assert.deepEqual(result,[...Array(32).keys()].map(i=>i*2));const c=new AbortController();c.abort();await assert.rejects(T.mapLimit([1,2],4,async i=>i,c.signal),/aborted/);console.log('Playback clock, missing contacts, gaps, stale R-X points and request bounds passed.');})().catch(e=>{console.error(e);process.exitCode=1;});
