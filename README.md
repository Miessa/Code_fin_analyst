# Système d'analyse financière ARSEL

Outil d'aide à l'analyse financière des modèles de projets soumis à ARSEL.
Il **extrait** les hypothèses et métriques d'un modèle de promoteur, en
**s'adaptant** à la façon dont chaque promoteur structure ses données, et
laisse l'**analyste valider** avant tout enregistrement.

Ce n'est PAS un outil d'audit/reconstruction du modèle : il ne recalcule pas
les formules du promoteur. Il lit, structure et restitue — pour juger le projet.

## Principe directeur

**Le LLM pointe, le code lit.**
- le LLM (Gemini) ne voit que des libellés + valeurs voisines et ne renvoie
  qu'une **adresse** de cellule ;
- le **code** détecte la structure de cette cellule et lit la ou les valeurs ;
- l'**analyste** valide.
Aucune valeur numérique ne transite par le LLM ; tout chiffre est lu par le
code à une adresse vérifiable.

## Structure adaptative — 4 primitives

Le système ne suppose aucune structure fixe. Pour chaque métrique, il détecte
à l'exécution quelle(s) **primitive(s)** le promoteur a utilisée(s) :

| primitive       | exemple                                   |
|-----------------|-------------------------------------------|
| valeur simple   | OPEX = 718 M                              |
| sélection       | sélecteur d'indice (1=EUR, 2=Cameroun…)   |
| série temporelle| courbe d'inflation sur 50 ans             |
| décomposition   | CAPEX = 9 composantes + total             |

Elles se **composent** : un CAPEX décomposé dont une composante a un sélecteur
pointant vers une série est détecté comme les trois à la fois.
Les séries temporelles sont restituées en **paliers datés** (pas de moyenne,
pas 200 points) : ex. « 7,22 % de 2023 à 2025, puis 2,00 % ensuite ».

## Fichiers

| fichier | rôle |
|---|---|
| `arsel_analyse.py` | **point d'entrée** interactif (à lancer) |
| `referentiel_arsel.json` | **données** : liste des concepts (définitions, exemples, mots-clés, plages, catégories) — éditable sans toucher au code |
| `collecter_libelles.py` | le code collecte TOUS les libellés (catalogue complet) |
| `gemini_provider.py` | le LLM cherche le bon libellé dans tout le catalogue (par numéro) |
| `primitives.py` | détecteurs des 4 primitives de structure |
| `series_temporelle.py` | segmentation des séries en paliers datés |
| `resoudre.py` | applique le traitement adapté à la structure détectée |

## Prérequis
```
pip install openpyxl google-genai
setx GEMINI_API_KEY "AIza..."     # puis rouvrir le terminal
```

## Lancement
```
python arsel_analyse.py "chemin\vers\MODELE.xlsm"
```
Référentiel personnalisé (optionnel) : ajouter son chemin en 2e argument.

## Déroulé
0. **Concepts** — définitions + exemples de chaque hypothèse cherchée
1. **Extraction** — LLM pointe · code détecte la structure · lit les valeurs
2. **Validation** — l'analyste : [v]alider / [c]orriger / [s]auter / [q]uitter
3. **Registre** — écrit `hypotheses_validees.json`

Sans clé Gemini, le système fonctionne en mode manuel : il liste les candidats
et demande l'appariement à l'analyste (il ne devine jamais).

## À compléter (prochaines briques d'analyse financière)
- **benchmark** : comparer les valeurs extraites aux normes ARSEL
- **résolution d'indice** : relier un sélecteur (ex. OPEX→2) à l'indice nommé
- **analyse tarif ↔ TRI cible** : substituer la contrainte ARSEL
- **détection des données manquantes** ; **fiche de restitution** structurée
