(function(){
  'use strict';
  const CA=window.CA;

  function highlight(text,query){
    const s=String(text||''),q=String(query||'').trim();
    if(!q) return CA.esc(s);
    const i=s.toLocaleLowerCase('ko').indexOf(q.toLocaleLowerCase('ko'));
    if(i<0) return CA.esc(s);
    return `${CA.esc(s.slice(0,i))}<mark>${CA.esc(s.slice(i,i+q.length))}</mark>${CA.esc(s.slice(i+q.length))}`;
  }

  function init(){
    CA.setupTopNav();
    const a=CA.aircraft,s=CA.sources;
    const complete=a.filter(x=>x.verificationGrade==='A+'||x.verificationGrade==='A').length;
    const scale=a.filter(x=>x.dataQuality.hasScaleGeometry).length,pos=a.filter(x=>x.dataQuality.hasPositionData).length;
    const vals={aircraftCount:a.length,sourceCount:s.length,localPdfCount:CA.DATA.metadata.localPdfCount,completeCount:complete,scaleCount:scale,positionCount:pos};
    Object.entries(vals).forEach(([id,v])=>{const el=document.getElementById(id);if(el) el.textContent=String(v);});
    document.getElementById('categoryChart').innerHTML=CA.Charts.categoryBars(a);
    document.getElementById('qualityChart').innerHTML=CA.Charts.qualityBars(a);

    const q=document.getElementById('portalSearch'),box=document.getElementById('suggestions'),encyUrl=document.body.dataset.encyclopediaUrl||'apps/encyclopedia.html';
    let results=[],active=-1;

    function close(){box.hidden=true;active=-1;q.setAttribute('aria-expanded','false');q.removeAttribute('aria-activedescendant');}
    function matchedAlias(item,z){return (item.aliases||[]).find(alias=>CA.normalize(alias).includes(CA.normalize(z))&&CA.normalize(item.model)!==CA.normalize(alias));}
    function syncActive(){
      const nodes=[...box.querySelectorAll('.suggestion[data-index]')];
      nodes.forEach((node,i)=>node.classList.toggle('active',i===active));
      if(active>=0&&nodes[active]){q.setAttribute('aria-activedescendant',nodes[active].id);nodes[active].scrollIntoView({block:'nearest'});}else q.removeAttribute('aria-activedescendant');
    }
    function render(){
      const z=q.value.trim();
      if(!z){close();return;}
      results=a.filter(x=>CA.matches(x,z)).slice(0,10);active=-1;
      box.innerHTML=results.length?results.map((x,i)=>{
        const alias=matchedAlias(x,z),meta=[x.manufacturer,x.family,alias?`일치 별칭: ${alias}`:null].filter(Boolean).join(' · ');
        return `<a id="suggestion-${i}" class="suggestion" data-index="${i}" role="option" href="${encyUrl}?aircraft=${encodeURIComponent(x.id)}">
          <span class="suggestion-main"><b class="suggestion-title">${highlight(x.model,z)}</b><small class="suggestion-meta">${highlight(meta,z)}</small></span>
          <span class="suggestion-badge">${CA.gradeBadge(x)}</span>
        </a>`;
      }).join(''):'<div class="suggestion suggestion-empty"><span>검색 결과 없음</span></div>';
      box.hidden=false;q.setAttribute('aria-expanded','true');
      box.querySelectorAll('.suggestion[data-index]').forEach(node=>node.addEventListener('pointerenter',()=>{active=Number(node.dataset.index);syncActive();}));
    }

    q?.addEventListener('input',render);
    q?.addEventListener('keydown',e=>{
      if(e.key==='Escape'){close();return;}
      if(e.key==='ArrowDown'||e.key==='ArrowUp'){
        e.preventDefault();
        if(box.hidden) render();
        if(!results.length) return;
        active=e.key==='ArrowDown'?(active+1)%results.length:(active<=0?results.length-1:active-1);
        syncActive();return;
      }
      if(e.key==='Enter'){
        const x=results[active>=0?active:0]||a.find(v=>CA.matches(v,q.value));
        if(x){e.preventDefault();location.href=`${encyUrl}?aircraft=${encodeURIComponent(x.id)}`;}
      }
    });
    q?.addEventListener('focus',()=>{if(q.value.trim())render();});
    document.addEventListener('click',e=>{if(!box.contains(e.target)&&e.target!==q)close();});
  }

  document.addEventListener('DOMContentLoaded',init);
})();
