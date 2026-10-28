'use strict';
const DRTransport=(()=>{
  async function mapLimit(items,limit,fn,signal){
    if(!Number.isInteger(limit)||limit<1||limit>8)throw new Error('Invalid request concurrency.');
    const results=new Array(items.length);let index=0,failed=false;
    async function worker(){while(index<items.length&&!failed){if(signal?.aborted)throw new DOMException('Request aborted','AbortError');const i=index++;try{results[i]=await fn(items[i],i);}catch(error){failed=true;throw error;}}}
    await Promise.all(Array.from({length:Math.min(limit,items.length)},worker));return results;
  }
  return {mapLimit};
})();
if(typeof module!=='undefined')module.exports=DRTransport;
