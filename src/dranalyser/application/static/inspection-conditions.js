'use strict';
const DRConditions=(()=>{
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=v=>Number.isFinite(v)?v.toPrecision(6):'Not available';
  function ratio(before,after){if(!(before>0)||!Number.isFinite(after)||after<0)return null;const r=after/before;return Number.isFinite(r)&&(r>0||after===0)?r:null;}
  function aggregate(result,lo,hi){
    const windows=(result.windows||[]).filter(w=>w.start_index>=lo&&w.stop_index<=hi&&w.start_index<w.stop_index);
    return result.channels.map(c=>{
      const values=windows.map(w=>w.channels[c.id]).filter(f=>f?.status==='model_consistent'&&Number.isFinite(f.rms)&&f.rms>=0).map(f=>f.rms).sort((a,b)=>a-b),m=Math.floor(values.length/2);
      return {id:c.id,label:c.label,meaning:c.meaning,units:c.units,rms:values.length?(values.length%2?values[m]:values[m-1]/2+values[m]/2):null,windows:values.length,
        reason:values.length?'':'No complete supported model window lies within this selected region.'};
    });
  }
  function build(result,bounds=null){
    const n=result.sample_count;
    if(bounds&&(!Number.isInteger(bounds.start)||!Number.isInteger(bounds.end)||bounds.start<0||bounds.end>n||bounds.start>=bounds.end))throw new Error('Place cursor A before cursor B within the capture, then apply the fault interval.');
    const selection=bounds?{...bounds,source:'operator A/B selection',basis:'Fault interval is [A,B); B starts post-fault. These are selected regions, not detected physical fault boundaries.'}:null;
    const regions=bounds?[['Pre-fault',0,bounds.start],['Fault',bounds.start,bounds.end],['Post-fault',bounds.end,n]].map(([name,lo,hi])=>({name,bounds:[lo,hi],channels:aggregate(result,lo,hi)})):[];
    const interpretations=[];
    if(bounds){for(const before of regions[0].channels){const during=regions[1].channels.find(c=>c.id===before.id&&c.units===before.units);if(!during||before.rms===null||during.rms===null)continue;
      const r=ratio(before.rms,during.rms),direction=during.rms>before.rms?'higher':during.rms<before.rms?'lower':'unchanged';
      interpretations.push(`${before.label}: fault-region fitted RMS ${direction} than selected pre-fault (${num(before.rms)} → ${num(during.rms)} ${before.units}${r===null?'':'; '+num(r)+'×'}).`);}}
    return {selection,regions,trip:result.trip?.text,ar:result.ar?.text,overview:result.channels.map(c=>({id:c.id,label:c.label,meaning:c.meaning,units:c.units,min:c.sample_min,max:c.sample_max})),interpretations,
      note:'Region RMS is the median of complete, supported fitted windows. Region labels are operator choices; source scaling/wiring and physical fault identity remain unverified.'};
  }
  function markup(report){
    const indications=report.trip||report.ar?`<h3>Trip and autoreclose</h3><p>${esc(report.trip||'No trip interpretation supplied.')}</p><p>${esc(report.ar||'No AR interpretation supplied.')}</p>`:'';
    const overview='<table><thead><tr><th>Channel / meaning</th><th>Recorded voltage or current range</th></tr></thead><tbody>'+report.overview.map(c=>`<tr><th>${esc(c.id+' '+c.label)}<small>${esc(c.meaning||'Assign channel meaning')}</small></th><td>${num(c.min)} to ${num(c.max)} <small>${esc(c.units)}</small></td></tr>`).join('')+'</tbody></table>';
    if(!report.selection)return '<h3>Voltage and current overview</h3><p>Select the fault interval with cursors A and B, then use “Compare A–B conditions” for pre-fault, fault and post-fault conditions. Supported cursor RMS/angles are beside the waveforms.</p>'+overview+indications;
    return `<h3>Pre-fault, fault and post-fault conditions</h3><p>${esc(report.note)}</p><p class="field-help">Selection: ${esc(report.selection.source)} · A starts fault; B starts post-fault. Reapply after moving cursors.</p><table><thead><tr><th>Channel</th>${report.regions.map(r=>`<th>${r.name} · fitted RMS</th>`).join('')}</tr></thead><tbody>${report.overview.map(c=>`<tr><th>${esc(c.id+' '+c.label)}<small>${esc(c.units)}</small></th>${report.regions.map(r=>{const channel=r.channels.find(ch=>ch.id===c.id);return `<td>${num(channel?.rms)}${channel?.rms===null?'<small>'+esc(channel.reason)+'</small>':''}</td>`;}).join('')}</tr>`).join('')}</tbody></table><h4>Current and voltage interpretation</h4>${report.interpretations.length?'<ul>'+report.interpretations.map(v=>'<li>'+esc(v)+'</li>').join('')+'</ul>':'<p>No matching supported pre-fault/fault RMS values inside the selected regions. Enlarge the selected supports or review the waveform/mapping.</p>'}${indications}`;
  }
  return {ratio,build,markup};
})();
if(typeof module!=='undefined')module.exports=DRConditions;
