# Fuel Analyser

Projet étudiant : analyse de l’évolution des prix des carburants en France depuis 2007. Python, Pandas et Streamlit ; fonctionnement local sans compte.

## Installation et lancement

Depuis la racine :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-notebook.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
# ou pour analyser les données :
.\.venv\Scripts\python.exe -m jupyterlab notebooks/exploration_annuelle.ipynb
```

Sur macOS/Linux, remplacer `.venv\Scripts\python.exe` par `.venv/bin/python`. L’installation initiale des bibliothèques nécessite Internet. Une fois installées, le dashboard et le notebook lisent les données locales. Le fond de carte est local.

## Architecture

```text
app.py                  Interface Streamlit
src/ingestion/          Lecture des sources
src/processing/         Nettoyage et extraction complets
src/analytics/          Vues et calculs en mémoire
src/storage/            Verrouillage de publication
src/pipeline.py         Publication de l’instantané nettoyé
scripts/                Préparation, mise à jour, livraison future
data/raw/annual/        ZIP officiels originaux
data/raw/snapshots/     CSV sources des collectes
data/raw/legacy_collections/ Historique de collecte antérieur conservé pour traçabilité
data/cleaned/current.parquet       Instantané complet, 47 colonnes
data/cleaned/historical/AAAA.parquet Une table historique complète par année
data/quality/           Rapports de nettoyage, hors des tables
notebooks/              Exploration et analyses personnelles
assets/maps/            Fond géographique et attribution
tests/                  Vérifications des règles de transformation
```

## Instantané : 47 colonnes

Toutes les colonnes sont conservées dans leur ordre d’origine, sans suppression de lignes. Identifiants et codes sont du texte ; prix et coordonnées sont numériques ; coordonnées du flux v2 divisées par 100 000 ; dates avec fuseau converties en UTC. Les dates sans fuseau ne sont pas interprétées arbitrairement : elles sont signalées et laissées manquantes dans la colonne typée. Les valeurs originales restent dans le CSV et les anomalies sont consignées avec ligne, colonne et valeur brute.

Les champs horaires, services, prix et rupture restent du JSON texte. Un JSON invalide reste conservé et signalé. L’automate est vrai/faux/inconnu. Les valeurs impossibles à convertir deviennent manquantes, avec traçabilité. Les prix atypiques restent conservés. Aucune concaténation de colonnes.

## Historique : une table logique, un fichier par année

Les fichiers locaux couvrent 2007–2026 ; 2026 est partielle selon la date de l’archive incluse.

Une ligne par élément `prix` du XML, même vide ou invalide. Une station sans élément prix reçoit une ligne avec `no_price=True`. Aucun doublon ni prix invalide n’est retiré du fichier nettoyé.

- Identité/localisation : `station_id`, `postal_code`, `city`, `address`, `road_type`, `latitude`, `longitude`.
- Déclaration : `fuel`, `fuel_code`, `price_eur_l`, `price_reported_at`.
- Contenu complet : `hours_json`, `opening_json`, `services_json`, `outages_json`, `closures_json`.
- Traçabilité : `latitude_raw`, `longitude_raw`, `price_raw`, `date_raw`, `archive_year`, `source_archive`, `source_station_index`, `source_price_index`.
- Conservation du XML : `station_source_json` contient tous les attributs et les enfants hors prix ; `price_source_json` contient l’élément prix complet, avec attributs, texte et enfants. Ces JSON sont des représentations structurées, pas des copies octet pour octet : les ZIP restent la référence originale.
- Qualité : `invalid_price`, `invalid_date`, `unknown_fuel`, `suspect_price`, `outside_archive_year`, `duplicate_price`, `conflicting_price`, `no_price`.

Prix 2007–2021 divisés par 1 000 ; prix 2022 et suivants conservés en €/L selon le format observé. Dates XML sans fuseau ajouté. Les services et horaires sont ceux de l’archive annuelle et ne prouvent pas leur état à chaque date de prix. Aucun département, région ou statut de disponibilité absent du XML n’est inventé. Ruptures et fermetures conservent leurs dates sources dans le JSON ; elles ne sont pas automatiquement considérées actives à chaque déclaration.

Les indicateurs de qualité peuvent se recouper : il ne faut pas additionner leurs compteurs. `duplicate_price` signale toutes les lignes participant à une répétition exacte dans la station source ; aucune n’est supprimée.

Les indicateurs analytiques sont calculés séparément : exclusions de valeurs invalides, atypiques ou contradictoires et déduplication en mémoire seulement. Une station compte une fois par jour et par carburant, sur sa dernière déclaration du jour ; aucun report aux jours suivants. Moyennes mensuelles des moyennes quotidiennes, avec couverture. Les dates d’archives annuelles peuvent se recouvrir ; ne pas concaténer naïvement plusieurs années pour compter des observations uniques.

## Préparer et actualiser

```powershell
python -B -m scripts.prepare_prices data/raw/snapshots/prices_source.csv
python -B -m scripts.prepare_annual
python -B -m scripts.prepare_annual --year 2022
python -B -m scripts.update_local
```

`prepare_prices` prend n’importe quel chemin vers un CSV v2 brut. `prepare_annual` relit les ZIP locaux et remplace les fichiers annuels préparés. La mise à jour facultative contacte les sources officielles sans compte : année courante, précédente et années manquantes, puis instantané complet. Les CSV collectés sont archivés : l’ancien historique réduit station-carburant n’est plus produit.

Les téléchargements et préparations de `update_local` sont isolés avant publication. Un échec réseau ne remplace pas les données en place. Une erreur gérée de publication déclenche une restauration ; une coupure brutale du système ne garantit pas une transaction globale. Fermer le notebook avant une mise à jour. Prévoir de l’espace disque pour les fichiers temporaires.

## Sources

- Flux v2 : https://www.data.gouv.fr/datasets/prix-des-carburants-en-france-flux-instantane-v2-amelioree
- Archives : https://donnees.roulez-eco.fr/opendata/annee
- Fond géographique : attribution et licence dans assets/maps/SOURCE.md ; utilisé seulement pour la carte.

Les ZIP, CSV et manifestes bruts restent intacts. Aucun secret, compte GitHub ou Hugging Face n’est requis.

## Livraison finale

Aucun ZIP n’est créé pendant le développement. `python -B -m scripts.package_local` sera utilisé uniquement à la fin du projet.

## Vérification des transformations

`python -B -m unittest discover -s tests -v` vérifie la conservation des colonnes, des identifiants, des JSON, des lignes invalides, des doublons et des stations sans prix.

## Audit avant validation

`notebooks/audit_qualite.ipynb` fournit les taux de signalement par année et par carburant, des exemples, les contrôles de stations et un examen des interruptions. Il ne modifie aucune donnée. Les exemples et le contrôle interannuel par station ne remplacent pas un contrôle exhaustif. Les décisions analytiques sont documentées dans [la politique de qualité](docs/qualite_donnees.md) et centralisées pour le notebook et le dashboard. Les tables historiques complètes sont conservées.

## Ouvrir les notebooks sous Windows

Double-cliquer sur `ouvrir_analyses.cmd` pour ouvrir les analyses avec l’environnement du projet. Le noyau des trois notebooks est `Python - Fuel analyser`. Si un notebook était déjà ouvert avant une modification des dépendances, redémarrer son noyau avant de relancer les cellules.

Diagnostic confirmé le 19 novembre 2026 : PyArrow 26.0.1 du Python général échouait au chargement de `_acero`, bloqué par le contrôle d’application Windows. PyArrow 24.0.0 fonctionne dans cet environnement et dans `.venv` ; cette version est déjà fixée dans les dépendances Windows. Aucune règle de sécurité Windows n’a été modifiée.

Les courbes et cartes enregistrées se consultent directement. Leur recalcul sur toutes les archives prend plusieurs minutes.

## Accueil Plotly

L’accueil sombre propose trois onglets : Évolution (six carburants sur toutes les années), Carte (prix moyens régionaux sur toute la période) et Grille (années × mois). La carte et la grille disposent de sélecteurs de carburant indépendants. Des panneaux sont réservés aux prochains graphiques.

Les synthèses locales sont préparées avec `python -B -m scripts.prepare_dashboard` et stockées dans `data/analytics/`. Elles sont recalculées si les archives, rapports, contours ou règles de qualité changent. Aucun téléchargement n’est nécessaire. La carte Plotly embarque les contours locaux et ne charge pas de fond externe. Les stations non rattachables ne participent pas aux moyennes régionales.

Démarrer depuis la racine du projet avec `.\.venv\Scripts\python.exe -m streamlit run app.py`.

## Prédiction à douze mois

La page Prédiction estime novembre 2026 à octobre 2027 pour les six carburants, un par un ou ensemble. L’entraînement s’arrête volontairement à octobre 2026, même après une mise à jour des sources. Les mois partiels sont exclus. Un gradient boosting par carburant prédit récursivement les prix à partir de retards, moyennes passées et variables saisonnières.

Deux fenêtres de validation de douze mois couvrent novembre 2023 à octobre 2025. Le test final, novembre 2025 à octobre 2026, reste séparé. La référence répète le prix du même mois de l’année précédente. Les deux MAE sont affichées, y compris lorsque la référence est meilleure. Les modèles finaux sont ensuite réentraînés jusqu’à octobre 2026.

Les bandes utilisent le 90e percentile des erreurs absolues des fenêtres de validation, tous horizons confondus : bandes indicatives, sans garantie de couverture à 90 %. Leur couverture réelle est mesurée sur le test final. Pas de variables économiques ou politiques externes ni de causalité revendiquée. Une rupture de la série mensuelle limite l’entraînement à la dernière séquence consécutive ; aucune valeur manquante n’est inventée.

## Navigation Streamlit

Quatre pages : **Analyse des prix** (onglets Évolution, Carte, Grille), **Prédiction**, **Budget**, **Données et méthode**. Les anciennes pages Évolution historique et Analyse géographique ont été supprimées. Les filtres du budget sont propres à cette page. Les sources, rapports qualité et la commande de mise à jour sont regroupés dans Données et méthode.
