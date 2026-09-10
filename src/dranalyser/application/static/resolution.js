'use strict';

const DRNativeSamples = (() => {
  function nearest(samples, t) {
    if(!samples.length || !Number.isFinite(t)) return null;
    let lo=0,hi=samples.length;
    while(lo<hi){const mid=(lo+hi)>>1;if(samples[mid][1]<t)lo=mid+1;else hi=mid;}
    if(lo===0) return samples[0];
    if(lo===samples.length) return samples.at(-1);
    return t-samples[lo-1][1] <= samples[lo][1]-t ? samples[lo-1] : samples[lo];
  }
  function step(samples,t,direction) {
    return direction>0 ? samples.find(s=>s[1]>t+1e-12) || null : samples.findLast(s=>s[1]<t-1e-12) || null;
  }
  return {nearest,step};
})();
if(typeof module!=='undefined') module.exports=DRNativeSamples;

function nativeSampleSummary(data,cursor,axis) {
  const esc=escapeHtml, num=x=>Number.isFinite(x)?Number(x).toPrecision(9):'unavailable';
  if(!data) return '<p class="field-help">Waveform uses the saved display envelope. Load native samples to inspect exact recorded points and measure this interval.</p>';
  const point=DRNativeSamples.nearest(data.samples,cursor),m=data.metrics;
  return `<div class="native-samples"><h3>Native sample inspection</h3><p>${esc(data.source_id)} · ${esc(data.source)} · ${esc(data.unit)} · ${data.samples.length} samples loaded.</p><p>${point ? `Nearest recorded sample: index ${point[0]} at ${num(axis.toDisplay(point[1]))} ms; value <strong>${num(point[2])} ${esc(data.unit)}</strong>. Sample − cursor = ${num((point[1]-cursor)*1000)} ms.` : 'No recorded sample in this selection.'}</p><p>Interval sample RMS <strong>${num(m.rms)} ${esc(data.unit)}</strong> · measured absolute peak <strong>${num(m.peak_abs)} ${esc(data.unit)}</strong> at ${num(axis.toDisplay(m.peak_local_s))} ms · ${esc(m.status)}.</p><p class="field-help">${esc(m.basis)} ${esc(data.note)}</p></div>`;
}
