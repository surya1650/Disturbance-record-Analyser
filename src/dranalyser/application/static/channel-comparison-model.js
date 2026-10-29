'use strict';
// Display identities only. This model never assigns terminals or authorizes analysis.
const DRChannelComparison = (() => {
  const order={voltage:0,other:1,current:2};
  const phases={A:0,B:1,C:2,AB:3,BC:4,CA:5,BA:6,CB:7,AC:8,N:9,'0':10,'3I0':11,'3V0':11};
  const titles={voltage:'Voltage channels',other:'Other analog channels',current:'Current channels'};
  const qualifiers=new Set(['RMS','DC','PEAK','MAG','ANGLE','FUNDAMENTAL','PHASOR','FREQUENCY','FREQ']);
  const clean=value=>String(value??'').trim().toUpperCase();
  const tokens=value=>clean(value).split(/[^A-Z0-9]+/).filter(Boolean);
  function unitQuantity(value){
    const unit=clean(value).split(/[\s(]/)[0];
    if(['V','KV','MV','UV'].includes(unit))return 'voltage';
    if(['A','KA','MA','UA'].includes(unit))return 'current';
    return '';
  }
  function nonElectricalUnit(value){
    const unit=clean(value).split(/[\s(]/)[0];
    return ['HZ','KHZ','MHZ','OHM','OHMS','Ω','DEG','DEGREE','DEGREES','RAD','W','KW','MW','VAR','KVAR','MVAR','S','MS','%'].includes(unit);
  }
  function alias(value,ryb=false){
    const token=clean(value);
    if(['3I0','3IO','I0','IO','3V0','3VO','V0','VO','U0','UO','3U0','3UO'].includes(token)){
      const meaning=token.replace(/U/g,'V').replace(/O/g,'0');
      return {meaning,quantity:meaning.includes('I')?'current':'voltage',phase:meaning.startsWith('3')?meaning:'0'};
    }
    const match=token.match(/^([VIU])(L?[123]|[ABCNRY]{1,2})$/);
    if(!match)return null;
    let phase=match[2],kind=match[1]==='I'?'I':'V';
    const numeric=/^L?[123]$/.test(phase);
    phase=phase.replace(/L?1/g,'A').replace(/L?2/g,'B').replace(/L?3/g,'C');
    if(!numeric&&(ryb||/[RY]/.test(phase)))phase=[...phase].map(p=>({R:'A',Y:'B',B:'C'})[p]||p).join('');
    if(!['A','B','C','N','AB','BC','CA','BA','CB','AC'].includes(phase))return null;
    return {meaning:kind+phase,quantity:kind==='V'?'voltage':'current',phase};
  }
  function phaseMode(phases){
    const valid=phases.filter(p=>alias('V'+p));
    const ryb=valid.some(p=>/[RY]/.test(p)),abc=valid.some(p=>/[AC]/.test(p));
    return ryb&&abc?'mixed':ryb?'ryb':'abc';
  }
  function labelWords(label){
    return tokens(label).flatMap(t=>{
      for(const q of qualifiers){
        if(t.startsWith(q)&&alias(t.slice(q.length)))return [q,t.slice(q.length)];
        if(t.endsWith(q)&&alias(t.slice(0,-q.length)))return [t.slice(0,-q.length),q];
      }
      return [t];
    });
  }
  function context(record){
    const headers=new Map((record?.inventory||[]).map(c=>[c.id,c]));
    const channels=(record?.channels||[]).filter(c=>c.kind==='analog');
    const labelPhases={voltage:[],current:[]},headerPhases={voltage:[],current:[]};
    for(const c of channels){
      const header=headers.get(c.id)||{},quantity=unitQuantity(c.units)||unitQuantity(header.declared_units);
      for(const word of labelWords(c.label)){
        const m=word.match(/^([IVU])([ABCNRY]{1,2})$/);
        if(m)labelPhases[m[1]==='I'?'current':'voltage'].push(m[2]);
      }
      if(quantity)headerPhases[quantity].push(clean(c.phase||header.phase));
    }
    return {headers,channels,labelModes:Object.fromEntries(Object.entries(labelPhases).map(([k,v])=>[k,phaseMode(v)])),
      headerModes:Object.fromEntries(Object.entries(headerPhases).map(([k,v])=>[k,phaseMode(v)]))};
  }
  function identifyWith(channel,ctx,mappings){
    const header=ctx.headers.get(channel.id)||{},units=channel.units||'',declared=header.declared_units||'';
    const physical=unitQuantity(units),declaredQuantity=unitQuantity(declared);
    const words=labelWords(channel.label),flavour=[...new Set([...words,...tokens(units),...tokens(declared)].filter(t=>qualifiers.has(t)))].sort().join('+')||'waveform';
    const selected=mappings?.[channel.id],reviewed=Boolean(selected&&selected!=='ignore');
    const suggestions=words.map(t=>alias(t,ctx.labelModes[t.startsWith('I')||t.startsWith('3I')?'current':'voltage']==='ryb')).filter(Boolean);
    const unique=[...new Map(suggestions.map(v=>[v.meaning,v])).values()];
    const chosen=reviewed?alias(selected):unique.length===1?unique[0]:null;
    const raw=clean(channel.phase||header.phase);
    const quantity=physical||declaredQuantity||chosen?.quantity||'other';
    const headerMeaning=raw?alias((quantity==='current'?'I':'V')+raw,ctx.headerModes[quantity]==='ryb'):null;
    let identity=chosen,reason='';
    if(selected==='ignore'){identity=null;reason='Meaning ignored; observations retained.';}
    else if(reviewed&&!chosen){identity=null;reason='Selected meaning is not a supported display identity.';}
    else if(reviewed&&unique.length===1&&chosen.meaning!==unique[0].meaning){identity=null;reason='Selected meaning conflicts with the source quantity/phase; no automatic pairing.';}
    else if(!reviewed&&(ctx.labelModes[quantity]==='mixed'||raw&&ctx.headerModes[quantity]==='mixed')){identity=null;reason='Mixed A/B/C and R/Y/B phase conventions; review the channel meaning.';}
    else if(!reviewed&&unique.length>1){identity=null;reason='Multiple quantity/phase tokens; review the channel meaning.';}
    else if(chosen&&headerMeaning&&chosen.phase!==headerMeaning.phase){identity=null;reason='Source meaning and declared phase disagree; review the channel meaning.';}
    else if(chosen&&((physical&&physical!==chosen.quantity)||(declaredQuantity&&declaredQuantity!==chosen.quantity)||nonElectricalUnit(units)||nonElectricalUnit(declared))){identity=null;reason='Channel meaning and declared units disagree; review the channel meaning.';}
    else if(!physical&&!reviewed){identity=null;reason='Physical units are unresolved; review the channel meaning before pairing.';}
    else if(!identity&&!reviewed&&headerMeaning&&physical){identity=headerMeaning;}
    if(identity&&declaredQuantity&&declaredQuantity!==identity.quantity){identity=null;reason='Channel meaning and declared units disagree; review the channel meaning.';}
    if(!reason&&!identity)reason='Quantity/phase identity is unresolved; observations retained.';
    // A declared header phase cannot make an angle, RMS or DC trace an AC waveform.
    const key=identity?`${identity.meaning}/${flavour}`:null;
    return {quantity,meaning:identity?.meaning||null,phase:identity?.phase||'',flavour,key,
      reviewed,reason,source:reviewed?'Source-analysis meaning choice':'Unverified source label/header'};
  }
  function identify(channel,record,mappings={}){return identifyWith(channel,context(record),mappings);}
  function plan(left,right,mappingsLeft={},mappingsRight={}){
    const entries=[];
    for(const[side,record,mappings]of [['left',left,mappingsLeft],['right',right,mappingsRight]]){
      const ctx=context(record);
      for(const channel of ctx.channels)entries.push({side,channel,...identifyWith(channel,ctx,mappings)});
    }
    const buckets=new Map();
    for(const e of entries)if(e.key){if(!buckets.has(e.key))buckets.set(e.key,{left:[],right:[]});buckets.get(e.key)[e.side].push(e);}
    const rows=[],used=new Set();
    for(const e of entries){
      if(used.has(e))continue;
      const bucket=e.key?buckets.get(e.key):null,unique=bucket&&bucket.left.length===1&&bucket.right.length===1;
      const partner=unique?bucket[e.side==='left'?'right':'left'][0]:null;
      used.add(e);if(partner)used.add(partner);
      const duplicate=bucket&&(bucket.left.length>1||bucket.right.length>1);
      const label=e.meaning?(e.meaning+(e.flavour==='waveform'?'':' · '+e.flavour)):e.channel.label||e.channel.id;
      rows.push({key:partner?e.key:`${e.key||'unresolved'}/${e.side}/${e.channel.id}`,label,
        quantity:e.quantity,meaning:e.meaning,left:e.side==='left'?e.channel:partner?.channel||null,
        right:e.side==='right'?e.channel:partner?.channel||null,
        reason:partner?'Quantity/phase match for display only; independent amplitude scales.':duplicate?
          'Duplicate quantity/phase identity; no counterpart is selected automatically.':e.reason||'No matching quantity/phase counterpart in the other recording.',
        _sort:[phases[e.phase]??99,e.meaning||'',e.flavour,clean(e.channel.label),e.side,e.channel.id]});
    }
    const cmp=(a,b)=>{for(let i=0;i<a.length;i++){if(a[i]===b[i])continue;return typeof a[i]==='number'?a[i]-b[i]:a[i]<b[i]?-1:1;}return 0;};
    rows.sort((a,b)=>order[a.quantity]-order[b.quantity]||cmp(a._sort,b._sort));
    return ['voltage','other','current'].map(quantity=>({quantity,label:titles[quantity],rows:rows.filter(r=>r.quantity===quantity).map(({_sort,...r})=>r)})).filter(g=>g.rows.length);
  }
  return {plan,identify};
})();
if(typeof module!=='undefined')module.exports=DRChannelComparison;
