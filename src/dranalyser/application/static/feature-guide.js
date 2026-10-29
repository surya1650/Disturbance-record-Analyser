'use strict';
const DRFeatureGuide=(()=>{
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const destinations=new Set(['waveforms','report','inputs','compare','study']);
  const definitions=[
    {id:'waveforms',title:'Waveforms & exact cursors',destination:'waveforms',
      what:'Inspect recorded analog values and digital states. Cursors show actual samples; missing observations stay unknown.',
      inputs:['A matching CFG/DAT pair, or a supported CFF recording.','Recoverable source samples.'],
      optional:['Line data, CT/VT ratios and terminal assignment are not needed to inspect raw observations.'],
      next:'Open waveforms'},
    {id:'rms-vectors',title:'RMS values & vectors',destination:'waveforms',
      what:'RMS describes the fitted fundamental magnitude. Vectors compare phase angles at a common supported model centre.',
      inputs:['Source analysis with suitable timing and complete four-cycle supports.','Correct voltage/current meanings and a supported angle reference for relative vectors.'],
      optional:['At 50 Hz four cycles span 80 ms. Short, changing or missing data can leave a value unavailable.','Moving a cursor does not create a fit or prove physical CT/VT wiring.'],
      next:'Inspect RMS & vectors'},
    {id:'conditions',title:'Pre-fault, fault & post-fault',destination:'report',
      what:'Compare supported typical RMS values before, during and after an interval you select.',
      inputs:['Apply source analysis.','Place A at fault start and B at post-fault start, with A before B; apply the A–B interval.','Each reported region needs complete supported fitted windows inside that region.'],
      optional:['Intervals are operator choices, not automatically authenticated physical fault boundaries.','The report can still explain raw observations and missing values when region RMS is unavailable.'],
      next:'Open simple report'},
    {id:'compare',title:'Compare recordings',destination:'compare',
      what:'See every analog channel in matching voltage/current rows, with explicit missing counterparts.',
      inputs:['Two recordings with recoverable analog observations in this incident.','Choose the second recording.'],
      optional:['Source start positions are for visual inspection; they do not establish a common event, physical ends or synchronized clocks.','Each channel retains its own units and vertical scale.'],
      next:'Compare recordings'},
    {id:'projection',title:'R–X & approximate distance',destination:'inputs',
      what:'Use supported phase-loop impedance and supplied line facts for a conditional model projection.',
      inputs:['Known voltage/current meanings and suitable scaled, supported source fits.','A supplied line model with length, positive-sequence X1 sections and provenance.','An explicit AB, BC or CA loop and an eligible selected source window.'],
      optional:['The source projection does not support ground loops without a separate compensation contract.','R–X uses the supported impedance points; missing line facts can still prevent distance calculation.','A conditional projection is not a verified fault location. Outside-line results remain explicit.'],
      next:'Review distance inputs'},
    {id:'study',title:'Operational incident study',destination:'study',
      what:'Assess an incident using confirmed line/end assignments, compatible records and the eligible calculation methods.',
      inputs:['Actual line/terminal evidence and verified channel meanings, scaling and CT polarity.','Suitable records assigned to their physical ends; two compatible end records for two-ended E5.','Reviewed digital meanings and asserted-state polarity for protection indication interpretation.'],
      optional:['E5 is unsynchronized: GPS/common clock quality is not a dependency.','E4 is an additional synchronized method and requires established clock quality at both ends.','A trip indication alone does not prove breaker opening or clearing time.'],
      next:'Open operational study'}
  ];
  function build(context={}){
    const c=context&&typeof context==='object'?context:{};
    const yes=key=>c[key]===true;
    const samples=yes('hasSamples'),analysis=yes('analysisReady'),fits=yes('hasSupportedFits');
    const states={
      waveforms:samples?['available','Source observations are available. Source scaling and timing limitations remain visible.']:['missing','No recoverable source samples are available. Check the matching data file and the decode reason.'],
      'rms-vectors':!samples?['missing','Open a recording with recoverable samples first.']:!analysis?['missing','Apply source analysis to evaluate supported RMS and angle windows.']:!fits?['limited','No supported fits were found. Exact source samples remain available; inspect the stated timing, support or fit reason.']:['available','Supported fits exist for some channel/windows. The current cursor or selected reference can still be unavailable.'],
      conditions:!analysis?['missing','Apply source analysis first; the report does not invent pre-fault or fault values.']:!yes('hasRegions')?['missing','Select and apply A–B. Until then there is no chosen pre-fault/fault/post-fault comparison.']:!fits?['limited','The selected interval is recorded, but region RMS needs supported windows wholly inside each region.']:['available','Applied regions can be reported. Each region/channel still needs its own wholly contained supported windows.'],
      compare:!yes('hasSecondRecord')?['missing','Add another recording to this incident to compare sources.']:!samples?['limited','A second recording exists, but this source has no recoverable samples. Inspect the decode reason.']:['available','Choose a second recording. Its recoverable channels determine which counterparts can be shown.'],
      study:yes('hasOperationalResult')?['available','An operational study result is stored. Read its method, exclusions and data-quality caveats.']:['missing','Confirm the line/end assignments and method-specific inputs in the operational study. Raw inspection and the simple report remain usable.']
    };
    const ground=typeof c.faultLoop==='string'&&/^[ABC]G$/i.test(c.faultLoop);
    const loop=yes('hasLoop')||typeof c.faultLoop==='string'&&/^(AB|BC|CA)$/i.test(c.faultLoop);
    const absent=[];
    if(!analysis)absent.push('applied source analysis');
    if(!fits)absent.push('supported voltage/current fits');
    if(!yes('hasLine'))absent.push('a supplied line model');
    if(!loop)absent.push('an explicit phase-phase loop');
    if(!yes('hasWindow'))absent.push('an eligible selected window');
    states.projection=ground?['limited','Ground-loop projection is unavailable here: a separate compensation contract is required. Choose AB, BC or CA only when that is the intended fault-loop assumption.']:absent.length?['missing','For approximate distance, provide '+absent.join(', ')+'.']:['limited','Inputs are selected; calculation eligibility still depends on valid line constants and the selected fit. Any distance remains an assumption-dependent projection.'];
    return definitions.map(feature=>({...feature,inputs:[...feature.inputs],optional:[...feature.optional],availability:states[feature.id][0],reason:states[feature.id][1]}));
  }
  function markup(contextOrRows={}){
    const rows=Array.isArray(contextOrRows)?contextOrRows:build(contextOrRows);
    const status={available:'Available',limited:'Limited · check conditions',missing:'Inputs needed'};
    const items=values=>'<ul>'+(Array.isArray(values)?values:[]).map(value=>'<li>'+esc(value)+'</li>').join('')+'</ul>';
    return '<div class="feature-guide-grid" role="list">'+rows.map(row=>`<article class="feature-guide-card" role="listitem" data-guide-feature="${esc(row.id)}"><div class="feature-guide-heading"><h4>${esc(row.title)}</h4><span class="feature-guide-status" data-availability="${esc(row.availability)}">${esc(status[row.availability]||'Review inputs')}</span></div><p>${esc(row.what)}</p><p class="feature-guide-reason">${esc(row.reason)}</p><details><summary>Required inputs & explanation</summary><h5>Needed for this feature</h5>${items(row.inputs)}<h5>Helpful explanation</h5>${items(row.optional)}</details><button type="button" data-go-feature="${destinations.has(row.destination)?row.destination:'inputs'}">${esc(row.next)}</button></article>`).join('')+'</div>';
  }
  return {build,markup};
})();
if(typeof module!=='undefined')module.exports=DRFeatureGuide;
