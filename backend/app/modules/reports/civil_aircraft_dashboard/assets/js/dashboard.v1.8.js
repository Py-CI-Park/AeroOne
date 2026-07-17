(function(){
  'use strict';
  const CA=window.CA;
  if(!CA) throw new Error('CA core required');

  const DEFAULT=['a320neo','737-8','a321xlr','787-9-imtow','a350-900'];
  const qp=CA.queryParams();
  const qCompare=(qp.get('compare')||'').split(',').filter(id=>CA.aircraftMap.has(id));
  const single=qp.get('aircraft');

  const radarHiddenFromUrl=(qp.get('radarHidden')||'').split(',').filter(Boolean);
  const state={
    selected:(qCompare.length?qCompare:(single&&CA.aircraftMap.has(single)?[single,...DEFAULT.filter(x=>x!==single).slice(0,4)]:CA.localGet('ca-v16-selected',DEFAULT))).filter(id=>CA.aircraftMap.has(id)).slice(0,6),
    metric:qp.get('metric')&&CA.metricDefs[qp.get('metric')]?qp.get('metric'):'rangeNm',
    baseline:qp.get('baseline')||null,
    focus:single||null,
    q:'',manufacturer:'all',category:'all',role:'all',
    mapRole:qp.get('mapRole')||'여객',
    mapCategory:qp.get('mapCategory')||'all',
    mapRange:['focus','all'].includes(qp.get('mapRange'))?qp.get('mapRange'):'focus',
    labelMode:['representative','selected','all','none'].includes(qp.get('labels'))?qp.get('labels'):'representative',
    shapeView:['top','side','front'].includes(qp.get('shape'))?qp.get('shape'):'top',
    shapeOverlay:qp.get('overlay')===null?true:qp.get('overlay')==='1',
    radarMode:['line','soft','active'].includes(qp.get('radar'))?qp.get('radar'):'line',
    radarActive:qp.get('radarActive')||null,
    radarHidden:new Set(radarHiddenFromUrl),
    catalogDetailOpen:qp.get('detail')===null?CA.localGet('ca-v16-detail',true):qp.get('detail')==='1'
  };

  if(!state.baseline||!state.selected.includes(state.baseline)) state.baseline=state.selected[0]||null;
  if(!state.focus||!CA.aircraftMap.has(state.focus)) state.focus=state.selected[0]||CA.aircraft[0].id;
  if(!state.radarActive||!state.selected.includes(state.radarActive)) state.radarActive=state.selected[0]||null;
  state.radarHidden=new Set([...state.radarHidden].filter(id=>state.selected.includes(id)));
  if(state.radarHidden.size>=state.selected.length) state.radarHidden.clear();

  function selectedAircraft(){return state.selected.map(id=>CA.aircraftMap.get(id)).filter(Boolean);}

  function persist(){
    CA.localSet('ca-v16-selected',state.selected);
    CA.localSet('ca-v16-detail',state.catalogDetailOpen);
    CA.updateUrl({
      compare:state.selected,metric:state.metric,baseline:state.baseline,aircraft:state.focus,
      shape:state.shapeView,overlay:state.shapeOverlay?'1':'0',mapRole:state.mapRole,mapCategory:state.mapCategory,mapRange:state.mapRange,labels:state.labelMode,
      radar:state.radarMode,radarActive:state.radarActive,radarHidden:[...state.radarHidden],detail:state.catalogDetailOpen?'1':'0'
    },true);
  }

  function optionList(id,values,label){
    const e=document.getElementById(id);
    if(!e) return;
    e.innerHTML=`<option value="all">${CA.esc(label)}</option>`+values.map(v=>`<option value="${CA.esc(v)}">${CA.esc(v)}</option>`).join('');
  }

  function catalogFiltered(){return CA.filterAircraft(CA.aircraft,{q:state.q,manufacturer:state.manufacturer,category:state.category,role:state.role});}

  function toggle(id){
    if(state.selected.includes(id)){
      if(state.selected.length===1){
        const x=document.getElementById('selectionMessage');
        x.textContent='비교 기체는 최소 1개를 유지해야 합니다.';
        setTimeout(()=>x.textContent='',2200);
        return;
      }
      state.selected=state.selected.filter(x=>x!==id);
      if(!state.selected.includes(state.baseline)) state.baseline=state.selected[0];
      state.radarHidden.delete(id);
      if(state.radarActive===id) state.radarActive=state.selected[0]||null;
    }else{
      if(state.selected.length>=6){
        const x=document.getElementById('selectionMessage');
        x.textContent='최대 6개 기체까지 비교할 수 있습니다.';
        setTimeout(()=>x.textContent='',2200);
        return;
      }
      state.selected.push(id);
      if(!state.radarActive) state.radarActive=id;
    }
    state.focus=id;
    persist();
    renderAll();
  }

  function renderCatalog(){
    const list=catalogFiltered(),root=document.getElementById('catalogList');
    document.getElementById('catalogCount').textContent=`${list.length} / ${CA.aircraft.length}`;
    root.innerHTML=list.map(a=>`<li class="catalog-row ${state.selected.includes(a.id)?'selected':''}">
      <input type="checkbox" aria-label="${CA.esc(a.model)} 비교 선택" data-toggle-id="${CA.esc(a.id)}" ${state.selected.includes(a.id)?'checked':''}>
      <div class="catalog-model catalog-text-left"><button class="model-link" data-focus-id="${CA.esc(a.id)}">${CA.highlight(a.model,state.q)}</button><small>${CA.esc(a.family)}</small></div>
      <span class="catalog-text-left">${CA.esc(a.manufacturer)}</span>
      <span class="catalog-text-left">${CA.esc(a.category)}</span>
      <span class="catalog-role">${CA.esc(a.role)}</span>
      <span class="catalog-status catalog-text-left">${CA.esc(a.status)}</span>
      <span>${a.role==='여객'?CA.seats(a):CA.payload(a)}</span>
      <span>${CA.value(a.mtowT,'t',1)}</span>
      <span>${CA.value(a.rangeNm,'nm',0)}</span>
      <span>${CA.value(a.lengthM,'m',2)}</span>
      <span>${CA.value(a.spanM,'m',2)}</span>
      <span>${CA.value(a.heightM,'m',2)}</span>
      <span><span class="badge grade">${CA.esc(a.verificationGrade)}</span></span>
    </li>`).join('');
    root.querySelectorAll('[data-toggle-id]').forEach(e=>e.addEventListener('change',()=>toggle(e.dataset.toggleId)));
    root.querySelectorAll('[data-focus-id]').forEach(e=>e.addEventListener('click',()=>{
      state.focus=e.dataset.focusId;persist();renderInline();CA.dispatchAircraft(e.dataset.focusId);
    }));
  }

  function renderSelection(){
    const root=document.getElementById('selectionStrip');
    root.innerHTML=selectedAircraft().map(a=>`<span class="selection-chip"><span class="swatch" style="background:${CA.colorFor(a.id,state.selected)}"></span>${CA.esc(a.model)}<button aria-label="${CA.esc(a.model)} 제거" data-remove-id="${CA.esc(a.id)}">×</button></span>`).join('');
    root.querySelectorAll('[data-remove-id]').forEach(b=>b.addEventListener('click',()=>toggle(b.dataset.removeId)));
    const sel=document.getElementById('baselineSelect');
    sel.innerHTML=selectedAircraft().map(a=>`<option value="${CA.esc(a.id)}" ${a.id===state.baseline?'selected':''}>${CA.esc(a.model)}</option>`).join('');
  }

  function renderMetrics(){
    const root=document.getElementById('metricButtons');
    root.innerHTML=Object.entries(CA.metricDefs).map(([k,d])=>`<button class="metric-btn ${k===state.metric?'active':''}" data-metric="${k}" type="button">${CA.esc(d.label)}</button>`).join('');
    root.querySelectorAll('[data-metric]').forEach(b=>b.addEventListener('click',()=>{state.metric=b.dataset.metric;persist();renderComparison();}));
  }

  function compactDetailCells(a){
    const cells=[
      ['좌석 / Payload',a.role==='여객'?CA.seats(a):CA.payload(a)],
      ['MTOW',CA.value(a.mtowT,'t',2)],['항속거리',CA.value(a.rangeNm,'nm',0)],
      ['Length',CA.value(a.lengthM,'m',2)],['Span',CA.value(a.spanM,'m',2)],['Height',CA.value(a.heightM,'m',2)]
    ];
    return cells.map(([l,v])=>`<div class="detail-cell"><span>${CA.esc(l)}</span><b>${CA.esc(v)}</b></div>`).join('');
  }

  function renderInline(){
    const a=CA.aircraftMap.get(state.focus)||selectedAircraft()[0];
    if(!a) return;
    const root=document.getElementById('inlineDetail'),color=CA.manufacturerColor(a);
    root.innerHTML=`<div class="mini-svg">${CA.SVG.aircraft(a,'top',{color,grid:false,dimensions:false})}</div>
      <div class="section-title"><div><h2>${CA.esc(a.model)}</h2><p>${CA.esc(a.manufacturer)} · ${CA.esc(a.family)} · ${CA.esc(a.category)}</p></div><div class="legend-row">${CA.statusBadge(a)}${CA.gradeBadge(a)}</div></div>
      <div class="detail-grid">${compactDetailCells(a)}</div><div class="section-actions" style="margin-top:9px"><button class="btn primary small" id="openFocusDetail">전체 상세</button><button class="btn small" id="toggleFocusCompare">${state.selected.includes(a.id)?'비교에서 제거':'비교에 추가'}</button></div>`;
    document.getElementById('openFocusDetail').addEventListener('click',()=>CA.dispatchAircraft(a.id));
    document.getElementById('toggleFocusCompare').addEventListener('click',()=>toggle(a.id));
  }

  function renderCatalogLayout(){
    const top=document.getElementById('dashboardTop'),btn=document.getElementById('catalogDetailToggle');
    top.classList.toggle('detail-collapsed',!state.catalogDetailOpen);
    btn.textContent=state.catalogDetailOpen?'상세 접기':'상세 펼치기';
    btn.setAttribute('aria-pressed',String(state.catalogDetailOpen));
  }

  function renderRadarControls(){
    if(!state.selected.includes(state.radarActive)) state.radarActive=state.selected[0]||null;
    state.radarHidden=new Set([...state.radarHidden].filter(id=>state.selected.includes(id)));
    if(state.radarHidden.size>=state.selected.length) state.radarHidden.clear();
    const select=document.getElementById('radarActiveSelect');
    select.innerHTML=selectedAircraft().map(a=>`<option value="${CA.esc(a.id)}" ${a.id===state.radarActive?'selected':''}>${CA.esc(a.model)}</option>`).join('');
    document.querySelectorAll('#radarModeButtons [data-radar-mode]').forEach(b=>{const on=b.dataset.radarMode===state.radarMode;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});
    const modeLabel=state.radarMode==='line'?'선만 표시':state.radarMode==='soft'?'연한 채우기':'선택 기체만 채우기';
    document.getElementById('radarModeNote').textContent=`${modeLabel} · 숨김 ${state.radarHidden.size}개 · 범례 클릭으로 전환`;
  }

  function deltaHtml(v,b){
    if(!Number.isFinite(v)||!Number.isFinite(b)||b===0) return '<span class="delta-zero">—</span>';
    const p=(v-b)/b*100,cls=Math.abs(p)<.05?'delta-zero':p>0?'delta-up':'delta-down';
    return `<span class="${cls}">${p>0?'+':''}${CA.num(p,1)}%</span>`;
  }

  function renderTable(){
    const list=selectedAircraft(),base=CA.aircraftMap.get(state.baseline),root=document.getElementById('comparisonTable'),metrics=Object.entries(CA.metricDefs);
    let html=`<table class="data-table"><thead><tr><th>지표</th>${list.map(a=>`<th><span class="swatch" style="background:${CA.colorFor(a.id,state.selected)}"></span> ${CA.esc(a.model)}${a.id===state.baseline?'<br><span class="badge grade">기준</span>':''}</th>`).join('')}</tr></thead><tbody>`;
    metrics.forEach(([k,d])=>{
      const vals=list.map(a=>d.get(a)).filter(Number.isFinite),mx=vals.length?Math.max(...vals):null,mn=vals.length?Math.min(...vals):null,bv=base?d.get(base):null;
      html+=`<tr><td><b>${CA.esc(d.label)}</b><br><small>${CA.esc(d.unit)}</small></td>${list.map(a=>{
        const v=d.get(a),tag=Number.isFinite(v)&&vals.length>1?(v===mx?'<span class="badge current">MAX</span> ':v===mn?'<span class="badge legacy">MIN</span> ':''):'';
        return `<td class="num">${tag}<b>${Number.isFinite(v)?`${CA.num(v,d.digits)} ${CA.esc(d.unit)}`:'—'}</b><br>${a.id===state.baseline?'<span class="delta-zero">기준 0.0%</span>':deltaHtml(v,bv)}</td>`;
      }).join('')}</tr>`;
    });
    root.innerHTML=html+'</tbody></table>';
  }

  function setSeriesFocus(id){
    const host=document.getElementById('radarChart');
    host.querySelectorAll('[data-series-group]').forEach(g=>{if(g.classList.contains('series-hidden'))return;g.style.opacity=!id||g.dataset.seriesId===id?'1':'.18';});
    host.querySelectorAll('.radar-legend-item').forEach(g=>{if(g.classList.contains('hidden-series'))return;g.style.opacity=!id||g.dataset.seriesId===id?'1':'.35';});
  }

  function bindRadar(){
    const host=document.getElementById('radarChart'),tip=CA.chartTooltip();
    host.querySelectorAll('.radar-point[data-series-id]').forEach(node=>{
      const id=node.dataset.seriesId;
      const show=e=>{setSeriesFocus(id);if(node.dataset.tooltip){const [m,ax,raw,norm]=node.dataset.tooltip.split('|');tip.show(`<b>${CA.esc(m)}</b><br>${CA.esc(ax)} · ${CA.esc(raw)}<br>${CA.esc(norm)}<br><small>클릭: 강조 기체</small>`,e.clientX||innerWidth/2,e.clientY||innerHeight/2);}};
      node.addEventListener('pointerenter',show);node.addEventListener('pointermove',show);node.addEventListener('pointerleave',()=>{setSeriesFocus(null);tip.hide();});
      node.addEventListener('focus',()=>setSeriesFocus(id));node.addEventListener('blur',()=>{setSeriesFocus(null);tip.hide();});
      node.addEventListener('click',()=>{state.radarActive=id;persist();renderComparison();});
      node.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();node.click();}});
    });
    host.querySelectorAll('.radar-legend-item[data-series-id]').forEach(node=>{
      const id=node.dataset.seriesId;
      node.addEventListener('pointerenter',()=>setSeriesFocus(id));node.addEventListener('pointerleave',()=>setSeriesFocus(null));
      node.addEventListener('click',()=>{if(state.radarHidden.has(id)){state.radarHidden.delete(id);}else if(state.selected.length-state.radarHidden.size>1){state.radarHidden.add(id);}persist();renderComparison();});
      node.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();node.click();}});
    });
  }

  function renderComparison(){
    const list=selectedAircraft(),d=CA.metricDefs[state.metric];
    document.getElementById('metricChart').innerHTML=CA.Charts.metricBar(list,state.metric,state.selected);
    renderRadarControls();
    document.getElementById('radarChart').innerHTML=CA.Charts.radar(list,state.selected,{mode:state.radarMode,activeId:state.radarActive,hiddenIds:[...state.radarHidden]});
    renderTable();
    document.getElementById('summaryStrip').innerHTML=list.map(a=>{
      const v=d.get(a),b=CA.aircraftMap.get(state.baseline),bv=b?d.get(b):null;
      return `<div class="summary-item"><b><span class="swatch" style="background:${CA.colorFor(a.id,state.selected)}"></span> ${CA.esc(a.model)}</b><span>${Number.isFinite(v)?`${CA.num(v,d.digits)} ${CA.esc(d.unit)}`:'—'} · ${a.id===state.baseline?'기준':deltaHtml(v,bv)}</span></div>`;
    }).join('');
    renderMetrics();
    bindRadar();
  }

  function bindScale(){
    // v1.8 실척 실루엣 상호작용: hover 치수 툴팁 + 강조, 클릭 시 백과(상세 모달) 딥링크.
    const host=document.getElementById('scaleView'),tip=CA.chartTooltip();
    const hits=[...host.querySelectorAll('.silhouette-hit[data-aircraft-id]')];
    hits.forEach(g=>{
      const show=e=>{
        const [m,meta,dims]=(g.dataset.tooltip||'').split('|');
        tip.show(`<b>${CA.esc(m)}</b><br>${CA.esc(meta)}<br>${CA.esc(dims)}<br><small>클릭: 백과 상세</small>`,e.clientX||innerWidth/2,e.clientY||innerHeight/2);
        hits.forEach(o=>{o.style.opacity=o===g?'1':'.2';});
      };
      const clear=()=>{tip.hide();hits.forEach(o=>o.style.opacity='');};
      g.addEventListener('pointerenter',show);g.addEventListener('pointermove',show);g.addEventListener('pointerleave',clear);
      g.addEventListener('focus',()=>show({clientX:innerWidth/2,clientY:innerHeight/2}));g.addEventListener('blur',clear);
      g.addEventListener('click',()=>{state.focus=g.dataset.aircraftId;persist();renderInline();CA.dispatchAircraft(g.dataset.aircraftId);});
      g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();g.click();}});
    });
  }

  function renderScale(){
    const list=selectedAircraft(),root=document.getElementById('scaleView');
    root.innerHTML=CA.SVG.compareSheet(list,state.shapeView,state.selected,state.shapeOverlay);
    document.querySelectorAll('[data-scale-view]').forEach(b=>{
      const active=b.dataset.scaleView===state.shapeView;
      b.classList.toggle('active',active);
      b.setAttribute('aria-pressed',active?'true':'false');
    });
    const overlay=document.getElementById('scaleOverlay');
    overlay.checked=state.shapeOverlay;
    document.getElementById('scaleOverlayText').textContent=`Overlay ${state.shapeOverlay?'ON':'OFF'}`;
    const viewLabel=state.shapeView==='top'?'Top / 상면':state.shapeView==='side'?'Side / 측면':'Front / 정면';
    document.getElementById('scaleModeNote').textContent=`${viewLabel} · Overlay ${state.shapeOverlay?'ON (단일 공통축척 오버레이)':'OFF (기체별 공통축척 패널)'}`;
    const light=document.getElementById('scaleLightbox');
    if(light.classList.contains('open')) light.querySelector('.scale-lightbox-view').innerHTML=root.innerHTML;
    bindScale();
  }

  function openScaleLightbox(){
    const lb=document.getElementById('scaleLightbox'),svg=document.querySelector('#scaleView svg');
    if(!svg) return;
    lb.querySelector('.scale-lightbox-view').innerHTML=svg.outerHTML;
    CA.openModal(lb,document.getElementById('scaleExpand'));
  }

  function bindMap(){
    const host=document.getElementById('marketMap'),tip=CA.chartTooltip();
    host.querySelectorAll('[data-aircraft-id]').forEach(g=>{
      const show=e=>{const [m,c,r,w]=(g.dataset.tooltip||'').split('|');tip.show(`<b>${CA.esc(m)}</b><br>${CA.esc(c)} · ${CA.esc(r)}<br>${CA.esc(w)}<br><small>클릭: 전체 상세</small>`,e.clientX||innerWidth/2,e.clientY||innerHeight/2);};
      g.addEventListener('pointerenter',show);g.addEventListener('pointermove',show);g.addEventListener('pointerleave',tip.hide);
      g.addEventListener('focus',()=>show({clientX:innerWidth/2,clientY:innerHeight/2}));g.addEventListener('blur',tip.hide);
      g.addEventListener('click',()=>{state.focus=g.dataset.aircraftId;persist();renderInline();CA.dispatchAircraft(g.dataset.aircraftId);});
      g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();g.click();}});
    });
  }

  function renderMap(){
    const host=document.getElementById('marketMap');
    host.innerHTML=CA.Charts.positionMap(CA.aircraft,{role:state.mapRole,selectedIds:state.selected,labelMode:state.labelMode,rangeMode:state.mapRange,category:state.mapCategory});
    const svg=host.querySelector('svg');
    const labelCount=Number(svg?.dataset.labelCount||0),omitted=Number(svg?.dataset.labelOmitted||0),overlap=Number(svg?.dataset.labelOverlapCount||0);
    document.getElementById('mapStatus').textContent=`레이블 ${labelCount}개 · 겹침 ${overlap}개${omitted?` · 공간 부족 자동 생략 ${omitted}개`:''}`;
    const excluded=CA.aircraft.filter(a=>a.role===state.mapRole&&(state.mapCategory==='all'||a.category===state.mapCategory)&&!a.dataQuality.hasPositionData);
    document.getElementById('marketNotice').innerHTML=excluded.length?excluded.map(a=>`<div class="notice"><b>${CA.esc(a.model)}</b> — ${CA.esc(a.comparisonBasis?.rangeBasis||'비교 필드 미공개')}</div>`).join(''):'<div class="notice">현재 필터의 모든 기체가 포지션 맵에 포함되었습니다.</div>';
    bindMap();
  }

  function renderEvidence(){
    const prefix=document.body.dataset.sourcePrefix||'../',root=document.getElementById('evidenceCards');
    root.innerHTML=selectedAircraft().map(a=>`<article class="card card-pad"><div class="section-title"><div><h2 style="font-size:17px"><span class="swatch" style="background:${CA.colorFor(a.id,state.selected)}"></span> ${CA.esc(a.model)}</h2><p>${CA.esc(a.manufacturer)} · 검증 ${CA.esc(a.verificationGrade)} · 완전성 ${a.dataQuality.completenessPct}% · 추적성 ${a.dataQuality.traceabilityPct}%</p></div><button class="btn small" data-open-evidence="${CA.esc(a.id)}">전체 상세</button></div><div class="evidence-list">${CA.fieldEvidenceHtml(a,prefix)}</div></article>`).join('');
    root.querySelectorAll('[data-open-evidence]').forEach(b=>b.addEventListener('click',()=>CA.dispatchAircraft(b.dataset.openEvidence)));
  }

  function renderAll(){renderCatalogLayout();renderCatalog();renderSelection();renderInline();renderComparison();renderScale();renderMap();renderEvidence();}

  function init(){
    CA.setupTopNav();
    CA.bindAircraftModal(document.body.dataset.sourcePrefix||'../');
    CA.bindModal(document.getElementById('scaleLightbox'));

    optionList('manufacturerFilter',CA.sortedUnique(CA.aircraft,'manufacturer'),'전체 제조사');
    optionList('categoryFilter',CA.sortedUnique(CA.aircraft,'category'),'전체 세그먼트');
    optionList('roleFilter',CA.sortedUnique(CA.aircraft,'role'),'전체 용도');
    optionList('mapCategory',CA.sortedUnique(CA.aircraft.filter(a=>a.role===state.mapRole),'category'),'전체 세그먼트');
    document.getElementById('mapRole').value=state.mapRole;
    document.getElementById('mapCategory').value=state.mapCategory;
    document.getElementById('mapRange').value=state.mapRange;
    document.getElementById('labelMode').value=state.labelMode;

    document.getElementById('search').addEventListener('input',e=>{state.q=e.target.value;renderCatalog();});
    document.getElementById('manufacturerFilter').addEventListener('change',e=>{state.manufacturer=e.target.value;renderCatalog();});
    document.getElementById('categoryFilter').addEventListener('change',e=>{state.category=e.target.value;renderCatalog();});
    document.getElementById('roleFilter').addEventListener('change',e=>{state.role=e.target.value;renderCatalog();});
    document.getElementById('baselineSelect').addEventListener('change',e=>{state.baseline=e.target.value;persist();renderComparison();});
    document.getElementById('catalogDetailToggle').addEventListener('click',()=>{state.catalogDetailOpen=!state.catalogDetailOpen;persist();renderCatalogLayout();});
    document.querySelectorAll('#radarModeButtons [data-radar-mode]').forEach(b=>b.addEventListener('click',()=>{state.radarMode=b.dataset.radarMode;persist();renderComparison();}));
    document.getElementById('radarActiveSelect').addEventListener('change',e=>{state.radarActive=e.target.value;persist();renderComparison();});
    document.getElementById('radarShowAll').addEventListener('click',()=>{state.radarHidden.clear();persist();renderComparison();});

    document.getElementById('mapRole').addEventListener('change',e=>{
      state.mapRole=e.target.value;state.mapCategory='all';
      optionList('mapCategory',CA.sortedUnique(CA.aircraft.filter(a=>a.role===state.mapRole),'category'),'전체 세그먼트');
      document.getElementById('mapCategory').value='all';persist();renderMap();
    });
    document.getElementById('mapCategory').addEventListener('change',e=>{state.mapCategory=e.target.value;persist();renderMap();});
    document.getElementById('mapRange').addEventListener('change',e=>{state.mapRange=e.target.value;persist();renderMap();});
    document.getElementById('labelMode').addEventListener('change',e=>{state.labelMode=e.target.value;persist();renderMap();});

    document.querySelectorAll('[data-scale-view]').forEach(b=>b.addEventListener('click',()=>{state.shapeView=b.dataset.scaleView;persist();renderScale();}));
    document.getElementById('scaleOverlay').addEventListener('change',e=>{state.shapeOverlay=e.target.checked;persist();renderScale();});
    document.getElementById('scaleExpand').addEventListener('click',openScaleLightbox);
    document.getElementById('scaleSaveSvg').addEventListener('click',()=>CA.downloadSvg(document.querySelector('#scaleView svg'),`Civil_Aircraft_v1.8_Same_Scale_${state.shapeView}_${state.shapeOverlay?'Overlay':'Panels'}.svg`));
    document.getElementById('scaleSavePng')?.addEventListener('click',()=>CA.downloadPng(document.querySelector('#scaleView svg'),`Civil_Aircraft_v1.8_Same_Scale_${state.shapeView}_${state.shapeOverlay?'Overlay':'Panels'}.png`));

    document.getElementById('copyUrl').addEventListener('click',()=>{persist();CA.copyText(location.href).then(()=>{const x=document.getElementById('selectionMessage');x.textContent='비교 URL을 복사했습니다.';setTimeout(()=>x.textContent='',1800);});});
    document.getElementById('resetSelection').addEventListener('click',()=>{state.selected=[...DEFAULT];state.baseline=state.selected[0];state.focus=state.selected[0];state.radarActive=state.selected[0];state.radarHidden.clear();state.radarMode='line';persist();renderAll();});
    document.getElementById('exportSelected').addEventListener('click',()=>{
      const list=selectedAircraft(),cols=[
        {label:'Model',value:'model'},{label:'Manufacturer',value:'manufacturer'},{label:'Role',value:'role'},{label:'Status',value:'status'},
        {label:'Typical seats',value:a=>CA.seats(a)},{label:'MTOW t',value:'mtowT'},{label:'Range nm',value:'rangeNm'},{label:'Payload t',value:'maxPayloadT'},
        {label:'Length m',value:'lengthM'},{label:'Span m',value:'spanM'},{label:'Height m',value:'heightM'},{label:'Size index',value:'sizeIndexA320neo100'},
        {label:'Verification',value:'verificationGrade'},{label:'Range basis',value:a=>a.comparisonBasis.rangeBasis},{label:'Weight variant',value:a=>a.comparisonBasis.weightVariant}
      ];
      CA.downloadText('\ufeff'+CA.csv(list,cols),'Civil_Aircraft_Selected_Comparison_v1.8.csv','text/csv;charset=utf-8');
    });

    persist();
    renderAll();
  }

  document.addEventListener('DOMContentLoaded',init);
})();
