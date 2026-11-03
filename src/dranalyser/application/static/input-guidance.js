'use strict';
const DRInputGuidance=(()=>{
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function assess(record={}){
    const blocks=(record.flags||[]).filter(f=>String(f).startsWith('[BLOCK'));
    const ratio=blocks.some(f=>/RATIO-P(?:\/)?S/.test(f));
    const items=[];
    if(ratio)items.push('Missing CT/VT ratings: enter the actual primary and secondary ratings. The app will recheck a marked CFG copy in a new revision.');
    if(blocks.some(f=>/TIME-/.test(f)))items.push('Source timing needs review for uniform-sample operational methods. Raw waveforms and supported actual-time diagnostics remain usable.');
    if(blocks.some(f=>/SCALE-/.test(f)))items.push('The recorded amplitude convention needs review before the affected physical calculations. A ratio correction does not settle this check.');
    if(blocks.some(f=>/CH-MISSING|CH-COLLISION/.test(f)))items.push('Review missing or competing channel meanings before assigning this record to the operational study.');
    if(blocks.length&&!items.length)items.push('Review the specific operational findings below. Waveform inspection remains available.');
    return {blocked:Boolean(record.blocked||blocks.length),ratio,blocks,items};
  }
  function markup(record={}){
    const state=assess(record);if(!state.blocked)return '';
    return `<section class="record-input-notice"><strong>Recoverable waveforms can be inspected.</strong><p>Inspect and compare the recorded values now. These findings affect optional physical calculations; they do not require you to supply a line model or CT/VT ratings just to view the source.</p><details><summary>Input review for optional physical calculations</summary>${state.items.map(v=>`<p>${esc(v)}</p>`).join('')}<button type="button" data-go-feature="inputs">Review required inputs →</button><details><summary>Exact operational findings</summary>${state.blocks.map(v=>`<p>${esc(v)}</p>`).join('')}</details></details></section>`;
  }
  function workflow(row={},source={}){
    const others=(row.bundle?.files||[]).filter(file=>file.kind==='comtrade'&&!file.duplicate_of&&file.name!==source.file).length;
    const samples=Number.isInteger(source.sample_count)&&source.sample_count>0?source.sample_count:0;
    return [
      {destination:'upload',label:'Upload',state:'Records retained',note:'Add the records for this incident. Original files and previous revisions are kept.'},
      {destination:'waveforms',label:'Analyse',state:samples?'Ready':'Check source',note:samples?`${samples.toLocaleString('en')} source samples. Inspect waveforms, RMS values, vectors and recorded signals.`:'Choose a recoverable recording; no line model or CT/VT values are needed for source inspection.'},
      {destination:'compare',label:'Compare',state:others?'Ready':'Optional',note:others?`${others} other recording${others===1?' is':'s are'} attached. Visual comparison needs no line, end confirmation or CT/VT review.`:'One recording is enough to start. Attach another capture when you want a comparison.'},
      {destination:'report',label:'Generate report',state:'Observations first',note:'Generate one incident report without a line model. Physical distance is optional; missing inputs are explained only where needed.'},
    ];
  }
  function workflowMarkup(row,source){
    return '<nav class="operator-workflow" aria-label="Incident steps"><ol>'+workflow(row,source).map((step,index)=>`<li>${step.destination==='upload'?`<a href="#upload/${encodeURIComponent(row.incident_id??row.id??'')}"><span>${index+1}</span> ${esc(step.label)}</a>`:`<button type="button" data-go-feature="${step.destination}"><span>${index+1}</span> ${esc(step.label)}</button>`}<small>${esc(step.state)}</small></li>`).join('')+'</ol></nav>';
  }
  function preferredRecording(row,records){
    const assignments=row.metadata?.assignments||{};
    const excluded=records.some(f=>assignments[f.name]?.role==='excluded');
    return (excluded?records.find(f=>/^reviewed-ratios-[0-9a-f]+\/reviewed\.(cfg|cff)$/i.test(f.name)):null)?.name||records[0]?.name||'';
  }
  function openInputs(file){
    const select=document.getElementById('inspection-record'),host=document.getElementById('inspection-workspace');
    if(!select||!host)return;
    host.dataset.requestedTask='inputs';host.dataset.requestedRecord=file;
    if(select.value!==file){select.value=file;select.dispatchEvent(new Event('change'));return;}
    host.querySelector('[data-workspace-tab=waveforms]')?.click();
    const inputs=host.querySelector('.operator-inputs');if(inputs)inputs.open=true;
    const details=[...host.querySelectorAll('[data-instrument-file]')].find(el=>el.dataset.instrumentFile===file);
    if(details){details.open=true;details.scrollIntoView({block:'start',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});}
  }
  return {assess,markup,workflow,workflowMarkup,preferredRecording,openInputs};
})();
if(typeof module!=='undefined')module.exports=DRInputGuidance;
