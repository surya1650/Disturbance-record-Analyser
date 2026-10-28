'use strict';
const DRPlaybackModel=(()=>{
  function lastAt(items,time,key=x=>x[0]){let lo=0,hi=items.length;while(lo<hi){const mid=(lo+hi)>>1;if(key(items[mid])<=time)lo=mid+1;else hi=mid;}return lo-1;}
  function stateAt(signal,time){if(!signal||signal.status!=='available'||!Number.isFinite(time))return null;const i=lastAt(signal.runs,time);if(i<0)return null;const r=signal.runs[i];return time<=r[1]&&[0,1].includes(r[2])?r[2]===signal.active:null;}
  function breaker(record,time){const open=stateAt(record.signals.open,time),closed=stateAt(record.signals.closed,time);return open===true&&closed===true?'conflict':open===true?'open indication':closed===true?'closed indication':'unknown';}
  const local=(record,ms)=>record.trigger_s+(ms-record.offset_ms)/1000;
  const shared=(record,seconds)=>(seconds-record.trigger_s)*1000+record.offset_ms;
  function range(records){const all=records.flatMap(r=>r.capture_s.map(t=>shared(r,t)));return [Math.min(...all),Math.max(...all)];}
  function advance(time,elapsed,speed,bounds,repeat=false){if(![time,elapsed,speed,...bounds].every(Number.isFinite)||elapsed<0||speed<=0||bounds[1]<=bounds[0])throw new Error('Invalid playback clock.');let next=time+elapsed*speed;const ended=next>=bounds[1];if(ended&&repeat)next=bounds[0]+(next-bounds[0])%(bounds[1]-bounds[0]);else next=Math.max(bounds[0],Math.min(bounds[1],next));return {time:next,ended:ended&&!repeat};}
  function pointAt(series,time){const i=lastAt(series,time);if(i<0)return null;const p=series[i];const step=i+1<series.length?series[i+1][0]-p[0]:i>0?p[0]-series[i-1][0]:0;return Number.isFinite(p[1])&&Number.isFinite(p[2])&&(time===p[0]||(step>0&&time-p[0]<=step*1.05))?p:null;}
  return {lastAt,stateAt,breaker,local,shared,range,advance,pointAt};
})();
if(typeof module!=='undefined')module.exports=DRPlaybackModel;
