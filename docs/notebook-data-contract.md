# Sélections filtrées depuis un notebook (#78)

Les notebooks versionnés utilisent désormais le contrat partagé livré par #89,
décrit dans [le workflow des notebooks](category-notebooks.md#shared-portfolio-contract-78).
Cette résolution conserve ces notebooks, leur provenance, leurs prix récents,
leurs références d’acquisition séparées et leurs quantités historiques.

`notebook_portfolio.portfolio_report` reste un adaptateur facultatif pour reproduire
une sélection avancée du dashboard dans une cellule personnelle : catégorie,
identité exacte, début et fin de période. Il ne déclenche pas un deuxième rapport
automatique dans les notebooks versionnés.

Depuis la racine du dépôt ou `notebook/`, définir facultativement
`CKIN2_DATA_ROOT` (racine contenant `data/processed/`) et `CKIN2_AS_OF`
(date ou instant d’analyse). Sans ces variables, le dépôt et l’instant courant
sont utilisés. Le tableau `context` affiche la racine résolue, la date et la
provenance des quantités. La consultation ne collecte aucun prix et n’écrit aucun
snapshot. Les fichiers privés restent hors Git ; les sorties des notebooks
versionnés sont vides.

Les remplacements propriétaires complets suivent `load_holdings` ; les
observations publiques visibles ne contribuent jamais aux quantités. Les anciens
remplacements sans provenance explicite restent signalés comme non vérifiés.
Les observations de marché récentes sont prises en compte jusqu’à l’instant
d’analyse, avec la même règle de dernier prix non manquant que le dashboard.

Pour reproduire une sélection du dashboard dans une cellule :

```python
report = portfolio_report(DATA_ROOT, category="skin", item_id="", start="2026-01-01",
                          end="2026-10-31", now=AS_OF)
display(report["context"])
display(report["current"])
```

Une fin antérieure à l’instant d’analyse utilise les quantités du dernier
snapshot global disponible avant cette fin. L’historique conserve les quantités
de chaque snapshot et exclut les prix futurs. Aucun inventaire actuel n’est
projeté dans le passé.

## Périmètres et validation

Les notebooks de catégorie et global conservent les calculs partagés de #89.
`others` sélectionne stickers, agents et charms ; `prediction` conserve son
expérience et son chargeur de prix compatibles avec les archives. La recherche
communautaire a un univers indépendant du patrimoine. Le notebook caisses utilise
les snapshots globaux enregistrés, sans fusion implicite avec l’ancien historique
de caisses.

`test_notebook_portfolio.py` exécute les six notebooks sur des jeux synthétiques
complets, partiels, absents, avec quantités inconnues et après remplacement
propriétaire. Il vérifie leurs résultats et l’adaptateur filtré contre le dashboard,
y compris prévisions, références séparées et sélection historique. Les fichiers
sont comparés avant/après lecture ; aucune sortie privée n’est versionnée.
