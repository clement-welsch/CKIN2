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
from global_analysis import analyze, market_indices
from global_snapshots import COLUMNS, build_snapshot, value_snapshots
from portfolio_data import CATEGORIES, ROOT, _parse_dates
from prediction import experiment
from transactions import COLUMNS as TRANSACTIONS, validate_transactions
from source_attribution import sources_page
from dashboard_categories import LABELS, category_data, category_figures, value_distribution


def escaped(value):
    return html.escape(str(value), quote=True)


def subset_snapshots(snapshots, categories, item_id):
    """Keep six explicit category markers so shared validation/valuation applies."""
    rows = []
    for stamp, group in snapshots.groupby("snapshot_date"):
        for category in CATEGORIES:
            selected = group.loc[group.category.eq(category)]
            if category not in categories:
                selected = selected.iloc[:0]
            elif item_id:
                selected = selected.loc[~selected.state.eq("holdings") | selected.item_id.eq(item_id)]
            if selected.empty:
                rows.append(dict(snapshot_date=stamp, category=category, state="empty", item_id=None, item_name=None, quantity=0))
            else:
                rows.extend(selected[COLUMNS].to_dict("records"))
    return pd.DataFrame(rows, columns=COLUMNS)


def view(root=ROOT, *, category="all", item_id="", start=None, end=None, now=None, components=None):
    root = Path(root)
    if category not in (*CATEGORIES, "all"):
        raise ValueError("Unknown category")
    now = _parse_dates(pd.Series([pd.Timestamp.now() if now is None else now]), "dashboard now").iloc[0]
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
    if item_id and item_id not in set(registry.loc[registry.category.isin(categories), "item_id"]):
        raise ValueError("Unknown object for this category")
    # Current holdings cannot be projected backward when end precedes now.
    historical_mode = end is not None and cutoff < now
    if historical_mode:
        available = data["history"]
        current_snapshot = available.loc[available.snapshot_date.eq(available.snapshot_date.max())]
    else:
        current_snapshot = data["current_detail"][COLUMNS]
    detail, current = value_snapshots(subset_snapshots(current_snapshot, categories, item_id), data["prices"])
    history = data["history"]
    if start is not None:
        history = history.loc[history.snapshot_date.ge(start)]
    _, historical = value_snapshots(subset_snapshots(history, categories, item_id), data["prices"])
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
    if components in (None, "performance") and (root / "data/processed/opening_inventory.csv").exists():
        from profit_loss import report
        with contextlib.redirect_stdout(io.StringIO()):
            pnl = report(root, when=cutoff)["items"]
        pnl = pnl.loc[pnl.category.isin(categories)]
        if item_id:
            pnl = pnl.loc[pnl.item_id.eq(item_id)]
        pnl_message = "FIFO depuis l'inventaire initial jusqu'à la date choisie ; coûts inconnus = N/A, frais de vente futurs non estimés."
    prediction = {key: pd.DataFrame(columns=["category"]) for key in ("audit", "future", "scores")}
    archive = pd.DataFrame(columns=["category"])
    if components in (None, "forecasts"):
        prediction = experiment(cohort, data["prices"], cutoff)
        archive, metrics = evaluate(root / "data/processed/forecast_archive", load_archive_prices(root), cutoff,
                                    target_start=start, target_end=cutoff)
    archive = archive.loc[archive.category.isin([*categories, "global"] if category == "all" else categories)]
    if item_id:
        archive = archive.iloc[:0]  # Frozen category baskets cannot be relabeled as item forecasts.
    return dict(now=now, cutoff=cutoff, historical_mode=historical_mode, categories=categories,
                registry=registry, detail=detail, current=current, historical=historical,
                indices=indices, diagnostic=diagnostic, transactions=transactions,
                pnl=pnl, pnl_message=pnl_message, prediction=prediction, archive=archive, prices=data["prices"], selected_item_id=item_id)


def table(frame):
    if frame.empty:
        return '<p class="empty">Aucune donnée disponible pour cette sélection.</p>'
    return '<div class="table">' + frame.to_html(index=False, na_rep="N/A", escape=True, border=0, float_format=lambda x: f"{x:,.2f}") + '</div>'


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
    overview = body
    item_body = section("Objets", table(data["detail"].loc[data["detail"].state.eq("holdings")]))
    performance_body = section("Historique du portefeuille", '<p>Prix × quantités de chaque snapshot. Les ajouts et retraits modifient la valeur ; ce graphique ne représente pas un rendement.</p>' +
                    chart(data["historical"].loc[data["historical"].category.isin([*data["categories"], "global"])], "snapshot_date", "total_value", "Valeur complète — EUR"))
    performance_body += section("Prix à panier constant", '<p>Cohorte de la sélection actuelle ; poids égaux par objet. Base et couverture ci-dessous. Les trous restent visibles.</p>' +
                    '<p>' + escaped(diagnostic_text) + '</p>' + chart(data["indices"], "date", "index_100", "Indices base 100") + table(data["indices"]))
    performance_body += section("Transactions", '<p>Dates inconnues conservées et signalées ; la période filtre les dates connues.</p>' + table(data["transactions"]))
    performance_body += section("Gains et pertes", '<p>' + escaped(data["pnl_message"]) + '</p>' + table(data["pnl"]))
    prediction = data["prediction"]
    forecast_body = section("Prévisions expérimentales", '<p>Prévisions de prix de la cohorte sélectionnée, sans signal d’achat/vente ni intervalle de confiance arbitraire. La période de début filtre les graphiques ; l’entraînement utilise tout le passé disponible avant la fin.</p>' +
                    table(prediction["audit"].loc[prediction["audit"].category.isin([*data["categories"], "global"])]) + table(prediction["future"]) + table(prediction["scores"]))
    forecast_body += section("Prévisions archivées", '<p>Paniers gelés originaux ; indisponibles sous un filtre objet. Les prévisions rétrospectives restent identifiées.</p>' + table(data["archive"]))
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
    navigation = '<nav aria-label="Vues du dashboard">' + "".join(
        '<a ' + ('aria-current="page" ' if key == page else '') + 'href="/?' +
        escaped(urlencode({**params, "page": key})) + '">' + title + '</a>' for key, title in pages.items()) + '<a href="/sources">Sources et licences</a></nav>'
    latest_price = data["detail"].price_date.max() if len(data["detail"]) else pd.NaT
    last_snapshot = data["historical"].snapshot_date.max() if len(data["historical"]) else pd.NaT
    return f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CKIN2 · Portefeuille</title><script src="/plotly.js"></script><style>
*{{box-sizing:border-box}}body{{margin:0;background:#101720;color:#e6edf5;font:15px/1.6 system-ui,sans-serif}}main{{max-width:1440px;margin:auto;padding:32px}}h1{{font-size:38px;margin:0}}h2{{font-size:22px}}.eyebrow{{color:#f8b55c;letter-spacing:3px}}p,small{{color:#acbbcd}}section,form{{background:#17202b;border:1px solid #2b394b;border-radius:16px;padding:24px;margin:22px 0}}form{{display:flex;flex-wrap:wrap;gap:16px;align-items:end}}label{{display:grid;gap:6px;min-width:140px;flex:1}}select,input,button{{font:inherit;border:1px solid #526079;border-radius:7px;padding:10px;background:#101720;color:#e6edf5;max-width:100%;min-width:0}}button{{background:#f8b55c;color:#101720;cursor:pointer}}.cards{{display:flex;gap:20px;flex-wrap:wrap}}article{{flex:1;min-width:220px;padding:20px;background:#101720;border-radius:10px}}strong{{display:block;font-size:28px}}.table{{overflow:auto;max-height:480px}}table{{border-collapse:collapse;width:100%;white-space:nowrap;font-size:13px}}td,th{{padding:10px;border-bottom:1px solid #324154;text-align:left}}th{{position:sticky;top:0;background:#202d3d}}.empty{{padding:20px;border:1px dashed #526079;border-radius:10px}}@media(max-width:650px){{main{{padding:14px}}section,form{{padding:14px}}h1{{font-size:29px}}label{{min-width:100%}}.cards{{display:block}}article{{margin-bottom:12px}}}}
</style><style>nav{{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0}}nav a{{color:#d4deeb;text-decoration:none;padding:10px 15px;border:1px solid #526079;border-radius:9px}}nav a[aria-current]{{background:#f8b55c;color:#101720}}h3{{font-size:17px}}</style></head><body><main><div class="eyebrow">CKIN2 / OBSERVATOIRE</div><h1>Mon portefeuille CS2</h1>{navigation}
<p><a href="/sources" style="color:#f8b55c">Sources et licences</a></p>
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
