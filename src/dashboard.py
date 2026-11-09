"""Local read-only portfolio dashboard; no collection or browser-side CDN."""

import argparse
import contextlib
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import pandas as pd
import plotly.express as px
from plotly.offline import get_plotlyjs

from forecast_archive import evaluate, load_archive_prices
from global_analysis import analyze, explain_changes, market_indices
from global_snapshots import COLUMNS, build_snapshot, value_snapshots
from portfolio_selection import selection, subset_snapshots, analysis_date
from portfolio_data import CATEGORIES, ROOT, _parse_dates
from prediction import experiment, scores
from dashboard_forecasts import forecast_figures
from transactions import COLUMNS as TRANSACTIONS, validate_transactions
from source_attribution import sources_page
from dashboard_categories import LABELS, category_data, category_figures, value_distribution
from dashboard_categories import figure_html
from dashboard_items import independent_prices, item_details, item_registry


def escaped(value):
    return html.escape(str(value), quote=True)


def view(root=ROOT, *, category="all", item_id="", start=None, end=None, now=None, components=None):
    root = Path(root)
    if category not in (*CATEGORIES, "all"):
        raise ValueError("Unknown category")
    now = analysis_date(now)
    def date(value):
        return _parse_dates(pd.Series([value]), "filter date").iloc[0] if value else None
    start, end = date(start), date(end)
    # Date inputs include the full chosen calendar day, bounded by now.
    cutoff = min(now, end.normalize() + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)) if end is not None else now
    if start is not None and start > cutoff:
        raise ValueError("Period start follows end")
    data = analyze(root, now=cutoff)
    categories = set(CATEGORIES) if category == "all" else {category}
    registry = pd.concat([data["holdings"][["item_id", "category", "item_name"]],
                          data["history"].loc[data["history"].state.eq("holdings"), ["item_id", "category", "item_name"]]]).drop_duplicates("item_id")
    registry = item_registry(root, registry, pd.concat([data["prices"], independent_prices(root, cutoff)], ignore_index=True), cutoff)
    if item_id and item_id not in set(registry.loc[registry.category.isin(categories), "item_id"]):
        raise ValueError("Unknown object for this category")
    # Current holdings cannot be projected backward when end precedes now.
    historical_mode = end is not None and cutoff < now
    detail, current = selection(data, categories, item_id=item_id, historical=historical_mode)
    history = data["history"]
    if start is not None:
        history = history.loc[history.snapshot_date.ge(start)]
    _, historical = value_snapshots(subset_snapshots(history, categories, item_id), data["prices"])
    # Retain the preceding snapshot to explain the first visible change.
    contributions = explain_changes(subset_snapshots(data["history"], categories, item_id), data["prices"])
    contributions = contributions.loc[contributions.category.isin(categories)]
    if start is not None:
        contributions = contributions.loc[contributions.end_date.ge(start)]
    cohort = data["holdings"].loc[data["holdings"].category.isin(categories)]
    if item_id:
        cohort = cohort.loc[cohort.item_id.eq(item_id)]
    indices, diagnostic = market_indices(cohort, data["prices"])
    if start is not None:
        indices = indices.loc[indices.date.ge(start)]
    tx_path = root / "data/processed/transactions.csv"
    transactions = validate_transactions(pd.read_csv(tx_path)) if tx_path.exists() and components in (None, "performance") else pd.DataFrame(columns=TRANSACTIONS)
    transactions = transactions.loc[transactions.category.isin(categories)]
    if item_id:
        transactions = transactions.loc[transactions.item_id.eq(item_id)]
    transactions = transactions.loc[transactions.date.isna() | transactions.date.le(cutoff)]
    if start is not None:
        transactions = transactions.loc[transactions.date.isna() | transactions.date.ge(start)]
    pnl, pnl_message = pd.DataFrame(), "Gains/pertes indisponibles : inventaire initial absent."
    sales = pd.DataFrame()
    if components in (None, "performance", "item") and (root / "data/processed/opening_inventory.csv").exists():
        from profit_loss import report
        with contextlib.redirect_stdout(io.StringIO()):
            fifo = report(root, when=cutoff)
            pnl, sales = fifo["items"], fifo["sales"]
        pnl = pnl.loc[pnl.category.isin(categories)]
        if item_id:
            pnl = pnl.loc[pnl.item_id.eq(item_id)]
        sales = sales.loc[sales.category.isin(categories)]
        if item_id:
            sales = sales.loc[sales.item_id.eq(item_id)]
        pnl_message = "FIFO depuis l'inventaire initial jusqu'à la date choisie ; coûts inconnus = N/A, frais de vente futurs non estimés."
    prediction = {key: pd.DataFrame(columns=["category"]) for key in ("audit", "future", "scores")}
    archive = pd.DataFrame(columns=["category"])
    archive_metrics = pd.DataFrame(columns=["category"])
    if components in (None, "forecasts"):
        prediction = experiment(cohort, data["prices"], cutoff)
        selected = [*categories, "global"] if category == "all" else list(categories)
        for key in ("audit", "future", "backtests", "monthly"):
            prediction[key] = prediction[key].loc[prediction[key].category.isin(selected)]
        if start is not None:
            prediction["backtests"] = prediction["backtests"].loc[prediction["backtests"].target_date.ge(start)]
            prediction["monthly"] = prediction["monthly"].loc[prediction["monthly"].date.ge(start)]
        prediction["scores"] = scores(prediction["backtests"])
        archive, archive_metrics = evaluate(root / "data/processed/forecast_archive", load_archive_prices(root), cutoff,
                                    target_start=start, target_end=cutoff)
        # A forecast not yet emitted at this cutoff cannot appear in a past view.
        archive = archive.loc[pd.to_datetime(archive.emitted_at).le(cutoff)]
        archive_metrics = archive_metrics.loc[archive_metrics.category.isin(selected)]
    archive = archive.loc[archive.category.isin([*categories, "global"] if category == "all" else categories)]
    if item_id:
        archive = archive.iloc[:0]  # Frozen category baskets cannot be relabeled as item forecasts.
        archive_metrics = archive_metrics.iloc[:0]
    return dict(now=now, cutoff=cutoff, historical_mode=historical_mode, categories=categories,
                registry=registry, detail=detail, current=current, historical=historical,
                indices=indices, diagnostic=diagnostic, transactions=transactions,
                pnl=pnl, sales=sales, pnl_message=pnl_message, contributions=contributions,
                prediction=prediction, archive=archive, archive_metrics=archive_metrics,
                prices=data["prices"], selected_item_id=item_id,
                provenance=(dict(basis="recorded_snapshot", collected_at=detail.snapshot_date.max())
                            if historical_mode else data["provenance"]))


def table(frame):
    if frame.empty:
        return '<p class="empty">Aucune donnée disponible pour cette sélection.</p>'
    display = frame.astype(object).where(frame.notna(), "N/A")
    return '<div class="table">' + display.to_html(index=False, na_rep="N/A", escape=True, border=0, float_format=lambda x: f"{x:,.2f}") + '</div>'


def chart(frame, x, y, title):
    if frame.empty or frame[y].notna().sum() == 0:
        return '<p class="empty">Graphique indisponible : données insuffisantes.</p>'
    figure = px.line(frame, x=x, y=y, color="category", markers=True, title=title)
    figure.update_traces(connectgaps=False)
    figure.update_layout(template="plotly_dark", paper_bgcolor="#17202b", plot_bgcolor="#17202b", margin=dict(l=36, r=20, t=60, b=35), autosize=True)
    return figure.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True, "displaylogo": False, "displayModeBar": False})


def render(root=ROOT, params=None, now=None):
    params = dict(params or {})
    page = params.pop("page", "overview")
    pages = {"overview": "Vue d’ensemble", "categories": "Catégories", "item": "Fiche objet",
             "performance": "Performance · Gains et pertes", "forecasts": "Prévisions", "community": "Recherche"}
    if page not in pages:
        raise ValueError("Unknown dashboard view")
    search = params.pop("search", "").strip()
    allowed = {"category", "item_id", "start", "end"}
    if not set(params).issubset(allowed):
        raise ValueError("Unknown filter")
    data = view(root, now=now, components=page, **params)
    diagnostic = data["diagnostic"]
    diagnostic_text = (f"{diagnostic['cohort_items']} objets · base : {diagnostic['base_date']} · "
                       f"ancienneté maximale des prix : {diagnostic['max_age_days']} jours · "
                       f"{diagnostic['excluded_estimated_dates']} dates estimées exclues. " + diagnostic["reason"])
    category = params.get("category", "all")
    categories = ''.join(f'<option value="{c}" {"selected" if c == category else ""}>{LABELS[c]}</option>' for c in ["all", *CATEGORIES])
    registry = data["registry"].loc[data["registry"].category.isin(data["categories"])]
    search_results = registry.loc[registry.item_name.str.contains(search, case=False, regex=False)] if search else registry
    options = '<option value="">Tous les objets</option>' + ''.join(
        f'<option value="{escaped(r.item_id)}" {"selected" if r.item_id == params.get("item_id") else ""}>{escaped(r.item_name)}</option>'
        for r in registry.sort_values("item_name").itertuples())
    global_value = data["current"].loc[data["current"].category.eq("global")]
    value = global_value.total_value.iloc[0] if len(global_value) else float("nan")
    known = global_value.known_value.iloc[0] if len(global_value) else float("nan")
    money = lambda v: f"{v:,.2f} EUR" if pd.notna(v) else "Indisponible"
    def section(title, content):
        return f'<section><h2>{title}</h2>{content}</section>'
    body = section("Valeur et couverture", '<div class="cards"><article><small>Total complet</small><strong>' + money(value) +
                   '</strong></article><article><small>Sous-total connu</small><strong>' + money(known) + '</strong></article></div>' +
                   ('<p>Quantités du dernier snapshot enregistré avant la fin de période ; aucune projection rétroactive de l’inventaire actuel.</p>' if data["historical_mode"] else '<p>Quantités actuelles, prix disponibles à la date affichée.</p>') +
                   table(data["current"].loc[data["current"].category.isin([*data["categories"], "global"])]))
    basis_labels = {"manual_csv": "CSV locaux ; date des quantités non documentée",
                    "not_imported": "Aucun inventaire importé",
                    "owner_declared_full_portfolio": "Export propriétaire déclaré complet",
                    "legacy_override_coverage_unverified": "Ancien remplacement : couverture non vérifiée",
                    "recorded_snapshot": "Snapshot enregistré"}
    provenance = data["provenance"]
    body += '<p>Provenance des quantités : ' + escaped(basis_labels[provenance["basis"]]) + '</p>'
    if provenance.get("collected_at") is not None and pd.notna(provenance["collected_at"]):
        body += '<p>Date enregistrée : ' + escaped(provenance["collected_at"]) + '</p>'
    overview = body
    item_body = section("Objets", table(data["detail"].loc[data["detail"].state.eq("holdings")]))
    performance_body = section("Historique du portefeuille", '<p>Prix × quantités de chaque snapshot. Les ajouts et retraits modifient la valeur ; ce graphique ne représente pas un rendement.</p>' +
                    chart(data["historical"].loc[data["historical"].category.isin([*data["categories"], "global"])], "snapshot_date", "total_value", "Valeur complète — EUR"))
    performance_body += section("Prix à panier constant", '<p>Cohorte de la sélection actuelle ; poids égaux par objet. Base et couverture ci-dessous. Les trous restent visibles.</p>' +
                    '<p>' + escaped(diagnostic_text) + '</p>' + chart(data["indices"], "date", "index_100", "Indices base 100") + table(data["indices"]))
    performance_body += section("Transactions", '<p>Dates inconnues conservées et signalées ; la période filtre les dates connues.</p>' + table(data["transactions"]))
    changes = data["contributions"]
    effects = changes.loc[changes.covered.eq(True)]
    effect_chart = '<p class="empty">Deux snapshots avec prix et quantités connus sont nécessaires.</p>'
    if not effects.empty:
        totals = effects.groupby(["end_date", "category"], as_index=False)[["price_effect", "quantity_effect"]].sum()
        figure = px.bar(totals, x="end_date", y=["price_effect", "quantity_effect"], facet_col="category", barmode="relative",
                        title="Contributions couvertes : effets prix et quantités — EUR")
        effect_chart = figure_html(figure)
    performance_body += section("Décomposition des variations", '<p>Effet prix = quantité initiale × variation du prix ; effet quantités = variation des quantités × prix final. '
                                'La date de fin sélectionne les variations ; le snapshot précédent reste utilisé. Les contributions non couvertes restent indisponibles et sont exclues du graphique. '
                                'Un sous-total couvert ne représente pas nécessairement la variation complète du portefeuille.</p>' + effect_chart + table(changes))
    performance_body += section("Gains et pertes", '<p>' + escaped(data["pnl_message"]) + '</p>' + table(data["pnl"]))
    performance_body += section("Ventes réalisées et frais", '<p>Résultats cumulés jusqu’à la date de fin, avant le filtre de début. Les produits nets incluent les frais de vente enregistrés. '
                                'Aucun frais de vente futur n’est estimé. Un coût inconnu ou un écart de réconciliation rend le résultat correspondant indisponible ; les statuts et couvertures restent visibles ci-dessus.</p>' + table(data["sales"]))
    prediction = data["prediction"]
    forecast_body = section("Prévisions expérimentales", '<p>Prévisions de prix de la cohorte sélectionnée, sans signal d’achat/vente ni intervalle de confiance arbitraire. La période de début filtre les graphiques ; l’entraînement utilise tout le passé disponible avant la fin.</p>' +
                    table(prediction["audit"].loc[prediction["audit"].category.isin([*data["categories"], "global"])]) + table(prediction["future"]) + table(prediction["scores"]))
    forecast_body += section("Prévisions archivées", '<p>Paniers gelés originaux ; indisponibles sous un filtre objet. Les prévisions rétrospectives restent identifiées.</p>' + table(data["archive"]))
    if page == "forecasts":
        forecast_body += section("Validation chronologique", '<p>Cible : indice de prix à panier fixe, horizon un mois. '
                                 'L’expérience recalcule les origines passées ; elle ne constitue pas un historique de prévisions émises. '
                                 'Les modèles sont comparés sur les mêmes fenêtres par échantillon ; les fenêtres sans Ridge restent dans baseline_common. '
                                 'La date de début filtre les cibles affichées, sans supprimer les observations antérieures nécessaires à l’entraînement.</p>' +
                                 forecast_figures(prediction) + table(prediction["backtests"]) +
                                 '<h3>Disponibilité mensuelle et fraîcheur</h3>' + table(prediction["monthly"]) +
                                 '<p>' + escaped(prediction["diagnostic"]) + '</p>')
        forecast_body += section("Erreurs des prévisions archivées", '<p>Évaluation séparée par nature (issued/retrospective), panier, révision, code et paramètres d’origine. '
                                 'Les cibles non réalisées ou sans prix suffisamment frais ne contribuent pas aux erreurs. '
                                 'Sous un filtre objet, aucune prévision de catégorie n’est réétiquetée.</p>' + table(data["archive_metrics"]))
    body = {"overview": overview + item_body, "item": item_body,
            "performance": performance_body, "forecasts": forecast_body,
            "community": section("Recherche communautaire", "<p>Le notebook community_book et son prototype hors ligne sont disponibles. Leur intégration détaillée dans cette vue est suivie dans #56 ; aucun résultat validé n’est supposé.</p>")}.get(page, "")
    if page == "categories":
        start_filter = _parse_dates(pd.Series([params["start"]]), "period start").iloc[0] if params.get("start") else None
        for result in category_data(root, data, start_filter):
            content = table(result["summary"]) + "<h3>Inventaire et couverture</h3>" + table(result["holdings"])
            content += value_distribution(result["holdings"]) + table(result["coverage"])
            content += "<p>Prix de marché observés, EUR. Chaque base 100 utilise le premier prix non manquant disponible avant la date de fin, même s’il précède la période affichée. Une base nulle rend l’indice indisponible.</p>"
            if not result["prices"].empty or not result["acquisitions"].empty:
                content += "".join(category_figures(result))
            else:
                content += '<p class="empty">Aucun historique de marché disponible.</p>'
            content += "<h3>Références d’acquisition</h3><p>Repères séparés, exclus des prix de marché et des coûts d’achat confirmés.</p>" + table(result["acquisitions"])
            body += section(LABELS[result["category"]], content)
    if page == "community":
        from dashboard_community import community_page
        start_filter = _parse_dates(pd.Series([params["start"]]), "period start").iloc[0] if params.get("start") else None
        body = community_page(root, data, start_filter, table)
    selected_detail = None
    if page == "item":
        links = "".join('<li><a style="color:#f8b55c" href="/?' +
                        escaped(urlencode({**params, "page": "item", "item_id": row.item_id})) + '">' +
                        escaped(row.item_name) + " · " + LABELS[row.category] + "</a></li>" for row in search_results.itertuples())
        body = section("Trouver un objet", '<form method="get"><input type="hidden" name="page" value="item">' +
                       "".join('<input type="hidden" name="' + key + '" value="' + escaped(params[key]) + '">' for key in ("category", "start", "end") if params.get(key)) +
                       '<label>Nom ou variante<input name="search" value="' + escaped(search) + '" placeholder="Nom exact, usure, StatTrak…"></label><button>Rechercher</button></form><ul>' +
                       (links or "<li>Aucun objet correspondant.</li>") + "</ul>")
        if params.get("item_id"):
            start_filter = _parse_dates(pd.Series([params["start"]]), "period start").iloc[0] if params.get("start") else None
            detail = item_details(root, data, params["item_id"], start_filter)
            selected_detail = detail
            title = escaped(detail["item"]["item_name"])
            content = "<p>Objet détenu dans l’inventaire sélectionné.</p>" if detail["held"] else "<p>Objet suivi, sans position dans l’inventaire sélectionné. Aucune quantité possédée n’est déduite du catalogue.</p>"
            labels = {"item_id": "Identifiant", "category": "Catégorie", "item_name": "Nom", "market_hash_name": "Nom Steam exact",
                      "metadata_source": "Source des métadonnées", "metadata_revision": "Révision", "collection": "Collection",
                      "source_id": "Identifiant source", "variant": "Variante", "wear": "Usure", "metadata_collected_at": "Date d’import"}
            content += table(pd.DataFrame([{"Propriété": label, "Valeur": detail["item"].get(key)} for key, label in labels.items()]))
            content += table(pd.DataFrame([{"Dernier prix (EUR)": detail["latest_price"], "Date du prix": detail["latest_date"],
                                            "Ancienneté (jours)": detail["age_days"], "Observations": detail["observations"], "Date de base 100": detail["base_date"]}]))
            content += "<p>Prix de marché observés en EUR ; la médiane historique des ventes Steam n’est pas encore importée. Base 100 au premier prix non manquant avant la date de fin, hors références d’acquisition. Base nulle = indice indisponible ; trous et dates estimées restent visibles.</p>"
            if detail["held"]:
                content += table(detail["summary"]) + table(detail["valuation"])
            content += "<h3>Coût et performance</h3><p>Prix d’achat déclaré dans le CSV, sans déduction depuis les références. Un coût absent reste inconnu. Ce prix unitaire ne prouve pas le coût FIFO de lots actuels.</p>"
            content += table(pd.DataFrame([{"Prix unitaire déclaré (EUR)": detail["purchase_metadata"]["purchase_unit_price"],
                                            "Date d’achat déclarée": detail["purchase_metadata"]["purchase_date"]}]))
            content += "<p>Gains et coût restant calculés par le module FIFO, lorsqu’un inventaire initial et un journal réconciliable sont disponibles.</p>" + table(detail["gains"])
            if not detail["prices"].empty or not detail["acquisitions"].empty:
                from analyze_categories import category_price_figures
                content += "".join(figure_html(figure) for figure in category_price_figures(detail["prices"], detail["acquisitions"]))
            else:
                content += '<p class="empty">Prix et graphiques indisponibles.</p>'
            content += "<h3>Références d’acquisition</h3><p>Repères uniquement : ni prix de marché ni achat confirmé.</p>" + table(detail["acquisitions"])
            content += '<p>Métadonnées tierces : consulter <a style="color:#f8b55c" href="/sources">Sources et licences — ByMykel / CSGO-API</a> pour la provenance et les droits associés.</p>'
            body += section(title, content)
    navigation = '<nav aria-label="Vues du dashboard">' + "".join(
        '<a ' + ('aria-current="page" ' if key == page else '') + 'href="/?' +
        escaped(urlencode({**params, "page": key})) + '">' + title + '</a>' for key, title in pages.items()) + '<a href="/sources">Sources et licences</a></nav>'
    latest_price = data["detail"].price_date.max() if len(data["detail"]) else pd.NaT
    if selected_detail is not None:
        latest_price = selected_detail["latest_date"]
    last_snapshot = data["historical"].snapshot_date.max() if len(data["historical"]) else pd.NaT
    latest_price = latest_price if pd.notna(latest_price) else "Indisponible"
    last_snapshot = last_snapshot if pd.notna(last_snapshot) else "Indisponible"
    return f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CKIN2 · Portefeuille</title><script src="/plotly.js"></script><style>
*{{box-sizing:border-box}}body{{margin:0;background:#101720;color:#e6edf5;font:15px/1.6 system-ui,sans-serif}}main{{max-width:1440px;margin:auto;padding:32px}}h1{{font-size:38px;margin:0}}h2{{font-size:22px}}.eyebrow{{color:#f8b55c;letter-spacing:3px}}p,small{{color:#acbbcd}}section,form{{background:#17202b;border:1px solid #2b394b;border-radius:16px;padding:24px;margin:22px 0}}form{{display:flex;flex-wrap:wrap;gap:16px;align-items:end}}label{{display:grid;gap:6px;min-width:140px;flex:1}}select,input,button{{font:inherit;border:1px solid #526079;border-radius:7px;padding:10px;background:#101720;color:#e6edf5;max-width:100%;min-width:0}}button{{background:#f8b55c;color:#101720;cursor:pointer}}.cards{{display:flex;gap:20px;flex-wrap:wrap}}article{{flex:1;min-width:220px;padding:20px;background:#101720;border-radius:10px}}strong{{display:block;font-size:28px}}.table{{overflow:auto;max-height:480px}}table{{border-collapse:collapse;width:100%;white-space:nowrap;font-size:13px}}td,th{{padding:10px;border-bottom:1px solid #324154;text-align:left}}th{{position:sticky;top:0;background:#202d3d}}.empty{{padding:20px;border:1px dashed #526079;border-radius:10px}}@media(max-width:650px){{main{{padding:14px}}section,form{{padding:14px}}h1{{font-size:29px}}label{{min-width:100%}}.cards{{display:block}}article{{margin-bottom:12px}}}}
</style><style>nav{{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0}}nav a{{color:#d4deeb;text-decoration:none;padding:10px 15px;border:1px solid #526079;border-radius:9px}}nav a[aria-current]{{background:#f8b55c;color:#101720}}h3{{font-size:17px}}</style></head><body><main><div class="eyebrow">CKIN2 / OBSERVATOIRE</div><h1>Mon portefeuille CS2</h1>{navigation}
<p>Lecture seule · données locales · actualisé à chaque chargement · analyse au {escaped(data["cutoff"])}<br>Dernier prix utilisé : {escaped(latest_price)} · dernier snapshot de la période : {escaped(last_snapshot)}</p>
<form method="get"><input type="hidden" name="page" value="{escaped(page)}"><label>Catégorie<select name="category" onchange="this.form.elements.item_id.value=''">{categories}</select></label><label>Objet<select name="item_id">{options}</select></label><label>Depuis<input type="date" name="start" value="{escaped(params.get("start", ""))}"></label><label>Jusqu’au<input type="date" name="end" value="{escaped(params.get("end", ""))}"></label><button>Actualiser</button><a href="/?page={escaped(page)}" style="color:#f8b55c">Réinitialiser</a></form>{body}</main></body></html>'''


def make_server(root=ROOT, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("Host") not in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"):
                self.send_error(403)
                return
            path = urlsplit(self.path)
            try:
                if path.path == "/plotly.js":
                    content, mime = get_plotlyjs(), "application/javascript"
                elif path.path == "/sources":
                    content, mime = sources_page(root), "text/html; charset=utf-8"
                elif path.path == "/":
                    query = parse_qs(path.query)
                    if any(len(values) != 1 for values in query.values()):
                        raise ValueError("Duplicate filters")
                    content, mime = render(root, {key: values[0] for key, values in query.items()}), "text/html; charset=utf-8"
                else:
                    self.send_error(404)
                    return
                status = 200
            except (ValueError, OSError, KeyError) as error:
                status, mime = 400, "text/html; charset=utf-8"
                content = '<html lang="fr"><meta charset="utf-8"><h1>Données indisponibles</h1><p>' + escaped(error) + '</p><a href="/">Réinitialiser</a></html>'
            payload = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)
        def log_message(self, *args):
            pass
    return HTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = make_server(args.root, args.port)
    print(f"CKIN2 read-only dashboard: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
