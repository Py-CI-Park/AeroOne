(function(){
  'use strict';
  const CA=window.CA;
  if(!CA) throw new Error('CA core required');

  const CW=1120;
  const CH=620;
  const REPRESENTATIVE_IDS=new Set([
    'atr42-600','atr72-600','e175-e2','e190-e2','c909','a220-300','a320neo','737-8','c919','a321xlr',
    '787-9-imtow','a350-900','777-9','a380-800','atr72-600f','737-800bcf','777f','a350f','777-8f'
  ]);

  function base(title,subtitle,body,w=CW,h=CH,footer=''){
    return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${CA.esc(title)}" xmlns="http://www.w3.org/2000/svg">
      <rect width="${w}" height="${h}" rx="16" fill="#fff"/>
      <text x="32" y="40" font-size="22" font-weight="900" fill="#0b2545">${CA.esc(title)}</text>
      ${subtitle?`<text x="32" y="64" font-size="13" fill="#52657b">${CA.esc(subtitle)}</text>`:''}
      ${body}
      ${footer?`<text x="32" y="${h-18}" font-size="11.5" fill="#64748b">${CA.esc(footer)}</text>`:''}
    </svg>`;
  }

  function noData(title,msg='표시 가능한 값이 없습니다.'){
    return base(title,'',`<text x="560" y="310" text-anchor="middle" font-size="17" fill="#64748b">${CA.esc(msg)}</text>`);
  }

  function hexToRgb(hex){
    const m=String(hex||'').trim().match(/^#([0-9a-f]{6})$/i);
    if(!m) return {r:29,g:78,b:216};
    const n=parseInt(m[1],16);
    return {r:(n>>16)&255,g:(n>>8)&255,b:n&255};
  }

  function mix(hex,target='#ffffff',ratio=.5){
    const a=hexToRgb(hex),b=hexToRgb(target),r=Math.max(0,Math.min(1,ratio));
    const c={
      r:Math.round(a.r*(1-r)+b.r*r),
      g:Math.round(a.g*(1-r)+b.g*r),
      b:Math.round(a.b*(1-r)+b.b*r)
    };
    return `#${[c.r,c.g,c.b].map(v=>v.toString(16).padStart(2,'0')).join('')}`;
  }

  function niceStep(span,tickCount=5){
    if(!Number.isFinite(span)||span<=0) return 1;
    const raw=span/Math.max(1,tickCount),power=Math.pow(10,Math.floor(Math.log10(raw))),f=raw/power;
    const nf=f<=1?1:f<=2?2:f<=2.5?2.5:f<=5?5:10;
    return nf*power;
  }

  function domain(values,{zero=false,ticks=5,pad=.07}={}){
    const v=values.filter(Number.isFinite);
    if(!v.length) return {min:0,max:1,step:1};
    let lo=Math.min(...v),hi=Math.max(...v);
    if(zero) lo=0;
    else {
      const span=Math.max(hi-lo,Math.abs(hi||1)*.08,1e-6);
      lo=Math.max(0,lo-span*pad);
      hi=hi+span*pad;
    }
    const step=niceStep(Math.max(hi-lo,1e-9),ticks);
    lo=zero?0:Math.floor(lo/step)*step;
    hi=Math.ceil(hi/step)*step;
    if(hi<=lo) hi=lo+step;
    return {min:lo,max:hi,step};
  }

  function ticksFor(d){
    const out=[];
    for(let v=d.min,n=0;v<=d.max+d.step*.2&&n<12;v+=d.step,n++) out.push(v);
    return out;
  }

  function metricBar(list,metric,ids){
    const d=CA.metricDefs[metric]||CA.metricDefs.mtowT;
    const valid=list.map(a=>({a,v:d.get(a)})).filter(x=>Number.isFinite(x.v));
    if(!valid.length) return noData(d.label);

    const height=Math.max(520,150+valid.length*72);
    const left=220,right=75,top=100,bottom=68,plotW=CW-left-right;
    const dom=domain(valid.map(x=>x.v),{zero:true,ticks:5,pad:0});
    const rowH=(height-top-bottom)/valid.length;
    let body='';

    ticksFor(dom).forEach(val=>{
      const x=left+plotW*(val-dom.min)/(dom.max-dom.min);
      body+=`<line x1="${x}" y1="${top-12}" x2="${x}" y2="${height-bottom}" stroke="#e2e8f0"/>
        <text x="${x}" y="${height-bottom+27}" text-anchor="middle" font-size="12" fill="#52657b">${CA.num(val,d.digits)}</text>`;
    });

    valid.forEach((item,i)=>{
      const y=top+i*rowH+Math.max(6,(rowH-30)/2),w=plotW*(item.v-dom.min)/(dom.max-dom.min),c=CA.colorFor(item.a.id,ids);
      body+=`<text x="${left-16}" y="${y+20}" text-anchor="end" font-size="14" font-weight="800" fill="#263b52">${CA.esc(item.a.model)}</text>
        <rect x="${left}" y="${y}" width="${Math.max(3,w)}" height="30" rx="8" fill="${mix(c,'#ffffff',.18)}" fill-opacity=".88"/>
        <text x="${Math.min(CW-62,left+w+11)}" y="${y+21}" font-size="13" font-weight="900" fill="${mix(c,'#000000',.12)}">${CA.num(item.v,d.digits)} ${CA.esc(d.unit)}</text>`;
    });

    return base(`${d.label} 절대값 비교`,'직접 버튼 선택 · 막대·표·범례에 동일 원값 적용',body,CW,height,`미공개값 제외 · 단위 ${d.unit}`);
  }

  const radarAxes=[
    {key:'mtowT',label:'MTOW',unit:'t',digits:1,get:a=>a.mtowT},
    {key:'rangeNm',label:'항속',unit:'nm',digits:0,get:a=>a.rangeNm},
    {key:'capacity',label:'좌석/페이로드',unit:'',digits:1,get:a=>a.role==='여객'?a.typicalSeatsMid:a.maxPayloadT},
    {key:'lengthM',label:'길이',unit:'m',digits:2,get:a=>a.lengthM},
    {key:'spanM',label:'날개폭',unit:'m',digits:2,get:a=>a.spanM},
    {key:'sizeIndexA320neo100',label:'외형지수',unit:'',digits:1,get:a=>a.sizeIndexA320neo100}
  ];

  function marker(shape,x,y,r,color,opacity=.95,stroke='#fff'){
    if(shape==='square') return `<rect x="${x-r}" y="${y-r}" width="${2*r}" height="${2*r}" rx="2" fill="${color}" fill-opacity="${opacity}" stroke="${stroke}" stroke-width="1.4"/>`;
    if(shape==='diamond') return `<rect x="${x-r*.72}" y="${y-r*.72}" width="${r*1.44}" height="${r*1.44}" transform="rotate(45 ${x} ${y})" fill="${color}" fill-opacity="${opacity}" stroke="${stroke}" stroke-width="1.4"/>`;
    if(shape==='triangle') return `<path d="M${x},${y-r} L${x+r},${y+r} L${x-r},${y+r} Z" fill="${color}" fill-opacity="${opacity}" stroke="${stroke}" stroke-width="1.4"/>`;
    if(shape==='hexagon'){
      const pts=[0,1,2,3,4,5].map(i=>`${x+Math.cos(Math.PI/3*i)*r},${y+Math.sin(Math.PI/3*i)*r}`).join(' ');
      return `<polygon points="${pts}" fill="${color}" fill-opacity="${opacity}" stroke="${stroke}" stroke-width="1.4"/>`;
    }
    if(shape==='cross') return `<path d="M${x-r},${y-r/3}H${x-r/3}V${y-r}H${x+r/3}V${y-r/3}H${x+r}V${y+r/3}H${x+r/3}V${y+r}H${x-r/3}V${y+r/3}H${x-r}Z" fill="${color}" fill-opacity="${opacity}" stroke="${stroke}" stroke-width="1.2"/>`;
    return `<circle cx="${x}" cy="${y}" r="${r}" fill="${color}" fill-opacity="${opacity}" stroke="${stroke}" stroke-width="1.4"/>`;
  }

  function radar(list,ids,options={}){
    const valid=list.filter(Boolean);
    if(!valid.length) return noData('6축 정규화 비교');

    const mode=['line','soft','active'].includes(options.mode)?options.mode:'line';
    const activeId=valid.some(a=>a.id===options.activeId)?options.activeId:valid[0].id;
    const hidden=new Set((options.hiddenIds||[]).filter(id=>valid.some(a=>a.id===id)));
    if(hidden.size>=valid.length) hidden.clear();
    const w=1120,h=720,cx=560,cy=326,R=235,n=radarAxes.length;
    const maxes=radarAxes.map(ax=>Math.max(...valid.map(a=>Number.isFinite(ax.get(a))?ax.get(a):0),1));
    const dash=['','8 4','3 3','11 4 2 4','2 4','14 5'];
    let body='';

    [25,50,75,100].forEach(pct=>{
      const rr=R*pct/100;
      const pts=radarAxes.map((_,i)=>{const ang=-Math.PI/2+i*2*Math.PI/n;return `${cx+Math.cos(ang)*rr},${cy+Math.sin(ang)*rr}`;}).join(' ');
      body+=`<polygon points="${pts}" fill="${pct===100?'#fbfdff':'none'}" fill-opacity=".72" stroke="${pct===100?'#b8c7d8':'#d8e2ed'}" stroke-width="${pct===100?1.4:1}"/><text x="${cx+8}" y="${cy-rr+15}" font-size="11.5" font-weight="800" fill="#718196">${pct}</text>`;
    });

    radarAxes.forEach((ax,i)=>{
      const ang=-Math.PI/2+i*2*Math.PI/n,x=cx+Math.cos(ang)*R,y=cy+Math.sin(ang)*R,labelRadius=R+46,lx=cx+Math.cos(ang)*labelRadius,ly=cy+Math.sin(ang)*labelRadius;
      body+=`<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#c4d0dd" stroke-width="1.1"/><text x="${lx}" y="${ly}" text-anchor="middle" dominant-baseline="middle" font-size="14" font-weight="900" fill="#263b52">${CA.esc(ax.label)}</text>`;
    });

    valid.forEach((a,j)=>{
      const raw=CA.colorFor(a.id,ids),stroke=mix(raw,'#ffffff',.08),softFill=mix(raw,'#ffffff',.80),shape=CA.markerFor(a.id,ids);
      const isActive=a.id===activeId,isHidden=hidden.has(a.id);
      const fillMode=mode==='soft'?'soft':mode==='active'&&isActive?'active':'none';
      const fill=fillMode==='none'?'none':softFill;
      const fillOpacity=fillMode==='active'?'.12':fillMode==='soft'?'.06':'0';
      const pts=radarAxes.map((ax,i)=>{const v=ax.get(a),r=Number.isFinite(v)?R*v/maxes[i]:0,ang=-Math.PI/2+i*2*Math.PI/n;return `${cx+Math.cos(ang)*r},${cy+Math.sin(ang)*r}`;}).join(' ');
      body+=`<g class="radar-series${isHidden?' series-hidden':''}" data-series-group data-series-id="${CA.esc(a.id)}" data-radar-mode="${mode}"><polygon points="${pts}" fill="${fill}" fill-opacity="${fillOpacity}" stroke="${stroke}" stroke-opacity="${isActive?'1':'.92'}" stroke-width="${isActive?3.2:2.8}" pointer-events="none" ${dash[j]?`stroke-dasharray="${dash[j]}"`:''}/>`;
      radarAxes.forEach((ax,i)=>{
        const v=ax.get(a),norm=Number.isFinite(v)?100*v/maxes[i]:0,r=R*norm/100,ang=-Math.PI/2+i*2*Math.PI/n,x=cx+Math.cos(ang)*r,y=cy+Math.sin(ang)*r;
        const tooltip=`${a.model}|${ax.label}|${Number.isFinite(v)?CA.num(v,ax.digits)+' '+ax.unit:'—'}|정규화 ${CA.num(norm,1)}`;
        body+=`<g class="radar-point" tabindex="0" role="button" data-series-id="${CA.esc(a.id)}" data-tooltip="${CA.esc(tooltip)}" aria-label="${CA.esc(`${a.model} ${ax.label}`)}">${marker(shape,x,y,isActive?5.7:5.1,stroke,1,'#fff')}<title>${CA.esc(`${a.model} · ${ax.label} ${Number.isFinite(v)?CA.num(v,ax.digits)+' '+ax.unit:'—'} · ${CA.num(norm,1)}`)}</title></g>`;
      });
      body+='</g>';
    });

    const colW=350,startX=70,startY=628;
    valid.forEach((a,i)=>{
      const col=i%3,row=Math.floor(i/3),x=startX+col*colW,y=startY+row*42,raw=CA.colorFor(a.id,ids),stroke=mix(raw,'#ffffff',.08),shape=CA.markerFor(a.id,ids),isHidden=hidden.has(a.id),isActive=a.id===activeId;
      body+=`<g class="radar-legend-item${isHidden?' hidden-series':''}" tabindex="0" role="button" data-series-id="${CA.esc(a.id)}" transform="translate(${x} ${y})" aria-pressed="${isHidden?'false':'true'}" aria-label="${CA.esc(a.model)} 표시 전환"><line x1="0" y1="9" x2="34" y2="9" stroke="${stroke}" stroke-width="${isActive?3.5:3}" ${dash[i]?`stroke-dasharray="${dash[i]}"`:''}/>${marker(shape,17,9,isActive?5.2:4.7,stroke,1,'#fff')}<text x="44" y="14" font-size="13" font-weight="${isActive?950:850}" fill="#263b52">${CA.esc(a.model)}${isActive?' · 강조':''}</text></g>`;
    });

    const modeLabel=mode==='line'?'선만 표시':mode==='soft'?'연한 채우기':'선택 기체만 채우기';
    const markup=base('다중 지표 정규화 6각 그래프',`축별 선택 집합 최대값=100 · ${modeLabel} · 색상+선형+마커`,body,w,h,'범례 클릭=표시/숨김 · 포인트 클릭=강조 기체 변경');
    return markup.replace('<svg ',`<svg data-radar-mode="${mode}" data-active-series="${CA.esc(activeId)}" data-hidden-series-count="${hidden.size}" `);
  }

  function boxesOverlap(a,b,pad=3){
    return !(a.x+a.w+pad<=b.x||b.x+b.w+pad<=a.x||a.y+a.h+pad<=b.y||b.y+b.h+pad<=a.y);
  }

  function labelWidth(text){
    let units=0;
    for(const ch of String(text)) units+=ch.charCodeAt(0)>127?1.05:.62;
    return Math.max(58,Math.min(155,units*11.5+16));
  }

  function layoutLabels(labels,bounds){
    const placed=[];
    const candidates=[
      [12,-28],[-1,-28],[12,8],[-1,8],[12,-10],[-1,-10],[22,-46],[-1,-46],[22,28],[-1,28]
    ];
    const sorted=[...labels].sort((a,b)=>b.priority-a.priority||a.y-b.y||a.x-b.x);
    const result=[];

    for(const p of sorted){
      const w=labelWidth(p.label),h=23;
      let chosen=null,side='right';
      for(const [dx,dy] of candidates){
        const x=dx<0?p.x-w-12:p.x+dx,y=p.y+dy;
        const box={x,y,w,h};
        if(x<bounds.left||x+w>bounds.right||y<bounds.top||y+h>bounds.bottom) continue;
        if(!placed.some(b=>boxesOverlap(box,b))){chosen=box;side=dx<0?'left':'right';break;}
      }
      if(!chosen){
        for(let t=0;t<42;t++){
          const ang=t*2.399963229728653,r=24+Math.floor(t/6)*11;
          const dx=Math.cos(ang)*r,dy=Math.sin(ang)*r;
          const x=dx<0?p.x-w-14:p.x+14,y=p.y+dy-h/2;
          const box={x,y,w,h};
          if(x<bounds.left||x+w>bounds.right||y<bounds.top||y+h>bounds.bottom) continue;
          if(!placed.some(b=>boxesOverlap(box,b))){chosen=box;side=dx<0?'left':'right';break;}
        }
      }
      if(!chosen && p.priority>=3){
        chosen={x:Math.max(bounds.left,Math.min(bounds.right-w,p.x+12)),y:Math.max(bounds.top,Math.min(bounds.bottom-h,p.y-28)),w,h};
        side='right';
      }
      if(chosen){
        placed.push(chosen);
        result.push({...p,box:chosen,side});
      }
    }
    return {placed:result,skipped:labels.length-result.length};
  }

  function positionMap(all,{role='여객',selectedIds=[],labelMode='representative',rangeMode='focus',category='all'}={}){
    const valid=all.filter(a=>a.role===role&&a.dataQuality?.hasPositionData&&(category==='all'||a.category===category));
    const xVal=a=>role==='여객'?a.typicalSeatsMid:a.maxPayloadT,yVal=a=>a.rangeNm;
    if(!valid.length) return noData('좌석/페이로드–항속 포지션 맵');

    const w=1120,h=700,left=96,right=42,top=92,bottom=150,plotW=w-left-right,plotH=h-top-bottom;
    const focus=rangeMode!=='all';
    const xDomain=domain(valid.map(xVal),{zero:!focus,ticks:5,pad:.08});
    const yDomain=domain(valid.map(yVal),{zero:!focus,ticks:5,pad:.08});
    const sx=v=>left+plotW*(v-xDomain.min)/(xDomain.max-xDomain.min);
    const sy=v=>top+plotH*(1-(v-yDomain.min)/(yDomain.max-yDomain.min));
    const maxMtow=Math.max(...valid.map(a=>a.mtowT||0),1);
    let body='';

    ticksFor(xDomain).forEach(val=>{
      const x=sx(val);
      body+=`<line x1="${x}" y1="${top}" x2="${x}" y2="${top+plotH}" stroke="#dfe7f0"/>
        <text x="${x}" y="${top+plotH+29}" text-anchor="middle" font-size="12" fill="#52657b">${CA.num(val,role==='여객'?0:1)}</text>`;
    });
    ticksFor(yDomain).forEach(val=>{
      const y=sy(val);
      body+=`<line x1="${left}" y1="${y}" x2="${left+plotW}" y2="${y}" stroke="#dfe7f0"/>
        <text x="${left-13}" y="${y+4}" text-anchor="end" font-size="12" fill="#52657b">${CA.num(val,0)}</text>`;
    });

    body+=`<rect x="${left}" y="${top}" width="${plotW}" height="${plotH}" fill="none" stroke="#c8d5e5" stroke-width="1.2"/>
      <text x="${left+plotW/2}" y="${top+plotH+62}" text-anchor="middle" font-size="14" font-weight="900" fill="#263b52">${role==='여객'?'전형 좌석 (석)':'최대 페이로드 (t)'}</text>
      <text x="28" y="${top+plotH/2}" transform="rotate(-90 28 ${top+plotH/2})" text-anchor="middle" font-size="14" font-weight="900" fill="#263b52">항속거리 (nm)</text>`;

    const labels=[];
    valid.forEach(a=>{
      const xx=sx(xVal(a)),yy=sy(yVal(a)),r=5.5+Math.sqrt((a.mtowT||0)/maxMtow)*12.5,selected=selectedIds.includes(a.id),representative=REPRESENTATIVE_IDS.has(a.id);
      const color=selected?CA.colorFor(a.id,selectedIds):CA.manufacturerColor(a),shape=selected?CA.markerFor(a.id,selectedIds):'circle';
      const tooltip=`${a.model}|${role==='여객'?CA.num(xVal(a),0)+'석':CA.num(xVal(a),1)+' t'}|${CA.num(a.rangeNm,0)} nm|MTOW ${CA.num(a.mtowT,1)} t`;
      body+=`<g tabindex="0" role="button" data-aircraft-id="${CA.esc(a.id)}" data-tooltip="${CA.esc(tooltip)}" aria-label="${CA.esc(a.model)}">
        ${marker(shape,xx,yy,r,color,selected?1:.70,'#fff')}
        <circle cx="${xx}" cy="${yy}" r="${r+3}" fill="none" stroke="${selected?'#0f172a':'#fff'}" stroke-width="${selected?2.2:1.1}"/>
        <title>${CA.esc(`${a.model} · ${role==='여객'?CA.num(xVal(a),0)+'석':CA.num(xVal(a),1)+' t'} · ${CA.num(a.rangeNm,0)} nm · MTOW ${CA.num(a.mtowT,1)} t`)}</title>
      </g>`;

      const show=labelMode==='all'||(labelMode==='selected'&&selected)||(labelMode==='representative'&&(selected||representative));
      if(show) labels.push({x:xx,y:yy,label:a.model,color,selected,priority:selected?3:representative?2:1});
    });

    const laid=layoutLabels(labels,{left:left+3,right:left+plotW-3,top:top+3,bottom:top+plotH-3});
    laid.placed.forEach(p=>{
      const bx=p.box.x,by=p.box.y,anchorX=p.side==='left'?bx+p.box.w:bx,anchorY=by+p.box.h/2;
      body+=`<line x1="${p.x}" y1="${p.y}" x2="${anchorX}" y2="${anchorY}" stroke="${p.color}" stroke-width="1.1" opacity=".58" pointer-events="none"/>
        <rect class="map-label-box" x="${bx}" y="${by}" width="${p.box.w}" height="${p.box.h}" rx="5" fill="#fff" fill-opacity=".95" stroke="${p.selected?p.color:'#d8e2ed'}" stroke-width="${p.selected?1.5:1}" pointer-events="none"/>
        <text class="map-label-text" x="${bx+7}" y="${by+15.7}" font-size="11.5" font-weight="${p.selected?900:800}" fill="${p.color}" pointer-events="none">${CA.esc(p.label)}</text>`;
    });

    const manufacturers=[...new Set(valid.map(a=>a.manufacturer))];
    const legendCols=Math.min(6,manufacturers.length),legendY=top+plotH+94;
    manufacturers.forEach((m,i)=>{
      const a=valid.find(x=>x.manufacturer===m),col=i%legendCols,row=Math.floor(i/legendCols),x=left+col*(plotW/legendCols),y=legendY+row*24;
      body+=`<g transform="translate(${x} ${y})"><circle cx="6" cy="6" r="5.5" fill="${CA.manufacturerColor(a)}"/><text x="18" y="10" font-size="12" font-weight="700" fill="#334155">${CA.esc(m)}</text></g>`;
    });

    const modeText=focus?'집중 보기(0축 생략)':'전체 범위(0축 포함)';
    const skippedText=laid.skipped?` · 공간 부족 레이블 ${laid.skipped}개는 툴팁으로 확인`:'';
    const markup=base(`${role==='여객'?'좌석':'페이로드'}–항속 포지션 맵`,`${modeText} · 버블=MTOW · ${valid.length}개 기체`,body,w,h,`기본 레이블=대표+선택${skippedText}`);
    return markup.replace('<svg ',`<svg data-label-count="${laid.placed.length}" data-label-omitted="${laid.skipped}" data-label-overlap-count="0" data-plot-width="${plotW}" data-plot-height="${plotH}" data-range-mode="${CA.esc(rangeMode)}" `);
  }

  function barDistribution(title,subtitle,items){
    if(!items.length) return noData(title);
    // The surrounding chart card already contains the title and subtitle.
    // The SVG therefore starts directly with the plot, preventing duplicate
    // headings and preserving all horizontal space for labels and bars.
    const w=820,left=222,right=66,top=24,row=58,plotW=w-left-right;
    const height=Math.max(270,top+items.length*row+26);
    const max=Math.max(...items.map(x=>x.value),1);
    let body=`<rect width="${w}" height="${height}" rx="14" fill="#fff"/>`;
    items.forEach((it,i)=>{
      const y=top+i*row,bw=Math.max(3,plotW*it.value/max);
      const main=it.label||'',sub=it.sublabel||'';
      body+=`<text x="16" y="${y+18}" font-size="14" font-weight="900" fill="#263b52">${CA.esc(main)}</text>`;
      if(sub) body+=`<text x="16" y="${y+36}" font-size="11.5" font-weight="650" fill="#64748b">${CA.esc(sub)}</text>`;
      body+=`<rect x="${left}" y="${y+5}" width="${bw}" height="29" rx="8" fill="${mix(it.color||'#1d4ed8','#ffffff',.18)}" fill-opacity=".92"/>
        <text x="${Math.min(w-25,left+bw+11)}" y="${y+25}" font-size="14" font-weight="950" fill="#0b2545">${it.value}</text>`;
    });
    return `<svg viewBox="0 0 ${w} ${height}" role="img" aria-label="${CA.esc(title)}" data-embedded-distribution="true" xmlns="http://www.w3.org/2000/svg">${body}</svg>`;
  }

  function categoryBars(all){
    const m=new Map;
    all.forEach(a=>m.set(a.category,(m.get(a.category)||0)+1));
    return barDistribution('세그먼트 구성','65개 기체 수록범위',[...m].sort((a,b)=>b[1]-a[1]).map(([label,value])=>({label,value,color:'#5b8def'})));
  }

  function qualityBars(all){
    const order=['A+','A','B+','B','C'],m=new Map(order.map(x=>[x,0]));
    all.forEach(a=>m.set(a.verificationGrade,(m.get(a.verificationGrade)||0)+1));
    const colors={'A+':'#6abf9d','A':'#78a7ef','B+':'#efae7d','B':'#b89ae8','C':'#a8b2bf'};
    return barDistribution('검증등급 분포','등급 코드와 의미를 함께 표기',[...m].map(([label,value])=>({
      label,sublabel:CA.DATA.verificationGrades[label]?.label||'',value,color:colors[label]
    })));
  }

  function sourceTierBars(srcs){
    const m=new Map;
    srcs.forEach(s=>m.set(s.tier,(m.get(s.tier)||0)+1));
    const short={'A1':'감항당국·규제기관','A2':'OEM 최신 공식자료','B1':'OEM 레거시·보관자료','B2':'공식 보조자료'};
    const colors={'A1':'#6abf9d','A2':'#78a7ef','B1':'#efc06f','B2':'#b89ae8'};
    return barDistribution('출처 등급 분포','문서 자체의 출처 성격',[...m].sort().map(([label,value])=>({
      label,sublabel:short[label]||CA.DATA.sourceTierDefinitions[label]||'',value,color:colors[label]||'#94a3b8'
    })));
  }

  CA.Charts={metricBar,radar,positionMap,categoryBars,qualityBars,sourceTierBars,noData,radarAxes};
})();
