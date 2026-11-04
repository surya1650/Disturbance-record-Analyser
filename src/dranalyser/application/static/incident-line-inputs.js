'use strict';
// Source names are display defaults; physical ends and electrical facts are reviewed inputs.
const DRIncidentLineInputs=(()=>{
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const records=row=>(row.bundle?.files||[]).filter(file=>file.kind==='comtrade'&&!file.duplicate_of);
  const saved=row=>row.metadata?.incident_line?.review||{};
  const name=file=>file?.display_name||String(file?.name||'').replace(/\\/g,'/').split('/').pop().replace(/\.[^.]+$/,'').replace(/_/g,' ').trim();
  const value=input=>input===null||input===undefined?'':String(input);
  const options=(items,current)=>items.map(([key,label])=>`<option value="${esc(key)}"${key===current?' selected':''}>${esc(label)}</option>`).join('');
  function endFields(row,end,review){
    const prior=review.ends?.[end]||{},record=records(row).find(file=>file.name===prior.record);
    const dropdown='<option value="">Not assigned</option>'+records(row).map(file=>`<option value="${esc(file.name)}"${file.name===prior.record?' selected':''}>${esc(name(file))} · ${esc(file.name)}</option>`).join('');
    const select=(key,label,choices)=>`<label>${label}<select name="${end}.${key}">${options(choices,prior[key]||'unknown')}</select></label>`;
    return `<fieldset data-line-end="${end}"><legend>${end==='S'?'Reference end (S)':'Other end (R) · optional'}</legend><label>Recording<select name="${end}.record">${dropdown}</select></label><label>End name<input name="${end}.name" maxlength="120" value="${esc(prior.name||name(record))}" placeholder="Uses recording name when selected"></label>${select('current_direction','Recorded current direction',[['unknown','Not confirmed'],['bus-to-line','From bus into line'],['line-to-bus','From line into bus']])}<details><summary>Voltage transformer details, when required</summary>${select('vt_type','Transformer type',[['unknown','Not confirmed'],['CVT','CVT'],['VT','VT']])}${select('vt_location','Transformer position',[['unknown','Not confirmed'],['line','Line side'],['bus','Bus side']])}</details></fieldset>`;
  }
  function markup(row){
    const review=saved(row),hasSections=Array.isArray(review.sections)&&review.sections.length>0,busy=['queued','running'].includes(row.state);
    const impedanceUnit=review.basis==='per-km'?'Ω/km':review.basis==='total'?'Ω':'choose basis';
    const number=(key,label,unit)=>`<label>${label} (<span${['r1','x1','r0','x0'].includes(key)?' data-line-unit':''}>${['r1','x1','r0','x0'].includes(key)?impedanceUnit:unit}</span>)<input name="${key}" type="number" min="0" step="any" value="${esc(value(review[key]))}" placeholder="Not supplied"${hasSections&&['r1','x1','r0','x0'].includes(key)?' disabled':''}></label>`;
    const sections=hasSections?'<p class="field-help">The saved section table is retained. Its section values remain authoritative; aggregate impedance fields are read-only here.</p><details><summary>Saved line sections</summary><ul>'+review.sections.map(section=>'<li>'+esc(value(section.from_km))+'–'+esc(value(section.to_km))+' km · R1 '+esc(value(section.r1_ohm_per_km))+' Ω/km · X1 '+esc(value(section.x1_ohm_per_km))+' Ω/km</li>').join('')+'</ul></details>':'';
    return `<section data-incident-line-inputs><details${row.metadata?.incident_line?' open':''}><summary>Enter or update this incident’s line inputs</summary><p>Save the facts you have on this incident. Empty values remain unknown. Waveforms and an observation report remain available while distance inputs are incomplete.</p><form data-line-input-form><div class="source-input-grid">${number('length_km','Full line length','km')}${number('kv','Nominal line voltage','kV')}<label>Impedance basis<select name="basis"${hasSections?' disabled':''}>${options([['','Not confirmed'],['per-km','Per kilometre (Ω/km)'],['total','Whole line (Ω)']],review.basis||'')}</select></label>${number('r1','Positive-sequence resistance R1','Ω')}${number('x1','Positive-sequence reactance X1','Ω')}</div>${sections}<details><summary>Optional zero-sequence inputs for methods that need them</summary><p>E5 does not require these values. Leave them empty when unknown.</p><div class="source-input-grid">${number('r0','Zero-sequence resistance R0','Ω')}${number('x0','Zero-sequence reactance X0','Ω')}</div></details><div class="event-study-end-grid">${endFields(row,'S',review)}${endFields(row,'R',review)}</div><label class="event-study-confirm"><input name="confirmed_same_event" type="checkbox"${review.confirmed_same_event===true?' checked':''}> When both ends are selected, I confirm they record the same event at opposite physical ends.</label><label class="event-study-confirm"><input name="uniform_line" type="checkbox"${review.uniform_line===true?' checked':''}${hasSections?' disabled':''}> These values describe one uniform line section.</label><label class="event-study-confirm"><input name="confirmed_line" type="checkbox"${review.confirmed_line===true?' checked':''}> I confirm this model applies to the selected line, without series compensation or unsupported parallel-circuit topology.</label><label>Reviewed by<input name="reviewer" maxlength="120" value="${esc(review.reviewer||'')}" placeholder="Who checked these facts?"></label><label>Source of line facts<textarea name="evidence" maxlength="2000" placeholder="Line schedule, drawing or parameter record">${esc(review.evidence||'')}</textarea></label><button type="submit" class="button primary"${busy?' disabled':''}>Save line inputs on this incident</button><p data-line-input-status role="status" aria-live="polite">${busy?'Wait for the current revision to finish.':'Saving keeps the same recordings and original files. Missing facts remain listed before a physical calculation.'}</p></form></details></section>`;
  }
  function payload(row,values){
    const review={basis:values.basis||'',ends:{},reviewer:String(values.reviewer||'').trim(),evidence:String(values.evidence||'').trim(),confirmed_line:values.confirmed_line===true,uniform_line:values.uniform_line===true,confirmed_same_event:values.confirmed_same_event===true};
    if(!['','per-km','total'].includes(review.basis))throw new Error('Choose whether the impedance is per kilometre or for the whole line.');
    for(const key of ['length_km','kv','r1','x1','r0','x0']){
      const raw=value(values[key]).trim(),number=Number(raw);
      if(raw&&(!Number.isFinite(number)||number<0||number>1e12))throw new Error(key+': supply a finite nonnegative value within the supported range or leave it empty.');
      if(raw&&number===0&&!['r1','r0'].includes(key))throw new Error(key+': supply a positive physical value or leave it empty.');
      review[key]=raw?number:null;
    }
    const prior=saved(row);
    if(Array.isArray(prior.sections)&&prior.sections.length)review.sections=JSON.parse(JSON.stringify(prior.sections));
    const used=new Set();
    for(const end of ['S','R']){
      const selected=values.ends?.[end]||{},record=String(selected.record||'').trim();
      if(!record)continue;
      const file=records(row).find(item=>item.name===record);
      if(!file)throw new Error('Select a recording from this incident for end '+end+'.');
      if(used.has(record))throw new Error('One recording cannot represent both physical ends.');
      used.add(record);
      const display=String(selected.name||'').trim()||name(file);
      if(!display||display.length>120)throw new Error('End '+end+': use a name of at most 120 characters.');
      const choice={record,name:display};
      for(const [key,allowed] of [['current_direction',['unknown','bus-to-line','line-to-bus']],['vt_type',['unknown','CVT','VT']],['vt_location',['unknown','line','bus']]]){
        choice[key]=selected[key]||'unknown';
        if(!allowed.includes(choice[key]))throw new Error('End '+end+': review '+key.replaceAll('_',' ')+'.');
      }
      review.ends[end]=choice;
    }
    return {revision:row.number,review};
  }
  async function save(row,values,request,{signal}={}){
    const active=()=>{if(signal?.aborted)throw new Error('Line-input save cancelled because the incident or revision changed.');};
    active();
    if(['queued','running'].includes(row.state))throw new Error('Wait for the current revision to finish before saving line inputs.');
    const body=payload(row,values),id=row.incident_id||row.id;
    const response=await request('/api/incidents/'+encodeURIComponent(id)+'/line-inputs',{method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    active();
    if(response?.incident_id!==id||!Number.isInteger(response.revision)||response.revision<=row.number)throw new Error('The saved line-input response does not match this incident revision. Reopen the incident.');
    return response;
  }
  function bind(row,host,signal,{request,onSaved}={}){
    const root=host.matches?.('[data-incident-line-inputs]')?host:host.querySelector('[data-incident-line-inputs]');
    if(!root)return;
    const form=root.querySelector('[data-line-input-form]'),status=root.querySelector('[data-line-input-status]'),field=key=>form.elements.namedItem(key);
    const suggestedNames=Object.fromEntries(['S','R'].map(end=>[end,name(records(row).find(file=>file.name===field(end+'.record').value))]));
    const current=()=>root.isConnected&&!signal?.aborted;
    const send=request||((path,options)=>api(path,options));
    form.addEventListener('change',event=>{
      const key=event.target.name;
      if(key==='basis')root.querySelectorAll('[data-line-unit]').forEach(label=>{label.textContent=event.target.value==='per-km'?'Ω/km':event.target.value==='total'?'Ω':'choose basis';});
      if(/^[SR]\.record$/.test(key)){
        const end=key[0],file=records(row).find(item=>item.name===event.target.value),input=field(end+'.name'),suggestion=file?name(file):'';
        if(!input.value.trim()||input.value===suggestedNames[end])input.value=suggestion;
        suggestedNames[end]=suggestion;
      }
      if(!['confirmed_line','confirmed_same_event','reviewer','evidence'].includes(key)){field('confirmed_line').checked=false;if(/^[SR]\./.test(key))field('confirmed_same_event').checked=false;}
      status.textContent='Inputs changed. Save the current facts; unresolved details remain unknown.';
    },{signal});
    form.addEventListener('submit',async event=>{
      event.preventDefault();if(form.dataset.busy)return;
      const values={ends:{}};
      for(const key of ['length_km','kv','r1','x1','r0','x0','basis','reviewer','evidence'])values[key]=field(key).value;
      for(const key of ['confirmed_line','uniform_line','confirmed_same_event'])values[key]=field(key).checked;
      for(const end of ['S','R'])values.ends[end]=Object.fromEntries(['record','name','current_direction','vt_type','vt_location'].map(key=>[key,field(end+'.'+key).value]));
      const controls=[...form.querySelectorAll('input,textarea,select,button')],disabled=controls.map(control=>control.disabled);
      try{
        payload(row,values);form.dataset.busy='true';controls.forEach(control=>{control.disabled=true;});status.textContent='Saving line inputs on this incident…';
        const result=await save(row,values,send,{signal});if(!current())return;
        status.textContent=Array.isArray(result.missing)&&result.missing.length?'Saved. Still needed for physical distance: '+result.missing.join('; '):'Line inputs saved. Calculate fault location after the new revision is ready.';
        await onSaved?.(result);
      }catch(error){if(current()&&error.name!=='AbortError')status.textContent=error.message;}
      finally{delete form.dataset.busy;if(current())controls.forEach((control,i)=>{control.disabled=disabled[i];});}
    },{signal});
  }
  return {markup,payload,save,bind};
})();
if(typeof module!=='undefined')module.exports=DRIncidentLineInputs;
