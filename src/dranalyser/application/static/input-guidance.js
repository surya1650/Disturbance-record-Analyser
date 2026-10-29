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
    return `<section class="record-input-notice"><strong>Waveforms are available. Some operational calculations need input review.</strong>${state.items.map(v=>`<p>${esc(v)}</p>`).join('')}<button type="button" data-go-feature="inputs">Review required inputs →</button><details><summary>Exact operational findings</summary>${state.blocks.map(v=>`<p>${esc(v)}</p>`).join('')}</details></section>`;
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
  return {assess,markup,preferredRecording,openInputs};
})();
if(typeof module!=='undefined')module.exports=DRInputGuidance;
