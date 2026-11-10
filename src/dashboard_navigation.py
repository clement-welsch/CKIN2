"""Compatible URL state, explicit period bounds and browser-local view controls."""

from html import escape
from urllib.parse import urlencode

import pandas as pd

from portfolio_data import _parse_dates

COMMON={'category','item_id','end'}
PERIOD_PAGES={'categories','item','performance','forecasts','community','comparison'}
INVENTORY={'search','sort','direction','price_status','quantity_status','page_number','page_size'}
FIELDS={p:COMMON | ({'start','period'} if p in PERIOD_PAGES else set()) for p in ('overview','categories','item','performance','forecasts','community','reconciliation','inventory','quality','comparison')}
FIELDS['item']|={'search'};FIELDS['inventory']|=INVENTORY
FIELDS['reconciliation']|={'observation_account'}
FIELDS['comparison']|={'comparison_before','comparison_after'}
LABELS={'category':'Catégorie','item_id':'Objet','start':'Depuis','end':'Jusqu’au','search':'Recherche','sort':'Tri','direction':'Ordre','price_status':'État des prix','quantity_status':'Quantités','page_number':'Page','page_size':'Taille de page','observation_account':'Compte observé','comparison_before':'Snapshot initial','comparison_after':'Snapshot final','period':'Période'}


def normalize(query,now):
    query=dict(query);page=query.get('page','overview')
    if page not in FIELDS:raise ValueError('Unknown dashboard view')
    unknown=set(query)-set().union(*FIELDS.values())-{'page','notice'}
    if unknown:raise ValueError('Unknown filter')
    notes=[]
    notice=query.pop('notice','')
    if len(notice)>500:raise ValueError('Invalid navigation notice')
    if notice:notes.append(notice)
    for key in list(query):
        if key!='page' and key not in FIELDS[page]:
            query.pop(key);notes.append(LABELS[key]+' réinitialisé : sans effet dans cette vue.')
    period=query.pop('period','custom')
    if period not in ('custom','all','30d','90d','365d'):raise ValueError('Unknown period')
    if period=='all':
        query.pop('start',None);query.pop('end',None)
    elif period!='custom':
        anchor=_parse_dates(pd.Series([query.get('end') or now]),'period end').iloc[0]
        anchor=min(anchor,pd.Timestamp(now)).normalize()
        query['end']=anchor.date().isoformat()
        query['start']=(anchor-pd.Timedelta(days=int(period[:-1]))).date().isoformat()
    return query,notes,period


def target_url(state,page):
    dropped=[LABELS[k] for k,v in state.items() if v and k not in FIELDS[page] and k!='page']
    chosen={k:v for k,v in state.items() if v and k in FIELDS[page]}
    if dropped:chosen['notice']='Filtres réinitialisés dans cette vue : '+', '.join(dropped)+'.'
    return '/?'+urlencode({'page':page,**chosen})


def active_filters(state,page,names=None):
    chips=[]
    for key,value in state.items():
        if key=='page' or not value or (key=='category' and value=='all'):continue
        remaining={k:v for k,v in state.items() if k!=key}
        if key in ('start','end'):remaining.pop('period',None)
        url=target_url(remaining,page)
        display=str(value)
        translations={'all':'Tous','case':'Caisses','skin':'Skins','souvenir':'Souvenirs','sticker':'Stickers','charm':'Charms','agent':'Agents','asc':'Croissant','desc':'Décroissant','item_name':'Nom','category':'Catégorie','quantity':'Quantité','unit_price':'Prix','price_date':'Date du prix','market_value':'Valeur connue','recent':'Prix récent','stale':'Prix ancien','missing':'Prix absent','invalid':'Prix invalides','known':'Renseignées','unknown':'Inconnues','30d':'30 jours','90d':'90 jours','365d':'Un an','custom':'Personnalisée'}
        if key=='item_id':display=(names or {}).get(value,'Identité sélectionnée')
        elif key!='search':display=translations.get(display,display)
        chips.append('<a href="'+escape(url,quote=True)+'">'+escape(LABELS[key]+': '+display)+' · retirer</a>')
    return '<nav aria-label="Filtres actifs">'+(''.join(chips) or '<span>Aucun filtre actif.</span>')+'<a href="/?page='+page+'">Tout réinitialiser</a></nav>'


def favorites_widget(url):
    return '<section id="favorite-views" data-current-url="'+escape(url,quote=True)+'"><h2>Vues favorites de ce navigateur</h2><p>Préférences locales ; aucune modification du portefeuille ni synchronisation distante.</p><label>Vue enregistrée<select id="favorite-select"><option value="">Choisir une vue</option></select></label><label>Nom de la vue<input id="favorite-name" maxlength="80"></label><div><button type="button" id="favorite-save">Enregistrer la vue actuelle</button> <button type="button" id="favorite-open">Ouvrir</button> <button type="button" id="favorite-rename">Renommer</button> <button type="button" id="favorite-delete">Supprimer</button></div><p id="favorite-status" role="status" aria-live="polite"></p></section><script src="/dashboard.js" defer></script>'
