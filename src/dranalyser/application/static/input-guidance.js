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
      {destination:'waveforms',label:'Inspect waveforms',state:samples?'Ready':'Check source',note:samples?`${samples.toLocaleString('en')} source samples. Inspect raw labels, analogs and recorded digital states without physical inputs.`:'Choose a recoverable recording; no line model or CT/VT values are needed for source inspection.'},
      {destination:'compare',label:'Compare recordings',state:others?'Ready':'Attach another capture',note:others?`${others} other recording${others===1?' is':'s are'} attached. Choose the second recording; no line, end confirmation or CT/VT review is required for visual comparison.`:'Attach another matching CFG/DAT pair to compare recorded values. Keep each pair in its own folder.'},
      {destination:'report',label:'Read report · location optional',state:'Observations first',note:'Build the source-observation report without a line model. Open optional fault location only when you want a physical distance; its own checks name the missing facts.'},
    ];
  }
  function workflowMarkup(row,source){
    return '<nav class="operator-workflow" aria-label="Steps for this recording"><ol>'+workflow(row,source).map((step,index)=>`<li><button type="button" data-go-feature="${step.destination}"><span>${index+1}</span> ${esc(step.label)}</button><small>${esc(step.state)}</small><p>${esc(step.note)}</p></li>`).join('')+'</ol></nav>';
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
    host.querySelector('[data-workspace-tab=inputs]')?.click();
    const details=[...host.querySelectorAll('[data-instrument-file]')].find(el=>el.dataset.instrumentFile===file);
    if(details){details.open=true;details.scrollIntoView({block:'start',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});}
  }
  return {assess,markup,workflow,workflowMarkup,preferredRecording,openInputs};
})();
if(typeof module!=='undefined')module.exports=DRInputGuidance;
