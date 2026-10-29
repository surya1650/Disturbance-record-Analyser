'use strict';
// A reviewed copy is a new artifact/revision; uploaded source bytes are never edited.
const instrumentEsc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function missingInstrumentRatings(file){
  const positive=v=>Number.isFinite(Number(v))&&Number(v)>0;
  return (file.channel_inventory||[]).filter(c=>c.kind==='analog'&&String(c.ps??c.primary_secondary??'').trim().toUpperCase()==='S'&&['A','KA','V','KV'].includes(String(c.unit??c.declared_units??'').trim().toUpperCase())&&!(positive(c.primary)&&positive(c.secondary)));
}
function instrumentReviewEditor(row,selectedFile=''){
  const records=(row.bundle?.files||[]).filter(f=>f.kind==='comtrade'&&!f.duplicate_of&&(!selectedFile||f.name===selectedFile)&&missingInstrumentRatings(f).length);
  if(!records.length)return '';
  const esc=instrumentEsc;
  return `<section class="instrument-review"><h3>Resolve missing CT / VT ratings</h3><p>The CFG declares secondary quantities but has missing or invalid instrument ratios. Enter the actual ratings to create a marked corrected copy. These inputs affect primary-unit calculations; raw waveform viewing remains available without them.</p>${records.map(f=>{
    const required=missingInstrumentRatings(f),unit=c=>String(c.unit??c.declared_units).trim().toUpperCase().endsWith('A')?'A':'V',kinds=[...new Set(required.map(unit))];
    if(!/^[0-9a-f]{64}$/.test(f.content_hash||''))return `<p>${esc(f.name)}: a complete source identity and matching data payload are needed before rechecking a reviewed copy. Inspect available source observations and the decode reason.</p>`;
    const common=kinds.map(u=>{const k=u==='A'?'ct':'vt',name=u==='A'?'CT':'VT';return `<div class="instrument-common-kind"><h4>${name} ratings (${u})</h4><label>Actual primary (${u})<input data-common="${k}-primary" type="number" min="0" step="any" placeholder="Enter verified rating"></label><label>Actual secondary (${u})<input data-common="${k}-secondary" type="number" min="0" step="any" placeholder="Enter verified rating"></label><button type="button" data-fill-ratings="${k}">Apply ${name} to listed ${u==='A'?'current':'voltage'} channels</button></div>`;}).join('');
    return `<details data-instrument-file="${esc(f.name)}" open><summary>${esc(f.name)} · required instrument inputs (${required.length} channels)</summary><p>Use amperes (A) for CT ratings and volts (V) for VT ratings on both sides. Enter primary and secondary ratings, not a bare ratio. VT ratings must use the same phase-to-phase or phase-to-neutral basis on both sides.</p><details class="instrument-common"><summary>Use shared verified ratings for channels of the same kind</summary>${common}<p class="field-help">Use shared values only when those actual ratings apply to every listed channel of that kind. Review each row.</p></details><div class="table-wrap"><table><thead><tr><th>Channel / original CFG declaration</th><th>Actual primary rating</th><th>Actual secondary rating</th></tr></thead><tbody>${required.map(c=>`<tr data-rating="${esc(c.id)}" data-unit="${unit(c)}"><td>${esc(c.id+' '+c.label)}<small>CFG: ${esc(c.primary)} / ${esc(c.secondary)} ${esc(c.unit??c.declared_units)} · secondary</small></td><td><input data-rating-value="primary" type="number" step="any" min="0" aria-label="${esc(c.id)} primary rating in ${unit(c)}" placeholder="Unknown"> ${unit(c)}</td><td><input data-rating-value="secondary" type="number" step="any" min="0" aria-label="${esc(c.id)} secondary rating in ${unit(c)}" placeholder="Unknown"> ${unit(c)}</td></tr>`).join('')}</tbody></table></div><label>Reviewer<input data-rating-reviewer maxlength="120" placeholder="Who checked the actual ratings?"></label><label>Source of these ratings<textarea data-rating-evidence maxlength="2000" placeholder="Relay settings, nameplate, drawing or other evidence"></textarea></label><label class="instrument-confirm"><input type="checkbox" data-rating-confirm> I checked the actual ratings and confirm the CFG secondary designation and a/b gains are appropriate. This is a declared review, not independent physical verification.</label><div class="inspection-toolbar"><button type="button" data-rating-action="check">Check inputs & rerun conformance</button><button type="button" data-rating-action="save">Create reviewed copy & recheck</button><button type="button" data-rating-action="download">Download reviewed COMTRADE ZIP</button></div><div class="instrument-rating-result" role="status"></div><p class="field-help">Original CFG/DAT/CFF and sample bytes stay unchanged. The reviewed copy, evidence and check results are saved in a new incident revision or included in the ZIP. Timing and other remaining blocks are reported, not bypassed.</p></details>`;
  }).join('')}</section>`;
}
function collectInstrumentReview(section,file){
  const ratios={};
  for(const row of section.querySelectorAll('[data-rating]')){
    const values={};for(const field of ['primary','secondary']){
      const input=row.querySelector(`[data-rating-value="${field}"]`),raw=input.value.trim(),value=Number(raw);
      if(input.validity?.badInput||!raw||!Number.isFinite(value)||value<1e-9||value>1e12)throw new Error(row.dataset.rating+': enter the actual positive '+field+' rating in '+row.dataset.unit+'.');
      values[field]=value;
    }ratios[row.dataset.rating]=values;
  }
  const reviewer=section.querySelector('[data-rating-reviewer]').value.trim(),evidence=section.querySelector('[data-rating-evidence]').value.trim();
  if(!reviewer||!evidence)throw new Error('Supply the reviewer and the source of the actual CT/VT ratings.');
  if(!section.querySelector('[data-rating-confirm]').checked)throw new Error('Confirm the reviewed secondary designation, gains and actual instrument ratings.');
  return {record_hash:file.content_hash,reviewer,evidence,confirmed_secondary:true,ratios};
}
function bindInstrumentReview(row,host=document,{onSuccess,signal}={}){
  host.querySelectorAll('[data-instrument-file]').forEach(section=>{
    const file=row.bundle.files.find(f=>f.name===section.dataset.instrumentFile),status=section.querySelector('.instrument-rating-result');
    if(!file)return;
    const current=()=>section.isConnected&&!signal?.aborted&&location.hash.startsWith('#incident/'+row.incident_id);
    section.onkeydown=e=>{if(e.key==='Enter'&&e.target.tagName==='INPUT')e.preventDefault();};
    section.querySelectorAll('input,textarea').forEach(input=>input.addEventListener('input',()=>{status.textContent='Inputs changed; check or create a reviewed copy using the current values.';}));
    section.querySelectorAll('[data-fill-ratings]').forEach(button=>button.onclick=()=>{
      const kind=button.dataset.fillRatings,u=kind==='ct'?'A':'V',primary=section.querySelector(`[data-common="${kind}-primary"]`),secondary=section.querySelector(`[data-common="${kind}-secondary"]`);
      if([primary,secondary].some(el=>el.validity?.badInput||!el.value||!Number.isFinite(Number(el.value))||Number(el.value)<1e-9||Number(el.value)>1e12)){status.textContent='Enter actual positive primary and secondary ratings before applying them.';return;}
      section.querySelectorAll(`[data-rating][data-unit="${u}"]`).forEach(r=>{r.querySelector('[data-rating-value="primary"]').value=primary.value;r.querySelector('[data-rating-value="secondary"]').value=secondary.value;});
      status.textContent='Shared ratings filled. Review every affected channel before checking or saving.';
    });
    section.querySelectorAll('[data-rating-action]').forEach(button=>button.onclick=async()=>{
      let review;try{review=collectInstrumentReview(section,file);}catch(error){status.textContent=error.message;return;}
      const controls=[...section.querySelectorAll('input,textarea,button')];controls.forEach(el=>el.disabled=true);status.textContent='Rechecking a derived copy with the supplied instrument ratings…';
      try{
        const action=button.dataset.ratingAction,request={record:file.name,revision:row.number,review};
        if(action==='download'){
          const response=await fetch(`/api/incidents/${row.incident_id}/instrument-review/export`,{method:'POST',signal,headers:{'Content-Type':'application/json','X-DR-Token':config?.token||''},body:JSON.stringify(request)});
          if(!response.ok){const error=await response.json();throw new Error(error.detail||'The reviewed export could not be generated.');}
          const blob=await response.blob();if(!current())return;
          const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='reviewed-instrument-ratios.zip';link.click();setTimeout(()=>URL.revokeObjectURL(url),3000);
          status.textContent='Reviewed COMTRADE ZIP downloaded with the original-source hashes, rating evidence and conformance results. Original incident files are unchanged.';return;
        }
        const saved=action==='save',result=await api(`/api/incidents/${row.incident_id}/instrument-review`,{...jsonPost({...request,save:saved}),signal});
        if(!current())return;
        const blocks=result.flags.filter(f=>f.startsWith('[BLOCK '));
        status.innerHTML=`<strong>${result.blocked?'Some operational checks still need review.':'The reviewed copy passes the current conformance gate.'}</strong>${blocks.map(f=>`<p>${instrumentEsc(f)}</p>`).join('')}<p>All checks ran again. Ratings are user-declared with evidence; original files are preserved.</p>`;
        if(saved){
          status.innerHTML+='<p>Reviewed copy saved. Waiting for the new revision to be inspected…</p>';
          for(let attempt=0;attempt<60;attempt++){
            if(!current())return;
            const updated=await api(`/api/incidents/${row.incident_id}`,{signal});
            if(!current())return;
            if(updated.number>result.revision){status.textContent='The reviewed copy was saved, and a newer incident revision now exists. Open the latest revision to continue.';return;}
            if(updated.number===result.revision&&!['queued','running'].includes(updated.state)){
              if(onSuccess){await onSuccess(updated,result);return;}
              await detail(row.incident_id);const select=document.getElementById('inspection-record');
              if(select&&[...select.options].some(o=>o.value===result.reviewed_record)){select.value=result.reviewed_record;select.dispatchEvent(new Event('change'));}
              notice('Reviewed copy created with original files preserved. Check its conformance status before operational assignment.');return;
            }
            await new Promise(resolve=>setTimeout(resolve,1000));
          }
          status.innerHTML+='<p>The revision remains queued. Reopen this incident to check its progress.</p>';
        }
      }catch(error){if(error.name!=='AbortError'&&current())status.textContent=error.message;}finally{controls.forEach(el=>el.disabled=false);}
    });
  });
}
if(typeof module!=='undefined')module.exports={missingInstrumentRatings,collectInstrumentReview,instrumentReviewEditor};
