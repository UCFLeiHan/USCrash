/* Progressive exploration of the manuscript, using the retained analysis tables. */
(() => {
  const q = s => document.querySelector(s);
  const number = n => Number(n).toLocaleString('en-US');
  const safe = s => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  const enter = el => { if (!reduced()) el.animate([{opacity:0,transform:'translateY(9px)'},{opacity:1,transform:'translateY(0)'}],{duration:420,easing:'cubic-bezier(.2,.7,.2,1)'}); };
  const familyLabels = ['Identifiers & provenance','Time','Location','Severity & outcomes','Vehicles & road users','Collision & event','Environment','Roadway & behaviors'];
  const familyCopy = [
    'Trace each crash to its original state record, source file, and preparation version.',
    'Locate the crash in time while retaining the precision of the reported date and time.',
    'Describe the reported location and distinguish valid coordinates from unavailable positions.',
    'Interpret standardized injury severity alongside reported fatalities, injuries, and source codes.',
    'Describe the vehicles and road users involved, with counts and precision where supported.',
    'Describe how the collision occurred and the first harmful event, retaining source terminology.',
    'Record weather, lighting, and road surface conditions together with their original codes.',
    'Describe the road, speed limits, intersections, work zones, and reported behavioral factors.'
  ];
  const colors=['#e7e5e1','#deebfa','#ccebf4','#fae2d4','#d5efd7','#ffedb5','#efd9ed','#e8ecea'];
  let research, panels, annual, fields, cities, schemaArtwork;

  function cityComparison(){
    q('.spatial-heading > .tabs')?.remove();
    const first=cities[0],figure=q('.spatial-body figure');
    figure.id='city-comparison';
    figure.innerHTML=`<div class="comparison-toolbar"><div class="comparison-title" aria-live="polite"><h4 id="comparison-area">${first.name}, ${first.state}</h4><span id="city-position">1 / ${cities.length}</span></div><div class="compare-controls" role="group" aria-label="Map comparison mode"><button data-comparison="wipe" aria-pressed="true">Swipe comparison</button><button data-comparison="pair" aria-pressed="false">Side by side</button></div></div><div class="comparison-stage"><div class="compare-canvas" data-mode="wipe" style="--reveal:50%"><div class="compare-map compare-a"><img id="compare-a" src="assets/compare-${first.key}-uscrash.svg" alt="${first.name} USCrash spatial distribution"></div><div class="compare-map compare-b"><img id="compare-b" src="assets/compare-${first.key}-us-accidents.svg" alt="${first.name} US-Accidents spatial distribution"></div><div class="wipe-divider" role="slider" tabindex="0" aria-label="Compare USCrash and US-Accidents at the same location" aria-valuemin="0" aria-valuemax="100" aria-valuenow="50" aria-valuetext="50% USCrash visible"><span aria-hidden="true">↔</span></div></div><nav class="area-pagination" aria-label="Browse comparison areas"><button id="city-prev" aria-label="Previous area" title="Previous area"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 6-6 6 6 6"/></svg></button><button id="city-next" aria-label="Next area" title="Next area"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m10 6 6 6-6 6"/></svg></button></nav></div><div class="comparison-counts"><span>USCrash <strong id="compare-count-a">${number(first.counts[0])}</strong></span><span>US-Accidents <strong id="compare-count-b">${number(first.counts[1])}</strong></span></div><img class="map-scale" src="assets/map-scale.webp" alt="Shared logarithmic scale from 1 to 1,000 crashes per 250 m by 250 m cell"><figcaption><span id="comparison-source">${first.source}</span> · 2021 · 250 m × 250 m cells · Counts are plotted records.</figcaption>`;
    let request=0,selected=0,target=0;
    async function selectCity(index){
      index=(index+cities.length)%cities.length;target=index;const token=++request,c=cities[index];
      const images=['uscrash','us-accidents'].map(ds=>{const img=new Image();img.src=`assets/compare-${c.key}-${ds}.svg`;return img});
      try{await Promise.all(images.map(img=>img.decode()));}catch(e){console.error(e);return;}
      if(token!==request)return;selected=index;
      ['a','b'].forEach((key,i)=>{q('#compare-'+key).src=images[i].src;q('#compare-'+key).alt=`${c.name} ${i===0?'USCrash':'US-Accidents'} spatial distribution`;q('#compare-count-'+key).textContent=number(c.counts[i]);});
      q('#comparison-area').textContent=`${c.name}, ${c.state}`;q('#comparison-source').textContent=c.source;q('#city-position').textContent=`${index+1} / ${cities.length}`;
      if(!reduced())[q('#compare-a'),q('#compare-b')].forEach(img=>img.animate([{opacity:.4},{opacity:1}],{duration:250,easing:'ease-out'}));
    }
    q('#city-prev').onclick=()=>selectCity(target-1);q('#city-next').onclick=()=>selectCity(target+1);
    q('.area-pagination').addEventListener('keydown',e=>{if(e.key==='ArrowLeft'){e.preventDefault();q('#city-prev').click()}else if(e.key==='ArrowRight'){e.preventDefault();q('#city-next').click()}});
    const canvas=q('.compare-canvas');
    document.querySelectorAll('[data-comparison]').forEach(b=>b.onclick=()=>{
      canvas.dataset.mode=b.dataset.comparison;canvas.scrollLeft=0;
      document.querySelectorAll('[data-comparison]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
      q('.wipe-divider').tabIndex=b.dataset.comparison==='wipe'?0:-1;
    });
    const divider=q('.wipe-divider');let reveal=50,dragging=false;
    function setReveal(value){reveal=Math.max(0,Math.min(100,value));canvas.style.setProperty('--reveal',reveal+'%');canvas.style.setProperty('--reveal-number',reveal/100);divider.setAttribute('aria-valuenow',reveal);divider.setAttribute('aria-valuetext',reveal+'% USCrash visible');}
    divider.onkeydown=e=>{let value;if(e.key==='ArrowLeft')value=reveal-(e.shiftKey?10:1);else if(e.key==='ArrowRight')value=reveal+(e.shiftKey?10:1);else if(e.key==='Home')value=0;else if(e.key==='End')value=100;else return;e.preventDefault();setReveal(value)};
    const move=e=>{if(!dragging||canvas.dataset.mode!=='wipe')return;const r=q('.compare-a').getBoundingClientRect();setReveal(Math.round(100*(e.clientX-r.left)/r.width));};
    canvas.onpointerdown=e=>{if(canvas.dataset.mode!=='wipe')return;dragging=true;canvas.setPointerCapture(e.pointerId);move(e)};
    canvas.onpointermove=move;canvas.onpointerup=()=>dragging=false;canvas.onpointercancel=()=>dragging=false;
  }

  function methods() {
    const stages = panels.methods;
    const bounds = [[1.1,29.3],[35.2,29.2],[69.5,29.3]];
    const colors = ['#4b97d2','#4e9e35','#773775'];
    const names = ['Data sources and acquisition','Crash-level data preparation','MMUCC-guided semantic harmonization'];
    q('#workflow').innerHTML = `<img class="original-workflow-image" src="assets/paper-workflow.webp" width="2400" height="976" alt="The original USCrash framework: official source acquisition, crash-level preparation, and MMUCC-guided semantic harmonization. Select any of the three stages to read its explanation.">${stages.map((s,i)=>`<button class="workflow-hotspot" data-stage="${i}" aria-label="Explore stage ${i+1}: ${names[i]}" aria-expanded="false" aria-controls="workflow-detail" style="--left:${bounds[i][0]}%;--width:${bounds[i][1]}%;--stage-color:${colors[i]}"><span>${i+1}. ${['Sources','Preparation','Harmonization'][i]}</span></button>`).join('')}`;
    let active=-1;
    q('#workflow').addEventListener('click',e=>{
      const b=e.target.closest('[data-stage]');if(!b)return;
      const i=+b.dataset.stage;active=active===i?-1:i;
      document.querySelectorAll('[data-stage]').forEach(x=>x.setAttribute('aria-expanded',String(+x.dataset.stage===active)));
      const detail=q('#workflow-detail');detail.classList.toggle('is-open',active>=0);detail.inert=active<0;
      if(active<0)return;
      const s=stages[active];
      q('#workflow-content').innerHTML=`<div class="source-stage-copy"><span class="eyebrow">STAGE 0${active+1} · ${['DATA ACQUISITION','DATA PREPARATION','SEMANTIC HARMONIZATION'][active]}</span><h3>${safe(s.title)}</h3><div class="stage-prose">${s.paragraphs.map(t=>`<p>${safe(t)}</p>`).join('')}</div><p class="source-note">${safe(s.note)}</p><button class="text-control" id="workflow-close">Close stage details ↑</button></div>`;
      enter(q('#workflow-content'));
      q('#workflow-close').onclick=()=>{b.click();b.focus()};
      if(matchMedia('(max-width: 600px)').matches) requestAnimationFrame(()=>q('#workflow-detail').scrollIntoView({behavior:reduced()?'instant':'smooth',block:'start'}));
    });
  }

  function schema() {
    const families=[...new Set(research.families.map(f=>f.family))];
    // Original PowerPoint shapes exported as a vector, with matching native buttons.
    const orbit=q('#schema-orbit');orbit.classList.add('paper-schema');
    orbit.innerHTML='<img class="paper-schema-artwork" src="assets/paper-schema-core.svg" width="711" height="710" alt="USCrash Data, 77 columns, organized into eight attribute groups. Original manuscript diagram without the outer attribute layer.">'+families.map((f,i)=>{const r=schemaArtwork.nodes[i];return `<button class="paper-schema-hotspot" data-family="${i}" style="left:${r.x}%;top:${r.y}%;width:${r.width}%;height:${r.height}%" aria-label="${familyLabels[i]}, ${research.families.filter(x=>x.family===f).length} fields" aria-expanded="false" aria-controls="schema-detail"></button>`}).join('');
    function reset(){q('#schema-detail').innerHTML='<span class="eyebrow">EIGHT SCHEMA GROUPS</span><h3>Harmonized attributes and source information</h3><p>Select a schema group to inspect its fields.</p><p>Harmonized attributes sit alongside raw codes, labels, and provenance. Unsupported values remain unknown or unavailable.</p><a class="inline-reference figure-zoom" href="assets/paper-schema.png" data-figure-title="Figure 2. Original manuscript schema">View the manuscript diagram ↗</a>';}
    reset();let active=-1;
    q('#schema-orbit').addEventListener('click',e=>{
      const b=e.target.closest('[data-family]');if(!b)return;
      const i=+b.dataset.family;active=active===i?-1:i;
      document.querySelectorAll('[data-family]').forEach(x=>x.setAttribute('aria-expanded',String(+x.dataset.family===active)));
      if(active<0){reset();enter(q('#schema-detail'));return;}
      const list=research.families.filter(x=>x.family===families[i]).map(x=>fields.find(f=>f.field_name===x.canonical_field));
      q('#schema-detail').innerHTML=`<span class="eyebrow">${list.length} FIELDS</span><h3>${familyLabels[i]}</h3><p>${familyCopy[i]}</p><div class="schema-field-list">${list.map(f=>`<details class="schema-field"><summary><span>${safe(f.field_name)}</span><i>＋</i></summary><p>${safe(f.description)}</p><small>${safe(f.data_type)}</small></details>`).join('')}</div><button class="text-control" id="schema-reset">Close group ↑</button>`;
      enter(q('#schema-detail'));q('#schema-reset').onclick=()=>{b.click();b.focus()};
    });
  }

  function bars(container, rows, title, note, options={}) {
    const max=options.max||100;
    const noun=options.countNoun||'records';
    container.innerHTML=`<div class="plot-heading"><h3>${safe(title)}</h3><span>${options.unit||'Share of records (%)'}</span></div><div class="bar-chart">${rows.map((r,i)=>`<button class="bar-row" style="--bar-color:${r.color||'#398a8b'}" aria-label="${safe(r.label)}: ${r.percent.toFixed(2)} percent; ${number(r.count)} ${noun}" data-bar="${i}"><span class="bar-label">${safe(r.label)}</span><span class="bar-track"><span class="bar-fill" style="width:${Math.max(0,r.percent/max*100)}%"></span></span><b>${r.percent.toFixed(1)}%</b></button>`).join('')}</div><p class="plot-readout" aria-live="polite">Select a bar to view the count and percentage.</p><p class="source-note">${safe(note)}</p>`;
    container.querySelector('.bar-chart').insertAdjacentHTML('afterend',`<div class="horizontal-axis" aria-hidden="true"><span></span><div>${[0,25,50,75,100].map(v=>`<span>${v}</span>`).join('')}</div><span></span></div><div class="horizontal-axis-label">${options.unit||'Crashes (%)'}</div>`);
    const show=b=>{const r=rows[+b.dataset.bar];container.querySelector('.plot-readout').textContent=`${r.label}: ${number(r.count)} ${noun} (${r.percent.toFixed(2)}%).${r.denominator?' Denominator: '+number(r.denominator)+'.':''}`;container.querySelectorAll('.bar-row').forEach(x=>x.classList.toggle('is-active',x===b));};
    container.querySelectorAll('[data-bar]').forEach(b=>{b.onpointerenter=()=>show(b);b.onfocus=()=>show(b);b.onclick=()=>show(b)});
    if(!reduced())container.querySelectorAll('.bar-fill').forEach((b,i)=>b.animate([{transform:'scaleX(0)'},{transform:'scaleX(1)'}],{duration:550,delay:i*12,easing:'cubic-bezier(.2,.7,.2,1)'}));
  }

  let coverageMode='years',currentState='FL';
  function coverage(code=currentState){
    currentState=code;const host=q('#coverage-plot');if(!host||!research)return;
    document.querySelectorAll('[data-coverage]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.coverage===coverageMode)));
    if(coverageMode==='attributes'){
      const rows=research.availability.filter(x=>x.state===code).map(x=>({label:x.family.replace('behaviour','behaviors'),percent:100*x.availability_ratio,count:x.valid_field_record_cells,denominator:x.possible_field_record_cells}));
      if(!rows.length){host.innerHTML='<p>No harmonized files are included for this state.</p>';return;}
      bars(host,rows,`${code} · Attribute availability`,'Availability is the share of valid analytical field–record cells in each group. Provenance and raw-code fields are excluded where specified in the analysis; this is not the percentage of complete crash records.',{unit:'Valid analytical cells (%)',countNoun:'valid field–record cells'});
      host.querySelector('.plot-readout').textContent='Select a group to inspect valid field–record cells.';
    }else{
      const values=annual.filter(x=>x.state===code),max=Math.max(100000,Math.ceil(Math.max(...values.map(x=>+x.records),1)/100000)*100000);
      host.innerHTML=`<div class="plot-heading"><h3>${safe(code)} · Annual crash records</h3><span>2001–2026</span></div><div class="year-chart" role="group" aria-label="Annual crash counts">${Array.from({length:26},(_,i)=>{const year=i+2001,a=values.find(x=>+x.year===year),count=a?+a.records:0;return `<button class="year-column ${a?'included':''}" data-year="${year}" data-count="${a?count:''}" aria-label="${year}: ${a?number(count)+' records':'no annual file'}"><span class="year-space"><span style="height:${a?Math.max(1,count/max*100):0}%"></span></span><span class="year-label">${String(year).slice(2)}</span></button>`}).join('')}</div><p class="plot-readout" aria-live="polite">Select a year to view its crash count.</p><p class="source-note">Each bar represents one retained state–year file. Blank years have no retained file. Changes can reflect source coverage as well as crash frequency; 2026 is partial.</p>`;
      const chart=host.querySelector('.year-chart');chart.outerHTML=academicAxis(max,chart.outerHTML,'Year (2001–2026)','Crash records');
      host.querySelectorAll('[data-year]').forEach(b=>{const show=()=>{host.querySelector('.plot-readout').textContent=`${code}, ${b.dataset.year}: ${b.dataset.count?number(b.dataset.count)+' retained crash records.':'no retained annual file.'}`;};b.onfocus=show;b.onpointerenter=show;b.onclick=show;});
    }
    coverageMatrix();enter(host);
  }

  function coverageMatrix(){
    const disclosure=q('.coverage-years'),summary=disclosure.querySelector('summary');
    const years=q('#matrix').closest('.matrix-scroll');
    let attributes=q('#attribute-matrix');
    if(!attributes){attributes=document.createElement('div');attributes.id='attribute-matrix';attributes.className='matrix-scroll';years.after(attributes);}
    let readout=q('#attribute-matrix-readout');if(!readout){readout=document.createElement('p');readout.id='attribute-matrix-readout';readout.className='matrix-readout';readout.setAttribute('aria-live','polite');attributes.after(readout);}
    const isAttributes=coverageMode==='attributes';years.hidden=isAttributes;attributes.hidden=!isAttributes;readout.hidden=!isAttributes;
    summary.innerHTML=`View the state × ${isAttributes?'attribute availability':'year coverage'} matrix <span>+</span>`;
    const note=disclosure.querySelector('p.small');
    note.textContent=isAttributes?'Each cell shows the percentage of valid analytical field–record cells within a schema group for a state. Availability does not imply accuracy or completeness of every crash record. Select a cell to inspect its numerator and denominator and update the selected state.':'Filled cells indicate a state–year file. Color intensity represents annual crash counts. Source reporting scope varies; Oklahoma includes a K/A/B subset, and North Carolina 2016–2020 includes fatal and serious-injury crashes.';
    if(!isAttributes)return;
    const groups=[...new Set(research.availability.map(x=>x.family))],codes=[...new Set(research.availability.map(x=>x.state))].sort();
    const labels=['Identifiers & provenance','Time','Location','Severity & outcomes','Vehicles & road users','Collision & event','Environment','Roadway & behavioral factors'];
    attributes.innerHTML=`<table class="availability-matrix"><caption>State × attribute availability (%)</caption><thead><tr><th scope="col">State</th>${labels.map(x=>`<th scope="col">${safe(x)}</th>`).join('')}</tr></thead><tbody>${codes.map(code=>`<tr class="${code===currentState?'selected-state':''}"><th scope="row">${code}</th>${groups.map((group,i)=>{const r=research.availability.find(x=>x.state===code&&x.family===group);if(!r)return '<td>—</td>';const pct=100*r.availability_ratio;return `<td><button data-availability-state="${code}" data-availability-group="${i}" style="background:color-mix(in srgb,#398a8b ${Math.round(pct*.7)}%,white)" aria-label="${code}, ${safe(labels[i])}: ${pct.toFixed(1)} percent available; ${number(r.valid_field_record_cells)} valid of ${number(r.possible_field_record_cells)} analytical field–record cells">${pct.toFixed(1)}%</button></td>`}).join('')}</tr>`).join('')}</tbody></table>`;
    readout.textContent='Select a cell to view availability counts.';
    attributes.querySelectorAll('[data-availability-state]').forEach(b=>b.onclick=()=>{
      const code=b.dataset.availabilityState,group=groups[+b.dataset.availabilityGroup],r=research.availability.find(x=>x.state===code&&x.family===group);
      const select=q('#state-select');select.value=code;select.dispatchEvent(new Event('change',{bubbles:true}));
      q('#attribute-matrix-readout').textContent=`${code} · ${labels[+b.dataset.availabilityGroup]}: ${(100*r.availability_ratio).toFixed(2)}% (${number(r.valid_field_record_cells)} valid analytical field–record cells / ${number(r.possible_field_record_cells)} possible).`;
      q(`#attribute-matrix [data-availability-state="${code}"][data-availability-group="${b.dataset.availabilityGroup}"]`)?.focus({preventScroll:true});
    });
  }

  // Palette values from the manuscript plotting scripts, keyed by category.
  const environmentColors={
    weather:{Clear:'#638FA8',Cloudy:'#83A6BA',Rain:'#A2BDCC',Snow:'#BDD0DA',Other:'#D3E0E7'},
    light_condition:{Daylight:'#9C83AF','Dark, lighted':'#AF9BC0','Dark, unlighted':'#C0B1CD',Dusk:'#D0C6DA',Other:'#E0D9E6'},
    road_surface_condition:{Dry:'#77A08E',Wet:'#94B4A6','Ice / frost':'#ADC6BB',Snow:'#C2D5CC',Other:'#D8E4DD'}
  };
  // Shared manuscript-style axes, with numeric ticks on a zero baseline.
  function academicAxis(max, chart, label, unit='Crashes (%)'){
    return `<div class="academic-chart"><span class="axis-title">${unit}</span><div class="y-ticks" aria-hidden="true">${Array.from({length:6},(_,i)=>`<span style="top:${i*20}%">${i===5?'0':max>=1000?+(max*(5-i)/5000).toFixed(1)+'k':+(max*(5-i)/5).toFixed(1)}</span>`).join('')}</div><div class="chart-grid" aria-hidden="true"></div>${chart}<div class="x-axis-title">${label}</div></div>`;
  }
  function hourlyComparison(plot,rows,note){
    const max=Math.ceil(Math.max(...rows.map(r=>r.percent))/5)*5;
    plot.innerHTML=`<div class="plot-heading"><h3>Hourly distribution</h3></div><div class="hour-legend"><span><i style="background:#7563A7"></i>Weekdays</span><span><i style="background:#BEB0D8"></i>Weekends</span></div><div class="hour-chart" role="group" aria-label="Weekday and weekend hourly distributions on the same scale">${Array.from({length:24},(_,hour)=>`<div class="hour-bin"><div class="hour-bars">${['weekday','weekend'].map(group=>{const r=rows.find(x=>+x.bin===hour&&x.group===group);return `<button data-hour="${hour}" data-group="${group}" style="height:${r.percent/max*100}%;--hour-color:${group==='weekday'?'#7563A7':'#BEB0D8'}" aria-label="${r.label}, ${group==='weekday'?'weekdays':'weekends'}: ${r.percent.toFixed(2)} percent; ${number(r.count)} records"></button>`}).join('')}</div><span>${hour}</span></div>`).join('')}</div><p class="plot-readout" aria-live="polite">Select an hour to compare weekday and weekend records.</p><p class="source-note">${note} Weekday and weekend shares each sum to 100% within their own group.</p>`;
    const chart=plot.querySelector('.hour-chart');chart.outerHTML=academicAxis(max,chart.outerHTML,'Hour of day');
    plot.querySelectorAll('[data-hour]').forEach(b=>{const show=()=>{const records=rows.filter(x=>+x.bin===+b.dataset.hour);plot.querySelector('.plot-readout').textContent=String(b.dataset.hour).padStart(2,'0')+':00 — '+records.map(r=>`${r.group==='weekday'?'Weekdays':'Weekends'}: ${number(r.count)} records (${r.percent.toFixed(2)}%; n = ${number(r.denominator)})`).join('. ')+'.';};b.onpointerenter=show;b.onfocus=show;b.onclick=show;});
  }

  const modes={temporal:[['hour','Hour of day'],['weekday','Day of week'],['month','Month']],severity:[],collision:[],environment:[['weather','Weather'],['light_condition','Lighting'],['road_surface_condition','Road surface']],roadway:[['functional_class','Road class'],['posted_speed_limit','Speed limit'],['speeding_involved','Speeding'],['alcohol_involved','Alcohol'],['drug_involved','Drugs'],['hit_and_run','Hit-and-run']]};
  let statsTopic='temporal',statsMode='hour';
  function statistics(resetMode=false){
    if(resetMode)statsMode=modes[statsTopic][0]?.[0]||statsTopic;
    document.querySelectorAll('[data-stat]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.stat===statsTopic)));
    const p=panels.statistics.find(x=>x.key===statsTopic);
    q('#stats-narrative').innerHTML=`<span class="eyebrow">DESCRIPTIVE ANALYSIS</span><h3>${safe(p.title)}</h3>${p.paragraphs.map(t=>`<p>${safe(t)}</p>`).join('')}<a class="inline-reference figure-zoom" href="${p.full}" data-figure-title="${safe(p.title)}: manuscript panel">View corresponding manuscript panel ↗</a>`;
    const controls=q('#stats-controls');controls.innerHTML=modes[statsTopic].map(([key,label])=>`<button data-mode="${key}" aria-pressed="${key===statsMode}">${label}</button>`).join('');
    controls.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{statsMode=b.dataset.mode;statistics()});
    let rows=[],title='',note='';
    if(statsTopic==='temporal'){
      if(statsMode==='hour'){
        rows=research.hour.map(x=>({...x,label:String(x.bin).padStart(2,'0')+':00'}));title='Hourly distribution';
        note='Shares within records with retained hour and day-of-week information. This hourly analysis excludes DC, following the manuscript analysis. Select an hour to inspect its count.';
      }else{rows=research.temporal.filter(x=>x.metric===statsMode).map(x=>({...x,label:statsMode==='month'?['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+x.bin-1]:['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][+x.bin]}));title=statsMode==='month'?'Monthly distribution':'Day-of-week distribution';note='Shares use records with retained information for the selected time dimension. Denominators differ by dimension.';}
    }else if(statsTopic==='severity'){
      rows=research.severity.map(x=>({...x,label:x.label,color:'#BE984A'}));title='Crash severity (KABCO)';note='Denominator: all 65,756,924 retained crashes. Unknown and unavailable values are shown explicitly.';
    }else if(statsTopic==='collision'){
      rows=research.collision.map((x,i)=>({...x,label:x.category,denominator:65756924,color:['#A8D2E2','#ECC1A8','#DCA897','#8DB7A4','#527F99','#A5B4C4','#C5B49A','#BEB5AA','#D4D4D4'][i]}));title='Manner of collision';note='Denominator: all retained crashes. “Not collision with MV in transport” also includes non-collision events. Unknown values remain visible.';
    }else if(statsTopic==='environment'){
      rows=research.environment.filter(x=>x.field===statsMode).map(x=>({...x,label:x.category,color:environmentColors[statsMode][x.category]}));title=modes.environment.find(x=>x[0]===statsMode)[1];note='Shares among 52,057,082 records with known weather, lighting, and road-surface conditions, matching the joint environmental analysis. They are not shares of all crashes.';
    }else{
      let source=research.roadway.filter(x=>x.field===statsMode);const known=['functional_class','posted_speed_limit'].includes(statsMode);
      if(known)source=source.filter(x=>!x.category.includes('Unknown')&&!x.category.includes('Source-specific'));
      const denominator=known?source.reduce((n,r)=>n+r.count,0):65756924;
      rows=source.map(x=>({...x,label:x.category,denominator,percent:100*x.count/denominator,color:statsMode==='functional_class'?'#638BA6':statsMode==='posted_speed_limit'?'#9884AE':({Yes:'#C47E72',No:'#A8C5CC'}[x.category]||'#DDDDDD')}));title=modes.roadway.find(x=>x[0]===statsMode)[1];note=known?`Shares among ${number(denominator)} records with a classified value. Unknown, unavailable, and unclassified values are excluded from this distribution.`:'Shares of all retained records. “No” and “Unknown / unavailable” are distinct categories.';
    }
    const plot=q('#stats-plot');
    if(statsTopic==='temporal'&&statsMode==='hour'){
      hourlyComparison(plot,rows,note);
    }else if(statsTopic==='temporal'){
      const max=Math.ceil(Math.max(...rows.map(x=>x.percent))/5)*5;
      plot.innerHTML=`<div class="plot-heading"><h3>${title}</h3></div><div class="time-chart" style="--columns:${rows.length}">${rows.map((r,i)=>`<button class="time-column" data-time="${i}" aria-label="${r.label}: ${r.percent.toFixed(2)} percent"><span class="time-space"><span style="height:${r.percent/max*100}%;background:${statsMode==='month'?'#438D9B':'#E38C78'}"></span></span><span>${r.label}</span></button>`).join('')}</div><p class="plot-readout" aria-live="polite">Select a bar to view the count and percentage.</p><p class="source-note">${note}</p>`;
      const chart=plot.querySelector('.time-chart');chart.outerHTML=academicAxis(max,chart.outerHTML,statsMode==='month'?'Month':'Day of week');
      plot.querySelectorAll('[data-time]').forEach(b=>{const show=()=>{const r=rows[+b.dataset.time];plot.querySelector('.plot-readout').textContent=`${r.label}: ${number(r.count)} records (${r.percent.toFixed(2)}%). Denominator: ${number(r.denominator)}.`;};b.onpointerenter=show;b.onfocus=show;b.onclick=show;});
    }else bars(plot,rows,title,note);
    enter(plot);enter(q('#stats-narrative'));
  }

  async function initialize(){
    try{
      [research,panels,annual,fields,cities,schemaArtwork]=await Promise.all(['research','paper-panels','annual','fields','cities','schema-artwork'].map(n=>fetch(`data/${n}.json`).then(r=>{if(!r.ok)throw Error(n);return r.json()})));
      methods();schema();coverage();statistics();cityComparison();
      document.querySelectorAll('[data-coverage]').forEach(b=>b.onclick=()=>{coverageMode=b.dataset.coverage;coverage()});
      document.querySelectorAll('[data-stat]').forEach(b=>b.onclick=()=>{statsTopic=b.dataset.stat;statistics(true)});
      document.addEventListener('statechange',e=>coverage(e.detail));
      document.querySelectorAll('[role=tablist]').forEach(list=>list.addEventListener('keydown',e=>{
        const items=[...list.querySelectorAll('[role=tab]')];const i=items.indexOf(document.activeElement);if(i<0)return;
        let next;if(e.key==='ArrowRight')next=(i+1)%items.length;else if(e.key==='ArrowLeft')next=(i-1+items.length)%items.length;else if(e.key==='Home')next=0;else if(e.key==='End')next=items.length-1;else return;e.preventDefault();items[next].focus();items[next].click();
      }));
    }catch(e){console.error(e);document.querySelectorAll('.loading-note').forEach(x=>x.textContent='This explorer could not load. The manuscript PDFs remain available below.');}
  }
  function navigation(){
    const links=[...document.querySelectorAll('header nav a')];
    const sections=[...document.querySelectorAll('main > section')];
    const groups={overview:'#abstract',abstract:'#abstract',harmonization:'#harmonization',schema:'#harmonization',coverage:'#coverage',statistics:'#coverage',validation:'#validation',access:'#access',citation:'#access'};
    let scheduled=false;
    const update=()=>{scheduled=false;const line=document.querySelector('header').getBoundingClientRect().bottom+80;let current='#abstract';for(const section of sections){if(section.getBoundingClientRect().top<=line)current=groups[section.id]||current;}links.forEach(link=>{if(link.getAttribute('href')===current)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');});};
    const schedule=()=>{if(!scheduled){scheduled=true;requestAnimationFrame(update)}};
    addEventListener('scroll',schedule,{passive:true});addEventListener('resize',schedule);addEventListener('hashchange',schedule);new ResizeObserver(schedule).observe(document.querySelector('main'));update();
  }
  navigation();
  initialize();
})();
