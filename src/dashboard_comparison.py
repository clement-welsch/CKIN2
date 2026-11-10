"""Compare two recorded snapshots with shared covered price/quantity effects."""

from html import escape
from urllib.parse import urlencode

import pandas as pd
import plotly.express as px

from dashboard_categories import figure_html
from dashboard_overview import money, stamp
from global_analysis import explain_changes
from global_snapshots import COLUMNS, value_snapshots
from portfolio_selection import subset_snapshots


def compare_snapshots(data, before='', after='', start=None):
    history=data['snapshots']
    if start is not None:
        history=history.loc[history.snapshot_date.ge(pd.Timestamp(start))]
    dates=sorted(history.snapshot_date.unique())
    if not dates:
        return dict(dates=[],before=None,after=None,rows=pd.DataFrame(),values=pd.DataFrame())
    before=pd.Timestamp(before) if before else pd.Timestamp(dates[-2] if len(dates)>1 else dates[-1])
    after=pd.Timestamp(after) if after else pd.Timestamp(dates[-1])
    if before not in dates or after not in dates or before>after:
        raise ValueError('Choisir deux snapshots disponibles dans l’ordre chronologique')
    selected=history.loc[history.snapshot_date.isin([before,after])]
    selected=subset_snapshots(selected,data['categories'],data['selected_item_id'])
    detail,values=value_snapshots(selected,data['prices'])
    if 'prices' in data.get('errors',{}):
        values[['known_value','total_value']]=float('nan')
    if before==after:
        held=detail.loc[detail.state.eq('holdings') & detail.category.isin(data['categories'])]
        rows=held[['item_id','item_name','category']].copy()
        rows['covered']=held.quantity.notna() & held.unit_price.notna() & ('prices' not in data.get('errors',{}))
        for column in ('price_effect','quantity_effect','value_change'):
            rows[column]=rows.covered.map(lambda ok:0.0 if ok else float('nan'))
    else:
        rows=explain_changes(selected,data['prices'])
        rows=rows.loc[rows.category.isin(data['categories'])]
    totals=values.loc[values.category.eq('global')].set_index('snapshot_date')
    delta=totals.loc[after,'total_value']-totals.loc[before,'total_value']
    covered=rows.loc[rows.covered]
    explained=covered.value_change.sum(min_count=1)
    if rows.empty and pd.notna(delta) and delta==0:
        explained=0.0
    residual=delta-explained if pd.notna(delta) and pd.notna(explained) else float('nan')
    return dict(dates=dates,before=before,after=after,rows=rows,values=values,
                covered=covered,delta=delta,explained=explained,residual=residual,
                excluded=int((~rows.covered).sum()))


def comparison_page(data,params,before,after,table,*,with_selection=False):
    notice=''
    try:
        result=compare_snapshots(data,before,after,params.get('start'))
    except ValueError:
        if not before and not after:raise
        result=compare_snapshots(data,start=params.get('start'))
        notice='<p role="status">Choix de snapshots réinitialisé : dates absentes, obsolètes ou incompatibles avec cette période.</p>'
    def finish(body):
        return (body, result['before'].isoformat() if result['before'] is not None else '', result['after'].isoformat() if result['after'] is not None else '') if with_selection else body
    body='<section><h2>Comparer deux états enregistrés</h2><p>Variation de valeur en euros, distincte d’un rendement ou d’un bénéfice réalisé. Les quantités sont celles de chaque snapshot.</p>'
    body+=notice
    if not result['dates']:
        return finish(body+'<p class="empty">Aucun snapshot disponible pour cette période. Aucun historique de quantités n’est reconstruit.</p></section>')
    body+='<form method="get"><input type="hidden" name="page" value="comparison">'
    body+=''.join('<input type="hidden" name="'+k+'" value="'+escape(str(v),quote=True)+'">' for k,v in params.items())
    for name,label in [('comparison_before','État initial'),('comparison_after','État final')]:
        selected=result['before' if name.endswith('before') else 'after']
        body+='<label>'+label+'<select name="'+name+'">'
        for date in result['dates']:
            value=pd.Timestamp(date)
            body+='<option value="'+value.isoformat()+'"'+(' selected' if value==selected else '')+'>'+escape(stamp(value))+'</option>'
        body+='</select></label>'
    body+='<button>Comparer les snapshots</button></form>'
    labels={'snapshot_date':'Date enregistrée','category':'Périmètre','known_value':'Sous-total connu (EUR)','total_value':'Valeur totale (EUR)','held_items':'Objets','unknown_quantities':'Quantités inconnues','missing_prices':'Prix absents','categories_not_imported':'Catégories non importées'}
    body+=table(result['values'].loc[result['values'].category.isin([*data['categories'],'global']),list(labels)].rename(columns=labels))
    body+='<p>Variation totale : '+money(result['delta'])+' · variation expliquée sur les lignes couvertes : '+money(result['explained'])+'.</p>'
    body+='<p>Lignes non comparables : '+str(result['excluded'])+'. Résidu calculable : '+money(result['residual'])+'. Une donnée inconnue ne devient jamais zéro.</p>'
    effects=result['covered']
    if not effects.empty:
        totals=effects.groupby('category',as_index=False)[['price_effect','quantity_effect']].sum()
        figure=px.bar(totals,x='category',y=['price_effect','quantity_effect'],barmode='relative',title='Effets prix et quantités sur les positions couvertes (EUR)',labels={'category':'Catégorie','value':'EUR','variable':'Effet'})
        body+=figure_html(figure)
    body+='<p>Effet prix : quantité initiale × variation du prix. Effet quantité : variation de quantité × prix final. Ces mouvements ne prouvent ni achat, ni vente, ni transfert sans journal justificatif.</p>'
    rows=result['rows'].copy()
    if not rows.empty:
        rows['magnitude']=rows.value_change.abs()
        rows=rows.sort_values(['magnitude','item_name','item_id'],ascending=[False,True,True],na_position='last')
        body+='<h3>Contributeurs et exclusions</h3><ul>'
        for row in rows.itertuples():
            target='/?'+escape(urlencode({**params,'page':'item','item_id':row.item_id}),quote=True)
            fact=('Effet prix '+money(row.price_effect)+' ; effet quantité '+money(row.quantity_effect)+'.') if row.covered else 'Non comparable : prix, quantité ou couverture de catégorie manquants.'
            body+='<li><a href="'+target+'">'+escape(row.item_name)+'</a> — '+escape(fact)+'</li>'
        body+='</ul>'
    return finish(body+'</section>')
