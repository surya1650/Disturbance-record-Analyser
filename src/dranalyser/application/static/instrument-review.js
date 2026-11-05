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
  return review?.record_hash===file.content_hash&&((review.basis==='PRIMARY'&&review.confirmed_primary===true&&Array.isArray(review.primary_channels))||(review.ratios&&typeof review.ratios==='object'))?review:null;
}
const primaryInstrumentReview=review=>review?.basis==='PRIMARY'&&review.confirmed_primary===true;
function primaryReviewableInstrumentChannels(row,file,requirements){
  const review=appliedInstrumentReview(row,file,requirements),saved=primaryInstrumentReview(review)?new Set(review.primary_channels):null;
  return (requirements?.primary_reviewable_channels||[]).filter(channel=>String(channel.recorded_ps??channel.recorded_primary_secondary??channel.ps??channel.primary_secondary??'').trim().toUpperCase()==='S'&&(!saved||saved.has(channel.id)));
}
const instrumentBasisChoices=section=>[...section.querySelectorAll('[data-rating-basis]')].filter(input=>Object.prototype.hasOwnProperty.call(input.dataset||{},'ratingBasis'));
function instrumentBasis(section){
  const choices=instrumentBasisChoices(section);
  return choices.length?choices.find(input=>input.checked)?.value||'':'secondary';
}
function updateInstrumentBasis(section){
  const basis=instrumentBasis(section),hasChoice=instrumentBasisChoices(section).length>0;
  for(const panel of section.querySelectorAll('[data-secondary-ratings]')){
    panel.hidden=hasChoice&&basis!=='secondary';
    panel.querySelectorAll('input,select').forEach(input=>input.disabled=hasChoice&&basis!=='secondary'||(input.hasAttribute('data-rating-value')&&!input.closest('[data-rating]').querySelector('[data-rating-override]').checked));
  }
  for(const panel of section.querySelectorAll('[data-primary-values]'))panel.hidden=basis!=='primary';
  const confirm=section.querySelector('[data-rating-confirm-text]');
  if(confirm)confirm.textContent=basis==='primary'?'I checked that the recorded engineering values already represent primary voltage/current for every listed channel. Apply no additional CT / VT multiplier. This is my declared review with source evidence.':'I checked that these ratings and any exceptions apply to their listed channels, that both VT ratings use the confirmed voltage basis, and that the CFG secondary designation and a/b gains are appropriate. This is my declared review with source evidence.';
  for(const panel of section.querySelectorAll('[data-rating-export]'))panel.hidden=hasChoice&&basis!=='secondary';
  const hasRatings=section.querySelectorAll('[data-rating]').length>0;
  for(const panel of section.querySelectorAll('[data-rating-declaration-fields]'))panel.hidden=hasChoice&&(!basis||(basis==='secondary'&&!hasRatings));
  for(const button of section.querySelectorAll('[data-rating-action]')){
    button.disabled=hasChoice&&(!basis||(basis==='secondary'&&!hasRatings)||(basis==='primary'&&button.dataset.ratingAction==='download'));
    if(button.dataset.ratingAction==='save')button.textContent=basis==='primary'?'Save primary values & recheck':'Save ratings & recheck';
  }
}
function instrumentBasisHint(requirements){
  const hint=requirements?.measurement_basis_hint;if(!hint)return '';
  const message=typeof hint==='string'?hint:hint.reason||hint.message||hint.summary||hint.description||'';
  const channels=(hint.channels||[]).filter(c=>typeof c.rms==='number'&&Number.isFinite(c.rms));
  const summaries=channels.map(c=>`${c.meaning||c.label||c.id}: ${Number(c.rms.toPrecision(4)).toLocaleString('en')} ${c.unit||''} RMS`).join(' · ');
  const support=hint.support,window=support&&Number.isFinite(support.start_s)&&Number.isFinite(support.end_s)?`One-cycle measurement window: ${Number(support.start_s.toPrecision(5))} to ${Number(support.end_s.toPrecision(5))} s.`:'';
  return message?`<div class="instrument-basis-hint"><p>${instrumentEsc(message)}</p>${summaries?`<p>${instrumentEsc(summaries)}</p>`:''}${window?`<p class="field-help">${instrumentEsc(window)}</p>`:''}<p class="field-help">Measured magnitudes are a guide only. They do not change the recording basis; confirm it from the recording settings or other source evidence.</p></div>`:'';
}
function reviewableInstrumentRatings(row,file,requirements){
  const review=appliedInstrumentReview(row,file,requirements),missing=requirements?.required_ratios??missingInstrumentRatings(file);
  const needed=new Set([...missing.map(c=>c.id),...Object.keys(review?.ratios||{}),...(primaryInstrumentReview(review)?(requirements?.reviewable_ratios||[]).map(c=>c.id):[])]);
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
  for(const input of instrumentBasisChoices(section))input.checked=Boolean(review&&(input.value===(primaryInstrumentReview(review)?'primary':'secondary')));
  updateInstrumentBasis(section);
}
function instrumentReviewEditor(row,selectedFile='',requirements={}){
  const records=(row.bundle?.files||[]).filter(f=>f.kind==='comtrade'&&!f.duplicate_of&&(!selectedFile||f.name===selectedFile)&&(reviewableInstrumentRatings(row,f,requirements[f.name]).length||primaryReviewableInstrumentChannels(row,f,requirements[f.name]).length));
  if(!records.length)return '';
  const esc=instrumentEsc;
  return `<section class="instrument-review"><h3>Confirm the recording values</h3><p>Choose whether the recorded engineering values are already primary or are actual CT / VT secondary values. A secondary flag or a 1 / 1 declaration alone cannot establish this. Valid original declarations remain unchanged unless you explicitly review their basis.</p>${records.map((f,index)=>{
    const requirement=requirements[f.name],review=appliedInstrumentReview(row,f,requirement),required=reviewableInstrumentRatings(row,f,requirement),primaryChannels=primaryReviewableInstrumentChannels(row,f,requirement),hasChoice=primaryChannels.length>0,unit=instrumentUnit,kinds=[...new Set(required.map(unit))],values=instrumentFormValues(required,review),basis=primaryInstrumentReview(review)?'primary':review?'secondary':'';
    if(!/^[0-9a-f]{64}$/.test(f.content_hash||''))return `<p>${esc(f.name)}: a complete source identity and matching data payload are needed before rechecking the saved ratings. Inspect available source observations and the decode reason.</p>`;
    const common=kinds.map(u=>{const k=u==='A'?'ct':'vt',name=u==='A'?'CT':'VT';return `<div class="instrument-common-kind"><h4>Universal ${name} ratings (${u})</h4><label>Actual primary (${u})<input data-common="${k}-primary" type="number" min="0" step="any" value="${esc(values.common[k]?.primary??'')}" placeholder="Enter verified rating"></label><label>Actual secondary (${u})<input data-common="${k}-secondary" type="number" min="0" step="any" value="${esc(values.common[k]?.secondary??'')}" placeholder="Enter verified rating"></label></div>`;}).join('');
    const choice=hasChoice?`<fieldset class="instrument-basis-choice"><legend>What do the recorded voltage and current values represent?</legend><label><input type="radio" name="instrument-basis-${index}-${esc(f.content_hash)}" data-rating-basis value="primary"${basis==='primary'?' checked':''}> <span>Use recorded primary values <small>No additional CT / VT multiplier.</small></span></label><label><input type="radio" name="instrument-basis-${index}-${esc(f.content_hash)}" data-rating-basis value="secondary"${basis==='secondary'?' checked':''}> <span>Actual secondary values <small>Requires the actual transformer ratings where missing.</small></span></label></fieldset>${instrumentBasisHint(requirement)}<div data-primary-values${basis==='primary'?'':' hidden'}><p>Keep the recorded engineering values in primary units. CT / VT ratings are not requested or multiplied again.</p><details><summary>Channels covered by this primary-value declaration (${primaryChannels.length})</summary><ul>${primaryChannels.map(c=>`<li data-primary-channel="${esc(c.id)}">${esc(c.id+' '+c.label)} · ${esc(c.unit??c.declared_units??'')}</li>`).join('')}</ul></details></div>`:'';
    const presets=hasChoice&&required.length?`<label>Verified secondary-rating preset (optional)<select data-rating-preset><option value="">Choose only if it matches the actual settings</option><option value="132">132 kV / 110 V line-to-line · CT 600 / 1 A</option><option value="220">220 kV / 110 V line-to-line · CT 800 / 1 A</option><option value="custom">Custom actual ratings</option></select></label><p class="field-help">Presets are entry shortcuts, not evidence of this recording's settings. Custom does not fill or clear your entries.</p>`:'';
    const vtBasis=hasChoice&&kinds.includes('V')?`<label>VT voltage basis on both sides<select data-vt-basis><option value="">Confirm the basis from the actual settings</option><option value="line-line">Both ratings are line-to-line</option><option value="phase-neutral">Both ratings are phase-to-neutral</option></select></label><p class="field-help">A 110 V line-to-line secondary rating corresponds to about 63.5 V phase-to-neutral. Do not treat every phase as 110 V. Use the same basis for both ratings.</p>`:'';
    return `<details data-instrument-file="${esc(f.name)}"${requirement?' data-ratings-loaded="true"':''} open><summary>${esc(f.name)} · ${review?(primaryInstrumentReview(review)?'saved primary values':'saved ratings'):'recording basis and instrument inputs'}</summary>${choice}<div data-secondary-ratings${hasChoice&&basis!=='secondary'?' hidden':''}><p>Use amperes (A) for CT ratings and volts (V) for VT ratings on both sides. Enter primary and secondary ratings, not a bare ratio. VT ratings must use the same phase-to-phase or phase-to-neutral basis on both sides.</p>${required.length?`<section class="instrument-common"><h4>Enter each rating once</h4>${presets}${common}${vtBasis}<p class="field-help">Universal CT applies automatically to listed current channels; universal VT applies to listed voltage channels. Valid existing ratios stay unchanged. Use exceptions below if a neutral or another channel has a different actual rating.</p></section><details class="instrument-overrides"><summary>Per-channel exceptions (optional) · ${required.length} affected channels</summary><p>Leave the exception boxes clear to use universal values. Enable a box only when that channel has different verified ratings.</p><div class="table-wrap"><table><thead><tr><th>Channel / original CFG declaration</th><th>Different rating?</th><th>Actual primary rating</th><th>Actual secondary rating</th></tr></thead><tbody>${required.map(c=>`<tr data-rating="${esc(c.id)}" data-unit="${unit(c)}"><td>${esc(c.id+' '+c.label)}<small data-rating-declaration>CFG: ${esc(c.primary)} / ${esc(c.secondary)} ${esc(c.unit??c.declared_units)} · secondary</small></td><td><label><input type="checkbox" data-rating-override${values.rows[c.id]?.override?' checked':''} aria-label="${esc(c.id)} use different ratings"> Override</label></td><td><input${values.rows[c.id]?.override?'':' disabled'} value="${esc(values.rows[c.id]?.primary??'')}" data-rating-value="primary" type="number" step="any" min="0" aria-label="${esc(c.id)} primary rating in ${unit(c)}" placeholder="Unknown"> ${unit(c)}</td><td><input${values.rows[c.id]?.override?'':' disabled'} value="${esc(values.rows[c.id]?.secondary??'')}" data-rating-value="secondary" type="number" step="any" min="0" aria-label="${esc(c.id)} secondary rating in ${unit(c)}" placeholder="Unknown"> ${unit(c)}</td></tr>`).join('')}</tbody></table></div></details>`:'<p class="recording-setup-ready">The original secondary ratings are complete and remain in use. Continue to Analyse; no new instrument entry or save is needed for this secondary basis.</p>'}</div><div data-rating-declaration-fields><label>Reviewer<input data-rating-reviewer value="${esc(review?.reviewer||'')}" maxlength="120" placeholder="Who checked the recording basis and actual settings?"></label><label>Source of this declaration<textarea data-rating-evidence maxlength="2000" placeholder="Recording settings, nameplate, drawing or other evidence">${esc(review?.evidence||'')}</textarea></label><label class="instrument-confirm"><input type="checkbox" data-rating-confirm> <span data-rating-confirm-text>${basis==='primary'?'I checked that the recorded engineering values already represent primary voltage/current for every listed channel. Apply no additional CT / VT multiplier. This is my declared review with source evidence.':'I checked that these universal ratings and any exceptions apply to their listed channels, and confirm the CFG secondary designation and a/b gains are appropriate. This is a declared review, not independent physical verification.'}</span></label><div class="inspection-toolbar"><button type="button" data-rating-action="check">Check inputs & rerun conformance</button><button type="button" data-rating-action="save">Save ratings & recheck</button></div></div><details data-rating-export${hasChoice&&basis!=='secondary'?' hidden':''}><summary>Optional corrected COMTRADE export</summary><p>Download a separate corrected copy only when another application needs it.</p><button type="button" data-rating-action="download">Download reviewed COMTRADE ZIP</button></details><div class="instrument-rating-result" role="status"></div><p class="field-help">Original CFG/DAT/CFF and sample bytes stay unchanged. The same recording and filename stay in this incident. Saved declarations, evidence and check results get a new input revision; an optional ZIP is a separate export. Timing and other remaining blocks are reported, not bypassed.</p></details>`;
  }).join('')}</section>`;
}
function collectInstrumentReview(section,file){
  const basis=instrumentBasis(section);
  if(!basis)throw new Error('Choose whether the recorded values are primary or actual secondary values.');
  const reviewer=section.querySelector('[data-rating-reviewer]').value.trim(),evidence=section.querySelector('[data-rating-evidence]').value.trim();
  if(!reviewer||!evidence)throw new Error('Supply the reviewer and the source of the recording basis and actual CT/VT ratings.');
  if(!section.querySelector('[data-rating-confirm]').checked)throw new Error(basis==='primary'?'Confirm that the listed recorded values are already primary and need no additional CT / VT multiplier.':'Confirm the reviewed secondary designation, gains and actual instrument ratings.');
  if(basis==='primary'){
    const primary_channels=[...section.querySelectorAll('[data-primary-channel]')].map(node=>node.dataset.primaryChannel).filter(Boolean);
    if(!primary_channels.length)throw new Error('No source-bound channels are available for this primary-value declaration. Reopen the recording.');
    return {record_hash:file.content_hash,reviewer,evidence,basis:'PRIMARY',confirmed_primary:true,primary_channels};
  }
  const vtBasis=section.querySelector('[data-vt-basis]');
  if(vtBasis&&!['line-line','phase-neutral'].includes(vtBasis.value))throw new Error('Confirm whether both VT ratings are line-to-line or both are phase-to-neutral.');
  if(vtBasis&&section.dataset?.presetVtBasis&&vtBasis.value!==section.dataset.presetVtBasis)throw new Error('The preset VT ratings are line-to-line. Choose that verified basis, or choose Custom and enter the actual phase-to-neutral ratings.');
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
  if(!Object.keys(ratios).length)throw new Error('The original secondary ratings are already complete; no replacement ratings are required.');
  return {record_hash:file.content_hash,reviewer,evidence,confirmed_secondary:true,ratios};
}
function bindInstrumentReview(row,host=document,{onSuccess,signal,isCurrent}={}){
  const bindSection=section=>{
    const file=row.bundle.files.find(f=>f.name===section.dataset.instrumentFile),status=section.querySelector('.instrument-rating-result');
    if(!file)return;
    const current=()=>section.isConnected&&!signal?.aborted&&(isCurrent?isCurrent():location.hash.startsWith('#incident/'+row.incident_id));
    let edited=false;
    const controlsInSection=()=>[...section.querySelectorAll('input,textarea,button'),...section.querySelectorAll('select')];
    section.onkeydown=e=>{if(e.key==='Enter'&&e.target.tagName==='INPUT')e.preventDefault();};
    [...section.querySelectorAll('input,textarea'),...section.querySelectorAll('select')].forEach(input=>input.addEventListener('input',()=>{edited=true;const confirm=section.querySelector('[data-rating-confirm]');if(input!==confirm)confirm.checked=false;status.textContent='Inputs changed; check and save the declaration for the current recording.';}));
    function updateInherited(kind){
      const unit=kind==='ct'?'A':'V';
      section.querySelectorAll(`[data-rating][data-unit="${unit}"]`).forEach(r=>{
        const override=r.querySelector('[data-rating-override]').checked;
        for(const field of ['primary','secondary']){const input=r.querySelector(`[data-rating-value="${field}"]`);input.disabled=!override||instrumentBasis(section)==='primary';if(!override){r.instrumentOverrideDraft??={};if(!Object.prototype.hasOwnProperty.call(r.instrumentOverrideDraft,field))r.instrumentOverrideDraft[field]=input.value;input.value=section.querySelector(`[data-common="${kind}-${field}"]`).value;}}
      });
    }
    section.querySelectorAll('[data-common]').forEach(input=>input.addEventListener('input',()=>updateInherited(input.dataset.common.split('-')[0])));
    section.querySelectorAll('[data-rating-override]').forEach(input=>input.addEventListener('change',()=>{
      edited=true;section.querySelector('[data-rating-confirm]').checked=false;const r=input.closest('[data-rating]');
      if(input.checked&&r.instrumentOverrideDraft){for(const field of ['primary','secondary'])r.querySelector(`[data-rating-value="${field}"]`).value=r.instrumentOverrideDraft[field]??'';delete r.instrumentOverrideDraft;}
      updateInherited(r.dataset.unit==='A'?'ct':'vt');status.textContent='Rating choices changed. Recheck before saving or downloading.';
    }));
    for(const input of instrumentBasisChoices(section))input.addEventListener('change',()=>{
      edited=true;section.querySelector('[data-rating-confirm]').checked=false;updateInstrumentBasis(section);
      status.textContent=input.value==='primary'?'Recorded values will remain primary. Any secondary-rating draft is retained if you switch back.':'Enter only verified actual secondary ratings. Any earlier draft is retained.';
    });
    section.querySelector('[data-rating-preset]')?.addEventListener('change',event=>{
      if(instrumentBasis(section)!=='secondary')return;
      edited=true;section.querySelector('[data-rating-confirm]').checked=false;
      const preset=event.target.value,ratings=preset==='132'?{ct:{primary:600,secondary:1},vt:{primary:132000,secondary:110}}:preset==='220'?{ct:{primary:800,secondary:1},vt:{primary:220000,secondary:110}}:null;
      delete section.dataset.presetVtBasis;
      if(ratings){
        for(const [kind,values] of Object.entries(ratings)){for(const [field,value] of Object.entries(values)){const input=section.querySelector(`[data-common="${kind}-${field}"]`);if(input)input.value=String(value);}updateInherited(kind);}
        if(section.querySelector('[data-vt-basis]')){section.dataset.presetVtBasis='line-line';section.querySelector('[data-vt-basis]').value='';}
        status.textContent='Preset copied into the fields. Verify the actual settings and confirm the VT line-to-line basis before saving.';
      }else status.textContent='Custom ratings remain as entered. Supply the verified actual values and voltage basis.';
    });
    updateInstrumentBasis(section);
    if(section.dataset.ratingsLoaded!=='true'){
      const controls=controlsInSection(),disabled=controls.map(input=>input.disabled);controls.forEach(input=>input.disabled=true);
      const restore=()=>controls.forEach((input,index)=>input.disabled=disabled[index]);
      const blockActions=()=>section.querySelectorAll('[data-rating-action]').forEach(button=>button.disabled=true);
      status.textContent='Checking which original channels need instrument ratings…';
      api(`/api/incidents/${row.incident_id}/instrument-review?record=${encodeURIComponent(file.name)}&revision=${row.number}`,{signal}).then(requirements=>{
      if(!current())return;
      if(requirements.record!==file.name||requirements.revision!==row.number||requirements.record_hash!==file.content_hash)throw new Error('Recording or revision changed; reopen these instrument inputs.');
      const required=reviewableInstrumentRatings(row,file,requirements),shown=[...section.querySelectorAll('[data-rating]')].map(r=>r.dataset.rating).sort(),primary=primaryReviewableInstrumentChannels(row,file,requirements),shownPrimary=[...section.querySelectorAll('[data-primary-channel]')].map(r=>r.dataset.primaryChannel).sort();
      const changed=JSON.stringify(required.map(c=>c.id).sort())!==JSON.stringify(shown)||JSON.stringify(primary.map(c=>c.id).sort())!==JSON.stringify(shownPrimary);
      if(edited){restore();if(changed){blockActions();status.textContent='The reviewable channels changed. Reopen this recording before saving; the current edits have been retained.';}else{section.dataset.ratingsLoaded='true';updateInstrumentBasis(section);}return;}
      if(changed){
        const replacementHost=document.createElement('div');replacementHost.innerHTML=instrumentReviewEditor(row,file.name,{[file.name]:requirements});
        const replacement=replacementHost.querySelector('[data-instrument-file]');
        if(!replacement){section.innerHTML='<p>No further instrument ratings are required for this recording.</p>';return;}
        section.replaceWith(replacement);bindSection(replacement);return;
      }
      restore();section.dataset.ratingsLoaded='true';
      hydrateInstrumentReview(section,required,appliedInstrumentReview(row,file,requirements));
      status.textContent=appliedInstrumentReview(row,file,requirements)?(primaryInstrumentReview(appliedInstrumentReview(row,file,requirements))?'Saved primary-value declaration loaded for this recording. Confirm it before saving changes.':'Saved ratings loaded for this recording. Confirm the current values before saving changes.'):'Confirm the recording basis, or enter the verified actual secondary ratings for the listed channels.';
    }).catch(error=>{if(current()&&error.name!=='AbortError'){restore();blockActions();status.textContent=error.message+' Reopen this recording to check its required channels before saving.';}});
    }
    section.querySelectorAll('[data-rating-action]').forEach(button=>button.onclick=async()=>{
      if(!current()||button.disabled)return;
      let review;try{review=collectInstrumentReview(section,file);}catch(error){status.textContent=error.message;return;}
      if(primaryInstrumentReview(review)&&button.dataset.ratingAction==='download'){status.textContent='Primary-value declarations apply to this original recording. A corrected secondary-ratio export is not available for this basis.';return;}
      const controls=controlsInSection(),disabledBefore=controls.map(el=>el.disabled);controls.forEach(el=>el.disabled=true);status.textContent='Rechecking this recording with the declared recording basis and instrument inputs…';
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
        status.innerHTML=`<strong>${result.blocked?'Some operational checks still need review.':'The recording passes the current conformance gate with these instrument inputs.'}</strong>${blocks.map(f=>`<p>${instrumentEsc(f)}</p>`).join('')}<p>All checks ran again. The recording basis and instrument inputs are user-declared with evidence; original files are preserved.</p>`;
        if(saved){
          status.innerHTML+='<p>Instrument inputs saved for this recording. Waiting for the input revision to be inspected…</p>';
          for(let attempt=0;attempt<60;attempt++){
            if(!current())return;
            const updated=await api(`/api/incidents/${row.incident_id}`,{signal});
            if(!current())return;
            if(updated.number>result.revision){status.textContent='The instrument inputs were saved, and a newer incident revision now exists. Open the latest revision to continue.';return;}
            if(updated.number===result.revision&&!['queued','running'].includes(updated.state)){
              if(onSuccess){await onSuccess(updated,result);return;}
              await detail(row.incident_id);const select=document.getElementById('inspection-record');
              const record=result.reviewed_record||result.record||file.name;if(select&&[...select.options].some(o=>o.value===record)){select.value=record;select.dispatchEvent(new Event('change'));}
              notice('Instrument inputs saved for this recording with original files preserved. Check the remaining input notes before operational assignment.');return;
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
if(typeof module!=='undefined')module.exports={missingInstrumentRatings,collectInstrumentReview,instrumentReviewEditor,appliedInstrumentReview,reviewableInstrumentRatings,primaryReviewableInstrumentChannels,instrumentFormValues,hydrateInstrumentReview,bindInstrumentReview,instrumentBasis,updateInstrumentBasis,instrumentBasisHint};
