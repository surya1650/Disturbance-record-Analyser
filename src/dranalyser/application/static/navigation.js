'use strict';

function navigationPanel(result) {
  return `<section class="panel navigator"><div class="panel-heading"><div><h2>Event and channel navigator</h2><p>Inspect one relay at a time. A cursor shared by its views does not synchronize other relays.</p></div></div><div class="nav-body">${result.navigator_path ? '<button class="button" id="load-navigator">Open navigator</button><div id="navigation-content"></div>' : '<p>This revision has no waveform navigator data. Review & rerun with the updated backend to add it.</p>'}</div></section>`;
}

function bindNavigation(row) {
  const button = document.getElementById('load-navigator');
  if (!button) return;
  button.onclick = async () => {
    button.disabled = true;
    try {
      const data = await api(`/api/incidents/${row.incident_id || row.id}/navigator?revision=${row.number}`);
      const host = document.getElementById('navigation-content');
      if (!host || !button.isConnected) return;
      mountNavigation(host, data, row);
      button.hidden = true;
    } catch (error) { button.disabled=false; notice(error.message); }
  };
}

function mountNavigation(host, data, row) {
  const esc = escapeHtml, model = DRNavigation;
  const records = row.result.relay_evidence || [];
  const num = n => Number.isFinite(n) ? n.toFixed(3) : 'unavailable';
  let evidence, record, axis, lo, hi, cursor, analogIndex=0, digitalIndex=-1, loop='AB';
  let exact=null, requestNumber=0;
  function clearExact(){exact=null;requestNumber++;const b=host.querySelector('#nav-native');if(b)b.disabled=false;}
  host.innerHTML = `<label>Relay record<select id="nav-record">${records.map((r,i)=>`<option value="${i}">End ${esc(r.end || 'unassigned')} · ${esc(r.protection_system)} · ${esc(r.file)}</option>`).join('')}</select></label><div id="nav-controls"></div><div id="nav-view"></div>`;
  const el = name => host.querySelector('#'+name);
  const svg = (label, content, height=230) => `<div class="nav-plot" role="region" tabindex="0" aria-label="${esc(label)}"><svg role="img" aria-label="${esc(label)}" viewBox="0 0 800 ${height}">${content}</svg></div>`;
  const text = (x,y,value,extra='') => `<text x="${x}" y="${y}" ${extra}>${esc(value)}</text>`;
  const line = (x1,y1,x2,y2,color='#80989b',extra='') => `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" ${extra}/>`;
  const timeX = t => 55 + (t-lo)/(hi-lo)*705;
  function sld() {
    const selected = evidence.end;
    const side = end => end === selected ? 'Selected relay indications below' : 'State unknown on this local timeline';
    return svg('Logical line diagram; breaker positions unknown',
      line(60,35,60,110)+line(740,35,740,110)+line(60,70,180,70)+line(260,70,540,70)+line(620,70,740,70)+
      '<rect x="180" y="48" width="80" height="44" fill="#f1f5f6" stroke="#82999e" stroke-dasharray="5 4"/>'+
      '<rect x="540" y="48" width="80" height="44" fill="#f1f5f6" stroke="#82999e" stroke-dasharray="5 4"/>'+
      text(30,22,'Bus S')+text(708,22,'Bus R')+text(220,75,'CB ?', 'text-anchor="middle"')+text(580,75,'CB ?', 'text-anchor="middle"')+
      text(400,58,'Line / circuit', 'text-anchor="middle"')+text(30,135,side('S'))+text(450,135,side('R'))+
      text(30,160,'Logical connectivity only. Trip or inactive open indication does not prove breaker position.'),180);
  }
  function waveform(channel) {
    const bins = model.selectedBins(channel,lo,hi), good=bins.filter(b=>b[2]!=null);
    if (!good.length) return '<p>No finite waveform bins in this interval.</p>';
    let low=Math.min(...good.map(b=>b[2])), high=Math.max(...good.map(b=>b[3]));
    if (low===high) {low-=1;high+=1;}
    const y=v=>185-(v-low)/(high-low)*155;
    let marks='';
    for (const b of good) {
      const x0=timeX(Math.max(b[0],lo)), x1=timeX(Math.min(b[1],hi));
      marks += line((x0+x1)/2,y(b[2]),(x0+x1)/2,y(b[3]),'#087f75','stroke-width="2"');
      if (b[2]===b[3]) marks += `<circle cx="${(x0+x1)/2}" cy="${y(b[2])}" r="1.7" fill="#087f75"/>`;
    }
    return svg('Waveform min/max envelopes on selected local interval',marks+line(55,190,760,190)+
      line(timeX(cursor),20,timeX(cursor),190,'#b65927','stroke-dasharray="4 3"')+
      text(5,30,num(high))+text(5,185,num(low))+text(55,215,num(axis.toDisplay(lo)))+
      text(760,215,num(axis.toDisplay(hi)),'text-anchor="end"'));
  }
  function rxPlot() {
    const series=(record.rx.loops[loop] || []).filter(p=>p[0]>=lo && p[0]<=hi);
    const good=series.filter(p=>p[1]!=null && p[2]!=null);
    if (!good.length) return '<p>No eligible '+esc(loop)+' display points in this interval. Review the input evidence and interval.</p>';
    const zones=record.rx.zones?.[loop.endsWith('G')?'earth':'phase'] || [];
    const extent=good.map(p=>p.slice(1)).concat(zones.flatMap(z=>z.points));
    let minR=Math.min(...extent.map(p=>p[0])), maxR=Math.max(...extent.map(p=>p[0]));
    let minX=Math.min(...extent.map(p=>p[1])), maxX=Math.max(...extent.map(p=>p[1]));
    const span=Math.max(maxR-minR,maxX-minX,.1)*1.1, cx=(minR+maxR)/2, cy=(minX+maxX)/2;
    const x=v=>400+(v-cx)*170/span, y=v=>110-(v-cy)*170/span;
    let path='', marks=zones.map(z=>`<polygon class="rx-zone" points="${z.points.map(p=>`${x(p[0])},${y(p[1])}`).join(' ')}" fill="none" stroke="#9162a5" stroke-dasharray="5 3"><title>${esc(z.name)} exported boundary</title></polygon>`).join('');
    for (const p of series) {
      if (p[1]==null || p[2]==null) {path='';continue;}
      const next=`${x(p[1])},${y(p[2])}`;
      if(path) marks+=`<polyline points="${path} ${next}" fill="none" stroke="#087f75"/>`;
      marks+=`<circle cx="${x(p[1])}" cy="${y(p[2])}" r="2" fill="#087f75"/>`;path=next;
    }
    const preceding=good.filter(p=>p[0]<=cursor).at(-1);
    if(preceding) marks+=`<circle cx="${x(preceding[1])}" cy="${y(preceding[2])}" r="6" fill="none" stroke="#b65927" stroke-width="2"/>`;
    return svg(loop+' R-X trajectory in primary ohm; equal axis scales',marks+
      line(315,195,485,195)+line(315,25,315,195)+text(510,205,'R primary Ω')+text(245,18,'X primary Ω')+
      text(315,225,num(cx-span/2))+text(485,225,num(cx+span/2),'text-anchor="end"')+
      text(10,55,`R range ${num(minR)} … ${num(maxR)}`)+text(10,78,`X range ${num(minX)} … ${num(maxX)}`))+
      `<p class="field-help">Exported ${loop.endsWith('G')?'earth':'phase'} boundaries (dashed): ${zones.map(z=>esc(z.name)).join(', ') || 'none eligible'}. Boundary intersection does not prove zone pickup or operation.</p><p class="field-help">${preceding ? `Last displayed point at/before cursor: ${num(axis.toDisplay(preceding[0]))} ms; R ${num(preceding[1])}, X ${num(preceding[2])} primary Ω. It is not an interpolated cursor value.` : 'No displayed point at/before cursor.'}</p>`;
  }
  function digitalTimeline(points) {
    const visible=points.slice(0,8), x=t=>270+(t-lo)/(hi-lo)*490;
    const rows=visible.map((p,i)=>{
      const y=25+i*30;
      const bars=p.intervals.filter(v=>v.start_s<=hi && v.end_s>=lo).map(v=>
        `<rect x="${x(Math.max(lo,v.start_s))}" y="${y-10}" width="${Math.max(1,x(Math.min(hi,v.end_s))-x(Math.max(lo,v.start_s)))}" height="16" fill="#087f75"/>`).join('');
      return text(8,y,p.channel.length>32 ? p.channel.slice(0,29)+'…' : p.channel)+line(270,y,760,y,'#ccd8da')+bars;
    }).join('');
    return svg('Digital active-interval overview on the selected local timeline',rows+
      line(x(cursor),10,x(cursor),visible.length*30+5,'#b65927','stroke-dasharray="4 3"')+
      text(270,visible.length*30+25,num(axis.toDisplay(lo)))+
      text(760,visible.length*30+25,num(axis.toDisplay(hi)),'text-anchor="end"'),Math.max(80,visible.length*30+40))+
      `<p class="field-help">Bars show recorded active intervals, not verified contact position. ${points.length>8 ? 'Overview shows the first eight points; select a digital point to inspect any other channel.' : ''} Unknown/unavailable points have no state inferred from an empty bar.</p>`;
  }
  function draw() {
    const originalChannel=record.analog[analogIndex];
    const channel=exact ? {...originalChannel,bins:exact.samples.map(p=>[p[1],p[1],p[2],p[2],1])} : originalChannel;
    const points=digitalIndex<0 ? record.digital : [record.digital[digitalIndex]];
    const events=model.events(points,lo,hi), bins=model.selectedBins(channel,cursor,cursor);
    const cb=record.digital.filter(p=>p.meanings.some(m=>m.startsWith('CB_OPEN') || m.includes('POLE_DEAD')));
    const status=points.map(p=>`<li>${esc(p.channel)} · ${esc(p.meanings.join(', ') || 'unmapped')} · <strong>${esc(model.pointState(p,cursor,record.capture_s))}</strong></li>`).join('');
    const window=evidence.measurements.window;
    el('nav-view').innerHTML=`<h3>Local event view · End ${esc(evidence.end)} · ${esc(evidence.protection_system)}</h3><p>${esc(evidence.file)}<br>Revision ${row.number} · ${esc(axis.label)}<br>Selected interval ${num(axis.toDisplay(lo))} → ${num(axis.toDisplay(hi))} ms · Cursor <strong>${num(axis.toDisplay(cursor))} ms</strong></p><p>Detected inception ${num(axis.toDisplay(evidence.inception_local_s))} ms. Analysis window [${num(axis.toDisplay(window.start_s))}, ${num(axis.toDisplay(window.end_s))}) ms; selection does not change it.</p>${sld()}${stageClockEvidence(record)}<p><strong>Selected relay breaker indications:</strong> ${cb.map(p=>`${esc(p.channel)}: ${esc(model.pointState(p,cursor,record.capture_s))}`).join('; ') || 'not recorded / unmapped; breaker state unknown'}</p><h3>Waveform · ${esc(channel?.name || 'unavailable')}</h3><p>${esc(channel?.source || '')} · ${esc(channel?.unit || '')} · ${esc(channel?.scaling || '')}</p>${waveform(channel)}<p class="field-help">Cursor bin: ${bins.length && bins[0][2]!=null ? `${num(bins[0][2])} … ${num(bins[0][3])} ${esc(channel.unit)}; ${bins[0][4]} samples over ${num(axis.toDisplay(bins[0][0]))} … ${num(axis.toDisplay(bins[0][1]))} ms` : 'No finite bin at cursor; no value interpolated.'}</p><h3>R-X inspection · ${esc(loop)}</h3><p>${esc(record.rx.reason)}</p>${rxContextEvidence(record.rx.context)}<p class="field-help">${(record.rx.zones?.omitted || []).map(esc).join('; ')}</p>${rxPlot()}<h3>Digital indications at cursor</h3><ul class="nav-point-states">${status || '<li>No digital point available.</li>'}</ul><h3>Recorded active intervals</h3><p>Bounds below are the original recorded interval, not clipped to the selected view. ≤ means onset before capture is unknown; ≥ means still active at the last sample. ${events.length>200 ? 'Showing the first 200 matches; select one digital point or narrow the interval.' : ''}</p><div class="table-wrap"><table class="evidence-table"><thead><tr><th>Original point / meaning</th><th>From → to (${esc(axis.label)})</th><th>Navigate</th></tr></thead><tbody>${events.slice(0,200).map((i,n)=>`<tr><td>${esc(i.channel)}<small>${esc(i.meanings.join(', ') || 'unmapped')}</small></td><td>${i.onset_unknown?'≤ ':''}${num(axis.toDisplay(i.start_s))} → ${i.continues_at_capture_end?'≥ ':''}${num(axis.toDisplay(i.end_s))}</td><td><button class="button quiet" data-event="${n}">Go to start</button></td></tr>`).join('') || '<tr><td colspan="3">No active interval observed in selection. Missing/unavailable points remain unknown.</td></tr>'}</tbody></table></div><p class="field-help">${esc(record.note)}</p><p class="field-help">Omitted analog: ${record.omitted_analog.map(esc).join(', ') || 'none'} · Omitted digital: ${record.omitted_digital.map(esc).join(', ') || 'none'} · Unmapped analog labels: ${record.unmapped_analog.map(esc).join(', ') || 'none'}</p><p class="field-help">${evidence.flags.map(esc).join('; ')} · CT saturation: ${evidence.ct_saturation ? 'detected' : 'not detected'} · Clipping: ${evidence.clipped_channels.map(esc).join(', ') || 'not detected'}. Displayed curves do not establish fault distance, zone operation or TB 854 validation.</p>`;
    const rxHeading=[...host.querySelectorAll('#nav-view h3')].find(h=>h.textContent.startsWith('R-X inspection'));
    rxHeading.insertAdjacentHTML('beforebegin',nativeSampleSummary(exact,cursor,axis));
    const states=host.querySelector('.nav-point-states');
    states.insertAdjacentHTML('beforebegin',digitalTimeline(points));
    host.querySelectorAll('[data-event]').forEach(b=>b.onclick=()=>setCursor(Math.max(lo,Math.min(hi,events[Number(b.dataset.event)].start_s))));
  }
  function setCursor(t) {cursor=t;el('nav-cursor').value=axis.toDisplay(t);draw();}
  function selectRecord(index) {
    clearExact();
    evidence=records[index];record=data.records.find(r=>r.file===evidence.file);
    if (!record || record.status!=='available' || evidence.status!=='analysed') {
      el('nav-controls').innerHTML='';el('nav-view').innerHTML=`<p>${esc(record?.reason || evidence.reason || 'Navigation unavailable for this record.')}</p>`;return;
    }
    axis=model.axis(evidence);[lo,hi]=record.capture_s;cursor=Math.max(lo,Math.min(hi,evidence.inception_local_s ?? lo));analogIndex=0;digitalIndex=-1;
    el('nav-controls').innerHTML=`<div class="nav-controls"><label>Analog channel<select id="nav-analog">${record.analog.map((c,i)=>`<option value="${i}">${esc(c.name)} · ${esc(c.source)} · ${esc(c.unit)}</option>`).join('')}</select></label><label>Digital point<select id="nav-digital"><option value="-1">All available points</option>${record.digital.map((p,i)=>`<option value="${i}">${esc(p.channel)}</option>`).join('')}</select></label><label>Impedance loop<select id="nav-loop"><option>AB</option><option>BC</option><option>CA</option><option>AG</option><option>BG</option><option>CG</option></select></label><label>From (ms)<input id="nav-lo" type="number" step="any" value="${axis.toDisplay(lo)}"></label><label>To (ms)<input id="nav-hi" type="number" step="any" value="${axis.toDisplay(hi)}"></label></div><p>${esc(axis.label)}. Switching relay resets the local interval and cursor.</p><button id="nav-apply" class="button">Apply interval</button> <button id="nav-reset" class="button">Full capture</button> <button id="nav-export" class="button">Export current view</button><p id="nav-error" role="status"></p>${config.native_sample_inspection ? '<button id="nav-native" class="button">Load native samples</button><button id="nav-prev-sample" class="button quiet">Previous sample</button><button id="nav-next-sample" class="button quiet">Next sample</button>' : '<p class="field-help">Native sample inspection requires the updated backend.</p>'}<label>Local cursor<input id="nav-cursor" type="range" step="any" min="${axis.toDisplay(lo)}" max="${axis.toDisplay(hi)}" value="${axis.toDisplay(cursor)}"></label>`;
    el('nav-analog').onchange=e=>{analogIndex=Number(e.target.value);clearExact();draw();};
    el('nav-digital').onchange=e=>{digitalIndex=Number(e.target.value);draw();};
    el('nav-loop').value=loop;el('nav-loop').onchange=e=>{loop=e.target.value;draw();};
    el('nav-cursor').oninput=e=>setCursor(axis.toLocal(Number(e.target.value)));
    el('nav-apply').onclick=()=>{
      const rawLo=el('nav-lo').value,rawHi=el('nav-hi').value;
      const range=rawLo!=='' && rawHi!=='' && model.interval(axis.toLocal(Number(rawLo)),axis.toLocal(Number(rawHi)),record.capture_s);
      if(!range){el('nav-error').textContent='Enter increasing bounds within this recording.';return;}
      [lo,hi]=range;clearExact();el('nav-error').textContent='';el('nav-cursor').min=axis.toDisplay(lo);el('nav-cursor').max=axis.toDisplay(hi);setCursor(Math.max(lo,Math.min(hi,cursor)));
    };
    el('nav-reset').onclick=()=>selectRecord(index);
    if(el('nav-native')) {
      el('nav-native').onclick=async()=>{
        const sequence=++requestNumber, button=el('nav-native');button.disabled=true;el('nav-error').textContent='Loading native samples?';
        const query=new URLSearchParams({revision:row.number,record:evidence.file,channel:record.analog[analogIndex]?.name || '',start_s:lo,end_s:hi});
        try {
          const samples=await api(`/api/incidents/${row.incident_id || row.id}/samples?${query}`);
          if(sequence!==requestNumber || !host.isConnected)return;
          exact=samples;el('nav-error').textContent='';draw();
        } catch(error) {if(sequence===requestNumber && host.isConnected)el('nav-error').textContent=error.message;}
        finally {if(sequence===requestNumber && button.isConnected)button.disabled=false;}
      };
      for(const [id,direction] of [['nav-prev-sample',-1],['nav-next-sample',1]])el(id).onclick=()=>{
        const sample=exact && DRNativeSamples.step(exact.samples,cursor,direction);
        if(sample){el('nav-error').textContent='';setCursor(sample[1]);}
        else el('nav-error').textContent=exact ? 'No further sample inside this interval.' : 'Load native samples first.';
      };
    }
    el('nav-export').onclick=()=>{
      const copy=el('nav-view').cloneNode(true);copy.querySelectorAll('button').forEach(b=>b.remove());
      const html=`<!doctype html><meta charset="utf-8"><title>Local DR event view</title><style>body{font:14px system-ui;max-width:1100px;margin:30px auto;padding:20px}svg{width:100%;max-height:320px}text{font:13px system-ui}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:10px}small{display:block}p{line-height:1.6}</style><h1>Local DR event view</h1><p>Incident ${esc(row.incident_id || row.id)} · Original record SHA-256 ${esc(evidence.record_hash)}</p>${copy.innerHTML}`;
      const url=URL.createObjectURL(new Blob([html],{type:'text/html'}));const a=document.createElement('a');a.href=url;a.download=`local-event-r${row.number}.html`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    };
    draw();
  }
  el('nav-record').onchange=e=>selectRecord(Number(e.target.value));
  if(records.length) selectRecord(0);
}
