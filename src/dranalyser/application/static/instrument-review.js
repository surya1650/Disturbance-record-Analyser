'use strict';
// Reviewed ratings update the same logical recording in an input revision; source bytes remain original.
const instrumentEsc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function missingInstrumentRatings(file){
  const positive=v=>Number.isFinite(Number(v))&&Number(v)>0;
  return (file.channel_inventory||[]).filter(c=>c.kind==='analog'&&String(c.ps??c.primary_secondary??'').trim().toUpperCase()==='S'&&['A','KA','V','KV'].includes(String(c.unit??c.declared_units??'').trim().toUpperCase())&&!(positive(c.primary)&&positive(c.secondary)&&Number(c.primary)!==Number(c.secondary)));
}
const instrumentUnit=c=>String(c.unit??c.declared_units??'').trim().toUpperCase().endsWith('A')?'A':'V';
function appliedInstrumentReview(row,file,requirements){
  const review=requirements&&Object.prototype.hasOwnProperty.call(requirements,'applied_review')?requirements.applied_review:row.metadata?.assignments?.[file.name]?.instrument_review;
  return review?.record_hash===file.content_hash&&review.ratios&&typeof review.ratios==='object'?review:null;
}
function reviewableInstrumentRatings(row,file,requirements){
  const review=appliedInstrumentReview(row,file,requirements),missing=requirements?.required_ratios??missingInstrumentRatings(file);
  const needed=new Set([...missing.map(c=>c.id),...Object.keys(review?.ratios||{})]);
  return (requirements?.reviewable_ratios||file.channel_inventory||[]).filter(c=>needed.has(c.id)).map(c=>({...c,primary:c.recorded_primary??c.primary,secondary:c.recorded_secondary??c.secondary}));
}
function instrumentFormValues(required,review){
  const common={},rows={};
  for(const channel of required){
    const ratio=review?.ratios?.[channel.id],kind=instrumentUnit(channel)==='A'?'ct':'vt';
    if(ratio&&!common[kind])common[kind]=ratio;
  }
  for(const channel of required){
    const ratio=review?.ratios?.[channel.id],base=common[instrumentUnit(channel)==='A'?'ct':'vt'];
    rows[channel.id]={...(ratio||{}),override:Boolean(ratio&&base&&(ratio.primary!==base.primary||ratio.secondary!==base.secondary))};
  }
  return {common,rows};
}
function hydrateInstrumentReview(section,required,review){
  const values=instrumentFormValues(required,review),headers=new Map(required.map(c=>[c.id,c]));
  for(const [kind,ratio] of Object.entries(values.common))for(const field of ['primary','secondary']){
    const input=section.querySelector(`[data-common="${kind}-${field}"]`);if(input)input.value=String(ratio[field]);
  }
  for(const row of section.querySelectorAll('[data-rating]')){
    const channel=headers.get(row.dataset.rating);if(!channel)continue;
    const saved=values.rows[channel.id],override=row.querySelector('[data-rating-override]');override.checked=saved.override;
    for(const field of ['primary','secondary']){const input=row.querySelector(`[data-rating-value="${field}"]`);input.value=saved[field]===undefined?'':String(saved[field]);input.disabled=!saved.override;}
    const declaration=row.querySelector('[data-rating-declaration]');
    if(declaration)declaration.textContent='CFG: '+String(channel.primary)+' / '+String(channel.secondary)+' '+String(channel.unit??channel.declared_units??'')+' · secondary';
  }
  section.querySelector('[data-rating-reviewer]').value=review?.reviewer||'';
  section.querySelector('[data-rating-evidence]').value=review?.evidence||'';
  section.querySelector('[data-rating-confirm]').checked=false;
}
function instrumentReviewEditor(row,selectedFile='',requirements={}){
  const records=(row.bundle?.files||[]).filter(f=>f.kind==='comtrade'&&!f.duplicate_of&&(!selectedFile||f.name===selectedFile)&&reviewableInstrumentRatings(row,f,requirements[f.name]).length);
  if(!records.length)return '';
  const esc=instrumentEsc;
  return `<section class="instrument-review"><h3>Review CT / VT ratings for this recording</h3><p>Fill missing ratings or update the values already reviewed for this recording. Valid original declarations remain unchanged. These inputs affect primary-unit calculations; raw waveform viewing remains available without them.</p>${records.map(f=>{
    const review=appliedInstrumentReview(row,f,requirements[f.name]),required=reviewableInstrumentRatings(row,f,requirements[f.name]),unit=instrumentUnit,kinds=[...new Set(required.map(unit))],values=instrumentFormValues(required,review);
    if(!/^[0-9a-f]{64}$/.test(f.content_hash||''))return `<p>${esc(f.name)}: a complete source identity and matching data payload are needed before rechecking the saved ratings. Inspect available source observations and the decode reason.</p>`;
    const common=kinds.map(u=>{const k=u==='A'?'ct':'vt',name=u==='A'?'CT':'VT';return `<div class="instrument-common-kind"><h4>Universal ${name} ratings (${u})</h4><label>Actual primary (${u})<input data-common="${k}-primary" type="number" min="0" step="any" value="${esc(values.common[k]?.primary??'')}" placeholder="Enter verified rating"></label><label>Actual secondary (${u})<input data-common="${k}-secondary" type="number" min="0" step="any" value="${esc(values.common[k]?.secondary??'')}" placeholder="Enter verified rating"></label></div>`;}).join('');
    return `<details data-instrument-file="${esc(f.name)}"${requirements[f.name]?' data-ratings-loaded="true"':''} open><summary>${esc(f.name)} · ${review?'saved ratings':'required instrument inputs'} (${required.length} channels)</summary><p>Use amperes (A) for CT ratings and volts (V) for VT ratings on both sides. Enter primary and secondary ratings, not a bare ratio. VT ratings must use the same phase-to-phase or phase-to-neutral basis on both sides.</p><section class="instrument-common"><h4>Enter each rating once</h4>${common}<p class="field-help">Universal CT applies automatically to listed current channels; universal VT applies to listed voltage channels. Valid existing ratios stay unchanged. Use exceptions below if a neutral or another channel has a different actual rating.</p></section><details class="instrument-overrides"><summary>Per-channel exceptions (optional) · ${required.length} affected channels</summary><p>Leave the exception boxes clear to use universal values. Enable a box only when that channel has different verified ratings.</p><div class="table-wrap"><table><thead><tr><th>Channel / original CFG declaration</th><th>Different rating?</th><th>Actual primary rating</th><th>Actual secondary rating</th></tr></thead><tbody>${required.map(c=>`<tr data-rating="${esc(c.id)}" data-unit="${unit(c)}"><td>${esc(c.id+' '+c.label)}<small data-rating-declaration>CFG: ${esc(c.primary)} / ${esc(c.secondary)} ${esc(c.unit??c.declared_units)} · secondary</small></td><td><label><input type="checkbox" data-rating-override${values.rows[c.id]?.override?' checked':''} aria-label="${esc(c.id)} use different ratings"> Override</label></td><td><input${values.rows[c.id]?.override?'':' disabled'} value="${esc(values.rows[c.id]?.primary??'')}" data-rating-value="primary" type="number" step="any" min="0" aria-label="${esc(c.id)} primary rating in ${unit(c)}" placeholder="Unknown"> ${unit(c)}</td><td><input${values.rows[c.id]?.override?'':' disabled'} value="${esc(values.rows[c.id]?.secondary??'')}" data-rating-value="secondary" type="number" step="any" min="0" aria-label="${esc(c.id)} secondary rating in ${unit(c)}" placeholder="Unknown"> ${unit(c)}</td></tr>`).join('')}</tbody></table></div></details><label>Reviewer<input data-rating-reviewer value="${esc(review?.reviewer||'')}" maxlength="120" placeholder="Who checked the actual ratings?"></label><label>Source of these ratings<textarea data-rating-evidence maxlength="2000" placeholder="Relay settings, nameplate, drawing or other evidence">${esc(review?.evidence||'')}</textarea></label><label class="instrument-confirm"><input type="checkbox" data-rating-confirm> I checked that these universal ratings and any exceptions apply to their listed channels, and confirm the CFG secondary designation and a/b gains are appropriate. This is a declared review, not independent physical verification.</label><div class="inspection-toolbar"><button type="button" data-rating-action="check">Check inputs & rerun conformance</button><button type="button" data-rating-action="save">Save ratings & recheck</button></div><details><summary>Optional corrected COMTRADE export</summary><p>Download a separate corrected copy only when another application needs it.</p><button type="button" data-rating-action="download">Download reviewed COMTRADE ZIP</button></details><div class="instrument-rating-result" role="status"></div><p class="field-help">Original CFG/DAT/CFF and sample bytes stay unchanged. The same recording and filename stay in this incident. Saved ratings, evidence and check results get a new input revision; an optional ZIP is a separate export. Timing and other remaining blocks are reported, not bypassed.</p></details>`;
  }).join('')}</section>`;
}
function collectInstrumentReview(section,file){
  const ratios={};
  for(const row of section.querySelectorAll('[data-rating]')){
    const override=row.querySelector('[data-rating-override]')?.checked,kind=row.dataset.unit==='A'?'ct':'vt';
    const values={};for(const field of ['primary','secondary']){
      const input=override?row.querySelector(`[data-rating-value="${field}"]`):section.querySelector(`[data-common="${kind}-${field}"]`),raw=input?.value.trim()||'',value=Number(raw);
      if(input?.validity?.badInput||!raw||!Number.isFinite(value)||value<1e-9||value>1e12)throw new Error((override?row.dataset.rating:'Universal '+kind.toUpperCase())+': enter the actual positive '+field+' rating in '+row.dataset.unit+'.');
      values[field]=value;
    }
    const factor=values.primary/values.secondary;if(factor<1e-12||factor>1e12)throw new Error(row.dataset.rating+': primary/secondary ratio is outside the supported numerical range.');
    ratios[row.dataset.rating]=values;
  }
  const reviewer=section.querySelector('[data-rating-reviewer]').value.trim(),evidence=section.querySelector('[data-rating-evidence]').value.trim();
  if(!reviewer||!evidence)throw new Error('Supply the reviewer and the source of the actual CT/VT ratings.');
  if(!section.querySelector('[data-rating-confirm]').checked)throw new Error('Confirm the reviewed secondary designation, gains and actual instrument ratings.');
  return {record_hash:file.content_hash,reviewer,evidence,confirmed_secondary:true,ratios};
}
function bindInstrumentReview(row,host=document,{onSuccess,signal,isCurrent}={}){
  const bindSection=section=>{
    const file=row.bundle.files.find(f=>f.name===section.dataset.instrumentFile),status=section.querySelector('.instrument-rating-result');
    if(!file)return;
    const current=()=>section.isConnected&&!signal?.aborted&&(isCurrent?isCurrent():location.hash.startsWith('#incident/'+row.incident_id));
    let edited=false;
    section.onkeydown=e=>{if(e.key==='Enter'&&e.target.tagName==='INPUT')e.preventDefault();};
    section.querySelectorAll('input,textarea').forEach(input=>input.addEventListener('input',()=>{edited=true;const confirm=section.querySelector('[data-rating-confirm]');if(input!==confirm)confirm.checked=false;status.textContent='Inputs changed; check and save these ratings for the current recording.';}));
    function updateInherited(kind){
      const unit=kind==='ct'?'A':'V';
      section.querySelectorAll(`[data-rating][data-unit="${unit}"]`).forEach(r=>{
        const override=r.querySelector('[data-rating-override]').checked;
        for(const field of ['primary','secondary']){const input=r.querySelector(`[data-rating-value="${field}"]`);input.disabled=!override;if(!override)input.value=section.querySelector(`[data-common="${kind}-${field}"]`).value;}
      });
    }
    section.querySelectorAll('[data-common]').forEach(input=>input.addEventListener('input',()=>updateInherited(input.dataset.common.split('-')[0])));
    section.querySelectorAll('[data-rating-override]').forEach(input=>input.addEventListener('change',()=>{edited=true;section.querySelector('[data-rating-confirm]').checked=false;const r=input.closest('[data-rating]');updateInherited(r.dataset.unit==='A'?'ct':'vt');status.textContent='Rating choices changed. Recheck before saving or downloading.';}));
    if(section.dataset.ratingsLoaded!=='true'){
      const controls=[...section.querySelectorAll('input,textarea,button')],disabled=controls.map(input=>input.disabled);controls.forEach(input=>input.disabled=true);
      const restore=()=>controls.forEach((input,index)=>input.disabled=disabled[index]);
      const blockActions=()=>section.querySelectorAll('[data-rating-action]').forEach(button=>button.disabled=true);
      status.textContent='Checking which original channels need instrument ratings…';
      api(`/api/incidents/${row.incident_id}/instrument-review?record=${encodeURIComponent(file.name)}&revision=${row.number}`,{signal}).then(requirements=>{
      if(!current())return;
      if(requirements.record!==file.name||requirements.revision!==row.number||requirements.record_hash!==file.content_hash)throw new Error('Recording or revision changed; reopen these instrument inputs.');
      const required=reviewableInstrumentRatings(row,file,requirements),shown=[...section.querySelectorAll('[data-rating]')].map(r=>r.dataset.rating).sort();
      if(edited){restore();if(JSON.stringify(required.map(c=>c.id).sort())!==JSON.stringify(shown)){blockActions();status.textContent='The reviewable channels changed. Reopen this recording before saving; the current edits have been retained.';}else section.dataset.ratingsLoaded='true';return;}
      if(JSON.stringify(required.map(c=>c.id).sort())!==JSON.stringify(shown)){
        const replacementHost=document.createElement('div');replacementHost.innerHTML=instrumentReviewEditor(row,file.name,{[file.name]:requirements});
        const replacement=replacementHost.querySelector('[data-instrument-file]');
        if(!replacement){section.innerHTML='<p>No further instrument ratings are required for this recording.</p>';return;}
        section.replaceWith(replacement);bindSection(replacement);return;
      }
      restore();section.dataset.ratingsLoaded='true';
      hydrateInstrumentReview(section,required,appliedInstrumentReview(row,file,requirements));
      status.textContent=appliedInstrumentReview(row,file,requirements)?'Saved ratings loaded for this recording. Confirm the current values before saving changes.':'Enter the actual ratings for the listed unresolved channels.';
    }).catch(error=>{if(current()&&error.name!=='AbortError'){restore();blockActions();status.textContent=error.message+' Reopen this recording to check its required channels before saving.';}});
    }
    section.querySelectorAll('[data-rating-action]').forEach(button=>button.onclick=async()=>{
      let review;try{review=collectInstrumentReview(section,file);}catch(error){status.textContent=error.message;return;}
      const controls=[...section.querySelectorAll('input,textarea,button')],disabledBefore=controls.map(el=>el.disabled);controls.forEach(el=>el.disabled=true);status.textContent='Rechecking this recording with the supplied instrument ratings…';
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
        status.innerHTML=`<strong>${result.blocked?'Some operational checks still need review.':'The recording passes the current conformance gate with these reviewed ratings.'}</strong>${blocks.map(f=>`<p>${instrumentEsc(f)}</p>`).join('')}<p>All checks ran again. Ratings are user-declared with evidence; original files are preserved.</p>`;
        if(saved){
          status.innerHTML+='<p>Ratings saved for this recording. Waiting for the input revision to be inspected…</p>';
          for(let attempt=0;attempt<60;attempt++){
            if(!current())return;
            const updated=await api(`/api/incidents/${row.incident_id}`,{signal});
            if(!current())return;
            if(updated.number>result.revision){status.textContent='The ratings were saved, and a newer incident revision now exists. Open the latest revision to continue.';return;}
            if(updated.number===result.revision&&!['queued','running'].includes(updated.state)){
              if(onSuccess){await onSuccess(updated,result);return;}
              await detail(row.incident_id);const select=document.getElementById('inspection-record');
              const record=result.reviewed_record||result.record||file.name;if(select&&[...select.options].some(o=>o.value===record)){select.value=record;select.dispatchEvent(new Event('change'));}
              notice('Ratings saved for this recording with original files preserved. Check the remaining input notes before operational assignment.');return;
            }
            await new Promise(resolve=>setTimeout(resolve,1000));
          }
          status.innerHTML+='<p>The revision remains queued. Reopen this incident to check its progress.</p>';
        }
      }catch(error){if(error.name!=='AbortError'&&current())status.textContent=error.message;}finally{controls.forEach((el,i)=>el.disabled=disabledBefore[i]);}
    });
  };
  host.querySelectorAll('[data-instrument-file]').forEach(bindSection);
}
if(typeof module!=='undefined')module.exports={missingInstrumentRatings,collectInstrumentReview,instrumentReviewEditor,appliedInstrumentReview,reviewableInstrumentRatings,instrumentFormValues,hydrateInstrumentReview,bindInstrumentReview};
