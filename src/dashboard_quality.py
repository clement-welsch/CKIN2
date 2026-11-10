"""Read-only data-quality diagnosis with scoped effects and concrete repair paths."""

import contextlib
import io
import json
from pathlib import Path

import pandas as pd

from dashboard_categories import acquisition_references
from dashboard_reconciliation import read_observation
from dashboard_status import STALE_DAYS, coverage
from data_diagnostics import read_dataset
from forecast_archive import records
from profit_loss import report as fifo_report
from transactions import validate_transactions

ERROR_GUIDES = {
    'holdings': ('Inventaire', 'Quantités actuelles et valeur du patrimoine indisponibles.', 'Vérifier les CSV inventory et le remplacement propriétaire ; restaurer explicitement une sauvegarde relue si nécessaire.'),
    'prices': ('Prix du patrimoine', 'Valorisations et prévisions dépendantes bloquées.', 'Vérifier les CSV prices/market_observations et les identités du catalogue. Corriger la source avant toute nouvelle collecte.'),
    'history': ('Snapshots', 'Historique et sélection passée indisponibles ; patrimoine actuel indépendant.', 'Vérifier global_inventory_history.csv et ses six marqueurs de catégorie. Restaurer une sauvegarde valide sans reconstruire les quantités passées.'),
    'metadata': ('Métadonnées facultatives', 'Enrichissement des variantes/catalogues indisponible ; identités patrimoniales conservées.', 'Relire market_catalog.csv et les publications data/market/releases avant un nouvel import explicite.'),
    'market': ('Prix de l’univers', 'Fiches et recherche dépendantes de ces prix indisponibles.', 'Valider data/market/observations.csv ; ne pas remplacer les prix du patrimoine par ces données.'),
    'transactions': ('Transactions', 'Journal sélectionné indisponible ; aucune transaction déduite.', 'Valider transactions.csv et ses dates, identités et montants.'),
    'fifo': ('Gains/pertes FIFO', 'Coûts et gains dépendants indisponibles.', 'Relire opening_inventory.csv et transactions.csv, puis vérifier la réconciliation.'),
    'archive': ('Archives de prévisions', 'Évaluation des archives indisponible ; modèles indépendants conservés.', 'Restaurer les enregistrements intègres de forecast_archive depuis une sauvegarde ; ne pas modifier les paniers gelés.'),
    'acquisitions': ('Références d’acquisition', 'Repères séparés indisponibles.', 'Vérifier les marqueurs source_column=0, les dates et les identités des CSV prices.'),
    'visible': ('Observation Steam visible', 'Rapprochement et correspondances indisponibles ; patrimoine inchangé.', 'Relire l’export local et sa sélection de comptes, puis refaire explicitement une prévisualisation steam_inventory.py.'),
    'community': ('Corpus de recherche', 'Recherche dépendante indisponible ; patrimoine indépendant.', 'Valider corpus.json, aliases.json et les annotations datées dans data/community.'),
    'item': ('Fiche objet', 'Détails dépendants indisponibles.', 'Vérifier les métadonnées et références de l’identité exacte.'),
    'collection': ('Historique de collecte', 'Dernier résultat de collecte invérifiable.', 'Relire les fichiers data/runtime/runs et leurs codes/dates ; aucune collecte ne sera relancée ici.'),
}


def collection_history(root, cutoff):
    events=[]
    for path in (Path(root)/'data/runtime/runs').glob('*.json'):
        value=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value,dict) or type(value.get('code')) is not int or value['code'] not in (0,1,2):
            raise ValueError('Invalid collection result')
        ended=pd.Timestamp(value['ended'])
        if pd.isna(ended) or ended.tzinfo is None:
            raise ValueError('Collection timestamps require an explicit timezone')
        for name in ('updated','failed','missing','stale'):
            if type(value.get(name)) is not int or value[name]<0:
                raise ValueError('Invalid collection counts')
        if ended.tz_convert('UTC').tz_localize(None)<=pd.Timestamp(cutoff):
            events.append((ended,value))
    if not events:
        return dict(status='Absence d’historique',event=None)
    event=max(events,key=lambda e:e[0])[1]
    return dict(status={0:'Réussite',1:'Résultat partiel',2:'Échec'}[event['code']],event=event)


def quality(root, data):
    root=Path(root)
    errors=dict(data.get('errors',{}))
    capture=read_dataset(errors,'visible',lambda:read_observation(root,data['cutoff']),None)
    tx=root/'data/processed/transactions.csv'
    if tx.exists():
        read_dataset(errors,'transactions',lambda:validate_transactions(pd.read_csv(tx)),None)
    read_dataset(errors,'archive',lambda:records(root/'data/processed/forecast_archive'),None)
    read_dataset(errors,'acquisitions',lambda:acquisition_references(root,data['registry'],data['cutoff']),None)
    if (root/'data/processed/opening_inventory.csv').exists():
        def validate_fifo():
            with contextlib.redirect_stdout(io.StringIO()):
                return fifo_report(root,when=data['cutoff'])
        read_dataset(errors,'fifo',validate_fifo,None)
    corpus=root/'data/community/corpus.json'
    if corpus.exists():
        from community_signals import research
        read_dataset(errors,'community',lambda:research(root,as_of=data['cutoff']),None)
    collection=read_dataset(errors,'collection',lambda:collection_history(root,data['cutoff']),dict(status='Historique invalide',event=None))
    status=coverage(data)
    issues=[]
    def add(scope,problem,impact,action):
        issues.append({'Périmètre':scope,'Problème':problem,'Impact':impact,'Correction proposée':action})
    for row in status['rows'].itertuples():
        if pd.isna(row.quantity):
            add(row.item_name,'Quantité inconnue','Total complet indisponible ; ligne exclue du sous-total connu.','Corriger la quantité dans la source patrimoniale relue ; une capture publique ne suffit pas.')
        if row.price_status=='missing':
            add(row.item_name,'Prix absent','Valeur de cette position indisponible.','Relire le nom Steam exact dans le catalogue ; lancer une mise à jour explicite sur un réseau autorisé.')
        elif row.price_status=='stale':
            add(row.item_name,'Prix ancien',f'Valeur connue fondée sur un prix de plus de {STALE_DAYS} jours.','Vérifier le dernier résultat de collecte et relancer explicitement la commande de mise à jour si nécessaire.')
    unavailable_categories = data['detail'].iloc[:0] if 'holdings' in errors and not data['historical_mode'] else data['detail']
    for row in unavailable_categories.loc[unavailable_categories.state.eq('not_imported') & unavailable_categories.category.isin(data['categories'])].itertuples():
        add(row.category,'Catégorie non importée','Son patrimoine est inconnu ; total global incomplet.','Importer un CSV relu ou un export propriétaire explicitement complet, puis prévisualiser avant application.')
    if status['unverified']:
        add('Patrimoine','Couverture du remplacement non vérifiée','Le total calculé ne certifie pas le patrimoine complet, notamment les objets stockés.','Comparer la source et les sauvegardes ; déclarer un export complet uniquement après vérification propriétaire.')
    if capture:
        unresolved=sorted({name for account in capture['accounts'] for name in account['unresolved']})
        for name in unresolved:
            add(name,'Correspondance Steam non résolue','Observation visible non rapprochée ; patrimoine inchangé.','Relire la correspondance exacte dans le catalogue et refaire la prévisualisation d’import.')
    for name in errors:
        scope,impact,action=ERROR_GUIDES[name]
        add(scope,'Jeu de données invalide ou illisible',impact,action)
    return dict(issues=pd.DataFrame(issues,columns=['Périmètre','Problème','Impact','Correction proposée']),collection=collection,errors=errors,status=status)


def quality_page(root,data,table):
    result=quality(root,data)
    body='<section><h2>Qualité des données et corrections</h2><p>Diagnostic en lecture seule. Aucune réparation, collecte ou remise à zéro automatique.</p>'
    body+='<p>État de la sélection : <b>'+result['status']['label']+'</b>. Les statuts de quantité et de prix sont partagés avec la synthèse et l’inventaire.</p>'
    body+='<h3>Dernier résultat local de collecte</h3><p>'+result['collection']['status']+'</p>'
    event=result['collection']['event']
    if event:
        body+=table(pd.DataFrame([{'Fin enregistrée':event['ended'],'Prix actualisés':event['updated'],'Échecs':event['failed'],'Prix absents':event['missing'],'Prix anciens selon le collecteur':event['stale']}]))
        body+='<p>Les seuils et périmètres du collecteur peuvent différer de la sélection affichée ; son résultat n’établit pas à lui seul la couverture du portefeuille.</p>'
    if result['issues'].empty:
        body+='<p>Aucun problème détecté pour cette sélection.</p>'
    else:
        body+=table(result['issues'])
    body+='<p><a href="/?page=inventory">Vérifier les positions détenues</a> · <a href="/?page=reconciliation">Comparer avec les observations visibles</a></p>'
    return body+'</section>'
