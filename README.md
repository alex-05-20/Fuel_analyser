# Fuel Analyser — version locale

Ce paquet contient les archives historiques officielles de 2007 à 2026, les six carburants présents dans la source et les fichiers préparés. L’année 2026 est partielle. Les données incluses permettent de travailler sans Internet, sans compte et sans clé secrète.

## État de cette livraison

Il s’agit du socle de données et de préparation. Le dashboard précédent a été retiré à la demande de l’étudiant ; la nouvelle interface sera construite ensemble. Aucun app.py n’est fourni à ce stade.

## Installation

Python 3.12 ou plus récent recommandé. Depuis le dossier extrait :

```text
python -m venv .venv
```

Sous Windows :

```text
.venv\Scripts\python.exe -m pip install -r requirements-notebook.txt
.venv\Scripts\python.exe -m jupyterlab exploration_annuelle.ipynb
```

Sous macOS/Linux : utiliser `.venv/bin/python` à la place. L’installation des bibliothèques nécessite Internet si elles ne sont pas déjà disponibles. Le paquet ne contient pas encore d’installateur de dépendances hors ligne ; une fois les bibliothèques installées, le notebook utilise uniquement les fichiers locaux.

## Données incluses

- data/raw/annual : ZIP officiels et manifeste des sources et empreintes.
- data/processed/annual/AAAA : prix, stations, interruptions en Parquet et rapport qualité JSON.
- data/raw/archives : sources des collectes locales, lorsqu’elles sont disponibles.
- data/processed/prices_current.csv : instantané des prix.
- data/historical/prices_history.csv : changements observés lors des collectes.

Les historiques annuels et l’historique des collectes se recouvrent : ne pas les concaténer sans traitement. La somme des lignes annuelles n’est pas un décompte d’observations uniques entre années. Les horodatages des archives sont conservés sans fuseau ajouté. Les prix atypiques et contradictoires sont signalés ; consulter quality.json. Le notebook charge une année à la fois pour limiter la mémoire.

## Mise à jour facultative avec Internet

```text
python -B -m scripts.update_local
```

Utiliser le Python de l’environnement activé. Cette commande contacte uniquement les sources publiques officielles, sans compte. Elle prépare les téléchargements avant publication, rafraîchit l’année courante et la précédente, récupère les années manquantes et met à jour l’instantané ainsi que les changements locaux. Les anciennes années complètes restent conservées. En cas d’échec réseau, la publication n’a pas commencé. Une erreur gérée pendant la publication déclenche une restauration ; une interruption brutale du système n’offre pas de transaction globale garantie. Fermer le notebook avant une mise à jour. Prévoir de l’espace disque pour les fichiers temporaires et les sauvegardes.

Une future interface proposera cette commande sous forme de bouton. Aucune mise à jour ne se lance automatiquement à l’ouverture du notebook.

## Sources et reproductibilité

Source : https://www.data.gouv.fr/datasets/prix-des-carburants-en-france-flux-instantane-v2-amelioree
Archives : https://donnees.roulez-eco.fr/opendata/annee
Données du ministère de l’Économie, licence ouverte indiquée sur la source. Les URL, dates de vérification et empreintes sont conservées dans data/raw/annual/manifest.json.

Repréparer les fichiers inclus : `python -B -m scripts.prepare_annual`.
Le manifeste LIVRAISON.json décrit les fichiers inclus et leurs empreintes SHA-256. Le ZIP n’inclut ni .env, ni environnement virtuel, ni Git, ni outils Hugging Face.


## Organisation du dépôt

- `src/ingestion/` : lecture des données sources.
- `src/processing/` : nettoyage et normalisation.
- `src/storage/` : fichiers locaux, historique et verrouillage.
- `src/pipeline.py` : publication d’une collecte locale.
- `src/analytics/`, `pages/`, `tests/` : emplacements réservés pour la suite.
- `scripts/` : collecte, préparation, mise à jour et création du ZIP.
- `exploration_annuelle.ipynb` : exploration locale des archives.
- `dist/` : livraison générée, exclue de Git.

## Commandes de préparation

Avec l’environnement virtuel activé, depuis la racine du projet :

```text
python -B -m scripts.refresh_prices
python -B -m scripts.download_annual
python -B -m scripts.prepare_annual
```

`refresh_prices` ne met à jour que le flux courant et son historique local. `download_annual` récupère les ZIP officiels ; `prepare_annual` produit les Parquet. Pour une actualisation regroupée, utiliser `update_local` comme décrit plus haut. `package_local` reconstruit `dist/Fuel_analyser_local.zip` avec une liste explicite de fichiers autorisés.

Le projet ne nécessite ni GitHub ni Hugging Face pour fonctionner. Les dépôts distants existants ne sont pas modifiés par ces commandes.


## Livraison finale

Aucun ZIP n’est conservé pendant le développement. La commande `python -B -m scripts.package_local` sera utilisée uniquement lorsque le projet sera terminé.
