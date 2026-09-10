'use strict';

const rxConfirmations={settings_identity:'This export belongs to this relay and CT/VT core',effective_at_event:'This settings version was effective at the fault time',phase_scaling_polarity:'Phase identities and primary scaling are correct; currents are positive bus into line',zero_sequence_voltage:'Voltage channels are phase-to-earth and the VT connection passes zero sequence'};
const rxSameMapping=(a,b)=>{
  const stable=v=>v && typeof v==='object' ? Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])])) : v;
  return JSON.stringify(stable(a || {}))===JSON.stringify(stable(b || {}));
};

function rxReviewEditor(row) {
  if(!config.rx_input_review) return '';
  const esc=escapeHtml;
  return `<section class="detail-section"><h3>Review R-X inputs</h3><p>Optional per-record declarations for ground loops and exported zone boundaries. Confirm against supporting documents or site evidence. These declarations do not validate the relay algorithm or protection operation.</p>${(row.bundle?.files || []).filter(f=>f.kind==='comtrade' && f.ok && !f.duplicate_of).map(f=>{
    const source=f.settings_source || {}, old=row.metadata.assignments?.[f.name]?.rx_review || {};
    const currentMapping=row.metadata.assignments?.[f.name]?.channel_mapping || {};
    const stale=old.record_hash && (old.record_hash!==f.content_hash || old.settings_hash!==source.sha256 || !rxSameMapping(old.channel_mapping,currentMapping));
    const r=stale ? {} : old;
    if(source.status!=='associated export') return `<details><summary>${esc(f.name)} · R-X review unavailable</summary><p>${esc(source.reason || 'No uniquely associated settings export.')}</p></details>`;
    return `<details data-rx-file="${esc(f.name)}"><summary>${esc(f.name)} · ${esc(source.file)}</summary><p class="field-help">Settings SHA-256 ${esc(source.sha256)}<br>Recording SHA-256 ${esc(f.content_hash)}. Association by filename/folder remains unverified until reviewed.</p>${stale ? '<p class="hint">Previous review no longer matches these inputs. Confirmations have been cleared.</p>' : ''}<label class="rx-check"><input type="checkbox" class="rx-enabled" ${r.record_hash?'checked':''}> Include this input review in the analysis revision</label>${Object.entries(rxConfirmations).map(([key,label])=>`<label class="rx-check"><input type="checkbox" data-rx-confirm="${key}" ${r[key]===true?'checked':''}> ${esc(label)}</label>`).join('')}<label>Reviewer<input class="rx-reviewer" maxlength="200" value="${esc(r.reviewer || '')}"></label><label>Supporting evidence / rationale<input class="rx-reason" maxlength="1000" value="${esc(r.reason || '')}"></label><div class="nav-controls"><label>Settings CT ratio (primary A / secondary A)<input class="rx-ct" type="number" step="any" min="0" value="${esc(r.ct_ratio ?? '')}"></label><label>Settings VT ratio (primary V / secondary V)<input class="rx-vt" type="number" step="any" min="0" value="${esc(r.vt_ratio ?? '')}"></label></div><p class="field-help">Ratios refer to the settings export's secondary-ohm base, including its voltage convention. They only scale displayed boundaries; recorded waveforms are unchanged. Leave unknown ratios blank to withhold overlays. Save channel corrections in a revision before reviewing R-X inputs.</p></details>`;
  }).join('')}</section>`;
}

function collectRxReviews(row,mappings) {
  const result={};
  document.querySelectorAll('[data-rx-file]').forEach(section=>{
    if(!section.querySelector('.rx-enabled').checked)return;
    const name=section.dataset.rxFile, f=row.bundle.files.find(f=>f.name===name);
    const previousMapping=row.metadata.assignments?.[name]?.channel_mapping || {};
    if(!rxSameMapping(mappings[name],previousMapping))throw new Error('Save channel corrections first, then review R-X inputs for '+name+'.');
    const value={record_hash:f.content_hash,settings_hash:f.settings_source.sha256,channel_mapping:mappings[name] || {},reviewer:section.querySelector('.rx-reviewer').value.trim(),reason:section.querySelector('.rx-reason').value.trim()};
    if(!value.reviewer || !value.reason)throw new Error('Provide reviewer and supporting evidence for '+name+'.');
    section.querySelectorAll('[data-rx-confirm]').forEach(input=>value[input.dataset.rxConfirm]=input.checked);
    for(const [key,selector] of [['ct_ratio','.rx-ct'],['vt_ratio','.rx-vt']]){
      const input=section.querySelector(selector);value[key]=input.value==='' ? null : Number(input.value);
      if(value[key]!==null && (!Number.isFinite(value[key]) || value[key]<=0))throw new Error('Settings ratios must be positive or blank.');
    }
    result[name]=value;
  });
  return result;
}

function rxContextEvidence(context) {
  if(!context)return '<p class="field-help">R-X input evidence is unavailable for this record/revision.</p>';
  const esc=escapeHtml, r=context.review || {}, s=context.settings_source || {};
  const status=(label,missing)=>`<p><strong>${label}:</strong> ${missing.length ? 'withheld' : 'eligible under reviewer declarations'}</p>${missing.length ? `<ul>${missing.map(v=>`<li>${esc(v)}</li>`).join('')}</ul>` : ''}`;
  return `<details class="rx-context"><summary>Ground-loop and zone input evidence</summary>${status('Ground loops',context.ground_missing)}${status('Zone conversion',context.zone_missing)}<p>Settings: ${esc(s.file || s.status || 'not supplied')}<br>Exact settings SHA-256 ${esc(s.sha256 || 'unavailable')}</p>${r.record_hash ? `<p>Reviewer: ${esc(r.reviewer)}<br>Evidence: ${esc(r.reason)}<br>Reviewed recording SHA-256 ${esc(r.record_hash)}<br>Reviewed settings SHA-256 ${esc(r.settings_hash)}</p><ul>${Object.entries(rxConfirmations).map(([key,label])=>`<li>${esc(label)}: ${r[key]===true?'declared confirmed':'unconfirmed'}</li>`).join('')}</ul>` : ''}<p>Native compensation: ${esc(JSON.stringify(context.compensation_source || {}))}</p><p>Derived k0: ${context.k0 ? `${esc(context.k0[0])} + j(${esc(context.k0[1])}); I0 = (IA + IB + IC) / 3` : 'withheld'}<br>Settings CT ratio ${esc(r.ct_ratio ?? 'unknown')} · VT ratio ${esc(r.vt_ratio ?? 'unknown')}<br>Primary Ω per secondary Ω: ${esc(context.primary_ohm_per_secondary_ohm ?? 'withheld')}</p><p>${esc(context.note)}</p></details>`;
}
