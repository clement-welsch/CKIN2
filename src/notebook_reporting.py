"""French report presentation; formatting copies never change analytical inputs."""

from numbers import Real
import pandas as pd

from dashboard_status import BASIS_LABELS

LABELS={
 'date':'Date','snapshot_date':'Date du snapshot','category':'Catégorie','item_name':'Objet','case_name':'Caisse','item_id':'Identifiant exact',
 'quantity':'Quantité','unit_price':'Prix unitaire (EUR)','market_value':'Valeur connue (EUR)','known_value':'Sous-total connu (EUR)','total_value':'Valeur totale (EUR)',
 'purchase_unit_price':'Prix d’achat déclaré (EUR)','purchase_date':'Date d’achat déclarée','purchase_cost':'Coût déclaré (EUR)','unrealized_change':'Écart brut (EUR)',
 'price_date':'Date du prix','price_age_days':'Ancienneté du prix (jours)','price_source':'Source du prix','price_date_estimated':'Date du prix estimée',
 'date_estimated':'Date estimée','held_items':'Objets détenus','priced_items':'Objets avec prix','unknown_quantities':'Quantités inconnues','missing_prices':'Prix absents',
 'categories_not_imported':'Catégories non importées','oldest_price_age_days':'Prix le plus ancien (jours)','first_date':'Première date','last_date':'Dernière date','observations':'Relevés',
 'index_100':'Indice base 100','equal_weight_index':'Indice à poids égaux','cases_observed':'Caisses observées','covered_items':'Objets couverts','cohort_items':'Objets du panier','base_date':'Date de base',
 'price_effect':'Effet prix (EUR)','quantity_effect':'Effet quantité (EUR)','value_change':'Variation de valeur (EUR)','start_date':'Début','end_date':'Fin','covered':'Comparable',
 'method':'Méthode','sample':'Échantillon','windows':'Fenêtres évaluées','MAE':'Erreur absolue moyenne (points d’indice)','RMSE':'Erreur quadratique (points d’indice)',
 'actual':'Indice observé','persistence':'Dernière valeur','trend':'Tendance simple','ridge':'Modèle Ridge','target_date':'Date cible','origin':'Date d’origine','emitted_at':'Date d’émission',
 'first_target':'Première cible','last_target':'Dernière cible','training_pairs':'Paires d’apprentissage','training_end':'Fin d’apprentissage','status':'Disponibilité','reason':'Explication',
 'age_days':'Ancienneté (jours)','valid_months':'Mois valides','missing_months':'Mois manquants','weight_pct':'Part de la valeur connue (%)',
 'change_pct':'Variation (%)','change_pct_since_first':'Évolution depuis le premier relevé (%)','drawdown_from_peak_pct':'Écart au sommet (%)','observed_range_pct':'Amplitude observée (%)',
 'quantity_coverage_pct':'Couverture des quantités (%)','first_price':'Premier prix (EUR)','latest_price':'Dernier prix (EUR)','peak_price':'Prix maximal (EUR)','peak_date':'Date du maximum',
 'source_file':'Fichier source','source_column':'Colonne source','item_type':'Type d’objet','video_id':'Vidéo','channel_id':'Chaîne','url':'Lien source','match_kind':'Type de correspondance',
 'confidence':'Spécificité de la règle','published_at':'Date de publication','collected_at':'Date de collecte','available_at':'Date de disponibilité','direction':'Opinion annotée',
 'arguments':'Arguments du créateur','verified_facts':'Faits vérifiés séparément','horizon':'Horizon annoncé','sponsorship':'Partenariat déclaré','extractor':'Version d’extraction',
 'language':'Langue','transcript_origin':'Origine de la transcription','baseline_common':'Prévisions simples aux mêmes dates','model_common':'Modèles aux mêmes dates',
 'calendar_months':'Mois calendaires','available_months':'Mois disponibles','baseline_windows':'Fenêtres des prévisions simples','model_windows':'Fenêtres du modèle','required_training_pairs':'Paires d’apprentissage requises',
 'future':'Prévision suivante','state':'État de couverture','forecasts':'Prévisions archivées','kind':'Nature de la prévision','revision':'Révision',
}
CATEGORY={'case':'Caisses','skin':'Skins','souvenir':'Souvenirs','sticker':'Stickers','charm':'Charms','agent':'Agents','global':'Portefeuille global'}
VALUES={**CATEGORY,'steam':'Steam','legacy_csv':'Export CSV','holdings':'Positions enregistrées','empty':'Import vide','not_imported':'Non importé','issued':'Émise','retrospective':'Simulation rétrospective','persistence':'Dernière valeur','trend':'Tendance simple','ridge':'Modèle Ridge','baseline_common':'Prévisions simples aux mêmes dates','model_common':'Modèles aux mêmes dates','exact':'Exacte','family':'Famille','ambiguous':'Ambiguë','up':'Hausse envisagée','down':'Baisse envisagée','neutral':'Neutre','unknown':'Inconnu'}
VALUES.update({'experimental_model':'Modèle expérimental évalué','insufficient_model_history':'Historique insuffisant pour le modèle','pending':'En attente','evaluated':'Évaluée','unavailable':'Indisponible','target_month_not_closed':'Mois cible non clôturé','not_emitted_at_evaluation_cutoff':'Non émise à cette date','missing_or_stale_target_price':'Prix cible absent ou ancien','No tracked items':'Aucun objet dans le panier','No exact common observed base date for the fixed cohort':'Aucune date de base observée commune au panier fixe','Zero price at the common base; relative comparison unavailable':'Prix nul à la base commune : comparaison relative indisponible','No tracked cohort in this category':'Aucun panier suivi dans cette catégorie'})

MONEY={'unit_price','market_value','known_value','total_value','purchase_unit_price','purchase_cost','unrealized_change','price_effect','quantity_effect','value_change','first_price','latest_price','peak_price'}
COUNTS={'quantity','held_items','priced_items','unknown_quantities','missing_prices','categories_not_imported','observations','covered_items','cohort_items','windows','training_pairs','cases_observed','valid_months','missing_months'}


def formatted(value,column=''):
    if value is None or value is pd.NA or value is pd.NaT:return 'Indisponible'
    if isinstance(value,(list,dict,tuple)):return str(value)
    if pd.isna(value):return 'Indisponible'
    if isinstance(value,(pd.Timestamp,)) or column in {'date','snapshot_date','price_date','first_date','last_date','purchase_date','peak_date','base_date','start_date','end_date','target_date','origin','training_end','first_target','last_target','published_at','collected_at','available_at','emitted_at'}:
        return pd.Timestamp(value).strftime('%d/%m/%Y %H:%M')
    if isinstance(value,bool):return 'Oui' if value else 'Non'
    if isinstance(value,Real):
        if column in COUNTS:return str(int(value)) if float(value).is_integer() else str(value)
        text=f'{value:,.2f}'.replace(',','\u202f').replace('.',',')
        return text+(' €' if column in MONEY else ' %' if column.endswith('_pct') else '')
    return VALUES.get(str(value),str(value)) if column in {'category','state','price_source','method','sample','kind','match_kind','direction','status','reason'} else str(value)


def report_table(frame):
    if isinstance(frame,pd.Series):
        return pd.DataFrame({'Indicateur':[LABELS.get(str(k),str(k).replace('_',' ')) for k in frame.index],
                             'Valeur':[formatted(v,str(k)) for k,v in frame.items()]})
    result=frame.copy()
    for column in result:
        result[column]=result[column].map(lambda value:formatted(value,str(column)))
    return result.rename(columns={c:LABELS.get(str(c),str(c).replace('_',' ').capitalize()) for c in result})


def french_display(display):
    def show(*objects,**kwargs):
        return display(*(report_table(o) if isinstance(o,(pd.DataFrame,pd.Series)) else o for o in objects),**kwargs)
    return show


class FrenchPlots:
    def __init__(self,px):self.px=px
    def __getattr__(self,name):
        method=getattr(self.px,name)
        if name not in ('line','bar','scatter'):return method
        def plot(frame,*args,**kwargs):
            frame=frame.copy()
            for column in ('category','method','sample'):
                if column in frame:frame[column]=frame[column].map(lambda v:VALUES.get(v,v))
            kwargs['labels']={**LABELS,**kwargs.get('labels',{})}
            return method(frame,*args,**kwargs)
        return plot


def portfolio_summary(result,label,display):
    print(label)
    print('Racine des données :',result.get('data_root','Non renseignée'),'| Analyse :',formatted(result.get('as_of'),'date'))
    print('Quantités :',BASIS_LABELS.get(result['provenance']['basis'],'Provenance à vérifier'))
    summary=result.get('summary',result.get('current'))
    selected=summary.loc[summary.category.eq('global')]
    if selected.empty:
        print('Aucun snapshot disponible : valorisation indisponible.')
    else:
        row=selected.iloc[0]
        print('Valeur totale :',formatted(row.total_value,'total_value'),'| Sous-total connu, potentiellement partiel :',formatted(row.known_value,'known_value'))
        print('Quantités inconnues :',int(row.unknown_quantities),'| Prix absents :',int(row.missing_prices),'| Catégories non importées :',int(row.categories_not_imported))
    print('Les prix sont des observations datées. Une variation de valeur ne constitue pas un gain réalisé.')
