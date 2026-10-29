'use strict';
const DRChannelComparisonView=(()=>{
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number=value=>value===0?'0':Number(value).toPrecision(4).replace(/\.0+(?=e|$)/,'');
  function axis(records){
    const timed=records.every(r=>r.time_range_s?.length===2&&r.time_range_s.every(Number.isFinite)&&r.time_range_s[1]>r.time_range_s[0]);
    const spans=records.map(r=>timed?r.time_range_s[1]-r.time_range_s[0]:Math.max(0,r.sample_count-1));
    return {timed,span:Math.max(...spans,1e-6),coordinate:(p,r)=>timed?(Number.isFinite(p[1])?p[1]-r.time_range_s[0]:null):p[0]};
  }
  function plot(channel,record,coordinates){
    const points=channel.trace||[],values=points.filter(p=>Number.isFinite(p[2])).map(p=>Math.abs(p[2]));
    let peak=0;for(const v of values)peak=Math.max(peak,v);if(!peak)peak=1;
    const x=p=>coordinates.coordinate(p,record)/coordinates.span*510,y=v=>78-v/peak*55;
    const gap=record.time_basis?.minimum_interval_s?record.time_basis.minimum_interval_s*8:Infinity;
    const parts=DRInspection.segments(points,gap).flatMap(part=>{
      const out=[];let run=[];for(const p of part){if(coordinates.coordinate(p,record)===null){if(run.length)out.push(run);run=[];}else run.push(p);}if(run.length)out.push(run);return out;
    });
    const phase=DRInspection.phaseFor(channel,record.channels),colour={A:'#c94145',B:'#b88a00',C:'#316ecc',N:'#606c78',unknown:'#176d82'}[phase];
    const path=parts.map(part=>part.map((p,i)=>`${i?'L':'M'}${x(p)},${y(p[2])}`).join(' ')).join(' ');
    const grids=[-1,0,1].map(f=>`<line x1="0" x2="510" y1="${y(f*peak)}" y2="${y(f*peak)}" class="comparison-grid"/>`).join('');
    const ticks=[0,.5,1].map(f=>`<span>${esc(number(coordinates.span*f*(coordinates.timed?1000:1)))}</span>`).join('');
    const labels=[1,0,-1].map(f=>`<span style="top:${y(f*peak)/150*100}%">${esc(number(f*peak))}</span>`).join('');
    return `<div class="comparison-plot"><small class="comparison-units">${esc(channel.units)} · own scale</small><div class="comparison-ylabels">${labels}</div><svg viewBox="0 0 510 150" preserveAspectRatio="none" role="img" aria-label="${esc(channel.id+' '+channel.label+' · '+channel.units+' · independent amplitude scale')}">${grids}<path d="${path}" stroke="${colour}" fill="none" vector-effect="non-scaling-stroke"/>${parts.filter(p=>p.length===1).map(p=>`<circle cx="${x(p[0])}" cy="${y(p[0][2])}" r="2" fill="${colour}"/>`).join('')}<line class="comparison-cursor" x1="0" x2="0" y1="0" y2="150"/></svg><div class="comparison-xticks">${ticks}</div></div>`;
  }
  function mount(host,left,right,mappingsLeft={},mappingsRight={}){
    const groups=DRChannelComparison.plan(left,right,mappingsLeft,mappingsRight),coordinates=axis([left,right]);
    const cell=(channel,record,side)=>channel?`<section class="comparison-cell" data-side="${side}" data-channel-id="${esc(channel.id)}"><h5>${esc(record.file)}</h5><p class="comparison-source">${esc(channel.id+' · '+channel.label)}<small>${esc(channel.units)} · source units, unverified scaling</small></p>${plot(channel,record,coordinates)}</section>`:`<section class="comparison-cell comparison-missing" data-side="${side}"><h5>${esc(record.file)}</h5><p class="comparison-source">No matching channel<small>Other source channels remain visible below.</small></p><div class="comparison-empty">No unique compatible counterpart</div></section>`;
    host.innerHTML=`<p class="field-help">${coordinates.timed?'Horizontal axis: milliseconds from each recording’s first sample.':'Horizontal axis: zero-based sample index; usable time is unavailable for one or both recordings.'} Both starts are placed together for inspection only; this does not align physical events or clocks. Each channel has its own labelled vertical scale. Traces are bounded display envelopes; open a recording above for exact cursor values.</p><label class="comparison-position">Move comparison cursor <input type="range" min="0" max="1000" step="1" value="0" aria-label="Comparison display cursor"><output></output></label>`+groups.map(group=>`<section class="comparison-group" data-quantity="${group.quantity}"><h4>${esc(group.label)}</h4>${group.rows.map(row=>`<article class="comparison-row" data-meaning="${esc(row.meaning||'')}" data-pair-key="${esc(row.key)}"><h4>${esc(row.label)}</h4><p class="comparison-reason">${esc(row.reason)}</p><div class="comparison-pair">${cell(row.left,left,'left')}${cell(row.right,right,'right')}</div></article>`).join('')}</section>`).join('')+(groups.length?'':'<p>No recoverable analog channels in either recording. Source headers and decode reasons remain available above.</p>');
    const slider=host.querySelector('input'),output=host.querySelector('output');
    function move(fraction){
      const f=Math.max(0,Math.min(1,fraction));slider.value=String(Math.round(f*1000));output.value=number(f*coordinates.span*(coordinates.timed?1000:1))+(coordinates.timed?' ms from each start':' sample index');
      for(const line of host.querySelectorAll('.comparison-cursor')){line.setAttribute('x1',String(f*510));line.setAttribute('x2',String(f*510));}
    }
    slider.oninput=()=>move(Number(slider.value)/1000);
    for(const svg of host.querySelectorAll('svg'))svg.onpointermove=e=>{const rect=svg.getBoundingClientRect();move((e.clientX-rect.left)/rect.width);};
    move(0);
  }
  return {mount,axis};
})();
if(typeof module!=='undefined')module.exports=DRChannelComparisonView;
