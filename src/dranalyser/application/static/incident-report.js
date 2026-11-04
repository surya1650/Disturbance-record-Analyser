'use strict';
// Presentation of an immutable backend report; no electrical calculations here.
const DRIncidentReport=(()=>{
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function paths(row,reportId){
    const base='/api/incidents/'+encodeURIComponent(row.incident_id??row.id)+'/incident-report';
    const saved=reportId?base+'/'+encodeURIComponent(reportId):null;
    return {base,latest:base+'?revision='+encodeURIComponent(row.number),html:saved?saved+'/html':null,data:saved?saved+'/data':null};
  }
  function checked(value,row){
    if(value?.revision!==row.number)throw new Error('The report revision changed. Reopen this incident before generating a report.');
    if(value.report===null)return null;
    if(typeof value.report_id!=='string'||!value.report_id||typeof value.model!=='object'||value.model===null)throw new Error('The saved report response is incomplete. Try again.');
    return {reportId:value.report_id,isCurrent:value.is_current!==false,...paths(row,value.report_id)};
  }
  function historyMarkup(value,row){
    const entries=(Array.isArray(value)?value:[]).filter(item=>typeof item?.report_id==='string'&&item.report_id).slice(0,20);
    return entries.map(item=>{
      const route=paths(row,item.report_id),date=new Date(typeof item.created_at==='string'?item.created_at:NaN),label=Number.isFinite(date.getTime())?date.toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'}):'Creation time unavailable';
      return '<li><a href="'+esc(route.html)+'" target="_blank" rel="noopener">'+esc(label)+'</a> <a href="'+esc(route.data)+'?download=true" download>JSON</a><small>'+esc(item.report_id)+'</small></li>';
    }).join('');
  }
  function mount(host,row,{signal,request}={}){
    host.innerHTML='<section class="incident-report-view"><div class="incident-report-intro"><h3>One clear incident report</h3><p>A four-page summary with a line diagram, fault distance when supported, electrical measurements, recorded signals and what still needs review. You can generate it with one recording; comparison and physical distance are optional.</p></div><div class="incident-report-actions"><button type="button" class="button primary" data-incident-generate>Generate report</button><span data-incident-report-status role="status" aria-live="polite">Generate a report from the saved incident evidence.</span></div><div class="incident-report-exports" hidden><a class="button" data-incident-open target="_blank" rel="noopener">Open report ↗</a><button type="button" class="button" data-incident-pdf disabled>Print / Save PDF</button><a class="button" data-incident-html download>Save HTML</a><a class="button" data-incident-data download>Save JSON</a><p class="field-help">Save PDF uses your browser’s print dialog. Each generation is saved; viewing another recording or moving cursors does not change it.</p></div><iframe class="incident-report-preview" title="Four-page incident report preview" sandbox="allow-same-origin allow-modals" hidden></iframe><details class="incident-report-history" hidden><summary>Saved reports</summary><ul data-incident-saved-reports></ul></details><div class="incident-report-help"><button type="button" data-go-feature="inputs">Review a missing analysis input</button><button type="button" data-incident-history>Revision history and originals</button></div></section>';
    const q=selector=>host.querySelector(selector),generate=q('[data-incident-generate]'),status=q('[data-incident-report-status]'),exports=q('.incident-report-exports'),frame=q('iframe'),pdf=q('[data-incident-pdf]');
    const send=request||((path,options)=>{if(typeof api!=='function')throw new Error('Application connection unavailable. Reload this page.');return api(path,options);});
    let sequence=0,busy=false;
    const current=token=>!signal?.aborted&&host.isConnected&&token===sequence;
    async function load(create){
      if(busy)return;busy=true;const token=++sequence;generate.disabled=true;
      status.textContent=create?'Generating the incident report…':'Opening the saved incident report…';
      try{
        const route=paths(row),value=await send(create?route.base:route.latest,create?{method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:row.number})}:{signal});
        if(!current(token))return;
        const saved=checked(value,row);
        if(!saved){status.textContent='No report has been generated for this revision. Generate one when you are ready.';return;}
        const history=historyMarkup(value.history,row);q('[data-incident-saved-reports]').innerHTML=history;q('.incident-report-history').hidden=!history;
        q('[data-incident-open]').href=saved.html;q('[data-incident-html]').href=saved.html+'?download=true';q('[data-incident-data]').href=saved.data+'?download=true';
        q('[data-incident-html]').download='incident-report-r'+row.number+'.html';q('[data-incident-data]').download='incident-report-r'+row.number+'.json';
        exports.hidden=false;frame.hidden=false;pdf.disabled=true;
        frame.onload=()=>{if(current(token))pdf.disabled=false;};frame.src=saved.html;
        generate.textContent='Generate updated report';
        status.textContent=saved.isCurrent?'Saved report ready · revision '+row.number+'. Earlier generations are in Saved reports below.':'Inputs changed; generate the report again. The displayed generation is preserved with its original inputs.';
      }catch(error){if(current(token)&&error.name!=='AbortError')status.textContent=error.message||'The report could not be generated. Your records remain available.';}
      finally{if(current(token)){busy=false;generate.disabled=false;}}
    }
    generate.addEventListener('click',()=>load(true),{signal});
    pdf.addEventListener('click',()=>{try{frame.contentWindow.focus();frame.contentWindow.print();}catch{status.textContent='Open the report in a new tab and use Print → Save as PDF.';}},{signal});
    q('[data-incident-history]').addEventListener('click',()=>{const history=document.querySelector('.incident-history');if(history){history.open=true;history.scrollIntoView({block:'start'});}},{signal});
    signal?.addEventListener('abort',()=>{sequence++;},{once:true});
    return {activate(){return load(false);}};
  }
  return {mount,paths,checked,historyMarkup};
})();
if(typeof module!=='undefined')module.exports=DRIncidentReport;
