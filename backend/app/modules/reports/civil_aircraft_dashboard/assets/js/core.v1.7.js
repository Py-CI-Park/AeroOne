
(function(){
'use strict';
const DATA=window.CIVIL_AIRCRAFT_DATA;if(!DATA)throw new Error('CIVIL_AIRCRAFT_DATA is required');
const aircraft=DATA.aircraft,sources=DATA.sources,localPdfArchive=DATA.localPdfArchive||[],aircraftMap=new Map(aircraft.map(a=>[a.id,a])),sourceMap=new Map(sources.map(s=>[s.id,s]));
const compareColors=['#2563eb','#dc2626','#0f766e','#7c3aed','#ea580c','#0284c7'];
const comparePastels=['#bfdbfe','#fecaca','#99f6e4','#ddd6fe','#fed7aa','#bae6fd'];
const markerShapes=['circle','square','diamond','triangle','hexagon','cross'];
const fieldLabels={typicalSeats:'전형 좌석',maxSeats:'최대 좌석',rangeNm:'항속거리',mtowT:'MTOW',lengthM:'길이',spanM:'날개폭',heightM:'높이',engine:'엔진',maxPayloadT:'최대 페이로드',cargoM3:'화물용적',status:'프로그램 상태'};
const metricDefs={
 mtowT:{label:'MTOW',unit:'t',digits:1,get:a=>a.mtowT},
 rangeNm:{label:'항속거리',unit:'nm',digits:0,get:a=>a.rangeNm},
 typicalSeatsMid:{label:'전형 좌석',unit:'석',digits:0,get:a=>a.role==='여객'?a.typicalSeatsMid:null},
 maxPayloadT:{label:'최대 페이로드',unit:'t',digits:1,get:a=>a.maxPayloadT},
 lengthM:{label:'길이',unit:'m',digits:2,get:a=>a.lengthM},
 spanM:{label:'날개폭',unit:'m',digits:2,get:a=>a.spanM},
 heightM:{label:'높이',unit:'m',digits:2,get:a=>a.heightM},
 sizeIndexA320neo100:{label:'외형 크기지수',unit:'A320=100',digits:1,get:a=>a.sizeIndexA320neo100}
};
function esc(v){return String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
function n(v,d=1){return Number.isFinite(v)?Number(v.toFixed(d)):0;}
function num(v,d=1){if(v===null||v===undefined||!Number.isFinite(Number(v)))return '—';return Number(v).toLocaleString('ko-KR',{maximumFractionDigits:d,minimumFractionDigits:0});}
function seats(a){if(a.role!=='여객')return '—';if(a.typicalSeatsMin==null&&a.typicalSeatsMax==null)return '—';return a.typicalSeatsMin===a.typicalSeatsMax?`${num(a.typicalSeatsMin,0)}석`:`${num(a.typicalSeatsMin,0)}–${num(a.typicalSeatsMax,0)}석`;}
function payload(a){return a.maxPayloadT==null?'—':`${num(a.maxPayloadT,1)} t`;}
function value(v,unit='',d=1){return v==null?'—':`${num(v,d)}${unit?' '+unit:''}`;}
function normalize(s){return String(s||'').toLowerCase().normalize('NFKD').replace(/[\s_./()\-–—]+/g,'').replace(/[^a-z0-9가-힣]/g,'');}
function searchText(a){return normalize([a.model,a.manufacturer,a.family,a.category,a.role,a.engine,a.notes,...(a.aliases||[])].join(' '));}

function highlight(text,query){
 const raw=String(text??''),q=String(query??'').trim();if(!q)return esc(raw);
 const terms=q.split(/\s+/).filter(Boolean).sort((a,b)=>b.length-a.length);
 if(!terms.length)return esc(raw);
 const escaped=terms.map(x=>x.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
 try{const re=new RegExp('('+escaped.join('|')+')','ig');return raw.split(re).map((part,i)=>i%2?`<mark>${esc(part)}</mark>`:esc(part)).join('')}catch{return esc(raw)}
}

function matches(a,q){const z=normalize(q);return !z||searchText(a).includes(z);}
function filterAircraft(list,o={}){return list.filter(a=>matches(a,o.q)&&(!o.category||o.category==='all'||a.category===o.category)&&(!o.role||o.role==='all'||a.role===o.role)&&(!o.manufacturer||o.manufacturer==='all'||a.manufacturer===o.manufacturer)&&(!o.status||o.status==='all'||a.statusCode===o.status)&&(!o.verifiedOnly||!['B','C'].includes(a.verificationGrade)));}
function sortedUnique(list,key){return [...new Set(list.map(x=>x[key]).filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b),'ko'));}
function statusClass(a){return a.statusCode==='legacy'?'legacy':(['development','certification','target'].includes(a.statusCode)?'target':'current');}
function statusBadge(a){return `<span class="badge ${statusClass(a)}">${esc(a.status)}</span>`;}
function gradeBadge(a){const d=DATA.verificationGrades[a.verificationGrade]||{};return `<span class="badge grade" title="${esc(d.definition||'')}">검증 ${esc(a.verificationGrade)}</span>`;}
function sourceTierBadge(s){return `<span class="badge source-${String(s.tier||'').toLowerCase()}">${esc(s.tier)}</span>`;}
function colorFor(id,ids){const i=Math.max(0,(ids||[]).indexOf(id));return compareColors[i%compareColors.length];}
function markerFor(id,ids){const i=Math.max(0,(ids||[]).indexOf(id));return markerShapes[i%markerShapes.length];}
function pastelFor(id,ids){const i=Math.max(0,(ids||[]).indexOf(id));return comparePastels[i%comparePastels.length];}
function manufacturerColor(a){return a.manufacturerColor||'#475569';}
function queryParams(){return new URLSearchParams(location.search);}
function updateUrl(params,replace=true){try{const u=new URL(location.href);Object.entries(params).forEach(([k,v])=>{if(v===null||v===undefined||v===''||(Array.isArray(v)&&!v.length))u.searchParams.delete(k);else u.searchParams.set(k,Array.isArray(v)?v.join(','):String(v));});history[replace?'replaceState':'pushState']({},'',u);}catch(_){}}
function localGet(k,fallback){try{const v=localStorage.getItem(k);return v?JSON.parse(v):fallback;}catch{return fallback;}}
function localSet(k,v){try{localStorage.setItem(k,JSON.stringify(v));}catch{}}
function copyText(text){if(navigator.clipboard?.writeText)return navigator.clipboard.writeText(text);const t=document.createElement('textarea');t.value=text;document.body.appendChild(t);t.select();document.execCommand('copy');t.remove();return Promise.resolve();}
function downloadText(text,filename,type='text/plain;charset=utf-8'){const b=new Blob([text],{type}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1000);}
function csv(rows,cols){const q=v=>'"'+String(v??'').replace(/"/g,'""')+'"';return [cols.map(c=>q(c.label)).join(','),...rows.map(r=>cols.map(c=>q(typeof c.value==='function'?c.value(r):r[c.value])).join(','))].join('\n');}
function downloadSvg(svg,filename){if(!svg)return;const clone=svg.cloneNode(true);clone.setAttribute('xmlns','http://www.w3.org/2000/svg');downloadText('<?xml version="1.0" encoding="UTF-8"?>\n'+clone.outerHTML,filename,'image/svg+xml;charset=utf-8');}
function downloadPng(svg,filename){if(!svg)return;const clone=svg.cloneNode(true);clone.setAttribute('xmlns','http://www.w3.org/2000/svg');const blob=new Blob([clone.outerHTML],{type:'image/svg+xml'}),url=URL.createObjectURL(blob),img=new Image();img.onload=()=>{const box=svg.viewBox.baseVal,w=box&&box.width?box.width:1200,h=box&&box.height?box.height:700,canvas=document.createElement('canvas');canvas.width=w*2;canvas.height=h*2;const c=canvas.getContext('2d');c.fillStyle='#fff';c.fillRect(0,0,canvas.width,canvas.height);c.drawImage(img,0,0,canvas.width,canvas.height);URL.revokeObjectURL(url);canvas.toBlob(b=>{const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)},'image/png')};img.src=url;}
function setupTopNav(){const b=document.querySelector('.mobile-menu'),n=document.querySelector('.topnav');if(b&&n)b.addEventListener('click',()=>{const open=n.classList.toggle('open');b.setAttribute('aria-expanded',String(open));});document.querySelectorAll('[data-export-svg]').forEach(btn=>btn.addEventListener('click',()=>{const svg=document.querySelector(btn.dataset.exportSvg+' svg');downloadSvg(svg,btn.dataset.filename||'chart.svg')}));document.querySelectorAll('[data-export-png]').forEach(btn=>btn.addEventListener('click',()=>{const svg=document.querySelector(btn.dataset.exportPng+' svg');downloadPng(svg,btn.dataset.filename||'chart.png')}));}
function sourceLink(s,prefix='./'){if(!s)return '';if(s.local)return `${prefix}${s.local}`;return s.url||'';}
function fieldEvidenceHtml(a,prefix='./'){return Object.entries(a.fieldEvidence||{}).map(([k,e])=>{const s=sourceMap.get(e.sourceId),link=sourceLink(s,prefix),status=e.status==='unavailable'?'<span class="badge target">미공개</span>':`<span class="badge ${e.status==='legacy'?'legacy':e.status==='target'?'target':'current'}">${esc(e.status)}</span>`;return `<div class="evidence-row"><b>${esc(fieldLabels[k]||k)}</b><span>${status}</span><span>${link?`<a href="${esc(link)}" target="_blank" rel="noopener">${esc(e.sourceId)}</a>`:esc(e.sourceId)}</span><span>${esc(e.pageRef||'')}<br><small>${esc(e.basis||e.note||'')}</small></span></div>`}).join('');}
function gradeLegendHtml(){
 const colors={'A+':'#16a34a','A':'#2563eb','B+':'#ea580c','B':'#7c3aed','C':'#64748b'};
 return Object.entries(DATA.verificationGrades).map(([g,d])=>`<article class="grade-card grade-policy-card" style="--grade-color:${colors[g]||'#64748b'}"><div class="grade-policy-head"><span class="grade-code">${esc(g)}</span><h3>${esc(d.label)}</h3></div><p>${esc(d.definition)}</p><small>${esc(d.screenRule)}</small></article>`).join('');
}
function colorLegendHtml(){
 const makerMap=new Map();aircraft.forEach(a=>{if(!makerMap.has(a.manufacturer))makerMap.set(a.manufacturer,manufacturerColor(a))});
 const makerRows=[...makerMap].map(([name,color])=>`<span class="policy-legend-item"><span class="policy-swatch" style="background:${esc(color)}"></span>${esc(name)}</span>`).join('');
 const compareRows=compareColors.map((color,i)=>`<span class="policy-legend-item"><span class="policy-swatch" style="background:${color}"></span><span class="policy-marker policy-marker-${markerShapes[i]||'circle'}" style="--policy-color:${color}"></span>선택 ${i+1}</span>`).join('');
 const tierRows=['A1','A2','B1','B2'].map(t=>`<span class="policy-legend-item">${sourceTierBadge({tier:t})}${esc(DATA.sourceTierDefinitions[t]||'')}</span>`).join('');
 return `<article class="policy-card legend-block"><h3>제조사 색상</h3><p>백과 카드와 전체 포지션 맵에서 제조사를 식별합니다.</p><div class="policy-legend-list">${makerRows}</div></article>
 <article class="policy-card legend-block"><h3>비교 선택 색상·마커</h3><p>선택 순번 1–6을 차트·레이더·표·실척 SVG에 동일 적용합니다.</p><div class="policy-legend-list">${compareRows}</div></article>
 <article class="policy-card legend-block"><h3>출처 등급 색상</h3><p>문서 성격을 나타내며 항공기 성능의 우열을 뜻하지 않습니다.</p><div class="policy-legend-list policy-tier-list">${tierRows}</div></article>
 <article class="policy-card legend-block"><h3>상태·접근성 규칙</h3><div class="policy-legend-list"><span class="policy-legend-item"><span class="badge current">현행</span>운용·현행 자료</span><span class="policy-legend-item"><span class="badge legacy">레거시</span>보관·단종 자료</span><span class="policy-legend-item"><span class="badge target">목표/개발</span>미동결·목표형</span></div><p class="policy-footnote">색상만 사용하지 않고 직접 레이블·배지·마커 형태를 함께 제공합니다.</p></article>`;
}
function detailCells(a){const cells=[
 ['전형 좌석',seats(a),a.comparisonBasis?.seatingBasis],['최대 좌석',a.maxSeats==null?'—':`${num(a.maxSeats,0)}석`,'인증/공표 최대'],['MTOW',value(a.mtowT,'t',2),a.comparisonBasis?.weightVariant],['항속거리',value(a.rangeNm,'nm',0),a.comparisonBasis?.rangeBasis],['최대 페이로드',payload(a),'대표 구조/운용 페이로드'],['화물용적',value(a.cargoM3,'m³',1),'공표값이 있을 때만 표시'],['길이',value(a.lengthM,'m',2),'공식 전체 길이'],['날개폭',value(a.spanM,'m',2),'공식 날개폭'],['높이',value(a.heightM,'m',2),'공식 높이'],['엔진',a.engine||'—','대표 엔진/선택지'],['순항',a.cruiseMach==null?'—':`M${num(a.cruiseMach,3)}`,'대표 순항 마하'],['EIS',a.eis??'—','목표형은 목표연도']
 ];return cells.map(([l,v,note])=>`<div class="detail-cell"><span>${esc(l)}</span><b>${esc(v)}</b><small>${esc(note||'')}</small></div>`).join('');}
function derivedCells(a){const cells=[['외형 크기지수',value(a.sizeIndexA320neo100,'',1),'A320neo=100'],['Footprint',value(a.footprintM2,'m²',1),'길이×날개폭'],['길이/날개폭',value(a.lengthSpanRatio,'',3),'외형 비율'],['높이/길이',value(a.heightLengthPct,'%',1),'외형 비율'],['MTOW/좌석',value(a.mtowPerSeatKg,'kg/석',1),'전형 좌석 중간값'],['항속/MTOW',value(a.rangePerMtowNmPerT,'nm/t',2),'단순 비교지표'],['Payload/MTOW',value(a.payloadMtowPct,'%',1),'화물·구조비교'],['데이터 완전성',value(a.dataQuality?.completenessPct,'%',0),'핵심 비교필드']];return cells.map(([l,v,note])=>`<div class="detail-cell"><span>${esc(l)}</span><b>${esc(v)}</b><small>${esc(note)}</small></div>`).join('');}
function openModal(backdrop,returnFocus){backdrop._returnFocus=returnFocus||document.activeElement;backdrop.classList.add('open');backdrop.setAttribute('aria-hidden','false');document.body.style.overflow='hidden';const f=backdrop.querySelector('button,[href],input,select,[tabindex]:not([tabindex="-1"])');f?.focus();const trap=e=>{if(e.key==='Escape'){closeModal(backdrop);return}if(e.key!=='Tab')return;const nodes=[...backdrop.querySelectorAll('button,[href],input,select,[tabindex]:not([tabindex="-1"])')].filter(x=>!x.disabled);if(!nodes.length)return;const first=nodes[0],last=nodes[nodes.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}};backdrop._trap=trap;document.addEventListener('keydown',trap);}
function closeModal(backdrop){if(!backdrop)return;backdrop.classList.remove('open');backdrop.setAttribute('aria-hidden','true');document.body.style.overflow='';if(backdrop._trap)document.removeEventListener('keydown',backdrop._trap);backdrop._returnFocus?.focus?.();}
function bindModal(backdrop){if(!backdrop)return;backdrop.querySelectorAll('[data-close-modal]').forEach(b=>b.addEventListener('click',()=>closeModal(backdrop)));backdrop.addEventListener('mousedown',e=>{if(e.target===backdrop)closeModal(backdrop)});}
function renderAircraftModal(a,prefix='./'){
 const bd=document.getElementById('aircraftModal');if(!bd||!window.CA.SVG)return;
 const family=aircraft.filter(x=>x.family===a.family&&x.id!==a.id);
 const color=manufacturerColor(a);
 bd.querySelector('[data-modal-title]').textContent=a.model;
 bd.querySelector('[data-modal-subtitle]').innerHTML=`${esc(a.manufacturer)} · ${esc(a.family)} · ${statusBadge(a)} ${gradeBadge(a)}`;
 bd.querySelector('.modal-body').innerHTML=`
 <section class="modal-section card card-pad"><div class="section-title"><div><h3>한눈에 보는 전체 정보</h3><p>${esc(a.notes)}</p></div><div class="legend-row"><span class="legend-item"><span class="swatch" style="background:${color}"></span>${esc(a.manufacturer)}</span><span class="legend-item">${esc(a.category)} · ${esc(a.role)}</span></div></div><div class="detail-grid">${detailCells(a)}</div></section>
 <section class="modal-section"><h3>3면도 · 공개 치수 기반 비교 도식</h3><div class="modal-views"><article class="modal-view"><h4>상면</h4>${CA.SVG.aircraft(a,'top',{color,grid:true})}</article><article class="modal-view"><h4>측면</h4>${CA.SVG.aircraft(a,'side',{color,grid:true})}</article><article class="modal-view"><h4>정면</h4>${CA.SVG.aircraft(a,'front',{color,grid:true})}</article></div><div class="notice">SVG는 공개 치수와 형상 분류를 사용한 파라메트릭 비교 도식이며 제조사 CAD·인증도면이 아닙니다.</div></section>
 <section class="modal-section card card-pad"><h3>파생 비교지표</h3><div class="detail-grid">${derivedCells(a)}</div></section>
 <section class="modal-section card card-pad"><h3>비교 조건</h3><div class="grid grid-3"><div class="callout"><strong>좌석 기준</strong><br>${esc(a.comparisonBasis?.seatingBasis||'—')}</div><div class="callout"><strong>항속 기준</strong><br>${esc(a.comparisonBasis?.rangeBasis||'—')}</div><div class="callout"><strong>중량 형상</strong><br>${esc(a.comparisonBasis?.weightVariant||'—')}</div></div></section>
 <section class="modal-section card card-pad"><h3>필드별 출처·근거</h3><div class="evidence-list">${fieldEvidenceHtml(a,prefix)}</div></section>
 <section class="modal-section card card-pad"><h3>동일 패밀리</h3><div class="family-links">${family.length?family.map(x=>`<button class="family-link" data-family-id="${esc(x.id)}">${esc(x.model)}</button>`).join(''):'<span class="section-note">등록된 동일 패밀리 인접 형상 없음</span>'}</div></section>`;
 bd.querySelectorAll('[data-family-id]').forEach(b=>b.addEventListener('click',()=>renderAircraftModal(aircraftMap.get(b.dataset.familyId),prefix)));
 if(!bd.classList.contains('open'))openModal(bd,document.activeElement);
 updateUrl({aircraft:a.id},true);
}
function bindAircraftModal(prefix='./'){const bd=document.getElementById('aircraftModal');bindModal(bd);document.addEventListener('ca:open-aircraft',e=>{const a=aircraftMap.get(e.detail?.id);if(a)renderAircraftModal(a,prefix)});const q=queryParams().get('aircraft');if(q&&aircraftMap.has(q))setTimeout(()=>renderAircraftModal(aircraftMap.get(q),prefix),20);}
function dispatchAircraft(id){document.dispatchEvent(new CustomEvent('ca:open-aircraft',{detail:{id}}));}
function chartTooltip(){let el=document.querySelector('.chart-tooltip');if(!el){el=document.createElement('div');el.className='chart-tooltip';document.body.appendChild(el)}return {show(html,x,y){el.innerHTML=html;el.style.left=Math.min(innerWidth-285,x+12)+'px';el.style.top=Math.min(innerHeight-120,y+12)+'px';el.classList.add('show')},hide(){el.classList.remove('show')}};}
window.CA={DATA,aircraft,sources,localPdfArchive,aircraftMap,sourceMap,compareColors,comparePastels,markerShapes,fieldLabels,metricDefs,esc,n,num,seats,payload,value,normalize,highlight,matches,filterAircraft,sortedUnique,statusBadge,gradeBadge,sourceTierBadge,colorFor,markerFor,pastelFor,manufacturerColor,queryParams,updateUrl,localGet,localSet,copyText,downloadText,csv,downloadSvg,downloadPng,setupTopNav,sourceLink,fieldEvidenceHtml,gradeLegendHtml,colorLegendHtml,detailCells,derivedCells,openModal,closeModal,bindModal,renderAircraftModal,bindAircraftModal,dispatchAircraft,chartTooltip};
})();
