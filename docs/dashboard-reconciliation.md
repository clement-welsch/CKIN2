# Rapprochement patrimoine / inventaire visible (#81)

Ouvrir **Patrimoine et inventaire visible** dans le dashboard, ou
`http://127.0.0.1:8765/reconciliation`. Cette page compare les quantités actuelles
connues aux observations visibles enregistrées localement par l’import existant.
Elle n’applique aucun ajustement, n’appelle pas Steam et ne lit pas les prix.
Un fichier facultatif de prix invalide ne bloque donc pas cette comparaison.

## Sources et périmètres

- Le patrimoine unique vient de `load_holdings` : CSV locaux ou remplacement
  propriétaire complet. La provenance et la date de capture propriétaire, si
  renseignée, apparaissent séparément. Un ancien remplacement sans couverture
  explicite reste signalé comme non vérifié ; les CSV n’ont pas de date de saisie
  déduite artificiellement de leur date de modification.
- La capture actuelle vient de `steam_inventory_visible.json`. Chaque compte
  garde sa date et sa source. Le sélecteur permet de comparer tous les comptes
  de cette capture ou un seul ; l’URL `?account=...` conserve la sélection.
  Aucun rôle principal/secondaire n’est deviné à partir d’un identifiant.
- Les captures d’audit et les quantités des comptes mis en cache ne sont jamais
  additionnées à la sélection actuelle. Les dates des comptes omis restent
  affichées comme contexte, sans réintroduire leurs quantités.
- La comparaison porte sur l’état actuel, sans filtres historiques de la page
  portefeuille. Le lien retour ramène au portefeuille ; les fiches objets
  utilisent l’identité exacte et la catégorie.

Les statuts partagés avec l’import distinguent non observé, visible inférieur,
visible supérieur, concordant, nouvellement observé et total connu inconnu.
Une quantité absente est affichée **Inconnue** ; aucune absence ne prouve une
vente, une quantité zéro ou un patrimoine vide. Une observation nouvelle ne
crée aucune quantité connue.

Les unités de stockage et les comptes omis restent hors couverture. Des dates de
capture différentes déclenchent un avertissement explicite. Même à date égale,
un transfert pendant les captures peut créer un manque ou un double comptage ;
aucun transfert n’est identifié automatiquement. Les correspondances non
résolues sont listées par compte et exclues des quantités rapprochées.

## Validation et limites

La lecture valide les identités, les comptes, les dates, les provenances, les
quantités et la concordance entre détail par compte et agrégat. Une capture
malformée bloque ce rapprochement et demande de refaire la prévisualisation ;
aucune réparation automatique ni lecture d’anciens audits en remplacement.
La synthèse du patrimoine ne dépend pas de ce fichier et reste indépendante.

Tests synthétiques : capture absente/vide, objet stocké non observé, quantités
inconnues, six statuts, deux comptes, compte omis, déplacement secondaire vers
principal, dates décalées, non-résolus, texte HTML échappé, provenance propriétaire
et ancienne, données invalides et absence d’écriture. Les tests HTTP couvrent
le cache désactivé, les filtres invalides et l’indépendance des prix.
