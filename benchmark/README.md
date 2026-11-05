# Benchmark des services d'IA (C7)

Le benchmark compare les services d'IA capables de réaliser les fonctionnalités F1 à F5 du besoin
(classer, noter, résumer, extraire, synthétiser). Il combine deux volets :

1. **Une analyse documentaire** des 7 services étudiés (grille ci-dessous) : conformité, souveraineté,
   coût, éco-responsabilité, contraintes techniques et prérequis, documentation et monitorage.
2. **Des tests réels et chiffrés** sur un jeu de 30 publications annotées à la main, avec le même
   prompt et les mêmes paramètres pour chaque service.

## Mode opératoire

```bash
# 1. Collecter des publications réelles
veilleia collecter

# 2. Tirer 30 publications équilibrées par source -> benchmark/jeu_test.json
veilleia jeu-test

# 3. ANNOTER À LA MAIN chaque publication dans jeu_test.json :
#    "categorie": technique | reglementaire | offre_outil | hors_sujet
#    "pertinence": 1 à 5 (pour la DSI d'un Département)

# 4. Lancer le benchmark sur les services dont la clé est présente dans .env
veilleia benchmark                      # tous
veilleia benchmark --services mistral,openai,albert
```

Résultats écrits dans `benchmark/resultats/` :

- `resultats_AAAA-MM-JJ.md` / `.csv` / `.json` : tableau comparatif ;
- `brut/<service>.jsonl` : chaque réponse, pour la **relecture humaine des résumés** (fidélité, F3) ;
- `brut/benchmark.db` : journal technique de chaque appel (latence, tokens).

## Indicateurs mesurés

| Indicateur | Fonctionnalité | Calcul |
|---|---|---|
| JSON conforme | F4 | % de réponses validées par le schéma `AnalyseArticle` |
| Exactitude du classement | F1 | % de catégories identiques à l'annotation humaine |
| Écart de pertinence | F2 | écart absolu moyen entre la note du modèle et la note humaine |
| Résumés en français | F3 | % de résumés détectés en français (la fidélité se juge à la relecture) |
| Latence moyenne / 95e centile | contrainte technique | secondes, mesurées par le connecteur |
| Tokens et coût | budget, sobriété | tokens consommés ; coût si les prix sont renseignés dans `config.yaml` |

F5 (synthèse) est évaluée à la relecture : on génère une synthèse par service retenu et on la juge
sur une grille simple (fidélité, structure, clarté, sources citées).

## Grille d'analyse documentaire

> À compléter à partir de la documentation officielle de chaque service, en citant la source et la
> date de consultation. Ne rien inscrire qui ne soit vérifié.

### Services étudiés

| Critère (poids) | Albert API (DINUM) | Mistral AI | OpenAI | Google Gemini | Anthropic Claude | Azure OpenAI | Modèle local (Ollama) |
|---|---|---|---|---|---|---|---|
| Adéquation F1–F5 (30 %) – *tests* | | | | | | *(non testé : même modèles qu'OpenAI)* | |
| RGPD et souveraineté (25 %) : localisation, lois extraterritoriales, réutilisation des données, contrat de sous-traitance | | | | | | | |
| Coût et achat public (10 %) : prix / million de tokens, offre gratuite, achat via marché ou centrale | | | | | | | |
| Éco-responsabilité (15 %) : tailles de modèles, données publiées sur l'empreinte, datacenters | | | | | | | |
| Contraintes et prérequis (10 %) : compte, SDK, JSON, limites de débit, matériel | | | | | | | |
| Documentation et monitorage (10 %) : qualité de la doc, console d'usage, journaux | | | | | | | |
| **Score pondéré / 5** | | | | | | | |

### Services non étudiés

| Service | Raison de l'exclusion |
|---|---|
| Outils de veille clés en main avec IA (ex. Feedly AI, Perplexity) | SaaS fermés : pas de paramétrage du modèle, intégration au SI impossible ou payante, données hors de contrôle |
| Plateformes cloud généralistes (AWS Bedrock, Google Vertex AI) | Mise en place disproportionnée (comptes cloud, IAM, facturation) pour le besoin |
| Chatbots grand public utilisés directement par les agents | Pas d'intégration au SI, conditions d'utilisation incompatibles avec un usage public professionnel |
| Entraînement ou affinage d'un modèle maison | Hors périmètre et hors budget : des services existants couvrent le besoin |

### Conclusion (à rédiger après les tests)

- **Services qui répondent au besoin** : … (avantages / inconvénients)
- **Services qui ne répondent pas au besoin** : … (raison)
- **Recommandation** : … (service principal + solution de repli)
