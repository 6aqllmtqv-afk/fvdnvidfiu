<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BestChange Data Monitor</title>
<style>
:root{font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#f5f7fb;color:#18202a}
*{box-sizing:border-box}body{margin:0}.wrap{max-width:1200px;margin:0 auto;padding:28px 18px 50px}
h1{font-size:28px;margin:0 0 8px}.sub{color:#667085;margin-bottom:24px}.panel{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:18px;box-shadow:0 3px 18px rgba(16,24,40,.05)}
.controls{display:grid;grid-template-columns:1fr 1fr auto;gap:12px;align-items:end}.field label{display:block;font-size:12px;color:#667085;margin:0 0 7px}
.combo{position:relative}.combo-btn{width:100%;height:44px;border:1px solid #d0d5dd;border-radius:9px;padding:0 12px;font-size:15px;background:#fff;text-align:left;cursor:pointer;display:flex;align-items:center;justify-content:space-between}.combo-btn .muted{color:#98a2b3}.combo-menu{display:none;position:absolute;z-index:50;left:0;right:0;top:50px;background:#fff;border:1px solid #d0d5dd;border-radius:10px;box-shadow:0 12px 32px rgba(16,24,40,.15);overflow:hidden}.combo.open .combo-menu{display:block}.combo-search{padding:10px;border-bottom:1px solid #eaecf0}.combo-search input{width:100%;height:38px;border:1px solid #d0d5dd;border-radius:8px;padding:0 10px;font-size:14px}.combo-list{max-height:320px;overflow:auto}.combo-option{padding:10px 12px;cursor:pointer;font-size:14px;display:flex;justify-content:space-between;gap:8px}.combo-option:hover{background:#f2f4f7}.combo-option.active{background:#f9fafb}.combo-option small{color:#98a2b3}.empty-options{padding:18px;color:#667085;font-size:13px}.btn{height:44px;border:0;border-radius:9px;padding:0 20px;font-weight:700;background:#111827;color:white;cursor:pointer}.btn:disabled{opacity:.5;cursor:wait}
.status{margin-top:14px;color:#667085;font-size:13px}.error{color:#b42318}.meta{display:flex;gap:20px;flex-wrap:wrap;margin:22px 0 12px;font-size:13px;color:#667085}.table-wrap{overflow:auto}.table{width:100%;border-collapse:collapse;min-width:920px}.table th,.table td{padding:14px 12px;border-bottom:1px solid #eaecf0;text-align:left}.table th{font-size:12px;color:#667085;font-weight:600;background:#f9fafb}.table td{font-size:14px}.rate{font-weight:750}.reserve{white-space:nowrap}.link{color:#175cd3;text-decoration:none}.empty{padding:34px;text-align:center;color:#667085}.search{width:100%;height:40px;border:1px solid #d0d5dd;border-radius:8px;padding:0 11px;margin-top:12px}.small{font-size:12px;color:#98a2b3}.badge{display:inline-flex;padding:4px 8px;border-radius:999px;background:#ecfdf3;color:#027a48;font-size:11px;font-weight:700}
@media(max-width:760px){.controls{grid-template-columns:1fr}.btn{width:100%}.combo-list{max-height:280px}}
</style>
</head>
<body><div class="wrap">
<h1>Exchange monitor</h1><div class="sub">Выбери направление — ниже появятся все доступные предложения BestChange по этой паре.</div>
<div class="panel">
<div class="controls">
<div class="field"><label>Отдаю</label><div class="combo" id="fromCombo"><button class="combo-btn" type="button"><span class="label muted">Загрузка…</span><span>⌄</span></button><div class="combo-menu"><div class="combo-search"><input type="text" placeholder="Поиск валюты…"></div><div class="combo-list"></div></div></div></div>
<div class="field"><label>Получаю</label><div class="combo" id="toCombo"><button class="combo-btn" type="button"><span class="label muted">Загрузка…</span><span>⌄</span></button><div class="combo-menu"><div class="combo-search"><input type="text" placeholder="Поиск валюты…"></div><div class="combo-list"></div></div></div></div>
<button class="btn" id="load">Показать обменники</button>
</div>
<input class="search" id="search" placeholder="Фильтр по названию обменника…">
<div class="status" id="status">Загрузка списка валют…</div>
</div>
<div class="meta" id="meta"></div>
<div class="panel table-wrap"><div id="table"><div class="empty">Выбери валюты и нажми «Показать обменники».</div></div></div>
</div>
<script>
const $=s=>document.querySelector(s); let currencies=[], changers=new Map(), lastRates=[]; let selected={from:null,to:null};
const load=$('#load'),status=$('#status'),table=$('#table'),meta=$('#meta'),search=$('#search');
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function fmt(v){if(v===null||v===undefined||v==='')return '—'; const n=Number(v); return Number.isFinite(n)?n.toLocaleString('ru-RU',{maximumFractionDigits:12}):esc(v)}
function nameOf(r){return r?.name || r?.title || r?.code || ('#'+r?.id)}
function extractItems(j, keys){
 if(Array.isArray(j)) return j;
 if(!j || typeof j!=='object') return [];
 for(const k of keys){
   const v=j[k];
   if(Array.isArray(v)) return v;
   if(v && typeof v==='object'){ const n=extractItems(v,keys); if(n.length) return n; }
 }
 for(const v of Object.values(j)){ const n=extractItems(v,keys); if(n.length) return n; }
 return [];
}
async function getJson(url){const r=await fetch(url,{cache:'no-store'});let j=null;try{j=await r.json()}catch(e){throw Error('Сервер вернул некорректный JSON')};if(!r.ok)throw Error(j.error||`HTTP ${r.status}`);return j}
function makeCombo(root,key){
 const btn=root.querySelector('.combo-btn'), label=root.querySelector('.label'), input=root.querySelector('.combo-search input'), list=root.querySelector('.combo-list');
 function render(filter=''){
   const q=filter.trim().toLowerCase(); const arr=currencies.filter(x=>!q || nameOf(x).toLowerCase().includes(q) || String(x.code||'').toLowerCase().includes(q));
   list.innerHTML=arr.length?arr.map(x=>`<div class="combo-option ${selected[key]===x.id?'active':''}" data-id="${x.id}"><span>${esc(nameOf(x))}</span><small>${esc(x.code||'')}</small></div>`).join(''):`<div class="empty-options">Ничего не найдено</div>`;
   list.querySelectorAll('.combo-option').forEach(el=>el.onclick=()=>{selected[key]=Number(el.dataset.id); const x=currencies.find(c=>c.id===selected[key]); label.textContent=nameOf(x); label.classList.remove('muted'); root.classList.remove('open'); render();});
 }
 btn.onclick=()=>{document.querySelectorAll('.combo.open').forEach(x=>x!==root&&x.classList.remove('open')); root.classList.toggle('open'); if(root.classList.contains('open')){input.value='';render();input.focus()}};
 input.oninput=()=>render(input.value);
 root._render=render; root._setLabel=()=>{const x=currencies.find(c=>c.id===selected[key]);if(x){label.textContent=nameOf(x);label.classList.remove('muted')}};
}
const fromCombo=$('#fromCombo'),toCombo=$('#toCombo'); makeCombo(fromCombo,'from'); makeCombo(toCombo,'to');
document.addEventListener('click',e=>{if(!e.target.closest('.combo'))document.querySelectorAll('.combo.open').forEach(x=>x.classList.remove('open'))});
function render(){const q=search.value.trim().toLowerCase();let rows=lastRates.filter(r=>{const c=changers.get(String(r.changerId));return !q || (c?.name||'').toLowerCase().includes(q)}); if(!rows.length){table.innerHTML='<div class="empty">По выбранному направлению предложений не найдено.</div>';return} rows.sort((a,b)=>(Number(b.rankRate??b.rate)||0)-(Number(a.rankRate??a.rate)||0)); table.innerHTML=`<table class="table"><thead><tr><th>#</th><th>Обменник</th><th>Курс</th><th>Отдам</th><th>Получим</th><th>Резерв</th><th>Мин.</th><th>Макс.</th><th>Метки</th><th></th></tr></thead><tbody>${rows.map((r,i)=>{const c=changers.get(String(r.changerId))||{};return `<tr><td>${i+1}</td><td><strong>${esc(c.name||('ID '+r.changerId))}</strong></td><td class="rate">${fmt(r.rate)}</td><td>${fmt(r.in)}</td><td>${fmt(r.out)}</td><td class="reserve">${fmt(r.reserve)}</td><td>${fmt(r.min)}</td><td>${fmt(r.max)}</td><td>${Array.isArray(r.marks)?r.marks.map(m=>`<span class="small">${esc(m)}</span>`).join(', '):'—'}</td><td>${c.url?`<a class="link" href="${esc(c.url)}" target="_blank" rel="noopener">Перейти</a>`:'<span class="small">—</span>'}</td></tr>`}).join('')}</tbody></table>`}
async function init(){try{
 const [cj,chj]=await Promise.all([getJson('/api/currencies'),getJson('/api/changers')]);
 currencies=extractItems(cj,['items','currencies','data','results']).map(x=>({id:Number(x.id??x.currencyId),name:x.name??x.title??x.code,code:String(x.code??'')})).filter(x=>Number.isFinite(x.id)&&x.name).sort((a,b)=>a.name.localeCompare(b.name,'ru'));
 extractItems(chj,['items','changers','data','results']).forEach(x=>changers.set(String(Number(x.id??x.changerId)),{id:Number(x.id??x.changerId),name:x.name??x.title??String(x.id),url:x.url??x.site??x.website??`https://www.bestchange.com/click.php?id=${Number(x.id??x.changerId)}`}));
 if(currencies.length<2) throw Error('BestChange вернул меньше двух валют.');
 selected.from=currencies.find(x=>x.code==='BTC')?.id ?? currencies[0].id; selected.to=currencies.find(x=>x.code==='USDTTRC20')?.id ?? currencies[1].id;
 fromCombo._setLabel(); toCombo._setLabel(); fromCombo._render(); toCombo._render();
 status.textContent=`Загружено валют: ${currencies.length}. Обменников: ${changers.size}.`;
 }catch(e){status.textContent=e.message;status.className='status error';load.disabled=true}}
load.onclick=async()=>{load.disabled=true;status.className='status';status.textContent='Получаю актуальные предложения…';meta.innerHTML='';try{if(selected.from==null||selected.to==null)throw Error('Выбери обе валюты.'); if(selected.from===selected.to)throw Error('Выбери разные валюты.');const j=await getJson(`/api/rates?from=${selected.from}&to=${selected.to}`);lastRates=Array.isArray(j.rates)?j.rates:[];const f=currencies.find(x=>x.id===selected.from),t=currencies.find(x=>x.id===selected.to);meta.innerHTML=`<span><b>${esc(nameOf(f))}</b> → <b>${esc(nameOf(t))}</b></span><span><span class="badge">${lastRates.length} предложений</span></span><span>Источник: ${esc(j.source||j.host||'BestChange')}</span>`;render();status.textContent=`Обновлено: ${new Date().toLocaleTimeString('ru-RU')}`}catch(e){status.textContent=e.message;status.className='status error';table.innerHTML='<div class="empty">Не удалось получить курсы.</div>'}finally{load.disabled=false}};
search.oninput=render; init();
</script></body></html>
