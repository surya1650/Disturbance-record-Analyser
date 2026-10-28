'use strict';
function missingInstrumentRatings(file){
  return (file.channel_inventory||[]).filter(c=>c.kind==='analog'&&String(c.ps).toUpperCase()==='S'&&['A','KA','V','KV'].includes(String(c.unit).toUpperCase())&&!(Number.isFinite(Number(c.primary))&&Number(c.primary)>0&&Number.isFinite(Number(c.secondary))&&Number(c.secondary)>0));
}
function instrumentReviewEditor(row){
  const records=(row.bundle?.files||[]).filter(f=>f.kind==='comtrade'&&f.ok&&!f.duplicate_of&&missingInstrumentRatings(f).length);
  if(!records.length)return '';
  return `<section class="instrument-review"><h3>Provide missing CT / VT ratings</h3><p>The source declares secondary quantities but its instrument ratios are missing or invalid. These inputs are needed to calculate primary currents and voltages. A voltage-level profile does not supply CT/VT ratings. Leave them unknown and continue the waveform viewer if you cannot verify them.</p>${records.map(f=>`<details data-instrument-file="${escapeHtml(f.name)}" ${row.metadata?.assignments?.[f.name]?.role==='excluded'?'':'open'}><summary>${escapeHtml(f.name)} · what ratings were actually used?</summary><p>Enter both ratings in A for current channels, or V for voltage channels. Do not enter a bare ratio or guess from the line voltage. Different channels may use different transformers. VT ratings must use the same phase-to-phase or phase-to-neutral basis on both sides; do not mix them.</p><div class="instrument-common"><label>Shared CT primary (A)<input data-common="ct-primary" type="number" min="0" step="any"></label><label>Shared CT secondary (A)<input data-common="ct-secondary" type="number" min="0" step="any"></label><button type="button" data-fill-ratings="ct">Apply CT to listed current channels</button><label>Shared VT primary (V)<input data-common="vt-primary" type="number" min="0" step="any"></label><label>Shared VT secondary (V)<input data-common="vt-secondary" type="number" min="0" step="any"></label><button type="button" data-fill-ratings="vt">Apply VT to listed voltage channels</button></div><p class="field-help">Use the shared fields only when the same verified ratings apply to all listed channels of that kind. Review every row below.</p><div class="table-wrap"><table><thead><tr><th>Channel / CFG declaration</th><th>Actual primary rating</th><th>Actual secondary rating</th></tr></thead><tbody>${missingInstrumentRatings(f).map(c=>{const unit=String(c.unit).toUpperCase().endsWith('A')?'A':'V';return `<tr data-rating="${escapeHtml(c.id)}" data-unit="${unit}"><td>${escapeHtml(c.id+' '+c.label)}<small>CFG: ${escapeHtml(c.primary)} / ${escapeHtml(c.secondary)} ${escapeHtml(c.unit)} · secondary</small></td><td><input data-rating-value="primary" type="number" step="any" min="0" aria-label="${escapeHtml(c.id)} primary rating in ${unit}"> ${unit}</td><td><input data-rating-value="secondary" type="number" step="any" min="0" aria-label="${escapeHtml(c.id)} secondary rating in ${unit}"> ${unit}</td></tr>`;}).join('')}</tbody></table></div><label>Who reviewed these ratings?<input data-rating-reviewer maxlength="120" placeholder="Reviewer name"></label><label>Where do the ratings come from?<textarea data-rating-evidence maxlength="2000" placeholder="Relay setting export, instrument nameplate or other traceable evidence"></textarea></label><label><input type="checkbox" data-rating-confirm> I confirm these actual ratings and that the CFG secondary designation and a/b gains are appropriate. This is a declared review, not independent physical verification.</label><div class="inspection-toolbar"><button type="button" data-rating-action="check">Check inputs & rerun conformance</button><button type="button" data-rating-action="save">Create reviewed copy & recheck</button></div><div class="instrument-rating-result" role="status"></div><p class="field-help">The original CFG/DAT/CFF remains unchanged. Saving adds a marked, reviewed copy and its evidence to a new incident revision. DAT sample bytes are retained; every conformance check runs again. Timing or other remaining blocks are not bypassed.</p></details>`).join('')}</section>`;
}
function collectInstrumentReview(section,file){
  const ratios={};
  for(const row of section.querySelectorAll('[data-rating]')){
    const values={};for(const field of ['primary','secondary']){
      const raw=row.querySelector(`[data-rating-value="${field}"]`).value.trim(),value=Number(raw);
      if(!raw||!Number.isFinite(value)||value<1e-9||value>1e12)throw new Error(row.dataset.rating+': enter the actual positive '+field+' rating in '+row.dataset.unit+'.');
      values[field]=value;
    }ratios[row.dataset.rating]=values;
  }
  const reviewer=section.querySelector('[data-rating-reviewer]').value.trim(),evidence=section.querySelector('[data-rating-evidence]').value.trim();
  if(!reviewer||!evidence)throw new Error('Supply the reviewer and the source of the actual CT/VT ratings.');
  if(!section.querySelector('[data-rating-confirm]').checked)throw new Error('Confirm the reviewed secondary designation, gains and actual instrument ratings.');
  return {record_hash:file.content_hash,reviewer,evidence,confirmed_secondary:true,ratios};
}
function bindInstrumentReview(row){
  document.querySelectorAll('[data-instrument-file]').forEach(section=>{
    section.onkeydown=e=>{if(e.key==='Enter'&&e.target.tagName==='INPUT')e.preventDefault();};
    const file=row.bundle.files.find(f=>f.name===section.dataset.instrumentFile),status=section.querySelector('.instrument-rating-result');
    section.querySelectorAll('[data-fill-ratings]').forEach(button=>button.onclick=()=>{
      const kind=button.dataset.fillRatings,unit=kind==='ct'?'A':'V',primary=section.querySelector(`[data-common="${kind}-primary"]`).value,secondary=section.querySelector(`[data-common="${kind}-secondary"]`).value;
      if(!primary||!secondary||!Number.isFinite(Number(primary))||!Number.isFinite(Number(secondary))||Number(primary)<=0||Number(secondary)<=0){status.textContent='Enter actual primary and secondary ratings before applying them.';return;}
      section.querySelectorAll(`[data-rating][data-unit="${unit}"]`).forEach(r=>{r.querySelector('[data-rating-value="primary"]').value=primary;r.querySelector('[data-rating-value="secondary"]').value=secondary;});
    });
    section.querySelectorAll('[data-rating-action]').forEach(button=>button.onclick=async()=>{
      let review;try{review=collectInstrumentReview(section,file);}catch(error){status.textContent=error.message;return;}
      const buttons=[...section.querySelectorAll('[data-rating-action]')];buttons.forEach(b=>b.disabled=true);status.textContent='Rechecking a derived copy with the supplied instrument ratings…';
      try{
        const saved=button.dataset.ratingAction==='save',result=await api(`/api/incidents/${row.incident_id}/instrument-review`,jsonPost({record:file.name,revision:row.number,review,save:saved}));
        const blocks=result.flags.filter(f=>f.startsWith('[BLOCK '));
        status.innerHTML=`<strong>${result.blocked?'Other conformance checks still withhold operational analysis.':'The reviewed copy passes the current conformance gate.'}</strong>${blocks.map(f=>`<p>${escapeHtml(f)}</p>`).join('')}<p>Ratings are user-declared with evidence; this does not establish field accuracy.</p>`;
        if(saved){
          status.innerHTML+='<p>Reviewed copy saved. Waiting for its incident inspection…</p>';
          for(let attempt=0;attempt<60;attempt++){
            const updated=await api(`/api/incidents/${row.incident_id}`);
            if(!['queued','running'].includes(updated.state)){
              if(location.hash.startsWith('#incident/'+row.incident_id)){
                await detail(row.incident_id);
                const select=document.getElementById('inspection-record');
                if(select&&[...select.options].some(o=>o.value===result.reviewed_record)){select.value=result.reviewed_record;select.dispatchEvent(new Event('change'));}
                notice('Reviewed copy created with original files preserved. Check its latest conformance status before choosing its operational role.');
              }return;
            }await new Promise(resolve=>setTimeout(resolve,1000));
          }status.innerHTML+='<p>The revision remains queued. Reopen this incident to check its progress.</p>';
        }
      }catch(error){status.textContent=error.message;}finally{buttons.forEach(b=>b.disabled=false);}
    });
  });
}

if(typeof module!=='undefined')module.exports={missingInstrumentRatings,collectInstrumentReview};
