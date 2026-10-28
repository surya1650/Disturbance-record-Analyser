'use strict';
const DRIncident=(()=>{
  const titles={viewer:'Waveforms & report',inputs:'Inputs',diagrams:'Diagrams',playback:'Playback',combine:'Combine captures',compare:'Compare recordings',evidence:'Detailed evidence',study:'Operational study',files:'Files & history'};
  const endTitle=end=>end==='S'?'Sending end':end==='R'?'Receiving end':'End unassigned';
  const link=(row,menu)=>`#incident/${row.incident_id}/${row.number}/${menu}`;
  const activeMenu=()=>{const menu=location.hash.split('/')[3];return titles[menu]?menu:'viewer';};
  function show(){
    const menu=activeMenu();
    document.querySelectorAll('[data-incident-pane]').forEach(el=>el.hidden=!el.dataset.incidentPane.split(' ').includes(menu));
    document.querySelectorAll('[data-incident-menu]').forEach(el=>{const selected=el.dataset.incidentMenu===menu;el.classList.toggle('active',selected);if(selected)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
    const more=document.getElementById('incident-more');if(more)more.value=['viewer','inputs','diagrams','playback'].includes(menu)?'':menu;
    const title=document.getElementById('incident-menu-title');if(title)title.textContent=titles[menu];
  }
  function navigation(row){
    return `<nav class="incident-menu" aria-label="Incident views">${['viewer','inputs','diagrams','playback'].map(menu=>`<a href="${link(row,menu)}" data-incident-menu="${menu}">${titles[menu]}</a>`).join('')}<label>More tools <select id="incident-more"><option value="">Choose…</option>${Object.entries(titles).filter(([k])=>!['viewer','inputs','diagrams','playback'].includes(k)).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></label></nav><h2 id="incident-menu-title" class="incident-menu-title"></h2><div class="incident-end-cards"></div>`;
  }
  function recordLabel(row,name){const p=row.presentation||{},end=p.record_ends?.[name];return `${endTitle(end)}${end&&p.names?.[end]?' · '+p.names[end]:''} · ${name}`;}
  function namesMarkup(row){
    const p=row.presentation,esc=escapeHtml;
    return `<section class="panel detail-section" data-incident-pane="inputs"><h2>Substations and recording ends</h2><p>Name both substations and label each recording. Successive captures from one relay belong to the same end. Labels are saved separately from electrical assignments.</p><form id="end-names-form"><div class="end-name-fields">${['S','R'].map(end=>`<label>${endTitle(end)} substation<input data-end-name="${end}" maxlength="120" placeholder="Enter substation name" value="${esc(p.names[end])}" ${p.name_sources[end]==='line definition'?'readonly':''}><small>${esc(p.name_sources[end])}</small></label>`).join('')}</div>${(row.bundle?.files||[]).filter(f=>f.kind==='comtrade').map(f=>`<label class="record-end-row"><span>${esc(f.name)}<small>CFG station: ${esc(f.station||'not supplied')}</small></span><select data-display-end="${esc(f.name)}" ${p.record_end_sources[f.name]==='operational assignment'?'disabled':''}><option value="">End unassigned</option><option value="S" ${p.record_ends[f.name]==='S'?'selected':''}>Sending end</option><option value="R" ${p.record_ends[f.name]==='R'?'selected':''}>Receiving end</option></select></label>`).join('')}<button class="button primary" type="submit">Save names & end labels</button><p id="end-names-status" role="status"></p></form><p class="field-help">Configured line names take priority when an operational line definition is assigned. Upload order does not identify an end. Names do not clear timing, CT/VT or channel checks.</p></section>`;
  }
  function presentation(row){
    const esc=escapeHtml,p=row.presentation;
    const host=document.querySelector('.incident-end-cards');if(host)host.innerHTML=['S','R'].map(end=>{
      const records=Object.entries(p.record_ends).filter(([,v])=>v===end).map(([k])=>k);
      return `<section><strong>${endTitle(end)}</strong><span>${esc(p.names[end]||'Substation name not entered')}</span><small>${records.length?records.map(esc).join(' · '):'No recording labelled'} · ${esc(p.name_sources[end])}</small>${records.length?`<button type="button" data-open-end="${end}">View waveforms</button>`:`<a href="${link(row,'inputs')}">Enter names / assign labels →</a>`}</section>`;
    }).join('');
    document.querySelectorAll('[data-open-end]').forEach(button=>button.onclick=()=>{const name=Object.keys(p.record_ends).find(k=>p.record_ends[k]===button.dataset.openEnd);const select=document.getElementById('inspection-record');if(select&&name&&select.value!==name){select.value=name;select.dispatchEvent(new Event('change'));}location.hash=link(row,'viewer');});
    document.querySelectorAll('[data-record]').forEach(select=>{for(const option of select.options){const [end,role]=option.value.split(':');if(['S','R'].includes(end)&&role)option.textContent=endTitle(end)+(p.names[end]?' · '+p.names[end]:'')+' · '+role[0].toUpperCase()+role.slice(1);}});
    const select=document.getElementById('inspection-record');if(select)for(const option of select.options)if(!option.value.startsWith('@join:'))option.textContent=recordLabel(row,option.value);
    document.querySelectorAll('[data-record-label]').forEach(el=>el.textContent=recordLabel(row,el.dataset.recordLabel));
    document.querySelectorAll('.source-compare-record option').forEach(el=>{if(el.value)el.textContent=recordLabel(row,el.value);});
    document.querySelectorAll('[data-named-report]').forEach(frame=>{frame.src=`/api/incidents/${row.incident_id}/named-report?revision=${row.number}&labels=${p.version}`;});
    document.dispatchEvent(new CustomEvent('dr-end-names',{detail:row}));
  }
  function bind(row){
    const more=document.getElementById('incident-more');if(more)more.onchange=()=>{if(more.value)location.hash=link(row,more.value);};
    const form=document.getElementById('end-names-form');if(form)form.onsubmit=async event=>{
      event.preventDefault();const status=document.getElementById('end-names-status'),button=form.querySelector('button');button.disabled=true;
      try{
        const names=Object.fromEntries([...form.querySelectorAll('[data-end-name]')].map(el=>[el.dataset.endName,el.value.trim()]));
        const record_ends=Object.fromEntries([...form.querySelectorAll('[data-display-end]')].map(el=>[el.dataset.displayEnd,el.value]));
        row.presentation=await api(`/api/incidents/${row.incident_id}/end-names`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:row.number,version:row.presentation.version,names,record_ends})});
        presentation(row);status.textContent='Names and labels saved. Electrical assignments and source samples are unchanged.';
      }catch(error){status.textContent=error.message;}finally{button.disabled=false;}
    };
    presentation(row);show();
  }
  function reportHeading(row,file){const esc=escapeHtml,p=row.presentation;return `<div class="report-end-heading"><p><strong>Sending end:</strong> ${esc(p.names.S||'Name not provided')} → <strong>Receiving end:</strong> ${esc(p.names.R||'Name not provided')}</p><p>${esc(recordLabel(row,file))} · display-label version ${p.version}</p><small>Names are ${esc(p.name_sources.S)} / ${esc(p.name_sources.R)}; physical identity is not authenticated by a label.</small></div>`;}
  function sourceDisplay(row,file,result){
    const p=row.presentation,s=result.snapshot,projection=s.selected_projection;
    const sending=p.record_ends[file]==='S'&&p.record_end_sources[file]==='operational assignment';
    return {...result,snapshot:{...s,line:{...s.line,terminals:{S:p.names.S||s.line.terminals?.S,R:p.names.R||s.line.terminals?.R}},selected_projection:projection?{...projection,eligible_overlay:sending&&projection.eligible_overlay,reason:sending?projection.reason:'Sending-end coordinate reference is not established for this source model. The reported model coordinate is not plotted as a sending-end location.'}:null}};
  }
  return {navigation,namesMarkup,bind,show,recordLabel,reportHeading,sourceDisplay,link,activeMenu,endTitle};
})();
if(typeof module!=='undefined')module.exports=DRIncident;
