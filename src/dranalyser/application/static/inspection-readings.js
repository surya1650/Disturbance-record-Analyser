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
    return {window,reference,channels,groups};
  }
  function cursorView(result,reference=''){
    const channels=new Map(),groups={voltage:[],current:[]},meta=Object.entries(result?.channels||{});
    const ready=([,c])=>c.status==='observed'&&Number.isFinite(c.fundamental_rms)&&c.fundamental_rms>0&&Array.isArray(c.phasor)&&c.phasor.length===2&&c.phasor.every(Number.isFinite)&&c.phasor.some(v=>v!==0);
    reference=reference||meta.find(entry=>/^V(?:\s|$)/.test(entry[1].units)&&ready(entry))?.[0]||meta.find(ready)?.[0]||meta[0]?.[0]||'';
    const ref=result?.channels?.[reference],refOk=ref&&ready([reference,ref]);
    for(const[id,c]of meta){
      const valid=c.status==='observed'&&Number.isFinite(c.fundamental_rms)&&c.fundamental_rms>=0;
      const reading={id,label:c.label,units:c.units,rms:valid?c.fundamental_rms:null,sample_rms:Number.isFinite(c.sample_rms)?c.sample_rms:Number.isFinite(c.total_rms)?c.total_rms:null,angle_deg:null,one_cycle:true,reason:c.reason||'',angle_reason:'A nonzero supported angle reference is required.',relative_residual:c.relative_residual,dc:c.dc,window:result.window};
      if(valid&&refOk&&ready([id,c])){const degrees=(Math.atan2(c.phasor[1],c.phasor[0])-Math.atan2(ref.phasor[1],ref.phasor[0]))*180/Math.PI;reading.angle_deg=((degrees+540)%360)-180;reading.angle_reason='';}
      channels.set(id,reading);const kind=/^V(?:\s|$)/.test(c.units)?'voltage':/^A(?:\s|$)/.test(c.units)?'current':null;
      if(!kind)reading.vector_reason=id+': voltage/current vector needs engineering units; review CT/VT scaling ('+String(c.units||'unknown units')+').';
      if(kind&&reading.angle_deg!==null)groups[kind].push(reading);
    }
    return {window:result?.window,reference,channels,groups,one_cycle:true,basis:result?.basis||'',reason:result?.reason||''};
  }
  function readingMarkup(meta,point,reading,cursor){
    if(meta.kind==='digital')return `<div class="inspection-reading"><strong>${esc(meta.id+' '+meta.label)} · ${esc(cursor)}</strong><p>State: ${point?.[2]===null||!point?'Unknown':esc(point[2])}</p></div>`;
    const shortUnit=units=>/^raw counts|^counts/i.test(units||'')?'counts':String(units||'').split(/[ (]/)[0]||'?';
    const sourceUnit=meta.units,analysisUnit=reading?.units||'Analysis pending',reason=reading?.reason||reading?.angle_reason||'';
    const summary=/assumed/i.test(analysisUnit)?'Assumed scaling · details':reason?'Why / units':'Units / fit details';
    return `<div class="inspection-reading"><strong>${esc(meta.id+' '+meta.label)} · ${esc(cursor)}</strong><dl><dt>Instantaneous</dt><dd>${point?.[2]===null||!point?'Unknown':esc(num(point[2]))} <span title="${esc(sourceUnit)}">${esc(shortUnit(sourceUnit))}</span></dd>${reading?.one_cycle?`<dt>One-cycle RMS</dt><dd>${num(reading.sample_rms)} <span title="${esc(sourceUnit)}">${esc(shortUnit(sourceUnit))}</span></dd>`:''}<dt>${reading?.one_cycle?'Fundamental RMS':'Fitted RMS'}</dt><dd>${num(reading?.rms)} <span title="${esc(analysisUnit)}">${reading?.rms===null||!reading?'':esc(shortUnit(analysisUnit))}</span></dd><dt>Angle</dt><dd>${reading?.angle_deg===null||!reading?'Not available':num(reading.angle_deg)+'°'}</dd></dl><details class="inspection-reading-details"><summary>${summary}</summary><small>Instantaneous: ${esc(sourceUnit)}. Analysis: ${esc(analysisUnit)}.</small>${reason?'<small>'+esc(reason)+'</small>':''}${reading?.one_cycle?'<small>Trailing nominal cycle ending at the selected source sample; measured RMS includes DC/harmonics. Fundamental uses an actual-time Fourier projection. Relative residual: '+esc(num(reading.relative_residual))+'. DC: '+esc(num(reading.dc))+'. Display observation; not an operational fault-location phasor.</small>':''}</details></div>`;
  }
  function vectorMarkup(v,colors={}){
    const reasons=v.one_cycle?[...new Set([v.reason,...[...v.channels.values()].flatMap(c=>[c.reason||c.angle_reason,c.vector_reason])].filter(Boolean))].slice(0,3):[];
    return (reasons.length?'<p class="field-help">'+reasons.map(esc).join(' ')+'</p>':'')+(v.one_cycle&&v.window?`<p class="field-help">One trailing cycle · samples ${esc(v.window.start_index)}–${esc(v.window.stop_index-1)} · ends at ${esc(num(v.window.end_s))} local s. All vectors share this window.</p>`:'')+['voltage','current'].map(kind=>{
      const channels=v.groups[kind],scale=Math.max(...channels.map(c=>c.rms),0);
      const arrows=channels.map(c=>{const a=c.angle_deg*Math.PI/180,x=100+75*(c.rms/scale)*Math.cos(a),y=100-75*(c.rms/scale)*Math.sin(a),color=/^#[0-9a-f]{6}$/i.test(colors[c.id])?colors[c.id]:'#176d82';
        return `<line x1="100" y1="100" x2="${x}" y2="${y}" stroke="${color}" stroke-width="2"/><circle cx="${x}" cy="${y}" r="3" fill="${color}"/><text x="${x+3}" y="${y-3}">${esc(c.id)}</text>`;}).join('');
      return `<section><h4>${kind==='voltage'?'Voltage':'Current'} vectors</h4>${channels.length?`<svg viewBox="0 0 200 200" role="img" aria-label="${kind} relative source vectors"><circle cx="100" cy="100" r="75" fill="none" stroke="#dae3e9"/><path d="M15 100H185M100 15V185" stroke="#dae3e9"/>${arrows}</svg><small>Independent ${kind} scale · RMS magnitude</small>`:'<p>No supported nonzero '+kind+' vectors at this cursor.</p>'}</section>`;
    }).join('')+`<p class="field-help">Angles relative to ${esc(v.reference||'unselected reference')} ${v.one_cycle?'over one common trailing nominal cycle ending at the selected sample':'at a common fitted model centre'}. Source/assumed scaling and physical wiring remain unverified.</p>`;
  }
  return {esc,num,windowAt,view,cursorView,readingMarkup,vectorMarkup};
})();
if(typeof module!=='undefined')module.exports=DRReadings;
