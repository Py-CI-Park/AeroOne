(function(){
  'use strict';
  // v1.8 포털: 전체 데이터(338KB) 없이 경량 메타(window.CIVIL_AIRCRAFT_META)만으로
  // KPI·분포 차트·검색 자동완성을 그린다. 백과/비교로 이동할 때 각 페이지가 전체 데이터를 로드한다.
  const META=window.CIVIL_AIRCRAFT_META;
  if(!META){console.error('CIVIL_AIRCRAFT_META required');return;}

  function esc(v){return String(v==null?'':v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
  function normalize(s){return String(s||'').toLowerCase().normalize('NFKD').replace(/[\s_./()\-–—]+/g,'').replace(/[^a-z0-9가-힣]/g,'');}
  function matches(item,q){const z=normalize(q);if(!z)return true;const hay=normalize([item.model,item.manufacturer,item.family,...(item.aliases||[])].join(' '));return hay.includes(z);}
  function highlight(text,query){const s=String(text||''),q=String(query||'').trim();if(!q)return esc(s);const i=s.toLocaleLowerCase('ko').indexOf(q.toLocaleLowerCase('ko'));if(i<0)return esc(s);return `${esc(s.slice(0,i))}<mark>${esc(s.slice(i,i+q.length))}</mark>${esc(s.slice(i+q.length))}`;}
  function gradeBadge(item){const d=META.gradeDefs[item.grade]||{};return `<span class="badge grade" title="${esc(d.definition||'')}">검증 ${esc(item.grade)}</span>`;}

  // 카드가 제목/부제를 이미 담으므로 SVG는 플롯만 그린다(charts.js barDistribution 과 동일한 형태).
  function barDistribution(items,colorFor){
    if(!items.length)return '<svg viewBox="0 0 820 270" role="img" aria-label="데이터 없음"><rect width="820" height="270" rx="14" fill="#fff"/><text x="410" y="140" text-anchor="middle" fill="#64748b">표시할 데이터가 없습니다</text></svg>';
    const w=820,left=222,right=66,top=24,row=58,plotW=w-left-right,height=Math.max(270,top+items.length*row+26),max=Math.max(...items.map(x=>x.value),1);
    let body=`<rect width="${w}" height="${height}" rx="14" fill="#fff"/>`;
    items.forEach((it,i)=>{
      const y=top+i*row,bw=Math.max(3,plotW*it.value/max),color=colorFor(it,i);
      body+=`<text x="16" y="${y+18}" font-size="14" font-weight="900" fill="#263b52">${esc(it.label)}</text>`;
      if(it.sublabel)body+=`<text x="16" y="${y+36}" font-size="11.5" font-weight="650" fill="#64748b">${esc(it.sublabel)}</text>`;
      body+=`<rect x="${left}" y="${y+6}" width="${bw.toFixed(1)}" height="26" rx="7" fill="${color}"/>`;
      body+=`<text x="${left+bw+10}" y="${y+24}" font-size="14" font-weight="900" fill="#1f3350">${it.value}</text>`;
    });
    return `<svg viewBox="0 0 ${w} ${height}" role="img" aria-label="분포 차트" preserveAspectRatio="xMinYMin meet"><style>text{font-family:Noto Sans KR,Pretendard,Segoe UI,Arial,sans-serif}</style>${body}</svg>`;
  }

  const QUALITY_COLORS={'A+':'#6abf9d','A':'#78a7ef','B+':'#efae7d','B':'#b89ae8','C':'#a8b2bf'};

  function init(){
    const b=document.querySelector('.mobile-menu'),nav=document.querySelector('.topnav');
    if(b&&nav)b.addEventListener('click',()=>{const open=nav.classList.toggle('open');b.setAttribute('aria-expanded',String(open));});

    Object.entries(META.counts).forEach(([id,v])=>{const el=document.getElementById(id);if(el)el.textContent=String(v);});
    const cat=document.getElementById('categoryChart');if(cat)cat.innerHTML=barDistribution(META.categoryDist,()=>'#5b8def');
    const qual=document.getElementById('qualityChart');if(qual)qual.innerHTML=barDistribution(META.qualityDist,it=>QUALITY_COLORS[it.label]||'#a8b2bf');

    const q=document.getElementById('portalSearch'),box=document.getElementById('suggestions'),encyUrl=document.body.dataset.encyclopediaUrl||'apps/encyclopedia.html';
    if(!q||!box)return;
    let results=[],active=-1;
    function close(){box.hidden=true;active=-1;q.setAttribute('aria-expanded','false');q.removeAttribute('aria-activedescendant');}
    function matchedAlias(item,z){return (item.aliases||[]).find(alias=>normalize(alias).includes(normalize(z))&&normalize(item.model)!==normalize(alias));}
    function syncActive(){const nodes=[...box.querySelectorAll('.suggestion[data-index]')];nodes.forEach((node,i)=>node.classList.toggle('active',i===active));if(active>=0&&nodes[active]){q.setAttribute('aria-activedescendant',nodes[active].id);nodes[active].scrollIntoView({block:'nearest'});}else q.removeAttribute('aria-activedescendant');}
    function render(){
      const z=q.value.trim();if(!z){close();return;}
      results=META.searchIndex.filter(x=>matches(x,z)).slice(0,10);active=-1;
      box.innerHTML=results.length?results.map((x,i)=>{
        const alias=matchedAlias(x,z),meta=[x.manufacturer,x.family,alias?`일치 별칭: ${alias}`:null].filter(Boolean).join(' · ');
        return `<a id="suggestion-${i}" class="suggestion" data-index="${i}" role="option" href="${encyUrl}?aircraft=${encodeURIComponent(x.id)}"><span class="suggestion-main"><b class="suggestion-title">${highlight(x.model,z)}</b><small class="suggestion-meta">${highlight(meta,z)}</small></span><span class="suggestion-badge">${gradeBadge(x)}</span></a>`;
      }).join(''):'<div class="suggestion suggestion-empty"><span>검색 결과 없음</span></div>';
      box.hidden=false;q.setAttribute('aria-expanded','true');
      box.querySelectorAll('.suggestion[data-index]').forEach(node=>node.addEventListener('pointerenter',()=>{active=Number(node.dataset.index);syncActive();}));
    }
    q.addEventListener('input',render);
    q.addEventListener('keydown',e=>{
      if(e.key==='Escape'){close();return;}
      if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();if(box.hidden)render();if(!results.length)return;active=e.key==='ArrowDown'?(active+1)%results.length:(active<=0?results.length-1:active-1);syncActive();return;}
      if(e.key==='Enter'){const x=results[active>=0?active:0]||META.searchIndex.find(v=>matches(v,q.value));if(x){e.preventDefault();location.href=`${encyUrl}?aircraft=${encodeURIComponent(x.id)}`;}}
    });
    q.addEventListener('focus',()=>{if(q.value.trim())render();});
    document.addEventListener('click',e=>{if(!box.contains(e.target)&&e.target!==q)close();});
  }

  document.addEventListener('DOMContentLoaded',init);
})();
