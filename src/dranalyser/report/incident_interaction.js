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
  function formatReadout(data,time){
    const readings=(Array.isArray(data?.channels)?data.channels:[]).map(channel=>{
      const point=nearestObservation(channel.trace,time),label=String(channel.label||'Channel');
      if(!point)return label+': unavailable here (gap or no retained support).';
      const original=String(channel.original_units||channel.units||'units unavailable');
      const physical=['A','V'].includes(original.split(' ',1)[0]);
      const proposed=physical&&channel.factor===1000?1000:1;
      const factor=point[2]!==0&&point[2]/proposed===0?1:proposed;
      const units=String(factor===1000?channel.units:original);
      const converted=point[2]/factor;
      const value=exact(converted)+' '+units+(factor!==1?' ('+exact(point[2])+' '+original+')':'');
      return label+': '+value+' · t='+exact(point[1])+' s local · sample '+exact(point[0])+'.';
    });
    return 'Instantaneous samples; nearest retained observation, no interpolation. '+readings.join(' ');
  }
  function readData(view){
    try{return JSON.parse(view.querySelector('.waveform-data')?.textContent||'null');}catch{return null;}
  }
  function retainedTimes(data){
    return [...new Set((data?.channels||[]).flatMap(channel=>(channel.trace||[]).filter(valid).map(point=>point[1])))].sort((a,b)=>a-b);
  }
  function mount(view){
    if(view.dataset.waveformBound)return;
    const svg=view.querySelector('svg.waveform'),output=view.querySelector('.waveform-readout');
    if(!svg||!output)return;
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
      output.textContent=formatReadout(data,time);
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
  return {nearestObservation,formatReadout,mount,mountSet,init};
})();
if(typeof module!=='undefined')module.exports=DRIncidentWaveforms;
if(typeof document!=='undefined'){
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>DRIncidentWaveforms.init(document),{once:true});
  else DRIncidentWaveforms.init(document);
}
