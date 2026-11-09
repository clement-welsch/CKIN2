(() => {
  'use strict';
  const root=document.getElementById('favorite-views');
  if(!root)return;
  const key='ckin2.views.v1', select=document.getElementById('favorite-select'), name=document.getElementById('favorite-name'), status=document.getElementById('favorite-status');
  const buttons=['save','open','rename','delete'].map(x=>document.getElementById('favorite-'+x));
  const pages=new Set(['overview','inventory','categories','item','performance','forecasts','community','reconciliation','quality','comparison']);
  const fields=new Set(['page','category','item_id','start','end','period','search','sort','direction','price_status','quantity_status','page_number','page_size','observation_account','comparison_before','comparison_after']);
  function validURL(value){
    if(typeof value!=='string'||value.length>4000||!value.startsWith('/?'))return false;
    const url=new URL(value,location.origin);
    if(url.origin!==location.origin||url.pathname!=='/'||url.hash||!pages.has(url.searchParams.get('page')||'overview'))return false;
    for(const [k,v] of url.searchParams){
      if(!fields.has(k)||url.searchParams.getAll(k).length!==1||v.length>500)return false;
      if(k==='category'&&!['all','case','skin','souvenir','sticker','charm','agent'].includes(v))return false;
      if(k==='item_id'&&v&&!/^[0-9a-f-]{36}$/.test(v))return false;
      if(['start','end','comparison_before','comparison_after'].includes(k)&&v&&(!/^\d{4}-\d{2}-\d{2}(T[\d:.]+)?$/.test(v)||!Number.isFinite(Date.parse(v))))return false;
      if(k==='period'&&!['all','custom','30d','90d','365d'].includes(v))return false;
      if(k==='sort'&&!['item_name','category','quantity','unit_price','price_date','market_value'].includes(v))return false;
      if(k==='direction'&&!['asc','desc'].includes(v))return false;
      if(k==='price_status'&&!['all','recent','stale','missing','invalid'].includes(v))return false;
      if(k==='quantity_status'&&!['all','known','unknown'].includes(v))return false;
      if(k==='page_size'&&!['10','25','50','100'].includes(v))return false;
      if(k==='page_number'&&(!/^\d+$/.test(v)||Number(v)<1))return false;
    }
    return true;
  }
  let views=[], writable=true;
  function message(text){status.textContent=text;}
  function redraw(chosen=''){
    select.replaceChildren(new Option('Choisir une vue',''));
    for(const view of views)select.add(new Option(view.name,view.id));
    select.value=chosen;
    buttons[1].disabled=!select.value;buttons[2].disabled=!writable||!select.value;buttons[3].disabled=!writable||!select.value;
  }
  try{
    const raw=JSON.parse(localStorage.getItem(key)||'[]');
    if(!Array.isArray(raw)||raw.length>100)throw new Error('invalid');
    const ids=new Set();
    views=raw.filter(v=>v&&typeof v.id==='string'&&v.id.length>0&&v.id.length<100&&!ids.has(v.id)&&ids.add(v.id)&&typeof v.name==='string'&&v.name.trim().length>0&&v.name.length<=80&&validURL(v.url));
    if(views.length!==raw.length)message('Certaines vues invalides ou obsolètes ont été ignorées.');
  }catch(error){
    if(error instanceof SyntaxError){message('Liste de favoris invalide : aucune vue chargée. Une sauvegarde explicite remplacera cette liste.');}
    else {writable=false;buttons[0].disabled=true;message('Stockage local indisponible. La consultation du portefeuille reste disponible.');}
  }
  function persist(next,chosen){
    try{localStorage.setItem(key,JSON.stringify(next));views=next;redraw(chosen);return true;}
    catch{writable=false;buttons[0].disabled=true;redraw(select.value);message('Enregistrement impossible : stockage local indisponible.');return false;}
  }
  select.addEventListener('change',()=>{const v=views.find(v=>v.id===select.value);if(v)name.value=v.name;redraw(select.value);});
  buttons[0].addEventListener('click',()=>{
    const label=name.value.trim(),url=root.dataset.currentUrl;
    if(!label){message('Saisir un nom pour cette vue.');return;}
    if(!validURL(url)){message('Cette sélection ne peut pas être enregistrée.');return;}
    if(views.length>=100){message('Limite de 100 vues atteinte.');return;}
    const id=Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
    if(persist([...views,{id,name:label,url}],id))message('Vue enregistrée localement.');
  });
  buttons[1].addEventListener('click',()=>{const v=views.find(v=>v.id===select.value);if(v&&validURL(v.url))location.assign(v.url);else message('Vue indisponible ou obsolète.');});
  buttons[2].addEventListener('click',()=>{const label=name.value.trim();if(!label){message('Saisir un nom.');return;}if(persist(views.map(v=>v.id===select.value?{...v,name:label}:v),select.value))message('Vue renommée.');});
  buttons[3].addEventListener('click',()=>{if(persist(views.filter(v=>v.id!==select.value),''))message('Vue supprimée.');});
  redraw();
})();
