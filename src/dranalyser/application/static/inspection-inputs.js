'use strict';
const DRSourceInputs=(()=>{
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function stable(value){if(Array.isArray(value))return '['+value.map(stable).join(',')+']';if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+stable(value[k])).join(',')+'}';return JSON.stringify(value);}
  function numeric(value,label){if(value===''||value===null||value===undefined)return null;if(!['number','string'].includes(typeof value)||!Number.isFinite(Number(value)))throw new Error(label+' must be a finite number or blank for unknown.');return Number(value);}
  function options(raw){
    const out={voltage_kv:Number(raw.voltageKv||0),mappings:Object.fromEntries(Object.entries(raw.mappings||{}).filter(([,v])=>v).sort())};
    const states=Object.fromEntries(Object.entries(raw.assertedStates||{}).filter(([,v])=>v!=='').map(([k,v])=>[k,Number(v)]).sort());
    if(Object.keys(states).length)out.asserted_states=states;
    if(raw.lineMode==='__custom__'){
      out.line_model={};for(const key of ['kv','length_km','x1_ohm_per_km','r1_ohm_per_km','r0_ohm_per_km','x0_ohm_per_km'])out.line_model[key]=numeric(raw.model?.[key],key);
      out.line_model.name=String(raw.model?.name||'User supplied line');
      out.line_model.provenance=String(raw.model?.provenance||'User declared model; physical validation not supplied.');
    }else if(raw.lineMode)out.line_id=raw.lineMode;
    if(raw.faultLoop)out.fault_loop=raw.faultLoop;
    if(raw.projectionWindow!==''&&raw.projectionWindow!==null&&raw.projectionWindow!==undefined){const value=Number(raw.projectionWindow);if(!Number.isInteger(value)||value<0||value>=512)throw new Error('Choose a source window from the available list.');out.projection_window=value;}
    return out;
  }
  function markup(prefs){
    const model=prefs.line_model||{};
    return `<details class="source-line-inputs" open><summary>Line data and diagram</summary><p class="field-help">Choose supplied line facts and a presumed fault loop, then select a supported source window. This computes an assumption-dependent model projection; missing fields remain Not available.</p><div class="source-input-grid"><label>Supplied line model <select class="source-line-mode"><option value="">Frozen incident model if supplied</option>${prefs.line_id?`<option value="${esc(prefs.line_id)}">${esc(prefs.line_id)} (loading provenance)</option>`:''}<option value="__custom__">Enter declared line values</option></select></label><label>Assumed fault loop <select class="source-fault-loop"><option value="">Not assigned · no loop inferred</option>${['AB','BC','CA'].map(v=>`<option>${v}</option>`).join('')}<option value="AG">AG · compensation not supplied</option><option value="BG">BG · compensation not supplied</option><option value="CG">CG · compensation not supplied</option></select></label><label>Window for approximate projection <select class="source-projection-window"><option value="">Choose after source analysis</option>${Number.isInteger(prefs.projection_window)?`<option value="${prefs.projection_window}">Saved source window ${prefs.projection_window}</option>`:''}</select></label></div><div class="source-custom-line source-input-grid" hidden><label>Line / circuit name<input data-line-field="name" value="${esc(model.name||'')}" maxlength="200" placeholder="Enter line name"></label>${[['kv','Nominal line voltage (kV)'],['length_km','Full model length (km)'],['x1_ohm_per_km','Positive-sequence X1 (Ω/km)'],['r1_ohm_per_km','Positive-sequence R1 (Ω/km)'],['r0_ohm_per_km','Zero-sequence R0 (Ω/km)'],['x0_ohm_per_km','Zero-sequence X0 (Ω/km)']].map(([key,label])=>`<label>${label}<input type="number" step="any" data-line-field="${key}" aria-label="${label}" value="${esc(model[key]??'')}" placeholder="Not available"></label>`).join('')}<label>Model provenance <input data-line-field="provenance" aria-label="Model provenance" value="${esc(model.provenance||'')}" maxlength="1000" placeholder="Source sheet, row or operator declaration"></label></div><p class="source-line-notes field-help"></p></details><div class="inspection-toolbar"><button class="source-accept-meanings">Use unique suggested meanings</button><span class="field-help">Suggestions remain unverified phase/indication assumptions.</span></div>`;
  }
  function catalogue(body,ok){if(!ok)throw new Error(body.detail||'Line catalogue request failed.');if(!Array.isArray(body.items))throw new Error('Line catalogue response did not contain a list of declared models.');return body.items;}
  return {stable,options,markup,catalogue};
})();
if(typeof module!=='undefined')module.exports=DRSourceInputs;
