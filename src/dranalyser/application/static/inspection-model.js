'use strict';
const DRInspection = (() => {
  function create(record) {
    const n=record.sample_count;
    return {record:record.file,revision:record.revision,n,order:record.channels.map(c=>c.id),hidden:new Set(),
      pins:{A:0,B:Math.max(0,n-1)},hover:0,view:[0,Math.max(0,n-1)],generation:0,requests:new Map(),
      visible(id){return !this.hidden.has(id);},
      toggle(id){this.hidden.has(id)?this.hidden.delete(id):this.hidden.add(id);},
      reorder(id,direction){const i=this.order.indexOf(id),j=i+direction;if(i>=0&&j>=0&&j<this.order.length)[this.order[i],this.order[j]]=[this.order[j],this.order[i]];},
      move(name,index){if(!Number.isFinite(index))return;const v=Math.max(0,Math.min(n-1,Math.round(index)));if(name==='hover')this.hover=v;else this.pins[name]=v;},
      addPin(){let i=2;while(this.pins[String.fromCharCode(65+i)]!==undefined)i++;this.pins[String.fromCharCode(65+i)]=this.hover;},
      removePin(name){if(!['A','B'].includes(name))delete this.pins[name];},
      zoom(factor,center=(this.view[0]+this.view[1])/2){const span=Math.min(n-1,Math.max(1,(this.view[1]-this.view[0])*factor));const lo=Math.max(0,Math.min(n-1-span,center-span/2));this.view=[lo,lo+span];},
      pan(fraction){const span=this.view[1]-this.view[0],lo=Math.max(0,Math.min(n-1-span,this.view[0]+span*fraction));this.view=[lo,lo+span];},
      reset(){this.view=[0,Math.max(0,n-1)];},
      request(channel){const serial=(this.requests.get(channel)||0)+1;this.requests.set(channel,serial);return {record:this.record,revision:this.revision,channel,generation:this.generation,serial};},
      accept(token){return token.record===this.record&&token.revision===this.revision&&token.generation===this.generation&&this.requests.get(token.channel)===token.serial;},
      invalidate(){this.generation++;this.requests.clear();}
    };
  }
  function delta(a,b){return {samples:b[0]-a[0],seconds:Number.isFinite(a[1])&&Number.isFinite(b[1])?b[1]-a[1]:null};}
  function value(sample){return !sample||sample[2]===null?'Unknown':String(sample[2]);}
  function nearest(points,index){return points.reduce((best,p)=>!best||Math.abs(p[0]-index)<Math.abs(best[0]-index)?p:best,null);}
  function segments(points,gap=Infinity){const out=[];let part=[];for(const p of points){const last=part.at(-1);if(p[2]===null||(last&&p[0]-last[0]===1&&p[1]!==null&&last[1]!==null&&p[1]-last[1]>gap)){if(part.length)out.push(part);part=[];}if(p[2]!==null)part.push(p);}if(part.length)out.push(part);return out;}
  return {create,delta,value,nearest,segments};
})();
if(typeof module!=='undefined')module.exports=DRInspection;
