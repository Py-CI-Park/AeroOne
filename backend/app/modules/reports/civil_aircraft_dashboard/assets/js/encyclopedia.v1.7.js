(function(){
  'use strict';
  const CA=window.CA;
  const initialId=CA.queryParams().get('aircraft');
  const state={
    q:'',category:'all',role:'all',manufacturer:'all',status:'all',verifiedOnly:false,
    focus:CA.aircraftMap.has(initialId)?initialId:null,mapRole:'여객',mapCategory:'all',mapRange:'focus',mapLabels:'representative'
  };
  let initialHandled=false;

  function options(id,values,label='전체'){
    const el=document.getElementById(id);
    if(!el) return;
    el.innerHTML=`<option value="all">${label}</option>`+values.map(v=>`<option value="${CA.esc(v)}">${CA.esc(v)}</option>`).join('');
  }

  function sizeText(a){
    if(!a.dataQuality?.hasScaleGeometry) return '공식 치수 미공개';
    return `${CA.num(a.lengthM,2)} × ${CA.num(a.spanM,2)} × ${CA.num(a.heightM,2)} m`;
  }

  function card(a){
    const color=CA.manufacturerColor(a),capacity=a.role==='여객'?CA.seats(a):CA.payload(a);
    return `<article class="aircraft-card" data-card-id="${CA.esc(a.id)}" style="--manufacturer-color:${color}">
      <button class="aircraft-card-main" data-open-id="${CA.esc(a.id)}" type="button" aria-label="${CA.esc(a.model)} 전체 상세 보기">
        <div class="aircraft-card-head"><h3>${CA.esc(a.model)}</h3><div class="meta">${CA.esc(a.manufacturer)} · ${CA.esc(a.family)} · ${CA.esc(a.category)}</div></div>
        <div class="aircraft-card-badges">${CA.gradeBadge(a)}${CA.statusBadge(a)}</div>
        <div class="aircraft-visual">${CA.SVG.mini(a,color)}</div>
        <div class="aircraft-card-stats">
          <div class="aircraft-stat"><span>Size · L × S × H</span><b>${CA.esc(sizeText(a))}</b></div>
          <div class="aircraft-stat"><span>MTOW</span><b>${CA.value(a.mtowT,'t',1)}</b></div>
          <div class="aircraft-stat"><span>${a.role==='여객'?'Seats':'Payload'}</span><b>${CA.esc(capacity)}</b></div>
          <div class="aircraft-stat"><span>Range</span><b>${CA.value(a.rangeNm,'nm',0)}</b></div>
        </div>
      </button>
      <div class="aircraft-card-actions"><button class="btn primary small" data-open-action="${CA.esc(a.id)}" type="button">전체 상세</button><a class="btn small" href="${document.body.dataset.dashboardUrl||'dashboard.html'}?compare=${encodeURIComponent(a.id)}">비교</a></div>
    </article>`;
  }

  function filtered(){return CA.filterAircraft(CA.aircraft,state);}

  function openAircraft(id){
    if(!CA.aircraftMap.has(id)) return;
    state.focus=id;
    CA.updateUrl({aircraft:id},true);
    renderMap();
    CA.dispatchAircraft(id);
  }

  function renderCatalog(){
    const list=filtered(),root=document.getElementById('catalog');
    document.getElementById('resultCount').textContent=`${list.length} / ${CA.aircraft.length}개`;
    root.innerHTML=list.length?list.map(card).join(''):'<div class="catalog-empty card">검색 조건에 맞는 기체가 없습니다.</div>';
    root.querySelectorAll('[data-open-id]').forEach(b=>b.addEventListener('click',()=>openAircraft(b.dataset.openId)));
    root.querySelectorAll('[data-open-action]').forEach(b=>b.addEventListener('click',()=>openAircraft(b.dataset.openAction)));

    if(!initialHandled&&state.focus){
      initialHandled=true;
      requestAnimationFrame(()=>{
        const cardEl=root.querySelector(`[data-card-id="${CSS.escape(state.focus)}"]`);
        cardEl?.scrollIntoView({block:'center'});
        openAircraft(state.focus);
      });
    }
  }

  function bindMap(){
    const host=document.getElementById('marketMap'),tip=CA.chartTooltip();
    host.querySelectorAll('[data-aircraft-id]').forEach(g=>{
      const show=e=>{const [m,c,r,w]=(g.dataset.tooltip||'').split('|');tip.show(`<b>${CA.esc(m)}</b><br>${CA.esc(c)} · ${CA.esc(r)}<br>${CA.esc(w)}<br><small>클릭: 전체 상세</small>`,e.clientX||innerWidth/2,e.clientY||innerHeight/2);};
      g.addEventListener('pointerenter',show);g.addEventListener('pointermove',show);g.addEventListener('pointerleave',tip.hide);
      g.addEventListener('focus',()=>show({clientX:innerWidth/2,clientY:innerHeight/2}));g.addEventListener('blur',tip.hide);
      g.addEventListener('click',()=>openAircraft(g.dataset.aircraftId));
      g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' ')openAircraft(g.dataset.aircraftId);});
    });
  }

  function renderMap(){
    document.getElementById('marketMap').innerHTML=CA.Charts.positionMap(CA.aircraft,{
      role:state.mapRole,selectedIds:state.focus?[state.focus]:[],labelMode:state.mapLabels,rangeMode:state.mapRange,category:state.mapCategory
    });
    bindMap();
  }

  function init(){
    CA.setupTopNav();CA.bindAircraftModal(document.body.dataset.sourcePrefix||'../');
    options('categoryFilter',CA.sortedUnique(CA.aircraft,'category'),'전체 세그먼트');
    options('roleFilter',CA.sortedUnique(CA.aircraft,'role'),'전체 용도');
    options('manufacturerFilter',CA.sortedUnique(CA.aircraft,'manufacturer'),'전체 제조사');
    options('statusFilter',CA.sortedUnique(CA.aircraft,'statusCode'),'전체 상태');
    const mapCategory=document.getElementById('mapCategory');
    mapCategory.innerHTML='<option value="all">전체 세그먼트</option>'+CA.sortedUnique(CA.aircraft,'category').map(v=>`<option value="${CA.esc(v)}">${CA.esc(v)}</option>`).join('');

    [['search','q','input'],['categoryFilter','category','change'],['roleFilter','role','change'],['manufacturerFilter','manufacturer','change'],['statusFilter','status','change']].forEach(([id,k,ev])=>document.getElementById(id)?.addEventListener(ev,e=>{state[k]=e.target.value;renderCatalog();}));
    document.getElementById('verifiedOnly').addEventListener('change',e=>{state.verifiedOnly=e.target.checked;renderCatalog();});

    document.getElementById('mapRole').addEventListener('change',e=>{state.mapRole=e.target.value;renderMap();});
    document.getElementById('mapCategory').addEventListener('change',e=>{state.mapCategory=e.target.value;renderMap();});
    document.getElementById('mapRange').addEventListener('change',e=>{state.mapRange=e.target.value;renderMap();});
    document.getElementById('mapLabels').addEventListener('change',e=>{state.mapLabels=e.target.value;renderMap();});

    document.getElementById('exportCatalog').addEventListener('click',()=>{
      const cols=[
        {label:'Model',value:'model'},{label:'Manufacturer',value:'manufacturer'},{label:'Family',value:'family'},{label:'Role',value:'role'},{label:'Status',value:'status'},
        {label:'Typical Seats',value:a=>CA.seats(a)},{label:'MTOW t',value:'mtowT'},{label:'Range nm',value:'rangeNm'},{label:'Payload t',value:'maxPayloadT'},
        {label:'Length m',value:'lengthM'},{label:'Span m',value:'spanM'},{label:'Height m',value:'heightM'},{label:'Verification',value:'verificationGrade'}
      ];
      CA.downloadText('\ufeff'+CA.csv(filtered(),cols),'Civil_Aircraft_Catalog_v1.7.csv','text/csv;charset=utf-8');
    });

    renderCatalog();renderMap();
  }

  document.addEventListener('DOMContentLoaded',init);
})();
