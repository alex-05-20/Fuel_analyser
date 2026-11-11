# Fuel Analyser

Projet Python, Pandas et Streamlit pour explorer les prix des carburants à partir de fichiers, sans SQL.

## Démarrage sur Windows

Depuis PowerShell, à la racine du projet, exécuter ces commandes.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Organisation

- `app.py` et `pages/` hébergent l’interface Streamlit.
- `src/ingestion/` charge les fichiers sources.
- `src/processing/` nettoie et transforme les données avec Pandas.
- `src/analytics/` calcule les indicateurs pour le tableau de bord.
- `src/storage/` regroupe la lecture et l’écriture des fichiers de travail.
- `data/raw/`, `data/processed/` et `data/historical/` accueillent les sources, les données traitées et leurs archives.
- `scripts/` accueille les commandes de préparation. `tests/` accueille les tests.
- `.streamlit/` contient la configuration de l’application.

## Pipeline de données

Depuis la racine du projet, télécharger le flux officiel et mettre à jour les fichiers.

```powershell
python -B -m scripts.refresh_prices
```

Pour traiter un fichier local, utiliser la même publication et les mêmes règles d'historisation.

```powershell
python -B -m scripts.prepare_prices chemin/vers/source.csv
```

Chaque collecte validée produit une archive datée dans data/raw/archives.
Le fichier data/historical/prices_history.csv conserve les changements observés.
Le fichier data/processed/prices_current.csv représente le dernier instantané reçu.

La comparaison porte sur le dernier état connu de chaque station et carburant,
avec ses prix, dates, disponibilité et informations géographiques.
Une observation identique est ignorée. Le retour à une ancienne valeur est enregistré.
Les stations absentes du dernier instantané restent dans l'historique et quittent le fichier courant.

observed_at indique la date de collecte en UTC. source_archive désigne le fichier reçu.
Les données issues de la version précédente sont conservées comme état initial avec ces
deux champs vides, car leur date de collecte et leur archive ne sont pas connues.

Chaque fichier est remplacé après écriture complète. Un verrou empêche deux publications
locales simultanées. Après une interruption entre les écritures de l'historique et du fichier
courant, relancer la collecte rétablit le fichier courant sans répéter les observations identiques.
La publication cloud et sa planification restent à configurer.

## Synchronisation Hugging Face

La commande suivante recharge l'historique depuis Hugging Face, collecte le flux officiel,
puis publie la nouvelle archive, l'historique et les prix actuels dans un même commit.

```powershell
python -B -m scripts.sync_prices
```

Configurer HF_TOKEN et HF_REPO_ID dans .env ou dans les variables d'environnement.
Le dépôt distant est la référence pour l'historique lors de cette commande.
Les fichiers locaux sont actualisés après la publication. Les collectes réalisées
uniquement avec refresh_prices ne sont pas fusionnées automatiquement dans cet historique cloud.
En cas de publication concurrente sur le dépôt, le commit échoue pour préserver
la version distante. Relancer sync_prices reprend la dernière version publiée.
La planification quotidienne reste à configurer.
