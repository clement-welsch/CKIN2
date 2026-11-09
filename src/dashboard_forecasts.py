"""Offline plots of existing chronological experiments, without forecast issuance."""

import plotly.express as px

from dashboard_categories import figure_html


def forecast_figures(prediction):
    """Keep categories and common-window samples separate in every comparison."""
    plots = []
    backtests = prediction['backtests']
    for category, rows in backtests.groupby('category'):
        # Plot model comparisons on identical targets, as in scores(model_common).
        common = rows.dropna(subset=['ridge'])
        samples = [('baseline_common', rows, ['persistence', 'trend']),
                   ('model_common', common, ['persistence', 'trend', 'ridge'])]
        for sample, frame, methods in samples:
            if frame.empty:
                continue
            figure = px.line(frame, x='target_date', y=['actual', *methods], markers=True,
                             title=f'{category} · {sample} · indice prévu / réalisé (un mois)')
            figure.update_traces(connectgaps=False)
            plots.append(figure_html(figure))
    metrics = prediction['scores']
    for metric in ('MAE', 'RMSE'):
        if not metrics.empty:
            figure = px.bar(metrics, x='category', y=metric, color='method', facet_col='sample',
                            barmode='group', hover_data=['windows', 'first_target', 'last_target'],
                            title=f'{metric} hors échantillon · mêmes cibles par comparaison')
            plots.append(figure_html(figure))
    return ''.join(plots) or '<p class="empty">Validation indisponible : historique insuffisant pour une comparaison chronologique.</p>'
