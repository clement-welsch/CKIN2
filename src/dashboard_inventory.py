"""Server-rendered held inventory: exact identities, bounded pages and full totals."""

from html import escape
from math import ceil
from urllib.parse import urlencode

import pandas as pd

from dashboard_categories import LABELS
from data_diagnostics import unavailable_valuation
from dashboard_overview import money, stamp
from dashboard_status import PRICE_LABELS, held_rows
from global_snapshots import COLUMNS, value_snapshots
from portfolio_data import CATEGORIES

SORTS = {'item_name':'Nom', 'category':'Catégorie', 'quantity':'Quantité', 'unit_price':'Prix',
         'price_date':'Date du prix', 'market_value':'Valeur connue'}


def inventory(data, *, search='', sort='item_name', direction='asc', price_status='all', quantity_status='all', page_number='1', page_size='25'):
    if sort not in SORTS or direction not in ('asc','desc') or price_status not in ('all','recent','stale','missing','invalid') or quantity_status not in ('all','known','unknown'):
        raise ValueError('Invalid inventory filter/sort')
    if not str(page_number).isdigit() or not str(page_size).isdigit() or int(page_number)<1 or int(page_size) not in (10,25,50,100):
        raise ValueError('Invalid inventory pagination')
    size=int(page_size)
    rows=held_rows(data['detail'], data['cutoff'], data.get('errors'))
    search=search.strip()
    if search:
        rows=rows.loc[rows.item_name.str.contains(search, case=False, regex=False)]
    if price_status!='all':
        rows=rows.loc[rows.price_status.eq(price_status)]
    if quantity_status!='all':
        rows=rows.loc[rows.quantity_status.eq(quantity_status)]
    keys=list(dict.fromkeys([sort,'item_name','item_id']))
    rows=rows.sort_values(keys,ascending=[direction=='asc']+[True]*(len(keys)-1),na_position='last',kind='stable')
    # Reuse snapshot valuation after selection, before pagination. Missing category
    # markers remain unavailable; excluded positions become explicitly empty.
    snapshot=data['detail'][COLUMNS].copy()
    snapshot=snapshot.loc[~snapshot.state.eq('holdings') | snapshot.item_id.isin(rows.item_id)]
    if not data['detail'].empty:
        stamp_value=data['detail'].snapshot_date.iloc[0]
        markers=[dict(snapshot_date=stamp_value,category=c,state='empty',item_id=None,item_name=None,quantity=0)
                 for c in CATEGORIES if c not in set(snapshot.category)]
        snapshot=pd.concat([snapshot,pd.DataFrame(markers,columns=COLUMNS)],ignore_index=True)
    _, totals=value_snapshots(snapshot,data['prices'])
    if 'prices' in data.get('errors', {}):
        _, totals = unavailable_valuation(snapshot, totals)
    summary=totals.loc[totals.category.eq('global')]
    pages=max(1,ceil(len(rows)/size))
    page=min(int(page_number),pages)
    return dict(rows=rows, page_rows=rows.iloc[(page-1)*size:page*size], summary=summary,
                count=len(rows), page=page, pages=pages, size=size,
                active=bool(search or price_status!='all' or quantity_status!='all' or data['selected_item_id'] or len(data['categories'])<len(CATEGORIES)))


def inventory_page(data, params, filters):
    if ('holdings' in data.get('errors', {}) and not data['historical_mode']) or ('history' in data.get('errors', {}) and data['historical_mode']):
        return '<section><h2>Inventaire détenu</h2><p>Quantités indisponibles : source invalide. <a href="/?page=quality">Vérifier les données</a>.</p></section>'
    result=inventory(data,**filters)
    def url(**changes):
        return '/?'+escape(urlencode({**params,**filters,'page':'inventory',**changes}),quote=True)
    def select(name,label,choices):
        value=filters.get(name,{'sort':'item_name','direction':'asc','price_status':'all','quantity_status':'all','page_size':'25'}.get(name,''))
        return '<label>'+label+'<select name="'+name+'">'+''.join('<option value="'+escape(k,quote=True)+'"'+(' selected' if str(value)==k else '')+'>'+escape(v)+'</option>' for k,v in choices)+'</select></label>'
    body='<section><h2>Inventaire détenu</h2><p>Positions du patrimoine sélectionné : les objets seulement suivis ou présents au catalogue ne créent aucune quantité détenue. Les quantités inconnues restent visibles.</p>'
    body+='<form method="get"><input type="hidden" name="page" value="inventory">'
    body+=''.join('<input type="hidden" name="'+k+'" value="'+escape(str(v),quote=True)+'">' for k,v in params.items())
    body+='<label>Rechercher un nom ou une variante<input name="search" value="'+escape(filters.get('search',''),quote=True)+'" type="search"></label>'
    body+=select('sort','Trier par',list(SORTS.items()))+select('direction','Ordre',[('asc','Croissant'),('desc','Décroissant')])
    body+=select('price_status','Prix',[('all','Tous'),*PRICE_LABELS.items()])+select('quantity_status','Quantités',[('all','Toutes'),('known','Renseignées'),('unknown','Inconnues')])
    body+=select('page_size','Objets par page',[(str(s),str(s)) for s in (10,25,50,100)])+'<button>Appliquer les filtres</button></form>'
    values=result['summary'].iloc[0] if not result['summary'].empty else {}
    body+='<p><b>'+str(result['count'])+' objets sur la sélection complète</b> · '+('Filtres actifs' if result['active'] else 'Aucun filtre de sélection')+'</p>'
    body+='<p>Valeur totale de la sélection : '+money(values.get('total_value',float('nan')))+' · sous-total connu, potentiellement partiel : '+money(values.get('known_value',float('nan')))+'. Totaux indépendants de la pagination.</p>'
    if ('holdings' in data.get('errors', {}) and not data['historical_mode']) or ('history' in data.get('errors', {}) and data['historical_mode']):
        return body+'<p class="empty">Inventaire indisponible : les données invalides doivent être corrigées.</p></section>'
    if result['page_rows'].empty:
        body+='<p class="empty">Aucun objet détenu ne correspond à cette sélection.</p>'
    else:
        body+='<div class="table"><table><caption>Objets détenus · identités exactes et couverture</caption><thead><tr>'+''.join('<th scope="col">'+v+'</th>' for v in ['Objet / variante','Catégorie','Quantité','Dernier prix','Date du prix','Valeur connue','Couverture'])+'</tr></thead><tbody>'
        for row in result['page_rows'].itertuples():
            target='/?'+escape(urlencode({**params,'page':'item','item_id':row.item_id}),quote=True)
            cells=['<a href="'+target+'">'+escape(row.item_name)+'</a>',escape(LABELS[row.category]),str(int(row.quantity)) if pd.notna(row.quantity) else 'Inconnue',money(row.unit_price),escape(stamp(row.price_date)),money(row.market_value),escape(row.coverage_status)]
            body+='<tr>'+''.join('<td>'+c+'</td>' for c in cells)+'</tr>'
        body+='</tbody></table></div>'
    body+='<nav aria-label="Pagination inventaire"><span>Page '+str(result['page'])+' / '+str(result['pages'])+'</span>'
    if result['page']>1:
        body+='<a href="'+url(page_number=result['page']-1)+'">Précédente</a>'
    if result['page']<result['pages']:
        body+='<a href="'+url(page_number=result['page']+1)+'">Suivante</a>'
    return body+'</nav></section>'
