'use strict';

// Presentation of a saved backend comparison; cursor/zoom never recalculate it.
const DRZoneComparison=(()=>{
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list=values=>Array.isArray(values)&&values.length?'<ul>'+values.map(v=>'<li>'+esc(v)+'</li>').join('')+'</ul>':'';
  const count=value=>Number.isSafeInteger(value)&&value>=0?String(value):'Unavailable';
  const number=value=>typeof value==='number'&&Number.isFinite(value)?String(Number(value.toPrecision(9))):'Unavailable';
  const hash=value=>typeof value==='string'&&/^[0-9a-f]{64}$/.test(value)?value:'Unavailable';
  const states={inside:'Inside',outside:'Outside',mixed:'Mixed',not_evaluable:'Not evaluable'};
  function markup(value,expectedHash){
    const heading='<h3>Reviewed zone-boundary comparison</h3>';
    if(value==null)return '<section class="zone-comparison" data-zone-comparison-status="legacy">'+heading+'<p>This revision predates zone-boundary comparison. Review & rerun to create an updated revision.</p></section>';
    if(value.version!==1)return '<section class="zone-comparison" data-zone-comparison-status="unsupported">'+heading+'<p>This saved comparison version is unsupported. Review & rerun to create an updated revision.</p></section>';
    if(hash(expectedHash)==='Unavailable'||value.record_hash!==expectedHash)return '<section class="zone-comparison" data-zone-comparison-status="not_evaluable">'+heading+'<p>Stored comparison recording identity does not match this source. Review & rerun before using its result.</p></section>';
    const available=value.status==='available',w=value.window||{},zones=Array.isArray(value.zones)?value.zones:[];
    const kind={phase:'phase',earth:'earth'}[value.characteristic_kind]||'unavailable';
    const rows=zones.map(zone=>{
      const state=available&&Object.hasOwn(states,zone.status)?zone.status:'not_evaluable';
      return '<tr><th>'+esc(zone.name||'Unnamed exported zone')+'<small>'+esc(zone.kind||'Unknown kind')+'</small></th><td>'+states[state]+'</td><td>'+count(zone.inside_count)+'</td><td>'+count(zone.outside_count)+'</td><td>'+count(zone.evaluated_count)+'</td><td>'+list(zone.reasons)+'</td></tr>';
    }).join('');
    return '<section class="zone-comparison" data-zone-comparison-status="'+(available?'available':'not_evaluable')+'" data-zone-comparison-version="1">'+heading+
      '<p><strong>'+(available?'Recorded impedance against exported boundaries':'Comparison not evaluable')+'</strong></p>'+
      '<p>Classified fault '+esc(value.fault_type||'unavailable')+' · loop '+esc(value.loop||'unavailable')+' · '+kind+' boundaries.</p>'+
      '<p class="field-help">Fixed operational window '+number(w.t_start_s)+' to '+number(w.t_end_s)+' source-local s. The display interval, selected display loop and cursor do not change this comparison.</p>'+
      '<p class="field-help">'+count(w.evaluated_count)+' evaluated / '+count(w.support_count)+' candidate phasor supports. These supports overlap; counts are not independent measurements or confidence coverage.</p>'+
      list(value.reasons)+(rows?'<div class="table-wrap"><table class="evidence-table"><thead><tr><th>Exported zone / kind</th><th>Result</th><th>Inside</th><th>Outside</th><th>Evaluated supports</th><th>Limits / reasons</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<p>No exported boundary is available for comparison.</p>')+
      list(value.notes)+'<p class="field-help">Containment does not establish zone enablement, pickup, timer expiry, scheme behavior or correct protection operation.</p>'+
      '<details><summary>Comparison source and settings identity</summary><p>Recording SHA-256 <code style="overflow-wrap:anywhere">'+hash(value.record_hash)+'</code><br>Settings SHA-256 <code style="overflow-wrap:anywhere">'+hash(value.settings_hash)+'</code></p></details></section>';
  }
  return {markup};
})();
if(typeof module!=='undefined')module.exports=DRZoneComparison;
