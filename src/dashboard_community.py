"""Read-only presentation of local research; never publish transcript text."""

import html

import pandas as pd
import plotly.express as px

from community_signals import research
from dashboard_categories import figure_html


def community_page(root, data, start, table):
    result = research(root, as_of=data['cutoff'])
    content = '<section><h2>Recherche communautaire expérimentale</h2><p>Utilité prédictive non démontrée. '
    content += 'Les opinions ne constituent ni des faits vérifiés ni des conseils d’achat/vente. '
    content += 'Aucune acquisition de transcription ou requête réseau au chargement. Les transcriptions intégrales ne sont pas affichées.</p>'
    content += '<p>' + html.escape(result['status']) + '</p>'
    channels = result['channels'].copy()
    if not channels.empty:
        channels = channels.reindex(columns=['name', 'verified', 'verified_at', 'channel_id', 'url'])
        known = pd.to_datetime(channels.verified_at).le(data['cutoff'])
        channels.loc[~known, 'verified'] = False
    content += '<h3>Chaînes et vérification</h3><p>Chaînes non vérifiées : aucune identité ni autorisation d’accès supposée.</p>' + table(channels)
    coverage = result['coverage']
    if not coverage.empty:
        coverage = coverage.loc[pd.to_datetime(coverage.collected_at).le(data['cutoff'])]
        if start is not None:
            coverage = coverage.loc[pd.to_datetime(coverage.published_at).ge(start)]
    content += '<h3>Couverture du corpus local</h3><p>La couverture porte sur les vidéos connues, indépendamment du filtre objet.</p>' + table(coverage)
    selected = set(data['registry'].loc[data['registry'].category.isin(data['categories']), 'item_id'])
    if data['selected_item_id']:
        selected &= {data['selected_item_id']}
    signals = result['signals'].copy()
    if not signals.empty:
        signals = signals.loc[signals.item_id.isin(selected) & signals.published_at.le(data['cutoff']) & signals.collected_at.le(data['cutoff'])].copy()
        if start is not None:
            signals = signals.loc[signals.published_at.ge(start)]
        later = signals.available_at.gt(data['cutoff'])
        for field in ('direction', 'horizon', 'arguments', 'verified_facts', 'sponsorship', 'available_at'):
            signals.loc[later, field] = None
    fields = ['video_id', 'item_id', 'match_kind', 'confidence', 'published_at', 'collected_at', 'available_at',
              'start_seconds', 'direction', 'horizon', 'arguments', 'verified_facts', 'sponsorship', 'extractor', 'alias_hash',
              'language', 'transcript_origin', 'acquisition_note']
    content += '<h3>Mentions et annotations</h3><p>Exact, famille ou ambigu : les scores décrivent la spécificité des règles, pas des probabilités calibrées. '
    content += 'available_at indique la disponibilité de l’annotation ; une annotation future est masquée. Les arguments du créateur et faits vérifiés restent séparés.</p>' + table(signals.reindex(columns=fields))
    links = ''.join('<li><a href="' + html.escape(row.url, quote=True) + '" rel="noreferrer">' +
                    html.escape(str(row.video_id)) + (' · passage ' + str(row.start_seconds) + ' s' if pd.notna(row.start_seconds) else ' · vidéo sans horodatage') +
                    '</a></li>' for row in signals.itertuples())
    content += '<h3>Sources des mentions</h3><ul>' + links + '</ul>'
    backtests = result['backtests']
    if not backtests.empty:
        backtests = backtests.loc[backtests.item_id.isin(selected)]
        if start is not None:
            backtests = backtests.loc[backtests.target_date.ge(start)]
    rows = []
    if not backtests.empty:
        for item_id, group in backtests.groupby('item_id'):
            common = group.dropna(subset=['price_model', 'community_model'])
            for method in ('persistence', 'trend', 'price_model', 'community_model'):
                if not common.empty:
                    errors = common[method] - common.actual
                    rows.append(dict(item_id=item_id, method=method, windows=len(common), first_target=common.target_date.min(),
                                     last_target=common.target_date.max(), MAE=errors.abs().mean(), RMSE=(errors.pow(2).mean())**0.5))
    metrics = pd.DataFrame(rows)
    content += '<h3>Comparaison sur les mêmes fenêtres</h3><p>Prix seuls / prix et signaux : expériences rétrospectives, horizon un mois, entraînement antérieur à chaque cible. '
    content += 'Les dates de début filtrent les cibles après entraînement. Une corrélation ne démontre aucune causalité.</p>'
    if not metrics.empty:
        content += figure_html(px.bar(metrics, x='item_id', y='MAE', color='method', barmode='group',
                                      hover_data=['windows', 'first_target', 'last_target'], title='Erreurs hors échantillon · fenêtres identiques'))
    else:
        content += '<p>Comparaison indisponible : corpus ou historique insuffisant ; aucune amélioration établie.</p>'
    audit = result['audit']
    if not audit.empty:
        audit = audit.loc[audit.item_id.isin(selected)]
    return content + table(metrics) + table(backtests) + '<h3>Disponibilité de l’expérience</h3>' + table(audit) + '</section>'
