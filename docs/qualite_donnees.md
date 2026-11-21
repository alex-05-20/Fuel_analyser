# Politique de qualite des donnees

Version 2026-11-17.1. Les sources et les tables historiques completes sont conservees. Les decisions suivantes s'appliquent aux vues analytiques du notebook et du dashboard, sans effacer de declarations des fichiers historiques.

| Controle | Decision |
| --- | --- |
| Identifiant | Texte conserve avec ses zeros initiaux ; identifiant absent ou non numerique exclu des analyses. |
| Carburant | Noms harmonises ; nom inconnu ou contradiction entre code connu et nom exclus des prix exploites. |
| Prix | Valeur absente, non numerique, non finie ou non positive inexploitable. Aucune valeur devinee. |
| Prix atypique | En dehors de [0,20 ; 5] EUR/L : quarantaine analytique. Ce seuil de prudence est une hypothese, pas une norme officielle ni une preuve d'erreur. Les valeurs restent consultables pour une analyse de sensibilite. |
| Doublon | Meme station, carburant, instant et prix numerique : une seule occurrence analytique. 1.50 et 1.500 sont equivalents. |
| Contradiction | Plusieurs valeurs numeriques au meme instant pour la meme station et le meme carburant : toutes inexploitables. Aucun choix arbitraire. |
| Date | Date absente ou invalide, ou hors de l'annee de l'archive : exclusion analytique. Aucun fuseau invente. |
| Declaration quotidienne | Derniere declaration de chaque station/carburant/jour. Si elle est invalide, ne pas reprendre une declaration plus ancienne. Aucun report aux jours sans declaration. |
| Code postal | Exactement cinq chiffres ; sinon absent dans la vue geographique. Aucun zero ajoute par supposition. |
| Coordonnees | Paire manquante, hors limites ou (0,0) : pas de point sur la carte ; le prix reste utilisable nationalement. Une longitude nulle seule n'est pas une erreur. |
| Metadonnees contradictoires | Identifiant conserve, metadonnees neutralisees dans la vue analytique ; pas de choix arbitraire de localisation. |
| Interruptions | Outil parse_intervals : distingue fin absente, invalide, anterieure au debut et fuseaux incompatibles. Une fin absente n'est pas inventee. Pas de deduc­tion de rupture a partir d'une absence de prix. |

Les conversions d'unites existantes sont maintenues ; prix_raw, date_raw, coordonnees brutes et JSON permettent de verifier la source. Les anciens indicateurs stockes de doublons/conflits decrivent la source ; les indicateurs dq_ recalcules constituent la decision analytique numerique.

Les controles couvrent validite, coherence et unicite. La completude et la couverture temporelle doivent accompagner les moyennes : une donnee manquante ne vaut jamais zero. Les stations declarantes changent selon les jours ; les moyennes ne sont ni ponderees par les volumes vendus ni une preuve de causalite politique ou economique. Les seuils doivent etre signales dans toute conclusion.

Le flux instantane conserve ses 47 colonnes et son nettoyage existant. Cette politique centralise avant tout l'exploitation de l'historique ; elle ne certifie pas l'exactitude de toutes les declarations sources.
