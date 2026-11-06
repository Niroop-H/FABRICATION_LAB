const $ = (id) => document.getElementById(id);
let latest = null;
fetch('/api/health').then(r => { if (!r.ok) throw Error(); return r.json(); }).then(() => $('health').textContent = '● Engine available').catch(() => $('health').textContent = 'Engine unavailable');
$('recipe').addEventListener('submit', async (event) => {
  event.preventDefault();
  $('run').disabled = true;
  $('download').disabled = true;
  latest = null;
  $('status').textContent = 'Calculating oxide growth…';
  for (const id of ['thickness', 'uncertainty', 'elapsed']) $(id).textContent = '—';
  $('chart').replaceChildren();
  try {
    const inputs = Object.fromEntries(new FormData(event.target));
    for (const key of ['temperature_c', 'duration_s', 'initial_thickness_nm']) inputs[key] = Number(inputs[key]);
    const response = await fetch('/api/simulate/oxidation', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(inputs), signal:AbortSignal.timeout(30000)});
    const result = await response.json();
    if (!response.ok) throw Error(result.error || 'Simulation failed.');
    latest = {inputs, ...result};
    $('thickness').textContent = result.final_thickness_nm.toFixed(2);
    $('uncertainty').textContent = '±' + result.uncertainty_nm.toFixed(2);
    $('elapsed').textContent = (inputs.duration_s / 60).toFixed(1);
    const svg = $('chart'), ns = 'http://www.w3.org/2000/svg';
    const add = (tag, attrs, text) => {const el = document.createElementNS(ns, tag); for (const [k,v] of Object.entries(attrs)) el.setAttribute(k,v); if(text !== undefined) el.textContent = text; svg.append(el);};
    const max = Math.max(result.final_thickness_nm * 1.15, 1);
    for(let i=0;i<=4;i++) {const y = 205-i*46.25; add('path',{d:`M48 ${y}H620`,stroke:'#283647'}); add('text',{x:2,y:y+4,fill:'#8798ad','font-size':10},(max*i/4).toFixed(1));}
    const points = [{time_s:0,oxide_thickness_nm:inputs.initial_thickness_nm},...result.profile];
    add('polyline',{points:points.map(p=>`${48+p.time_s/inputs.duration_s*572},${205-p.oxide_thickness_nm/max*185}`).join(' '),fill:'none',stroke:'#6ce4c9','stroke-width':3});
    add('text',{x:48,y:230,fill:'#8798ad','font-size':10},'0');
    add('text',{x:620,y:230,fill:'#8798ad','font-size':10,'text-anchor':'end'},inputs.duration_s);
    svg.setAttribute('aria-label',`Oxide grows from ${inputs.initial_thickness_nm} to ${result.final_thickness_nm.toFixed(2)} nm over ${inputs.duration_s} seconds.`);
    $('status').textContent = 'Complete. Educational estimate; see model limitations.';
    $('download').disabled = false;
  } catch(error) { $('status').textContent = error.name === 'TimeoutError' ? 'Request timed out. Please retry.' : error.message; }
  finally { $('run').disabled = false; }
});
$('download').addEventListener('click', () => {
  if (!latest) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(latest,null,2)], {type:'application/json'}));
  const link = document.createElement('a'); link.href = url; link.download = 'oxidation-result.json'; link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
});
