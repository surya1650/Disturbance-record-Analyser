'use strict';

async function loadStageReviewSource(row) {
  if (!config.stage_input_review || row.state !== 'needs_review') return;
  const previous = (row.revisions || []).filter(r=>r.number<row.number && ['completed','attention'].includes(r.state)).sort((a,b)=>b.number-a.number)[0];
  if (previous) row.stageSource = (await api(`/api/incidents/${row.incident_id}?revision=${previous.number}`)).result?.relay_evidence || [];
}

function stageReviewEditor(row) {
  if (!config.stage_input_review) return '';
  const esc = escapeHtml;
  const records = (row.stageSource || []).filter(r=>r.stages?.inventory_hash && r.stages.status==='observed');
  return `<section class="detail-section"><h3>Review corresponding fault stages</h3><p>Give corresponding intervals at different relays the same group label within this incident. Use separate labels for initial faults, evolving stages and each reclose shot. Confirm from supporting evidence; similar current patterns and matching trigger zeros do not establish identity.</p>${records.map(r=>{
    const source=row.bundle.files.find(f=>f.name===r.file), old=row.metadata.assignments?.[r.file]?.stage_review || {};
    if(!source || source.content_hash!==r.record_hash)return `<p>${esc(r.file)}: current source prerequisites are unavailable.</p>`;
    const review=old.inventory_hash===r.stages.inventory_hash ? old : {};
    return `<details data-stage-file="${esc(r.file)}"><summary>${esc(r.file)} · local stage identities</summary><p>${esc(r.stages.caveat)}</p><label class="rx-check"><input type="checkbox" class="stage-enabled" ${review.inventory_hash?'checked':''}> Include this stage review in the next revision</label>${r.stages.intervals.filter(s=>s.stable && s.phase_pattern && (!r.stages.quality_reasons.length || s.estimation_window?.status==='eligible')).map(s=>`<label>${esc(s.id)} · ${esc(s.kind)} · ${esc(s.phase_pattern)} · ${s.start_s.toFixed(4)} → ${s.end_s.toFixed(4)} local s<input data-stage-id="${esc(s.id)}" maxlength="80" pattern="[A-Za-z0-9_-]+" value="${esc(review.groups?.[s.id] || '')}" placeholder="Group label, or blank to leave unreviewed"></label>`).join('')}<label>Reviewer<input class="stage-reviewer" maxlength="200" value="${esc(review.reviewer || '')}"></label><label>Supporting evidence / rationale<input class="stage-reason" maxlength="1000" value="${esc(review.reason || '')}"></label>${[['same_incident','These selected intervals belong to this incident'],['same_circuit','These records represent the same line/circuit and the declared relays'],['stage_identity','Each group identifies the same physical stage across the reviewed relays']].map(([key,label])=>`<label class="rx-check"><input type="checkbox" data-stage-confirm="${key}" ${review[key]?'checked':''}> ${label}</label>`).join('')}${config.stage_location ? `<label class="rx-check"><input type="checkbox" class="stage-location" ${review.location_requested?'checked':''}> Use guarded interiors of these groups for separate E5 stage locations (both selected terminals must opt in)</label>` : ''}<p class="field-help">Inventory SHA-256 ${esc(r.stages.inventory_hash)}. Reviewer declarations do not authenticate the reviewer or verify clocks. Separate stage estimates require explicit selection at both terminal primaries; original analysis windows remain recorded. Save line, terminal, protection-system or mapping changes before reviewing stages.</p></details>`;
  }).join('') || '<p>Complete an analysis first, then use Review & rerun to associate its stage intervals.</p>'}</section>`;
}

function collectStageReviews(row, mappings, assignments) {
  const result={};
  document.querySelectorAll('[data-stage-file]').forEach(section=>{
    if(!section.querySelector('.stage-enabled').checked)return;
    const name=section.dataset.stageFile, r=row.stageSource.find(r=>r.file===name), a=assignments[name];
    if(!a || a.end!==r.end || a.protection_system!==r.protection_system || !rxSameMapping(mappings[name],r.channel_mapping) || document.getElementById('review-line').value!==(row.metadata.line_id || ''))throw new Error('Save identity or mapping changes first, then review stages for '+name+'.');
    const review={inventory_hash:r.stages.inventory_hash, reviewer:section.querySelector('.stage-reviewer').value.trim(), reason:section.querySelector('.stage-reason').value.trim(), groups:{}};
    section.querySelectorAll('[data-stage-id]').forEach(input=>{if(input.value.trim())review.groups[input.dataset.stageId]=input.value.trim();});
    if(!review.reviewer || !review.reason || !Object.keys(review.groups).length)throw new Error('Provide a stage group, reviewer and supporting evidence for '+name+'.');
    if(new Set(Object.values(review.groups)).size!==Object.keys(review.groups).length)throw new Error('Keep each stage group unique within '+name+'; reclose shots need separate labels.');
    section.querySelectorAll('[data-stage-confirm]').forEach(input=>review[input.dataset.stageConfirm]=input.checked);
    if(config.stage_location) review.location_requested=!!section.querySelector('.stage-location')?.checked;
    result[name]=review;
  });
  return result;
}
