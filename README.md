# ARSEL Financial Analyst

Le projet est organisé en deux pipelines :

1. la Phase 1 extrait et fait valider les métriques du modèle Excel ;
2. la Phase 2 normalise ces métriques, calcule les indicateurs et produit une analyse comparative.

## Commandes principales

```powershell
python arsel_analyse.py "C:\chemin\modele.xlsm"
python run_phase2.py hypotheses_validees.json
```

La seconde commande produit les trois formats suivants dans `outputs/phase2/` :

- `analyse_financiere_phase2.json`
- `analyse_financiere_phase2.md`
- `analyse_financiere_phase2.docx`

## Organisation

| Dossier | Contenu |
|---|---|
| `arsel_core/` | moteur d'extraction et de validation de la Phase 1 |
| `phase2/` | normalisation, calculs, benchmarks et génération des rapports |
| `benchmark_hybrid/` | collecte hybride et référentiel détaillé de benchmarks |
| `data/` | ontologie ARSEL utilisée par la Phase 1 |
| `evaluation/` | scripts, données et résultats d'évaluation technique |
| `tests/` | tests automatisés |
| `docs/` | documentation et schémas |
| `outputs/` | rapports générés |
| `legacy/` | ancienne implémentation conservée comme archive |

Les deux fichiers nommés auparavant `referentiel_normes.json` ont maintenant des rôles explicites :

- `phase2/data/comparison_controls.json` contient les seuils et règles de comparaison ;
- `benchmark_hybrid/data/referentiel_normes.json` contient les observations détaillées par source et par projet.

## Prérequis

```powershell
pip install -r requirements.txt
setx GEMINI_API_KEY "votre-cle"
```

Sans clé Gemini, la Phase 1 reste utilisable avec sa sélection hybride locale
(présélection, TF-IDF et embeddings) et la validation manuelle. Si
`sentence-transformers` ou son modèle local ne sont pas disponibles, elle se
replie automatiquement sur la présélection et TF-IDF. La Phase 2 est
déterministe et ne nécessite pas d'appel LLM.

## Outils d'évaluation

Les outils secondaires se lancent comme modules afin de conserver des imports propres :

```powershell
python -m evaluation.evaluer_tfidf "C:\chemin\modele.xlsm"
python -m evaluation.benchmark_pipeline "C:\chemin\modele.xlsm" evaluation/data/ground_truth_kikot.json
```
