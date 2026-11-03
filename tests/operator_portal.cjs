'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
// Small DOM fixture: real parent/child moves, selectors, tab focus and events.
// This exercises the existing viewer nodes being moved, rather than cloned.
class Element{
  constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.attributes={};this.dataset={};this.handlers={};this.hidden=false;this.isConnected=true;this.className='';this.classList={add:name=>{this.className+=' '+name;}};}
  setAttribute(key,value){this.attributes[key]=String(value);if(key==='class')this.className=value;if(key.startsWith('data-'))this.dataset[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=String(value);}
  removeAttribute(key){delete this.attributes[key];}
  getAttribute(key){return this.attributes[key]??null;}
  append(...nodes){for(const node of nodes){node.remove();node.parentElement=this;this.children.push(node);}}
  remove(){if(this.parentElement)this.parentElement.children=this.parentElement.children.filter(node=>node!==this);this.parentElement=null;}
  insertBefore(node,before){node.remove();node.parentElement=this;this.children.splice(this.children.indexOf(before),0,node);}
  after(node){const parent=this.parentElement,index=parent.children.indexOf(this);node.remove();node.parentElement=parent;parent.children.splice(index+1,0,node);}
  matches(selector){return selector.split(',').some(raw=>{const value=raw.trim();if(value.startsWith('.'))return this.className.split(/\s+/).includes(value.slice(1));if(value.startsWith('[')){const m=/^\[([^=\]]+)(?:=["']?([^"'\]]+)["']?)?\]$/.exec(value);return !!m&&this.attributes[m[1]]!==undefined&&(m[2]===undefined||this.attributes[m[1]]===m[2]);}return this.tagName===value.toUpperCase();});}
  querySelectorAll(selector){const parts=selector.trim().split(/\s+/),last=parts.pop(),out=[];const visit=node=>{for(const child of node.children){if(child.matches(last)&&(!parts.length||child.closest(parts.join(' '))))out.push(child);visit(child);}};visit(this);return out;}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  closest(selector){let node=this;while(node){if(node.matches(selector))return node;node=node.parentElement;}return null;}
  addEventListener(type,fn){(this.handlers[type]??=[]).push(fn);}
  dispatch(type,event){for(const fn of this.handlers[type]||[])fn(event);}
  focus(){document.activeElement=this;}
  scrollIntoView(){this.scrolled=true;}
  set textContent(value){this.text=value;this.children=[];}
  get textContent(){return this.text||'';}
  set innerHTML(value){this.markup=value;this.children=[];const stack=[this];for(const token of value.matchAll(/<\/?[a-zA-Z][^>]*>/g)){const raw=token[0];if(raw.startsWith('</')){stack.pop();continue;}const tag=/^<([^\s/>]+)/.exec(raw)[1],node=new Element(tag);for(const attr of raw.slice(tag.length+1,-1).matchAll(/([^\s=]+)(?:="([^"]*)")?/g)){node.setAttribute(attr[1],attr[2]??'');if(attr[1]==='hidden')node.hidden=true;}stack.at(-1).append(node);if(!['input','br','hr','img','meta','link'].includes(tag))stack.push(node);}}
  get innerHTML(){return this.markup||'';}
}
const docRoot=new Element(),inspectionHost=new Element();inspectionHost.setAttribute('id','inspection-workspace');docRoot.append(inspectionHost);
const document={activeElement:null,createElement:tag=>new Element(tag),getElementById:id=>id==='inspection-workspace'?inspectionHost:null,querySelector:selector=>docRoot.querySelector(selector)};
const section=new Element();inspectionHost.append(section);
section.innerHTML='<h2>Old source heading</h2><p>Old source help</p><div class="inspection-toolbar"><label><select class="source-voltage"></select></label><button class="source-run"></button></div><details class="source-mappings"></details><div class="source-extra-inputs"><details class="source-line-inputs"></details></div><p class="source-job-status"></p><div class="source-report-tools"></div><div class="source-condition-tools"></div><div class="source-condition-summary"></div><div class="source-line-summary"></div><details class="source-technical"></details><details class="source-evidence"></details><section class="source-compare"><select class="source-compare-record"></select></section>';
const traces=new Element();traces.className='inspection-traces';inspectionHost.append(traces);
const originals={traces,run:section.querySelector('.source-run'),mapping:section.querySelector('.source-mappings'),comparison:section.querySelector('.source-compare'),evidence:section.querySelector('.source-evidence')};
const data={file:'raw.cfg',sample_count:1000,channels:[{kind:'analog'}],time_range_s:[0,1],nominal_frequency_hz:50};
const row={incident_id:'portal',number:2,bundle:{files:[{name:'raw.cfg',kind:'comtrade'},{name:'remote.cfg',kind:'comtrade'}]}};
let activated=0;const activeTasks=[];
const context=vm.createContext({document,DRInputGuidance:require('../src/dranalyser/application/static/input-guidance.js'),DRFeatureGuide:require('../src/dranalyser/application/static/feature-guide.js'),instrumentReviewEditor:()=>'<section class="instrument-review"><input data-actual-ratio></section>',bindInstrumentReview(){},DRIncidentReport:{mount(){return {activate(){activated++;}};}},setPortalTask:task=>activeTasks.push(task)});
vm.runInContext(fs.readFileSync('src/dranalyser/application/static/operator-workspace.js','utf8')+';globalThis.workspace=DROperatorWorkspace;',context);
const controller=new AbortController(),workspace=context.workspace.mount(section,{traces,row,data,signal:controller.signal});
assert.deepEqual(JSON.parse(JSON.stringify(context.workspace.tasks())),[{id:'waveforms',title:'Analyse'},{id:'compare',title:'Compare'},{id:'report',title:'Report'}]);
const root=section.querySelector('.operator-workspace'),input=root.querySelector('.operator-inputs'),technical=root.querySelector('.operator-source-details');
assert.ok(!input.open&&!technical.open,'engineering inputs and technical panels are closed on first use');
assert.equal(originals.traces.closest('[data-workspace-content]').dataset.workspaceContent,'waveforms');
assert.equal(originals.comparison.closest('[data-workspace-content]').dataset.workspaceContent,'compare');
assert.equal(originals.mapping.closest('.operator-inputs'),input);assert.equal(originals.evidence.closest('.operator-source-details'),technical);
assert.equal(originals.run.closest('[data-workspace-content]').dataset.workspaceContent,'waveforms','the primary analysis action remains outside collapsed inputs');
assert.equal(activated,0,'starting the waveform viewer never generates a report');
workspace.select('inputs');assert.equal(input.open,true);assert.equal(activeTasks.at(-1),'waveforms','legacy required-input links open the contextual Analyse inputs');
workspace.select('evidence');assert.equal(technical.open,true);assert.equal(activeTasks.at(-1),'waveforms');
workspace.select('compare');assert.equal(root.querySelector('[data-workspace-pane="compare"]').hidden,false);assert.equal(root.querySelector('[data-workspace-pane="waveforms"]').hidden,true);
const compareTab=root.querySelector('[data-workspace-tab="compare"]');
root.querySelector('[role=tablist]').dispatch('keydown',{target:compareTab,key:'ArrowRight',preventDefault(){}});
assert.equal(activeTasks.at(-1),'report');assert.equal(activated,1);assert.equal(document.activeElement.dataset.workspaceTab,'report');
assert.equal(root.querySelector('[data-workspace-tab="report"]').getAttribute('aria-selected'),'true');
assert.equal(root.querySelector('[data-workspace-tab="compare"]').tabIndex,-1);
console.log('Operator portal: three tasks, optional contextual inputs, intact viewer/comparison nodes, legacy links and keyboard tabs passed');
