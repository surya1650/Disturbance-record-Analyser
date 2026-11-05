'use strict';
// Offline readouts from the frozen report observations; no interpolation or fetch.
const DRIncidentWaveforms=(()=>{
  const finite=value=>typeof value==='number'&&Number.isFinite(value);
  const valid=point=>Array.isArray(point)&&point.length>=3&&finite(point[0])&&finite(point[1])&&finite(point[2]);
  const exact=value=>Object.is(value,-0)?'0':String(value);
  function segments(trace){
    const rows=[];let current=[];
    for(const point of Array.isArray(trace)?trace:[]){
      if(!valid(point)||(current.length&&point[1]<current.at(-1)[1])){if(current.length)rows.push(current);current=[];}
      if(valid(point))current.push(point);
    }
    if(current.length)rows.push(current);
    return rows;
  }
  function nearestObservation(trace,time){
    if(!finite(time))return null;
    for(const rows of segments(trace)){
      if(time<rows[0][1]||time>rows.at(-1)[1])continue;
      let selected=rows[0];
      for(const point of rows)if(Math.abs(point[1]-time)<Math.abs(selected[1]-time))selected=point;
      return selected.slice(0,3);
    }
    return null;
  }
  function readoutRows(data,time){
    return (Array.isArray(data?.channels)?data.channels:[]).map(channel=>{
      const point=nearestObservation(channel.trace,time),label=String(channel.label||'Channel');
      if(!point)return {label,value:null,units:null,source_time_s:null,sample:null,reason:'Gap or no retained support'};
      const original=String(channel.original_units||channel.units||'units unavailable');
      const physical=['A','V'].includes(original.split(' ',1)[0]);
      const proposed=physical&&channel.factor===1000?1000:1;
      const factor=point[2]!==0&&point[2]/proposed===0?1:proposed;
      return {label,value:point[2]/factor,units:String(factor===1000?channel.units:original),
        source_time_s:point[1],sample:point[0],reason:null,
        original_value:factor===1?null:point[2],original_units:factor===1?null:original};
    });
  }
  function readingValue(row){
    return exact(row.value)+' '+row.units+(row.original_value!==null?' ('+exact(row.original_value)+' '+row.original_units+')':'');
  }
  function formatReadout(data,time){
    const readings=readoutRows(data,time).map(row=>{
      if(row.reason)return row.label+': unavailable here (gap or no retained support).';
      return row.label+': '+readingValue(row)+' · t='+exact(row.source_time_s)+' s local · sample '+exact(row.sample)+'.';
    });
    return 'Instantaneous samples; nearest retained observation, no interpolation. '+readings.join(' ');
  }
  function digitalRows(data,time){
    return (Array.isArray(data?.digital_inspection?.channels)?data.digital_inspection.channels:[]).slice(0,4).map(channel=>{
      const polarity=channel.asserted_state===0||channel.asserted_state===1?channel.asserted_state:null;
      // Both endpoints are recorded samples. The space between runs remains unknown,
      // including the unsampled bracket around a transition to the opposite bit.
      const segment=finite(time)&&(Array.isArray(channel.segments)?channel.segments:[]).find(row=>
        finite(row?.from_s)&&finite(row?.to_s)&&row.to_s>=row.from_s&&time>=row.from_s&&time<=row.to_s&&(row.state===0||row.state===1));
      const summary=channel.window_summary||{},state=segment?segment.state:null;
      const asserted=state===null||polarity===null?null:state===polarity;
      const reason=segment?null:'Gap or no retained support';
      const bounds=summary.duration_bounds_s;
      let duration='Unknown';
      if(polarity===null){
        const high=summary.high_duration_bounds_s;
        if(Array.isArray(high)&&high.length===2&&high.every(finite)&&high[0]>=0&&high[1]>=high[0])
          duration='High span '+(high[0]===high[1]?exact(high[0]):exact(high[0])+'–'+exact(high[1]))+' s; active unverified';
        else if(finite(summary.observed_high_span_s)&&summary.observed_high_span_s>=0)
          duration='Observed high span '+(summary.observed_high_span_s>0?'≥':'')+exact(summary.observed_high_span_s)+' s; active unverified';
        else duration='Unknown polarity';
      }
      else if(Array.isArray(bounds)&&bounds.length===2&&bounds.every(finite)&&bounds[0]>=0&&bounds[1]>=bounds[0]){
        duration=(bounds[0]===bounds[1]?exact(bounds[0]):exact(bounds[0])+'–'+exact(bounds[1]))+' s';
      }
      const support=[];
      if(summary.censored_start||summary.censored_end)support.push('boundary censored');
      if(summary.gap_count>0||summary.unknown_samples>0)support.push('missing observations');
      if(support.length&&!['Unknown','Unknown polarity'].includes(duration))
        duration+=' (recorded portion; '+support.join('; ')+')';
      const active=polarity===null?null:typeof summary.active_during_window==='boolean'?summary.active_during_window:null;
      const window=Array.isArray(summary.time_range_s)&&summary.time_range_s.length===2&&summary.time_range_s.every(finite)&&
        summary.time_range_s[1]>=summary.time_range_s[0]?summary.time_range_s.slice():null;
      return {label:String(channel.label||channel.id||'Signal'),state,asserted,reason,support_reason:String(summary.reason||''),
        at_cursor:state===null?'Unavailable ('+reason.toLowerCase()+')':(state===1?'High (1)':'Low (0)')+(polarity===null?' · polarity unreviewed':asserted?' · Asserted':' · Cleared'),
        active_in_window:polarity===null?'Unknown polarity':active===null?'Unknown':active?'Yes':'No',
        recorded_active_duration:duration,window_time_range_s:window,polarity_label:String(channel.polarity_label||'')};
    });
  }
  function recordClockText(data){
    const clock=data?.record_clock;
    if(!clock||typeof clock!=='object')return 'Record clock unavailable; source-local elapsed seconds only.';
    const start=String(clock.start_display||'Unavailable'),trigger=String(clock.trigger_display||'Unavailable');
    const reason=clock.cursor_time_reason||clock.reason;
    return 'Record start: '+start+' · Trigger: '+trigger+' · Time zone: '+String(clock.timezone_label||'Not declared')+
      ' · Cursor clock unavailable'+(reason?': '+String(reason).replace(/\.+$/,''):'; source-local elapsed seconds only')+'.';
  }
  function renderReadout(output,data,time){
    const doc=output.ownerDocument;
    if(!doc||typeof doc.createElement!=='function'){output.textContent=formatReadout(data,time);return;}
    output.textContent='';
    output.setAttribute('role','status');output.setAttribute('aria-live','polite');output.setAttribute('aria-atomic','true');
    const element=(tag,text,className)=>{
      const node=doc.createElement(tag);
      if(text!==undefined)node.textContent=String(text);
      if(className)node.setAttribute('class',className);
      return node;
    };
    const table=(caption,headers,rows,className,reasons=[])=>{
      const node=element('table',undefined,className);
      node.append(element('caption',caption));
      const head=element('thead'),header=element('tr');
      for(const label of headers){const cell=element('th',label);cell.setAttribute('scope','col');header.append(cell);}
      head.append(header);node.append(head);
      const body=element('tbody');
      for(const [index,values] of rows.entries()){
        const row=element('tr');
        if(reasons[index])row.setAttribute('title',reasons[index]);
        values.forEach((value,index)=>{const cell=element(index===0?'th':'td',value);if(index===0)cell.setAttribute('scope','row');row.append(cell);});
        body.append(row);
      }
      node.append(body);output.append(node);
    };
    output.append(element('p',recordClockText(data),'waveform-clock-context'));
    table('Instantaneous samples · nearest retained observation; no interpolation.',
      ['Phase','Instantaneous value','Source local s','Sample'],readoutRows(data,time).map(row=>
        [row.label,row.reason?'Unavailable ('+row.reason.toLowerCase()+')':readingValue(row),row.reason?'—':exact(row.source_time_s),row.reason?'—':exact(row.sample)]),'waveform-readout-table');
    const digitals=digitalRows(data,time);
    const window=digitals[0]?.window_time_range_s;
    const sameWindow=window&&digitals.every(row=>row.window_time_range_s&&row.window_time_range_s.every((value,index)=>value===window[index]));
    const omittedChannels=data?.digital_inspection?.omitted_channels;
    const omittedSegments=(Array.isArray(data?.digital_inspection?.channels)?data.digital_inspection.channels:[]).slice(0,4)
      .reduce((total,channel)=>total+(Number.isInteger(channel.omitted_segments)&&channel.omitted_segments>0?channel.omitted_segments:0),0);
    const omissions=[];
    if(Number.isInteger(omittedChannels)&&omittedChannels>0)omissions.push(exact(omittedChannels)+' signals omitted');
    if(omittedSegments>0)omissions.push(exact(omittedSegments)+' segments omitted');
    if(digitals.length)table('Recorded digital states at cursor '+exact(time)+' local s'+
      (sameWindow?'; selected window '+exact(window[0])+'–'+exact(window[1])+' local s':'')+
      (omissions.length?'; '+omissions.join('; '):'')+'. Asserted meanings require reviewed polarity.',
      ['Signal','At cursor','Active in window','Recorded active duration'],digitals.map(row=>
        [row.label,row.at_cursor,row.active_in_window,row.recorded_active_duration]),'waveform-digital-table',digitals.map(row=>row.support_reason));
  }
  function readData(view){
    try{return JSON.parse(view.querySelector('.waveform-data')?.textContent||'null');}catch{return null;}
  }
  function retainedTimes(data){
    const analog=(data?.channels||[]).flatMap(channel=>(channel.trace||[]).filter(valid).map(point=>point[1]));
    const digital=(data?.digital_inspection?.channels||[]).slice(0,4).flatMap(channel=>(channel.segments||[])
      .filter(row=>finite(row?.from_s)&&finite(row?.to_s)&&row.to_s>=row.from_s&&(row.state===0||row.state===1))
      .flatMap(row=>[row.from_s,row.to_s])).filter(time=>!Array.isArray(data?.range)||data.range.length!==2||
        !data.range.every(finite)||(time>=data.range[0]&&time<=data.range[1]));
    return [...new Set([...analog,...digital])].sort((a,b)=>a-b);
  }
  function mount(view){
    if(view.dataset.waveformBound)return;
    const svg=view.querySelector('svg.waveform'),output=view.querySelector('.waveform-readout');
    if(!svg||!output)return;
    output.setAttribute('role','status');output.setAttribute('aria-live','polite');
    view.dataset.waveformBound='true';
    if(!view.hasAttribute('tabindex'))view.setAttribute('tabindex','0');
    let time=null,cursor=svg.querySelector('[data-waveform-cursor]');
    if(!cursor){cursor=svg.ownerDocument.createElementNS('http://www.w3.org/2000/svg','line');cursor.setAttribute('data-waveform-cursor','');cursor.setAttribute('class','waveform-cursor');cursor.setAttribute('aria-hidden','true');svg.append(cursor);}
    cursor.setAttribute('visibility','hidden');
    const instruction='Hover or touch a trace for retained sample values. Focus this chart and use arrow keys; Home/End select the first/last retained time.';
    const reset=()=>{time=null;cursor.setAttribute('visibility','hidden');output.textContent=instruction;};
    const show=next=>{
      const data=readData(view),range=data?.range,plot=data?.plot;
      if(!Array.isArray(range)||range.length!==2||!range.every(finite)||range[1]<=range[0]||!plot)return;
      time=Math.max(range[0],Math.min(range[1],next));
      const x=plot.left+(time-range[0])/(range[1]-range[0])*(plot.right-plot.left);
      for(const [key,value] of Object.entries({x1:x,x2:x,y1:plot.top,y2:plot.bottom,visibility:'visible'}))cursor.setAttribute(key,String(value));
      renderReadout(output,data,time);
    };
    const pointer=event=>{
      const data=readData(view),plot=data?.plot,range=data?.range,matrix=svg.getScreenCTM?.();
      if(!plot||!Array.isArray(range)||!matrix||!finite(event.clientX)||!finite(event.clientY))return;
      const point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;
      const local=point.matrixTransform(matrix.inverse());
      if(local.x<plot.left||local.x>plot.right||local.y<plot.top||local.y>plot.bottom){reset();return;}
      show(range[0]+(local.x-plot.left)/(plot.right-plot.left)*(range[1]-range[0]));
    };
    svg.addEventListener('pointermove',pointer);svg.addEventListener('pointerdown',pointer);
    svg.addEventListener('pointerleave',event=>{if(event.pointerType!=='touch')reset();});
    view.addEventListener('keydown',event=>{
      if(event.key==='Escape'){reset();event.preventDefault();return;}
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      const data=readData(view),times=retainedTimes(data);if(!times.length)return;
      let selected;
      if(event.key==='Home')selected=times[0];
      else if(event.key==='End')selected=times.at(-1);
      else if(time===null)selected=event.key==='ArrowLeft'?times.at(-1):times[0];
      else if(event.key==='ArrowRight')selected=times.find(value=>value>time)??times.at(-1);
      else selected=times.findLast(value=>value<time)??times[0];
      show(selected);event.preventDefault();
    });
    view.addEventListener('blur',reset);
    view.addEventListener('waveform-reset',reset);
    reset();
  }
  function mountSet(set){
    if(set.dataset.waveformSetBound)return;
    const buttons=[...set.querySelectorAll('[data-waveform-mode-button]')];
    const panels=[...set.querySelectorAll('.waveform-mode-panel')];
    if(!buttons.length||!panels.length)return;
    set.dataset.waveformSetBound='true';
    for(const button of buttons)button.addEventListener('click',()=>{
      const mode=button.dataset.waveformModeButton;
      if(!panels.some(panel=>panel.dataset.waveformMode===mode))return;
      for(const panel of panels){panel.hidden=panel.dataset.waveformMode!==mode;for(const view of panel.querySelectorAll('.waveform-view'))view.dispatchEvent(new Event('waveform-reset'));}
      for(const option of buttons)option.setAttribute('aria-pressed',String(option===button));
    });
  }
  function init(root){for(const set of root?.querySelectorAll?.('.waveform-set')||[])mountSet(set);for(const view of root?.querySelectorAll?.('.waveform-view')||[])mount(view);}
  return {nearestObservation,readoutRows,formatReadout,digitalRows,recordClockText,renderReadout,mount,mountSet,init};
})();
if(typeof module!=='undefined')module.exports=DRIncidentWaveforms;
if(typeof document!=='undefined'){
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>DRIncidentWaveforms.init(document),{once:true});
  else DRIncidentWaveforms.init(document);
}
