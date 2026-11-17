# Contribuer à CKIN2

## 1. Présentation

CKIN2 est une application de suivi et d'analyse d'inventaire Counter-Strike 2.

Les contributions doivent préserver l'intégrité des données, la fiabilité des calculs et la cohérence des fonctionnalités existantes.

Les instructions destinées aux agents IA sont définies dans `AGENTS.md`.

## 2. Périmètre des contributions

Les contributions peuvent concerner :

- Le suivi et l'historique des inventaires.
- La collecte et le traitement des données.
- Les calculs, statistiques et visualisations.
- L'amélioration de l'interface utilisateur.
- La correction de bugs et l'amélioration des performances.
- Les tests et la documentation.

Toute modification doit correspondre à une demande ou une issue identifiée.

Éviter les refactorings sans rapport avec l'objectif initial.

## 3. Workflow GitHub

### Branches

- Utiliser une branche dédiée à chaque issue.
- Partir de la branche de développement définie dans le dépôt.
- Ne pas modifier directement la branche principale pour une fonctionnalité.
- Préserver les modifications locales existantes.

Conventions de nommage recommandées :

- `feat/` : nouvelle fonctionnalité.
- `fix/` : correction de bug.
- `refactor/` : restructuration sans changement fonctionnel.
- `docs/` : documentation.
- `ci/` : intégration continue.

### Commits

Rédiger les messages de commit en anglais, avec un préfixe explicite.

Exemples :

```text
feat: add inventory history filtering
fix: correct inventory value calculation
test: add inventory parsing regression tests
docs: update installation instructions
```

Un seul commit est suffisant pour une modification simple. Les modifications plus importantes peuvent être réparties en plusieurs commits cohérents.

Ne pas créer de commits artificiels.

### Pull requests

- Créer une PR ciblée sur une issue.
- Décrire les changements réalisés.
- Indiquer les tests réellement exécutés.
- Signaler les limitations et risques connus.
- Vérifier les contrôles automatiques disponibles.
- Ne pas fusionner sans autorisation explicite du porteur du projet.

## 4. Qualité du code

- Respecter l'architecture et les conventions existantes.
- Privilégier les solutions simples et maintenables.
- Réutiliser les composants déjà disponibles.
- Éviter les dépendances inutiles.
- Préserver la compatibilité des données existantes.
- Ne jamais intégrer de secrets ou de fichiers temporaires au dépôt.

Les changements de structure des données doivent être justifiés et accompagnés d'une stratégie de compatibilité ou de migration lorsque nécessaire.

## 5. Intégrité des données

- Ne jamais modifier ou supprimer des données réelles pour faciliter un test.
- Distinguer les données observées, calculées, estimées et indisponibles.
- Préserver la précision des valeurs numériques et des dates.
- Vérifier les traitements susceptibles de créer des doublons.
- Utiliser des données fictives ou isolées dans les tests.
- Respecter les limitations et conditions d'utilisation des API externes.

## 6. Tests et validation

Adapter les validations à la nature des modifications.

### Corrections simples

- Exécuter les tests directement concernés.
- Vérifier l'absence de régression évidente.
- Contrôler les modifications Git avant livraison.

### Modifications fonctionnelles

- Tester le comportement nominal.
- Tester les cas limites pertinents.
- Vérifier la compatibilité avec les données existantes.
- Exécuter les tests de non-régression concernés.

### Modifications critiques

Pour les changements affectant la persistance, les calculs financiers, les données historiques ou les intégrations externes :

- Renforcer les tests automatisés.
- Vérifier les scénarios d'erreur.
- Contrôler les risques de perte ou de corruption de données.
- Vérifier les résultats sur des données de test représentatives.

Ne pas relancer une suite complète si son résultat est déjà valide pour le même état du code, sauf justification.

Les commandes exactes de compilation et de test doivent être documentées après vérification de l'architecture réelle du dépôt.

## 7. Documentation

Mettre à jour la documentation lorsqu'une contribution modifie :

- L'installation ou la configuration.
- Le comportement d'une fonctionnalité.
- Le format ou la structure des données.
- Les dépendances.
- Les procédures de développement ou de validation.

Éviter les modifications documentaires sans rapport avec la contribution.

## 8. Critères de livraison

Une contribution est prête pour revue lorsque :

1. Le comportement demandé est implémenté.
2. Les critères d'acceptation sont satisfaits.
3. Les tests pertinents ont été exécutés.
4. Les données existantes sont préservées.
5. La documentation concernée est à jour.
6. Les limites et risques éventuels sont signalés.

La fusion reste soumise à l'autorisation du porteur du projet.