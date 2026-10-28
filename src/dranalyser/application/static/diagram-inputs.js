'use strict';
const DRDiagrams=(()=>{
  const esc=v=>DRSourceReport.esc(v),num=v=>Number.isFinite(v)?Number(v.toPrecision(6)).toString():'Not available';
  function mount(section,data,row,recordController,workbench){
    const saved=row.diagramInputs||{version:0,diagram:{}},q=s=>section.querySelector(s);
    let version=saved.version,applied=saved.diagram||{},appliedOptions=saved.options||{},result=null,dirty=false;
    const input=document.createElement('section');input.className='diagram-inputs';
    input.innerHTML=`<h3>R–X diagram inputs</h3><p class="field-help">Phase-loop trajectories use supported source phasors. Enter actual relay boundaries only if available. Mho reach means the diameter from the origin at the characteristic angle. A polygon uses the exact ordered R/X vertices; no quadrilateral shape is guessed.</p><div class="diagram-input-grid"><label>Reviewer<input data-diagram-field="reviewer" maxlength="200" value="${esc(applied.reviewer||'')}"></label><label>Settings / scaling evidence<input data-diagram-field="evidence" maxlength="2000" value="${esc(applied.evidence||'')}" placeholder="Settings version, CT/VT sheet and event date"></label><label>Zone impedance basis<select data-diagram-field="zone_basis"><option value="primary">Primary Ω</option><option value="secondary">Secondary Ω</option></select></label><label>Settings CT ratio (primary A / secondary A)<input data-diagram-field="ct_ratio" type="number" min="0" step="any" value="${esc(applied.ct_ratio??'')}"></label><label>Settings VT ratio (primary V / secondary V)<input data-diagram-field="vt_ratio" type="number" min="0" step="any" value="${esc(applied.vt_ratio??'')}"></label></div><label class="diagram-check"><input data-diagram-field="primary_scaling_confirmed" type="checkbox" ${applied.primary_scaling_confirmed?'checked':''}> I reviewed the selected source phase identities, V/A primary scaling and bus-into-line current polarity against this evidence. No assumed missing CT default is used for zone overlays.</label><div class="diagram-zones"></div><button type="button" class="diagram-add-zone">Add phase-zone boundary</button><p class="field-help">Ground-loop compensation and exported zone interpretation use the existing settings-review workflow in Operational study. Attach the actual settings export using Attach late records. Manual diagrams do not decide pickup, trip, direction or fault location.</p><button type="button" class="diagram-save button primary">Save inputs & update diagrams</button><p class="diagram-save-status" role="status"></p>`;
    q('.source-input-pane').append(input);q('[data-diagram-field="zone_basis"]').value=applied.zone_basis||'primary';
    const diagrams=document.createElement('section');diagrams.className='panel detail-section source-diagrams';diagrams.dataset.incidentPane='diagrams';
    diagrams.innerHTML=`<h2>Line and R–X diagrams</h2><div class="source-line-summary"></div><h3>R–X phase-loop observations</h3><div class="inspection-toolbar"><label>Loop <select class="diagram-loop"><option>AB</option><option>BC</option><option>CA</option><option>AG</option><option>BG</option><option>CG</option></select></label><label>Source window <select class="diagram-window"><option value="">All supported centres</option></select></label><button class="diagram-focus" type="button">Inspect selected waveform window</button><a class="button" href="${DRIncident.link(row,'inputs')}">Edit line / relay inputs</a></div><p class="diagram-status"></p><div class="diagram-plot"></div><div class="diagram-selected"></div><p class="field-help">Each point represents a fitted source-window centre. Gaps remain disconnected. These observations and declared boundaries do not verify relay operation or physical fault location.</p>`;
    section.append(diagrams);
    function addZone(zone={name:'',shape:'mho',reach:null,angle:null,points:[]}){
      const host=q('.diagram-zones');if(host.children.length>=6)return;
      const el=document.createElement('div');el.className='diagram-zone';
      el.innerHTML=`<div class="diagram-input-grid"><label>Zone name<input data-zone="name" maxlength="80" value="${esc(zone.name)}" placeholder="e.g. Z1 phase"></label><label>Boundary shape<select data-zone="shape"><option value="mho">Mho through origin</option><option value="polygon">Explicit polygon</option></select></label><label>Mho reach (Ω)<input data-zone="reach" type="number" min="0" step="any" value="${esc(zone.reach??'')}"></label><label>Mho characteristic angle (°)<input data-zone="angle" type="number" min="-180" max="180" step="any" value="${esc(zone.angle??'')}"></label></div><label class="diagram-polygon">Polygon vertices · one R,X pair per line<textarea data-zone="points" placeholder="R,X">${esc((zone.points||[]).map(p=>p.join(', ')).join('\n'))}</textarea></label><button type="button" class="diagram-remove-zone">Remove boundary</button>`;
      host.append(el);const shape=el.querySelector('[data-zone="shape"]');shape.value=zone.shape;
      const toggle=()=>{for(const key of ['reach','angle'])el.querySelector(`[data-zone="${key}"]`).parentElement.hidden=shape.value!=='mho';el.querySelector('.diagram-polygon').hidden=shape.value!=='polygon';};toggle();shape.onchange=toggle;
      el.querySelector('.diagram-remove-zone').onclick=()=>{el.remove();changed();};
    }
    (applied.zones||[]).forEach(addZone);q('.diagram-add-zone').onclick=()=>{addZone();changed();};
    function changed(){dirty=true;q('.diagram-save-status').textContent='Unsaved diagram inputs. Save to update the plotted declarations.';}
    input.addEventListener('change',changed);input.addEventListener('input',changed);
    section.addEventListener('change',event=>{if(event.target.matches('[data-meaning],.source-voltage')){q('[data-diagram-field=primary_scaling_confirmed]').checked=false;changed();}});
    function read(){
      const value={};for(const el of input.querySelectorAll('[data-diagram-field]'))value[el.dataset.diagramField]=el.type==='checkbox'?el.checked:el.type==='number'?(el.value===''?null:Number(el.value)):el.value.trim();
      value.zones=[...input.querySelectorAll('.diagram-zone')].map(el=>{const get=k=>el.querySelector(`[data-zone="${k}"]`).value.trim(),shape=get('shape');const points=shape==='polygon'?get('points').split('\n').filter(s=>s.trim()).map(line=>line.split(',').map(s=>{if(!s.trim())throw new Error('Each polygon vertex requires both R and X.');return Number(s);})):[];
        return {name:get('name'),shape,reach:shape==='mho'&&get('reach')!==''?Number(get('reach')):null,angle:shape==='mho'&&get('angle')!==''?Number(get('angle')):null,points};});
      if(![value.ct_ratio,value.vt_ratio,...value.zones.flatMap(z=>[z.reach,z.angle,...z.points.flat()])].every(v=>v===null||Number.isFinite(v)))throw new Error('Diagram numbers must be finite; leave unknown values blank.');return value;
    }
    async function save(options){
      const body=await api(`/api/incidents/${row.incident_id}/diagram-inputs`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:row.number,record:data.file,version,options,diagram:read()})});
      if(recordController.signal.aborted)throw new DOMException('Recording changed','AbortError');
      version=body.version;applied=body.diagram;appliedOptions=body.options;row.diagramInputs=body;dirty=false;document.dispatchEvent(new CustomEvent('dr-source-inputs-saved',{detail:{incident_id:row.incident_id,record:data.file,version}}));q('.diagram-save-status').textContent='Inputs saved for this recording and revision. Source samples and operational settings are unchanged.';draw();return body;
    }
    function line(){
      if(!result)return;const snapshot=DRIncident.sourceDisplay(row,data.file,result).snapshot,p=row.presentation;
      const displayed=snapshot.line;
      q('.source-line-summary').innerHTML=DRSourceReport.schematic(displayed,result.options?.fault_loop||result.options?.line_model||result.options?.line_id?snapshot.selected_projection:null)+`<p class="field-help">Substation display names: ${esc(p.name_sources.S)} / ${esc(p.name_sources.R)}. Selected recording: ${esc(DRIncident.recordLabel(row,data.file))}.</p>`;
    }
    function draw(){
      const status=q('.diagram-status'),plot=q('.diagram-plot'),detail=q('.diagram-selected');plot.innerHTML='';detail.innerHTML='';line();
      if(!result){status.textContent='Waiting for source analysis. Apply inputs in the Inputs menu if required.';return;}
      const loop=q('.diagram-loop').value,chosen=q('.diagram-window').value,windows=result.derived_quantities?.windows||[],rows=chosen===''?windows:windows.filter(w=>String(w.index)===chosen);
      if(loop.endsWith('G')){status.textContent='Ground-loop R–X is withheld here. A reviewed native relay compensation form, matching settings export, CT/VT bases and zero-sequence VT support are required. Use the operational settings-review workflow when these inputs are available.';return;}
      const context=options=>DRSourceInputs.stable({voltage_kv:options.voltage_kv||0,mappings:options.mappings||{}});
      const confirmed=applied.primary_scaling_confirmed&&applied.reviewer&&applied.evidence&&!result.assumptions?.length&&context(appliedOptions)===context(result.options);
      let factor=applied.zone_basis==='secondary'?(applied.vt_ratio&&applied.ct_ratio?applied.vt_ratio/applied.ct_ratio:null):1;
      if(!Number.isFinite(factor)||factor<=0)factor=null;
      const eligible=confirmed&&factor!==null;
      const zones=eligible?(applied.zones||[]).map(z=>{const points=z.shape==='polygon'?z.points:Array.from({length:73},(_,i)=>{const angle=z.angle*Math.PI/180,r=z.reach/2;return [r*Math.cos(angle)+r*Math.cos(i*Math.PI/36),r*Math.sin(angle)+r*Math.sin(i*Math.PI/36)];});return {...z,points:points.map(p=>p.map(v=>v*factor))};}):[];
      const good=rows.filter(w=>w.loops[loop]?.impedance_ohm?.every(Number.isFinite));
      status.textContent=`${good.length} / ${rows.length} source centres available for ${loop}. ${eligible?`Declared boundaries: ${zones.length}; primary Ω per settings Ω ${num(factor)}.`:'Zone overlays withheld: review primary scaling / phase polarity and supply reviewer, evidence and any secondary-ohm CT/VT ratios.'}${dirty?' Unsaved inputs have not been plotted.':''}`;
      const selected=chosen===''?null:rows[0];if(selected)detail.innerHTML=DRSourceReport.derived(selected);if(!good.length){plot.innerHTML='<p>'+esc(rows[0]?.loops[loop]?.reason||'No corresponding supported V/A fits. The waveform viewer remains available.')+'</p>';return;}
      const points=good.map(w=>w.loops[loop].impedance_ohm).concat(zones.flatMap(z=>z.points),[[0,0]]);
      const values=points.flat();if(values.some(v=>!Number.isFinite(v)||Math.abs(v)>1e100)){plot.textContent='R–X display exceeds the supported numeric range.';return;}
      const rs=points.map(p=>p[0]),xs=points.map(p=>p[1]),rlo=Math.min(...rs),rhi=Math.max(...rs),xlo=Math.min(...xs),xhi=Math.max(...xs),span=Math.max(rhi-rlo,xhi-xlo,.1)*1.15,rc=(rhi+rlo)/2,xc=(xhi+xlo)/2,x=v=>350+(v-rc)*380/span,y=v=>235-(v-xc)*380/span;
      let marks='';for(let i=0;i<=4;i++){const a=rc-span/2+span*i/4,b=xc-span/2+span*i/4;marks+=`<line x1="${x(a)}" x2="${x(a)}" y1="45" y2="425" stroke="#e1e9ee"/><text x="${x(a)}" y="446" text-anchor="middle">${esc(num(a))}</text><line x1="160" x2="540" y1="${y(b)}" y2="${y(b)}" stroke="#e1e9ee"/><text x="150" y="${y(b)+4}" text-anchor="end">${esc(num(b))}</text>`;}
      if(x(0)>=160&&x(0)<=540)marks+=`<line x1="${x(0)}" x2="${x(0)}" y1="45" y2="425" stroke="#8297a5"/>`;if(y(0)>=45&&y(0)<=425)marks+=`<line x1="160" x2="540" y1="${y(0)}" y2="${y(0)}" stroke="#8297a5"/>`;
      for(const zone of zones)marks+=`<polygon points="${zone.points.map(p=>`${x(p[0])},${y(p[1])}`).join(' ')}" fill="none" stroke="#9560a7" stroke-dasharray="6 4"><title>${esc(zone.name)} · declared boundary</title></polygon>`;
      let prior=null;for(const w of rows){const p=w.loops[loop]?.impedance_ohm;if(!p?.every(Number.isFinite)){prior=null;continue;}if(prior&&w.index===prior.index+1)marks+=`<line x1="${x(prior.p[0])}" y1="${y(prior.p[1])}" x2="${x(p[0])}" y2="${y(p[1])}" stroke="#176d82"/>`;marks+=`<circle cx="${x(p[0])}" cy="${y(p[1])}" r="${chosen===''?3:6}" fill="#176d82"><title>Window ${w.index}: R ${esc(num(p[0]))}, X ${esc(num(p[1]))} Ω</title></circle>`;prior={index:w.index,p};}
      plot.innerHTML=`<svg viewBox="0 0 700 485" role="img" aria-label="${loop} R-X source observations with equal R and X scales"><g font-size="11" fill="#405667">${marks}<text x="350" y="473" text-anchor="middle">R (Ω · ${confirmed?'reviewer-declared primary':'conditional source scaling'})</text><text x="35" y="235" transform="rotate(-90 35 235)" text-anchor="middle">X (Ω)</text><text x="350" y="20" text-anchor="middle">${loop} · equal axis scales · ${zones.map(z=>esc(z.name)).join(', ')||'no zone overlay'}</text></g></svg>`;
    }
    q('.diagram-loop').onchange=draw;q('.diagram-window').onchange=draw;
    q('.diagram-focus').onclick=()=>{const index=Number(q('.diagram-window').value),w=result?.windows.find(w=>w.index===index);if(q('.diagram-window').value!==''&&w){workbench?.focusWindow(w.start_index,w.stop_index);location.hash=DRIncident.link(row,'viewer');}};
    document.addEventListener('dr-end-names',line,{signal:recordController.signal});
    function update(next){result=next;const chosen=q('.diagram-window').value;q('.diagram-window').innerHTML='<option value="">All supported centres</option>'+(result?.windows||[]).map(w=>`<option value="${w.index}">Window ${w.index} · ${num(w.support_s[0])}–${num(w.support_s[1])} local s</option>`).join('');q('.diagram-window').value=chosen;if(q('.diagram-window').selectedIndex<0)q('.diagram-window').value='';draw();}
    draw();return {save,update,read};
  }
  return {mount};
})();
