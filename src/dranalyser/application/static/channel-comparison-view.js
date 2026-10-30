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
  function digitalTrack(channel,record,coordinates){
    const activity=channel.activity||{},intervals=activity.high_intervals||[];
    const marks=intervals.map(span=>{
      const start=coordinates.coordinate([span.start_index,span.start_s,1],record),last=coordinates.coordinate([span.last_index,span.last_s,1],record);
      if(!Number.isFinite(start)||!Number.isFinite(last)||last<start)return '';
      const x=start/coordinates.span*510,width=(last-start)/coordinates.span*510;
      return width>0?`<rect x="${x}" y="8" width="${width}" height="14" fill="#176d82"/>`:`<circle cx="${x}" cy="15" r="2" fill="#176d82"/>`;
    }).join('');
    return `<article class="comparison-digital-track" data-digital-channel="${esc(channel.id)}"><p title="${esc(channel.label+' · '+channel.id)}">${esc(channel.label)}<small>${esc(channel.id)} · ${Number.isInteger(activity.transition_count)?esc(activity.transition_count)+' recorded changes':'change count unavailable'}</small></p><svg viewBox="0 0 510 30" preserveAspectRatio="none" role="img" aria-label="${esc(channel.label+' recorded state-1 sampled spans; missing intervals remain unknown')}">${marks}<line class="comparison-cursor" x1="0" x2="0" y1="0" y2="30"/></svg>${activity.omitted_intervals?'<small>'+esc(activity.omitted_intervals)+' additional high intervals omitted from this bounded overview; open Waveforms for native observations.</small>':''}</article>`;
  }
  function digitalSection(record,side,coordinates){
    const channels=(record.channels||[]).filter(c=>c.kind==='digital').slice().sort((a,b)=>(b.activity?.transition_count||0)-(a.activity?.transition_count||0));
    return `<section class="comparison-digital-record" data-digital-side="${side}"><h5 title="${esc(record.file)}">${esc(record.file)}</h5>${channels.length?channels.slice(0,4).map(c=>digitalTrack(c,record,coordinates)).join('')+(channels.length>4?'<details><summary>Show '+esc(channels.length-4)+' additional digital channels</summary>'+channels.slice(4).map(c=>digitalTrack(c,record,coordinates)).join('')+'</details>':''):'<p>No digital channels were recorded in this source.</p>'}</section>`;
  }
  function mount(host,left,right,mappingsLeft={},mappingsRight={},options={}){
    const groups=DRChannelComparison.plan(left,right,mappingsLeft,mappingsRight),coordinates=axis([left,right]);
    const cell=(channel,record,side)=>channel?`<section class="comparison-cell" data-side="${side}" data-channel-id="${esc(channel.id)}"><h5 title="${esc(record.file)}">${esc(record.file)}</h5><p class="comparison-source" title="${esc(channel.label+' · '+channel.id)}">${esc(channel.label)}<small>${esc(channel.id)} · ${esc(channel.units)} · source units, unverified scaling</small></p>${plot(channel,record,coordinates)}</section>`:`<section class="comparison-cell comparison-missing" data-side="${side}"><h5 title="${esc(record.file)}">${esc(record.file)}</h5><p class="comparison-source">No matching channel<small>Other source channels remain visible below.</small></p><div class="comparison-empty">No unique compatible counterpart</div></section>`;
    host.innerHTML=`<p class="field-help">${coordinates.timed?'Horizontal axis: milliseconds from each recording’s first sample.':'Horizontal axis: zero-based sample index; usable time is unavailable for one or both recordings.'} Both starts are placed together for inspection only; this does not align physical events or clocks. Each channel has its own labelled vertical scale. Traces are bounded display envelopes; open a recording above for exact cursor values.</p><label class="comparison-position">Move comparison cursor <input type="range" min="0" max="1000" step="1" value="0" aria-label="Comparison display cursor"><output></output></label>`+groups.map(group=>`<section class="comparison-group" data-quantity="${group.quantity}"><h4>${esc(group.label)}</h4>${group.rows.map(row=>`<article class="comparison-row" data-meaning="${esc(row.meaning||'')}" data-pair-key="${esc(row.key)}"><h4>${esc(row.label)}</h4><p class="comparison-reason">${esc(row.reason)}</p><div class="comparison-pair">${cell(row.left,left,'left')}${cell(row.right,right,'right')}</div></article>`).join('')}</section>`).join('')+(groups.length?'':'<p>No recoverable analog channels in either recording. Source headers and decode reasons remain available above.</p>');
    const playback='<div class="comparison-playback"><button type="button" data-comparison-play aria-pressed="false">Play</button><button type="button" data-comparison-reset>Back to start</button><label>Playback speed <select data-comparison-speed><option value="0.1">0.1×</option><option value="0.25" selected>0.25×</option><option value="0.5">0.5×</option><option value="1">1×</option><option value="2">2×</option></select></label><span data-comparison-playback-status role="status">Display playback only; starts are compared without clock synchronization.</span></div>';
    host.innerHTML=host.innerHTML.replace('</label>','</label>'+playback);
    host.innerHTML+='<section class="comparison-digitals"><h4>Digital channels</h4><p class="field-help">Changed channels first, four initially visible per source. Bars show recorded state-1 sampled spans only, not verified assertion polarity, trip or physical breaker operation. Blank areas may be state 0 or unavailable; gaps are not filled.</p><div class="comparison-pair">'+digitalSection(left,'left',coordinates)+digitalSection(right,'right',coordinates)+'</div></section>';
    const slider=host.querySelector('input'),output=host.querySelector('output'),play=host.querySelector('[data-comparison-play]'),reset=host.querySelector('[data-comparison-reset]'),speed=host.querySelector('[data-comparison-speed]'),status=host.querySelector('[data-comparison-playback-status]');
    const requestFrame=options.requestFrame||globalThis.requestAnimationFrame?.bind(globalThis),cancelFrame=options.cancelFrame||globalThis.cancelAnimationFrame?.bind(globalThis);
    let position=0,frame=null,playing=false,destroyed=false,last=null;
    const visible=options.visible||(()=>host.isConnected!==false&&!host.closest?.('[hidden]')&&globalThis.document?.hidden!==true&&(!host.getClientRects||host.getClientRects().length>0));
    function pause(message='Playback paused.'){
      playing=false;last=null;if(frame!==null)cancelFrame?.(frame);frame=null;play.textContent='Play';play.setAttribute('aria-pressed','false');status.textContent=message;
    }
    function move(fraction){
      const f=Math.max(0,Math.min(1,fraction));position=f;slider.value=String(Math.round(f*1000));output.value=number(f*coordinates.span*(coordinates.timed?1000:1))+(coordinates.timed?' ms from each start':' sample index');
      for(const line of host.querySelectorAll('.comparison-cursor')){line.setAttribute('x1',String(f*510));line.setAttribute('x2',String(f*510));}
    }
    function tick(timestamp){
      frame=null;if(destroyed||!playing)return;if(!visible()){pause('Playback paused because the comparison is hidden.');return;}
      if(last!==null)move(position+Math.max(0,Math.min(timestamp-last,250))*Number(speed.value)/(coordinates.span*1000));last=timestamp;
      if(position>=1){pause('End of the longer recording; no missing samples are extended.');return;}frame=requestFrame(tick);
    }
    function start(){
      if(destroyed||playing||!requestFrame||!coordinates.timed||!visible())return;
      if(position>=1)move(0);playing=true;last=null;play.textContent='Pause';play.setAttribute('aria-pressed','true');status.textContent='Playing the shared display cursor; events and clocks remain independent.';frame=requestFrame(tick);
    }
    slider.oninput=()=>{pause();move(Number(slider.value)/1000);};
    play.disabled=!coordinates.timed||!requestFrame;play.onclick=()=>playing?pause():start();
    reset.onclick=()=>{pause();move(0);};speed.onchange=()=>{last=null;};
    if(!coordinates.timed)status.textContent='Playback requires usable times in both recordings. Manual sample-index inspection remains available.';
    for(const svg of host.querySelectorAll('svg'))svg.onpointermove=e=>{if(playing)return;const rect=svg.getBoundingClientRect();move((e.clientX-rect.left)/rect.width);};
    move(0);
    const destroy=()=>{destroyed=true;pause('Comparison closed.');};
    options.signal?.addEventListener('abort',destroy,{once:true});if(options.signal?.aborted)destroy();
    return {destroy,pause,play:start,position:()=>position};
  }
  return {mount,axis,digitalTrack};
})();
if(typeof module!=='undefined')module.exports=DRChannelComparisonView;
