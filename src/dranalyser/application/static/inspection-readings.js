'use strict';
const DRReadings=(()=>{
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=v=>Number.isFinite(v)?v.toPrecision(6):'Not available';
  function windowAt(result,index){
    if(!Number.isInteger(index))return null;
    return (result?.windows||[]).filter(w=>w.start_index<=index&&index<w.stop_index)
      .sort((a,b)=>Math.abs((a.start_index+a.stop_index-1)/2-index)-Math.abs((b.start_index+b.stop_index-1)/2-index))[0]||null;
  }
  function phasor(c){return c?.status==='model_consistent'&&Number.isFinite(c.rms)&&c.rms>=0&&c.phasor?.length===2&&c.phasor.every(Number.isFinite)&&Number.isFinite(c.centre_s);}
  function view(result,index,reference=''){
    const window=windowAt(result,index),channels=new Map(),groups={voltage:[],current:[]},meta=result?.channels||[];
    const ready=c=>{const f=window?.channels[c.id];return phasor(f)&&f.rms>0&&f.phasor.some(v=>v!==0);};
    reference=reference||meta.find(c=>c.meaning==='VA'&&ready(c))?.id||meta.find(ready)?.id||meta[0]?.id||'';
    const ref=window?.channels[reference],refOk=phasor(ref)&&ref.rms>0&&ref.phasor.some(v=>v!==0);
    for(const c of meta){
      const fit=window?.channels[c.id];let reading={id:c.id,label:c.label,units:c.units,rms:null,angle_deg:null,reason:fit?.reason||'No supported model window covers this cursor.'};
      if(phasor(fit)){
        reading={...reading,rms:fit.rms,centre_s:fit.centre_s,reason:'',angle_reason:'A nonzero reference and matching model centre are required.'};
        if(refOk&&fit.rms>0&&fit.phasor.some(v=>v!==0)&&Math.abs(fit.centre_s-ref.centre_s)<=1e-12){
          const degrees=(Math.atan2(fit.phasor[1],fit.phasor[0])-Math.atan2(ref.phasor[1],ref.phasor[0]))*180/Math.PI;
          reading.angle_deg=((degrees+540)%360)-180;reading.angle_reason='';
        }
      }
      channels.set(c.id,reading);
      const kind=/^V(?:\s|$)/.test(c.units)?'voltage':/^A(?:\s|$)/.test(c.units)?'current':null;
      if(kind&&reading.angle_deg!==null)groups[kind].push(reading);
    }
    const reasons={};for(const kind of ['voltage','current']){
      const units=kind==='voltage'?/^V(?:\s|$)/:/^A(?:\s|$)/;
      reasons[kind]=meta.filter(c=>units.test(c.units)).map(c=>{const r=channels.get(c.id);return r.angle_deg===null?`${c.id}: ${r.reason||r.angle_reason||'A nonzero phasor is required.'}`:null;}).filter(Boolean);
      if(!reasons[kind].length&&!groups[kind].length)reasons[kind]=[result?'No channels with supported '+kind+' units.':'Electrical analysis is being prepared.'];
    }
    return {window,reference,channels,groups,reasons};
  }
  function readingMarkup(meta,point,reading,cursor,rmsPoint,rmsReason){
    if(meta.kind==='digital')return `<div class="inspection-reading"><strong>${esc(meta.id+' '+meta.label)} · ${esc(cursor)}</strong><p>State: ${point?.[2]===null||!point?'Unknown':esc(point[2])}</p></div>`;
    return `<div class="inspection-reading"><strong>${esc(meta.id+' '+meta.label)} · ${esc(cursor)}</strong><dl><dt>Instantaneous</dt><dd>${point?.[2]===null||!point?'Unknown':esc(num(point[2]))}<small>${esc(meta.units)}</small></dd><dt>Sample RMS · 1 cycle</dt><dd>${num(rmsPoint?.[2])}<small>${esc(meta.units)}</small></dd><dt>Fundamental RMS</dt><dd>${num(reading?.rms)}<small>${esc(reading?.units||'Analysis pending')}</small></dd><dt>Angle</dt><dd>${reading?.angle_deg===null||!reading?'Not available':num(reading.angle_deg)+'°'}</dd></dl>${rmsPoint?.[2]===null||!rmsPoint?`<small>${esc(rmsReason||'A complete trailing sample window is required.')}</small>`:''}${reading?.reason?`<details><summary>Why unavailable?</summary>${esc(reading.reason)}</details>`:''}${reading?.rms!==null&&reading?.angle_deg===null?`<small>${esc(reading?.angle_reason||'')}</small>`:''}</div>`;
  }
  function graphMarkup(meta,point,rmsPoint,reading,mode,timeLabel=''){
    const units=meta.units?.startsWith('raw')?'counts':meta.units?.split(' ')[0]||'';
    const instant=point&&Number.isFinite(point[2])?num(point[2]):'Unknown';
    if(meta.kind==='digital')return `<strong>${esc(meta.id)} · State ${esc(instant)}</strong><span>${esc(timeLabel)}</span>`;
    return `<strong>${esc(meta.id)} <span>${esc(timeLabel)}</span></strong><span>Instantaneous <b>${esc(instant)} ${esc(units)}</b></span><span>Sample RMS <b>${num(rmsPoint?.[2])} ${esc(units)}</b></span>${mode==='fundamental'?`<span>Fundamental RMS <b>${num(reading?.rms)} ${esc(reading?.units?.split(' ')[0]||units)}</b></span>`:''}`;
  }
  function vectorMarkup(v,colors={}){
    return ['voltage','current'].map(kind=>{
      const channels=v.groups[kind],scale=Math.max(...channels.map(c=>c.rms),0);
      const arrows=channels.map(c=>{const a=c.angle_deg*Math.PI/180,x=100+75*(c.rms/scale)*Math.cos(a),y=100-75*(c.rms/scale)*Math.sin(a),color=/^#[0-9a-f]{6}$/i.test(colors[c.id])?colors[c.id]:'#176d82';
        return `<line x1="100" y1="100" x2="${x}" y2="${y}" stroke="${color}" stroke-width="2"/><circle cx="${x}" cy="${y}" r="3" fill="${color}"/><text x="${x+3}" y="${y-3}">${esc(c.id)}</text>`;}).join('');
      return `<section><h4>${kind==='voltage'?'Voltage':'Current'} vectors</h4><svg viewBox="0 0 200 200" role="img" aria-label="${kind} relative source vectors"><circle cx="100" cy="100" r="75" fill="none" stroke="#dae3e9"/><path d="M15 100H185M100 15V185" stroke="#dae3e9"/>${arrows}</svg>${channels.length?`<small>Independent ${kind} scale · RMS magnitude</small>`:'<p>No supported nonzero '+kind+' vectors at this cursor.</p><small>'+esc(v.reasons?.[kind]?.[0]||'A supported nonzero fundamental and reference are required.')+'</small>'}${v.reasons?.[kind]?.length?`<details><summary>${channels.length?'Some channels unavailable':'Why unavailable?'}</summary>${v.reasons[kind].map(reason=>`<p>${esc(reason)}</p>`).join('')}</details>`:''}</section>`;
    }).join('')+`<p class="field-help">Angles relative to ${esc(v.reference||'unselected reference')} at a common fitted model centre. Source/assumed scaling and physical wiring remain unverified.</p>`;
  }
  return {esc,num,windowAt,view,readingMarkup,graphMarkup,vectorMarkup};
})();
if(typeof module!=='undefined')module.exports=DRReadings;
