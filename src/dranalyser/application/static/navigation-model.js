'use strict';

// Local presentation coordinates only. No correlation lag or other relay clock is applied.
const DRNavigation = (() => {
  function axis(evidence) {
    const valid = Number.isFinite(evidence.trigger_offset_s);
    const origin = valid ? evidence.trigger_offset_s : 0;
    return {label: valid ? 'ms from this relay trigger' : 'ms from record local origin; trigger unavailable',
      toDisplay: t => Number.isFinite(t) ? (t-origin)*1000 : NaN,
      toLocal: t => Number.isFinite(t) ? t/1000+origin : NaN};
  }
  function pointState(point, t, capture) {
    if (!point || !Number.isFinite(t) || t < capture[0] || t > capture[1] ||
        ['insufficient samples', 'unavailable for continuous navigation'].includes(point.state)) return 'unknown';
    return point.intervals.some(i => t >= i.start_s && (t < i.end_s ||
      (i.continues_at_capture_end && t <= i.end_s))) ? 'active indication' : 'inactive indication';
  }
  function events(points, lo, hi) {
    return points.flatMap(p => p.intervals.map(i => ({...i, channel:p.channel, meanings:p.meanings})))
      .filter(i => i.start_s <= hi && i.end_s >= lo).sort((a,b) => a.start_s-b.start_s || a.channel.localeCompare(b.channel));
  }
  function interval(lo, hi, capture) {
    if (!Number.isFinite(lo) || !Number.isFinite(hi) || lo >= hi || lo < capture[0]-1e-9 || hi > capture[1]+1e-9) return null;
    return [Math.max(lo,capture[0]), Math.min(hi,capture[1])];
  }
  function selectedBins(channel, lo, hi) { return (channel?.bins || []).filter(b => b[0] <= hi && b[1] >= lo); }
  return {axis, pointState, events, interval, selectedBins};
})();
if (typeof module !== 'undefined') module.exports = DRNavigation;
