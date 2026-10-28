'use strict';
const DRInspection = (() => {
  function create(record) {
    const n=record.sample_count;
    const ordered=[...record.channels].sort((a,b)=>Number(a.kind==='digital')-Number(b.kind==='digital')||Number((b.activity?.transition_count||0)>0)-Number((a.activity?.transition_count||0)>0));
    return {record:record.file,revision:record.revision,sourceIdentity:identity(record.source_sha256),n,order:ordered.map(c=>c.id),hidden:new Set(ordered.filter(c=>c.kind==='digital'&&c.activity?.transition_count===0).map(c=>c.id)),
      colors:{A:'#c94145',B:'#b88a00',C:'#316ecc',N:'#606c78',unknown:'#176d82'},phases:{},groups:{},
      setColour(phase,color){if(!/^#[0-9a-f]{6}$/i.test(color)||!Object.hasOwn(this.colors,phase))throw new Error('Use a six-digit colour.');this.colors[phase]=color;},
      pins:{A:0,B:Math.max(0,n-1)},hover:0,view:[0,Math.max(0,n-1)],generation:0,requests:new Map(),
      visible(id){return !this.hidden.has(id);},
      toggle(id){this.hidden.has(id)?this.hidden.delete(id):this.hidden.add(id);},
      reorder(id,direction){const i=this.order.indexOf(id),j=i+direction;if(i>=0&&j>=0&&j<this.order.length)[this.order[i],this.order[j]]=[this.order[j],this.order[i]];},
      move(name,index){if(!Number.isFinite(index))return;const v=Math.max(0,Math.min(n-1,Math.round(index)));if(name==='hover')this.hover=v;else this.pins[name]=v;},
      addPin(){if(Object.keys(this.pins).length>=16)throw new Error('Up to 16 cursors are supported. Remove a cursor to add another.');let i=2;while(this.pins[String.fromCharCode(65+i)]!==undefined)i++;this.pins[String.fromCharCode(65+i)]=this.hover;},
      removePin(name){if(!['A','B'].includes(name))delete this.pins[name];},
      zoom(factor,center=(this.view[0]+this.view[1])/2){const span=Math.min(n-1,Math.max(1,(this.view[1]-this.view[0])*factor));const lo=Math.max(0,Math.min(n-1-span,center-span/2));this.view=[lo,lo+span];},
      pan(fraction){const span=this.view[1]-this.view[0],lo=Math.max(0,Math.min(n-1-span,this.view[0]+span*fraction));this.view=[lo,lo+span];},
      follow(index){const [lo,hi]=this.view,span=hi-lo;if(index>=lo&&index<=hi)return false;const first=Math.max(0,Math.min(this.n-1-span,index<lo?index:index-span));this.view=[first,first+span];return true;},
      reset(){this.view=[0,Math.max(0,n-1)];},
      request(channel){const serial=(this.requests.get(channel)||0)+1;this.requests.set(channel,serial);return {record:this.record,revision:this.revision,source:this.sourceIdentity,channel,generation:this.generation,serial};},
      accept(token){return token.record===this.record&&token.revision===this.revision&&token.source===this.sourceIdentity&&token.generation===this.generation&&this.requests.get(token.channel)===token.serial;},
      invalidate(){this.generation++;this.requests.clear();}
    };
  }
  function identity(hashes){return JSON.stringify(Object.entries(hashes||{}).sort(([a],[b])=>a.localeCompare(b)));}
  function exactPoints(native,channelIds,indices){
    const out=[];for(const id of channelIds){const points=native.get(id);if(!points?.length)return null;const samples=[];
      for(const index of indices){const p=points[index-points[0][0]];if(!p||p[0]!==index)return null;samples.push(p);}out.push({id,samples});}
    return out;
  }
  function delta(a,b){return {samples:b[0]-a[0],seconds:Number.isFinite(a[1])&&Number.isFinite(b[1])?b[1]-a[1]:null};}
  function value(sample){return !sample||sample[2]===null?'Unknown':String(sample[2]);}
  function nearest(points,index){return points.reduce((best,p)=>!best||Math.abs(p[0]-index)<Math.abs(best[0]-index)?p:best,null);}
  function segments(points,gap=Infinity,boundaries=[]){const out=[];let part=[],boundary=0;for(const p of points){const last=part.at(-1);if(last)while(boundary<boundaries.length&&boundaries[boundary]<=last[0])boundary++;if(p[2]===null||(last&&((boundary<boundaries.length&&boundaries[boundary]<=p[0])||(p[0]-last[0]===1&&p[1]!==null&&last[1]!==null&&p[1]-last[1]>gap)))){if(part.length)out.push(part);part=[];}if(p[2]!==null)part.push(p);}if(part.length)out.push(part);return out;}
  function phaseFor(channel,channels) {
    const raw=String(channel.phase||'').trim().toUpperCase();
    const ryb=channels.some(c=>['R','Y'].includes(String(c.phase||'').toUpperCase()));
    if(ryb&&['R','Y','B'].includes(raw))return {R:'A',Y:'B',B:'C'}[raw];
    if(['A','B','C','N'].includes(raw))return raw;
    if(['L1','L2','L3','1','2','3'].includes(raw))return {L1:'A',L2:'B',L3:'C',1:'A',2:'B',3:'C'}[raw];
    const match=String(channel.label||'').toUpperCase().match(/^(?:I|V)([ABCN])$/);
    return match?match[1]:'unknown';
  }
  function groupChannels(channels,state) {
    const groups=new Map();for(const c of channels){const name=state.groups[c.id];const key=c.kind==='analog'&&name?`${name}/${c.units}`:c.id;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(c);}return [...groups.values()];
  }
  function milliseconds(seconds,timeline){
    if(!Number.isFinite(seconds))return 'Time unavailable';
    const offset=timeline?.trigger_offset_s,ms=(seconds-(Number.isFinite(offset)?offset:0))*1000;
    return `${ms>0?'+':''}${Object.is(ms,-0)||Math.abs(ms)<.0005?'0.000':ms.toFixed(3)} ms${Number.isFinite(offset)?'':' from first sample'}`;
  }
  function relayTime(seconds,timeline){
    if(!Number.isFinite(seconds)||!timeline?.start_local)return 'Relay time unavailable';
    const start=Date.parse(timeline.start_local+'Z');if(!Number.isFinite(start))return 'Relay time unavailable';
    const fraction=(timeline.start_local.split('.')[1]||'').padEnd(6,'0').slice(0,6),extra=Number(fraction)%1000;
    const micros=Math.round(start*1000+extra+seconds*1e6);if(!Number.isSafeInteger(micros))return 'Relay time unavailable';
    const millis=Math.floor(micros/1000),remainder=String(micros-millis*1000).padStart(3,'0');
    return new Date(millis).toISOString().replace('T',' ').replace('Z',remainder)+' relay local';
  }
  function axisTicks(data,view,native){
    const source=[...(data.timeline?.ticks||[]),...([...(native?.values()||[])][0]||[])];
    const unique=[...new Map(source.filter(p=>Number.isFinite(p[1])&&p[0]>=view[0]&&p[0]<=view[1]).map(p=>[p[0],p])).values()].sort((a,b)=>a[0]-b[0]);
    if(!unique.length)return Array.from({length:6},(_,i)=>[Math.round(view[0]+i*(view[1]-view[0])/5),null]);
    const selected=[];for(let i=0;i<6;i++){const target=view[0]+i*(view[1]-view[0])/5,p=nearest(unique,target);if(!selected.some(q=>q[0]===p[0]))selected.push(p);}return selected;
  }
  function rmsSeries(result,id){
    return (result?.windows||[]).map(w=>{const fit=w.channels[id],valid=fit?.status==='model_consistent'&&Number.isFinite(fit.rms)&&fit.rms>=0;
      return [(w.start_index+w.stop_index-1)/2,valid?fit.centre_s:null,valid?fit.rms:null];});
  }
  function amplitudeLabel(value){
    const a=Math.abs(value);if(a===0)return '0';
    const suffix=a>=1e6?'M':a>=1e3?'k':'',divisor=suffix==='M'?1e6:suffix==='k'?1e3:1;
    return (a<.001||a>=1e9?value.toExponential(2):Number((value/divisor).toPrecision(4)).toString()+suffix);
  }
  function amplitudeScale(points,kind='analog',mode='waveform'){
    let peak=0;for(const p of points)if(Number.isFinite(p[2]))peak=Math.max(peak,Math.abs(p[2]));
    const target=peak*1.05||1,power=10**Math.floor(Math.log10(target)),fraction=target/power;
    let top=([1,2,5,10].find(n=>n>=fraction)||10)*power;if(!Number.isFinite(top))top=peak||1;
    const positive=mode!=='waveform',ticks=kind==='digital'?[0,1]:positive?[0,top/2,top]:[-top,0,top];
    const y=v=>kind==='digital'?82-v*60:positive?92-v/top*80:52-v/top*40;
    return {ticks,y,top};
  }
  function qualityMessage(file){
    if(file.duplicate_of)return `Identical copy of ${file.duplicate_of}.`;
    if(!file.ok)return 'Operational decoding needs review. Open source inspection for recoverable observations; the exact reason is in Input details.';
    const notes=(file.flags||[]).filter(f=>f.startsWith('[BLOCK')).map(f=>/gap|jitter|drift|timestamp/i.test(f)?'Sample intervals vary. Actual-time source diagnostics remain available; uniform-sample calculations need suitable timing.':/crest factor|RMS|sqrt/i.test(f)?'The exported amplitude convention needs review for physical measurements; no scaling convention is inferred.':/CH-MISSING/.test(f)?'Assign the missing phase/channel meanings for calculations that use them.':f.replace(/^\[[^\]]+\]\s*/,''));
    return notes.length?notes.join(' '):'Recorded inputs are available for assignment.';
  }
  function operationalGuidance(file){
    const flags=(file.flags||[]).join(' '),notes=[];
    if(flags.includes('TIME-DAT'))notes.push('TIME-DAT: the uniform-grid fault-location pipeline withheld this capture. Monotonic DAT source timestamps can still support waveform inspection and sample RMS. No timestamp repair is applied.');
    if(flags.includes('SCALE-CF'))notes.push('SCALE-CF: the crest-factor check needs review. Short pre-trigger support can make it inconclusive. Crest factor alone does not establish RMS storage or a gain correction; do not multiply the record by √2 on this basis.');
    if(flags.includes('WIN-PREFAULT'))notes.push('Short pre-trigger capture: some pre-fault and superimposed methods lack support. Inspect each capture or join compatible successive captures from the same relay; joining does not automatically clear operational blocks.');
    if(file.blocked&&!notes.length)notes.push('Operational calculations are withheld pending the input checks below. Independent source inspection remains available where samples can be recovered.');
    return notes;
  }
  return {create,identity,exactPoints,delta,value,nearest,segments,phaseFor,groupChannels,qualityMessage,operationalGuidance,milliseconds,relayTime,axisTicks,rmsSeries,amplitudeScale,amplitudeLabel};
})();
if(typeof module!=='undefined')module.exports=DRInspection;
