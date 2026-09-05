# Guide d’accès à la banque DuckDB

Ce guide rassemble les commandes utiles pour consulter la banque de benchmarks ARSEL depuis PowerShell. Les exemples utilisent la base active et ouvrent systématiquement DuckDB en lecture seule afin d’éviter toute modification accidentelle.

Les commandes doivent être exécutées depuis la racine du projet :

```text
C:\Users\Admin\Downloads\ARSEL\Code_fin_analyst
```

## 1. Identifier les fichiers DuckDB

Afficher les chemins complets de toutes les bases :

```powershell
Get-ChildItem .\benchmark_bank -Recurse -Filter *.duckdb |
Select-Object -ExpandProperty FullName
```

Afficher également la taille et la date de modification :

```powershell
Get-ChildItem .\benchmark_bank -Recurse -Filter *.duckdb |
Format-List FullName, Length, LastWriteTime
```

Les principales bases sont :

| Fichier | Fonction |
|---|---|
| `benchmark_bank\data\benchmark_bank.duckdb` | Base active utilisée par la Phase 2 |
| `benchmark_bank\data\staging.duckdb` | Données importées en attente de contrôle ou de promotion |
| `benchmark_bank\data\backups\*.duckdb` | Sauvegardes historiques de la base active |

## 2. Vérifier que DuckDB est installé

```powershell
python -c "import duckdb; print(duckdb.__version__)"
```

En cas d’erreur `ModuleNotFoundError` :

```powershell
python -m pip install duckdb pandas
```

## 3. Principe des commandes en lecture seule

Toutes les commandes de consultation utilisent cette connexion :

```python
duckdb.connect(r"benchmark_bank\data\benchmark_bank.duckdb", read_only=True)
```

L’option `read_only=True` protège la base active contre les modifications accidentelles.

## 4. Afficher les tables disponibles

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('SHOW TABLES').fetchdf().to_string(index=False))"
```

Les vues à utiliser pour les consultations ordinaires sont :

| Vue | Contenu |
|---|---|
| `current_projects` | Version actuelle des projets individuels |
| `current_observations` | Version actuelle des observations et métriques |
| `current_sources` | Sources actuellement enregistrées |
| `current_ingestion_runs` | Exécutions d’ingestion actuelles |
| `current_normalization_events` | Transformations et règles de normalisation actuelles |

Les tables commençant par `bank_` conservent toutes les révisions et servent surtout à l’audit historique.

## 5. Examiner la structure d’une table

Projets :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('DESCRIBE current_projects').fetchdf().to_string(index=False))"
```

Observations :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('DESCRIBE current_observations').fetchdf().to_string(index=False))"
```

Sources :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('DESCRIBE current_sources').fetchdf().to_string(index=False))"
```

Remplacer le nom placé après `DESCRIBE` pour inspecter une autre table.

## 6. Afficher quelques lignes

Dix projets :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('SELECT * FROM current_projects LIMIT 10').fetchdf().to_string(index=False))"
```

Dix observations :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('SELECT * FROM current_observations LIMIT 10').fetchdf().to_string(index=False))"
```

Toutes les sources :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('SELECT source_id, organization, source_type, publication_date, review_status FROM current_sources ORDER BY organization').fetchdf().to_string(index=False))"
```

## 7. Compter les données présentes

Nombre de projets :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('SELECT COUNT(*) AS nombre_projets FROM current_projects').fetchdf().to_string(index=False))"
```

Nombre d’observations :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('SELECT COUNT(*) AS nombre_observations FROM current_observations').fetchdf().to_string(index=False))"
```

Comptage général des vues courantes :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q='''SELECT 'projects' objet, COUNT(*) nombre FROM current_projects UNION ALL SELECT 'observations', COUNT(*) FROM current_observations UNION ALL SELECT 'sources', COUNT(*) FROM current_sources UNION ALL SELECT 'ingestion_runs', COUNT(*) FROM current_ingestion_runs UNION ALL SELECT 'normalization_events', COUNT(*) FROM current_normalization_events'''; print(c.execute(q).fetchdf().to_string(index=False))"
```

## 8. Explorer les projets

Répartition par technologie :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('SELECT technology, COUNT(*) AS nombre FROM current_projects GROUP BY technology ORDER BY nombre DESC').fetchdf().to_string(index=False))"
```

Répartition par région :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('SELECT region, COUNT(*) AS nombre FROM current_projects GROUP BY region ORDER BY nombre DESC').fetchdf().to_string(index=False))"
```

Répartition par pays :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('SELECT country_iso3, COUNT(*) AS nombre FROM current_projects GROUP BY country_iso3 ORDER BY nombre DESC LIMIT 50').fetchdf().to_string(index=False))"
```

Projets hydroélectriques :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT project_id, project_name, country_iso3, region, technology, project_type FROM current_projects WHERE lower(technology) LIKE '%hydro%' ORDER BY country_iso3, project_name LIMIT 100\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

Projets solaires :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT project_id, project_name, country_iso3, region, technology FROM current_projects WHERE lower(technology) LIKE '%solar%' ORDER BY country_iso3, project_name LIMIT 100\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

Rechercher un projet par une partie de son nom :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT project_id, project_name, country_iso3, technology FROM current_projects WHERE project_name ILIKE '%Kikot%'\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

Remplacer `Kikot` par le nom recherché.

## 9. Explorer les observations et métriques

Liste des métriques disponibles :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('SELECT metric, COUNT(*) AS nombre FROM current_observations GROUP BY metric ORDER BY nombre DESC').fetchdf().to_string(index=False))"
```

Répartition par type d’observation :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('SELECT observation_type, COUNT(*) AS nombre FROM current_observations GROUP BY observation_type ORDER BY nombre DESC').fetchdf().to_string(index=False))"
```

Répartition par unité normalisée :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('SELECT normalized_unit, COUNT(*) AS nombre FROM current_observations GROUP BY normalized_unit ORDER BY nombre DESC').fetchdf().to_string(index=False))"
```

Afficher une métrique particulière :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT observation_id, source_id, project_id, metric, normalized_value, normalized_unit, currency, price_year, statistic, review_status FROM current_observations WHERE metric='investment_per_mw' LIMIT 100\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

Remplacer `investment_per_mw` par la métrique recherchée.

Rechercher les métriques contenant un mot :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT DISTINCT metric FROM current_observations WHERE metric ILIKE '%cost%' ORDER BY metric\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

## 10. Relier les projets à leurs observations

Afficher les observations des projets hydroélectriques :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT p.project_name, p.country_iso3, p.technology, o.metric, o.normalized_value, o.normalized_unit, o.currency, o.price_year FROM current_projects p JOIN current_observations o ON o.project_id=p.project_id WHERE lower(p.technology) LIKE '%hydro%' ORDER BY p.project_name, o.metric LIMIT 200\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

Afficher toutes les observations d’un projet identifié :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT p.project_name, o.metric, o.raw_value_numeric, o.raw_unit, o.normalized_value, o.normalized_unit, o.quality_level, o.review_status FROM current_projects p JOIN current_observations o ON o.project_id=p.project_id WHERE p.project_id='IDENTIFIANT_DU_PROJET' ORDER BY o.metric\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

Remplacer `IDENTIFIANT_DU_PROJET` par un identifiant réel obtenu dans `current_projects`.

## 11. Consulter les références IRENA et World Bank

Compter les observations par organisme :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q='''SELECT s.organization, COUNT(*) AS nombre FROM current_observations o LEFT JOIN current_sources s ON s.source_id=o.source_id GROUP BY s.organization ORDER BY nombre DESC'''; print(c.execute(q).fetchdf().to_string(index=False))"
```

Afficher les observations IRENA :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT o.metric, o.normalized_value, o.normalized_low, o.normalized_high, o.normalized_unit, o.currency, o.price_year, o.statistic, o.economic_perimeter FROM current_observations o JOIN current_sources s ON s.source_id=o.source_id WHERE s.organization ILIKE '%IRENA%' ORDER BY o.metric LIMIT 200\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

Afficher les projets et observations liés à la Banque mondiale :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT p.project_name, p.country_iso3, p.technology, o.metric, o.normalized_value, o.normalized_unit FROM current_projects p JOIN current_observations o ON o.project_id=p.project_id JOIN current_sources s ON s.source_id=o.source_id WHERE s.organization ILIKE '%World Bank%' ORDER BY p.project_name, o.metric LIMIT 200\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

## 12. Calculer des statistiques simples

Statistiques pour une métrique :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT COUNT(normalized_value) AS n, MIN(normalized_value) AS minimum, quantile_cont(normalized_value,0.25) AS p25, MEDIAN(normalized_value) AS mediane, quantile_cont(normalized_value,0.75) AS p75, MAX(normalized_value) AS maximum FROM current_observations WHERE metric='investment_per_mw' AND normalized_value IS NOT NULL\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

Statistiques par technologie pour une métrique liée aux projets :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT p.technology, COUNT(o.normalized_value) AS n, MEDIAN(o.normalized_value) AS mediane, quantile_cont(o.normalized_value,0.25) AS p25, quantile_cont(o.normalized_value,0.75) AS p75, o.normalized_unit FROM current_projects p JOIN current_observations o ON o.project_id=p.project_id WHERE o.metric='investment_per_mw' AND o.normalized_value IS NOT NULL GROUP BY p.technology, o.normalized_unit ORDER BY n DESC\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

Ne regrouper ensemble que des observations ayant la même unité et un périmètre économique compatible.

## 13. Contrôler la qualité des données

Observations par statut de revue :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('SELECT review_status, COUNT(*) AS nombre FROM current_observations GROUP BY review_status ORDER BY nombre DESC').fetchdf().to_string(index=False))"
```

Observations par niveau de qualité :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute('SELECT quality_level, COUNT(*) AS nombre FROM current_observations GROUP BY quality_level ORDER BY nombre DESC').fetchdf().to_string(index=False))"
```

Observations sans valeur normalisée :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT metric, value_status, COUNT(*) AS nombre FROM current_observations WHERE normalized_value IS NULL AND normalized_low IS NULL AND normalized_high IS NULL GROUP BY metric, value_status ORDER BY nombre DESC\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

Projets sans technologie, qui devraient normalement être absents :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print(c.execute(\"SELECT COUNT(*) AS projets_sans_technologie FROM current_projects WHERE technology IS NULL OR trim(technology)=''\").fetchdf().to_string(index=False))"
```

Doublons potentiels par nom, pays et technologie :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q='''SELECT project_name, country_iso3, technology, COUNT(*) AS nombre FROM current_projects GROUP BY project_name, country_iso3, technology HAVING COUNT(*) > 1 ORDER BY nombre DESC'''; print(c.execute(q).fetchdf().to_string(index=False))"
```

## 14. Examiner les ingestions et les normalisations

Historique courant des ingestions :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q='''SELECT ingestion_run_id, source_id, adapter_name, adapter_version, status, started_at, completed_at FROM current_ingestion_runs ORDER BY started_at DESC'''; print(c.execute(q).fetchdf().to_string(index=False))"
```

Nombre de normalisations par règle :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT json_extract_string(payload_json, '$.rule_id') AS rule_id, rule_version, json_extract_string(payload_json, '$.field_name') AS field_name, COUNT(*) AS nombre FROM current_normalization_events GROUP BY rule_id, rule_version, field_name ORDER BY nombre DESC\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

Normalisations appliquées à une observation :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT json_extract_string(payload_json, '$.observation_id') AS observation_id, json_extract_string(payload_json, '$.field_name') AS field_name, json_extract_string(payload_json, '$.rule_id') AS rule_id, rule_version, created_at FROM current_normalization_events WHERE json_extract_string(payload_json, '$.observation_id')='IDENTIFIANT_OBSERVATION' ORDER BY created_at\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

## 15. Consulter les données JSON détaillées

Les colonnes `payload_json` conservent les objets complets. Afficher le JSON d’un projet :

```powershell
python -c "import duckdb,json; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); v=c.execute(\"SELECT payload_json FROM current_projects WHERE project_id='IDENTIFIANT_DU_PROJET'\").fetchone(); print(json.dumps(json.loads(v[0]), ensure_ascii=False, indent=2) if v else 'Projet introuvable')"
```

Afficher le JSON d’une observation :

```powershell
python -c "import duckdb,json; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); v=c.execute(\"SELECT payload_json FROM current_observations WHERE observation_id='IDENTIFIANT_OBSERVATION'\").fetchone(); print(json.dumps(json.loads(v[0]), ensure_ascii=False, indent=2) if v else 'Observation introuvable')"
```

## 16. Consulter la base de staging

Afficher ses tables :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\staging.duckdb', read_only=True); print(c.execute('SHOW TABLES').fetchdf().to_string(index=False))"
```

Compter les projets et observations en staging :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\staging.duckdb', read_only=True); q=\"SELECT 'projects' AS objet, COUNT(*) AS nombre FROM current_projects UNION ALL SELECT 'observations', COUNT(*) FROM current_observations\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

Cette commande suppose que les vues `current_projects` et `current_observations` existent également dans le staging. Utiliser `SHOW TABLES` pour le confirmer.

## 17. Comparer la base active et le staging

Cette commande attache les deux fichiers dans une connexion temporaire en mémoire et les ouvre en lecture seule :

```powershell
python -c "import duckdb; c=duckdb.connect(':memory:'); c.execute(\"ATTACH 'benchmark_bank/data/benchmark_bank.duckdb' AS active (READ_ONLY)\"); c.execute(\"ATTACH 'benchmark_bank/data/staging.duckdb' AS staging (READ_ONLY)\"); q=\"SELECT 'active_projects' objet, COUNT(*) nombre FROM active.current_projects UNION ALL SELECT 'staging_projects', COUNT(*) FROM staging.current_projects UNION ALL SELECT 'active_observations', COUNT(*) FROM active.current_observations UNION ALL SELECT 'staging_observations', COUNT(*) FROM staging.current_observations\"; print(c.execute(q).fetchdf().to_string(index=False))"
```

Projets présents dans le staging mais absents de la base active :

```powershell
python -c "import duckdb; c=duckdb.connect(':memory:'); c.execute(\"ATTACH 'benchmark_bank/data/benchmark_bank.duckdb' AS active (READ_ONLY)\"); c.execute(\"ATTACH 'benchmark_bank/data/staging.duckdb' AS staging (READ_ONLY)\"); q='''SELECT s.project_id, s.project_name, s.country_iso3, s.technology FROM staging.current_projects s LEFT JOIN active.current_projects a ON a.project_id=s.project_id WHERE a.project_id IS NULL ORDER BY s.project_name'''; print(c.execute(q).fetchdf().to_string(index=False))"
```

## 18. Consulter une sauvegarde

Lister les sauvegardes :

```powershell
Get-ChildItem .\benchmark_bank\data\backups -Filter *.duckdb -Recurse |
Format-List FullName, Length, LastWriteTime
```

Afficher les tables d’une sauvegarde particulière :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\backups\benchmark_bank_20260826T203911Z.duckdb', read_only=True); print(c.execute('SHOW TABLES').fetchdf().to_string(index=False))"
```

Adapter le nom du fichier à la sauvegarde que vous souhaitez consulter.

## 19. Exporter un résultat vers CSV

Exporter les projets hydroélectriques :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT project_id, project_name, country_iso3, region, technology, project_type FROM current_projects WHERE lower(technology) LIKE '%hydro%' ORDER BY country_iso3, project_name\"; c.execute(q).fetchdf().to_csv(r'outputs/projets_hydroelectriques.csv', index=False, encoding='utf-8-sig'); print('Export créé : outputs/projets_hydroelectriques.csv')"
```

Exporter une métrique :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); q=\"SELECT * FROM current_observations WHERE metric='investment_per_mw'\"; c.execute(q).fetchdf().to_csv(r'outputs/investment_per_mw.csv', index=False, encoding='utf-8-sig'); print('Export créé : outputs/investment_per_mw.csv')"
```

La base reste en lecture seule, mais ces commandes créent un nouveau fichier CSV dans `outputs`.

## 20. Utiliser un petit script interactif Python

Pour éviter de répéter la connexion, lancer Python :

```powershell
python
```

Puis saisir :

```python
import duckdb

connexion = duckdb.connect(
    r"benchmark_bank\data\benchmark_bank.duckdb",
    read_only=True,
)

connexion.execute("SHOW TABLES").fetchdf()
connexion.execute("SELECT * FROM current_projects LIMIT 10").fetchdf()
connexion.execute("SELECT * FROM current_observations LIMIT 10").fetchdf()
connexion.close()
```

Pour quitter Python :

```python
exit()
```

## 21. Ouvrir DuckDB avec une interface graphique

La base peut être ouverte avec DBeaver ou une autre interface compatible DuckDB. Utiliser le fichier :

```text
C:\Users\Admin\Downloads\ARSEL\Code_fin_analyst\benchmark_bank\data\benchmark_bank.duckdb
```

Configurer la connexion en lecture seule lorsque l’interface le permet. Éviter d’ouvrir simultanément la base en écriture dans plusieurs applications.

## 22. Règles de sécurité

Pour une simple consultation :

1. Utiliser `read_only=True`.
2. Interroger de préférence les vues `current_*`.
3. Ajouter `LIMIT` lors de l’exploration de tables volumineuses.
4. Ne pas exécuter `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER` ou `CREATE` sur la base active.
5. Ne pas modifier manuellement les tables `bank_*`.
6. Ne pas utiliser le staging pour une analyse finale avant sa promotion.
7. Conserver les sauvegardes et snapshots inchangés.
8. Vérifier l’unité, la devise, l’année monétaire et le périmètre avant de calculer une statistique.

## 23. Diagnostic rapide en cas de problème

Vérifier que le fichier existe :

```powershell
Test-Path .\benchmark_bank\data\benchmark_bank.duckdb
```

Vérifier qu’il peut être ouvert en lecture seule :

```powershell
python -c "import duckdb; c=duckdb.connect(r'benchmark_bank\data\benchmark_bank.duckdb', read_only=True); print('Connexion réussie'); c.close()"
```

Si une erreur indique que la base est verrouillée, fermer les autres scripts ou interfaces qui pourraient l’avoir ouverte en écriture, puis réessayer.

Si une commande échoue parce qu’une colonne ou une table n’existe pas, exécuter d’abord :

```sql
SHOW TABLES;
DESCRIBE nom_de_la_table;
```

La structure réelle de la base reste toujours la référence.
