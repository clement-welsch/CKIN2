# Données communes aux notebooks et au dashboard (#78)

Les rapports de patrimoine des notebooks `cases`, `skins`, `souvenirs`,
`others`, `global` et `prediction` passent par `notebook_portfolio.portfolio_report`.
Ce point d’entrée appelle la sélection du dashboard : mêmes identités exactes,
quantités, observations de prix, valeurs et couvertures. Les acquisitions restent
des références séparées ; elles ne deviennent ni prix de marché ni achats confirmés.

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

## Périmètres d’analyse

- `global` : patrimoine des six catégories ; mêmes tableaux de valeur et
  d’historique que le dashboard sans filtre.
- `skins`, `souvenirs` : catégorie correspondante ; `others` présente séparément
  stickers, agents et charms, comme les vues catégories du dashboard.
- `prediction` : expérience du dashboard Prévisions, mêmes paramètres par défaut.
  Les archives restent évaluées séparément ; aucun modèle n’est réécrit.
- `cases` : rapport partagé de la catégorie `case` en tête. L’exploration ensuite
  conservée porte sur les prix de caisses, les quantités actuelles connues et
  l’ancien historique de snapshots de caisses. Sa cohorte de prix et ses anciens
  snapshots ont un périmètre distinct de l’indice et des snapshots globaux.
  Les quantités inconnues restent dans le rapport partagé et sont exclues de
  cette exploration ancienne. Les coûts FIFO sont consultables dans les fiches
  objets du dashboard ; aucune référence d’acquisition n’est assimilée à un coût.
- `community` : corpus de recherche indépendant, inchangé.

## Validation synthétique

`test_notebook_portfolio.py` exécute les cellules des six notebooks et compare
leurs valeurs, détails et historiques au dashboard sur des données complètes,
partielles, absentes et remplacées par le propriétaire. Les fichiers sont
comparés avant/après lecture. Un test de sélection historique vérifie les
quantités du snapshot et l’exclusion des observations futures.
