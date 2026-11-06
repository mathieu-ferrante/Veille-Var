# Benchmark des services d'IA (C7)

Le benchmark compare les services d'IA capables de réaliser les fonctionnalités F1 à F5 du besoin
(classer, noter, résumer, extraire, synthétiser). Il combine deux volets :

1. **Une analyse documentaire** des 7 services étudiés (grille ci-dessous) : conformité, souveraineté,
   coût, éco-responsabilité, contraintes techniques et prérequis, documentation et monitorage.
2. **Des tests réels et chiffrés** sur un jeu de 30 publications annotées à la main, avec le même
   prompt et les mêmes paramètres pour chaque service.

### Services testés et services étudiés sur documentation

| Service | Volet | Raison |
|---|---|---|
| Mistral AI | Tests + documentation | Offre gratuite d'expérimentation, fournisseur européen |
| Google Gemini | Tests + documentation | Offre gratuite (AI Studio) |
| Modèle local (Ollama) | Tests + documentation | Gratuit, exécuté sur le poste |
| OpenAI, Anthropic Claude, Azure OpenAI | Documentation seule | API uniquement payantes : pas de dépense engagée sans commande publique pour une phase d'étude |
| Albert API (DINUM) | Documentation seule | Accès réservé aux administrations, sur demande |

Le connecteur gère déjà tous ces fournisseurs (`config.yaml`) : un service étudié sur documentation
peut être testé plus tard en ajoutant simplement sa clé dans `.env`, sans modifier le code.

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
veilleia benchmark --services mistral,gemini,ollama
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

## Résultats des tests (6 novembre 2026)

Mêmes 30 publications annotées, même prompt, température 0,1. Détail : `resultats/resultats_2026-11-06.md`
(prompt v2, résultats retenus) et `resultats/resultats_2026-11-06_prompt_v1.md` (premier passage).

| Service | Modèle | JSON conforme (F4) | Classement (F1) v1 → v2 | Écart pertinence (F2) v1 → v2 | Résumés FR (F3) | Latence moy. |
|---|---|---|---|---|---|---|
| Mistral AI | ministral-8b | 100 % | 73,3 % → **76,7 %** | 0,33 → **0,57** | 100 % | 2,8 s |
| Google Gemini | gemini-3.5-flash-lite | 100 % | 66,7 % → **80,0 %** | 0,53 → 0,60 | 100 % | **1,2 s** |
| Ollama (local) | gemma3:12b | 100 % | 73,3 % → **76,7 %** | 0,97 → 0,90 | 100 % | 5,7 s (poste libre) / 26 s (GPU partagé) |

**Amélioration du prompt (v1 → v2).** L'analyse des erreurs du premier passage a montré une cause
principale : les actualités commerciales sans intérêt étaient classées « hors sujet » au lieu de
« offre_outil » avec une pertinence basse (règle d'annotation). Le prompt précise désormais que la
catégorie décrit la nature de la publication, indépendamment de son intérêt. Le classement progresse pour
les trois services ; l'écart de notation de Mistral augmente un peu mais reste sous le critère (≤ 1 point).

**Limites.** L'objectif de 85 % de bon classement n'est atteint par aucun service. Les erreurs restantes
sont communes aux trois services sur les n° 17, 21, 22 et 24, dont deux avaient été marqués ambigus dès
l'annotation : l'écart vient en partie de l'ambiguïté des catégories elles-mêmes. Deux passages successifs
du même prompt sur Mistral ont donné 80 % puis 76,7 % (une publication d'écart) : une différence de
3 points entre services n'est donc pas significative sur 30 publications. Piste : faire annoter le jeu
par une deuxième personne pour mesurer l'accord entre humains, et l'agrandir au fil des semaines.

**Latence du modèle local.** Mesurée à 5,7 s sur un poste libre, puis à 26 s lorsque la carte graphique
était partagée avec d'autres logiciels (8 tokens générés par seconde) : en production, un serveur dédié
est nécessaire.

Choix du modèle local par essai préalable (même jeu de test) : llama3.2:3b donnait 5/5 à 27 publications
sur 30 (écart 2,55, inutilisable), mistral-nemo 60 % de bon classement, gemma3:12b retenu.

**Coût réel mesuré en production** (Mistral, semaine du 30/10 au 06/11/2026) : 164 analyses par
ministral-8b = 0,023 $ ; synthèse par mistral-large-4 = 0,020 $ par synthèse. Soit environ **0,04 $
par semaine, moins de 0,20 $ par mois**, pour un budget de 30 €/mois.

## Grille d'analyse documentaire

Sources officielles consultées le 06/11/2026 (liste en fin de document). Notes de 1 (mauvais) à 5
(excellent). « n.m. » = non mesuré : service non testé, le score pondéré n'est donc pas calculé.

| Critère (poids) | Mistral AI | Ollama + gemma3:12b | Google Gemini | Albert API | OpenAI | Anthropic | Azure OpenAI |
|---|---|---|---|---|---|---|---|
| Adéquation F1–F5 (30 %) | 5 | 4 | 5 | n.m. | n.m. | n.m. | n.m. |
| RGPD et souveraineté (25 %) | 4 | 5 | 2 | 5 | 2 | 1 | 3 |
| Coût et achat public (10 %) | 5 | 4 | 4 | 4 | 3 | 4 | 2 |
| Éco-responsabilité (15 %) | 5 | 3 | 2 | 3 | 2 | 2 | 2 |
| Contraintes et prérequis (10 %) | 4 | 2 | 3 | 2 | 4 | 4 | 2 |
| Documentation et monitorage (10 %) | 4 | 3 | 4 | 3 | 4 | 4 | 4 |
| **Score pondéré / 5** | **4,55** | **3,80** | **3,40** | n.m. | n.m. | n.m. | n.m. |

### Justification par service

**Mistral AI (testé) – 4,55**
- Adéquation : classement 76,7 % et notation la plus proche de l'humain (écart 0,57), à égalité
  pratique avec Gemini.
- Souveraineté : société française, données hébergées dans l'UE par défaut ; le point d'accès
  `api.eu.mistral.ai` garantit l'inférence dans l'UE (les métadonnées peuvent en sortir). Contrat de
  sous-traitance (DPA) publié. Pas de qualification SecNumCloud. Point de vigilance : en offre gratuite,
  Mistral peut utiliser les données pour entraîner ses modèles (refus possible) → l'offre payante est
  exigée en production.
- Coût : 0,15 $ / 0,15 $ par million de tokens (ministral-8b), 0,70 $ / 2,10 $ (mistral-large-4).
- Éco-responsabilité : seul fournisseur étudié à avoir publié une analyse de cycle de vie (Mistral
  Large 2, juillet 2025, avec Carbone 4 et l'ADEME) : 1,14 g CO₂e et 45 mL d'eau pour une réponse de
  400 tokens. Petit modèle (8 milliards de paramètres) pour 99 % des appels.
- Contraintes : compte et clé d'API ; mode JSON natif ; offre gratuite limitée à certains modèles
  (quota nul sur mistral-small et mistral-medium, constaté) ; mistral-large-4 raisonne avant de
  répondre (plafond de tokens et délai à adapter, constaté).
- Documentation et monitorage : documentation claire, console de consommation, limites de débit
  renvoyées dans les en-têtes de chaque réponse.

**Ollama + gemma3:12b (testé) – 3,80**
- Adéquation : bon classement (76,7 %), notation moins fine (écart 0,90), le plus lent (5,7 s sur poste libre).
- Souveraineté : aucune donnée ne quitte le poste. Ollama sous licence MIT ; gemma3 sous les
  « Gemma Terms of Use » de Google (usages interdits listés, pas de revendication sur les sorties).
- Coût : pas de facturation à l'appel, mais il faut un serveur avec carte graphique (12 Go de mémoire
  vidéo pour ce modèle) et son électricité, non chiffrés ici.
- Éco-responsabilité : consommation électrique du poste non mesurée ; pas de données publiées.
- Contraintes : matériel dédié, installation et mises à jour des modèles à la charge de la DSI.
- Monitorage : pas de console ; le monitorage de VeilleIA (latence, erreurs, JSON) le couvre.

**Google Gemini (testé) – 3,40**
- Adéquation : le plus rapide (1,2 s) et meilleur classement après amélioration du prompt (80 %) ; la qualité n'est pas en cause.
- Souveraineté : société américaine (Cloud Act). Localisation du traitement non publiée. Les conditions
  d'utilisation imposent l'offre **payante** pour un service rendu à des utilisateurs de l'Espace
  économique européen : l'offre gratuite testée n'est pas utilisable en production par le Département.
- Coût : 0,30 $ / 2,50 $ par million de tokens (flash-lite).
- Éco-responsabilité : pas de donnée trouvée par modèle.
- Contraintes : modèles retirés ou saturés rapidement (gemini-2.5 fermé aux nouveaux comptes,
  gemini-3.7/3.8 saturés lors des essais), limite de débit stricte en gratuit (refus HTTP 429 constatés).

**Albert API (DINUM, non testé)**
- Gratuite, hébergée en France chez des hébergeurs en partie qualifiés SecNumCloud, catalogue de modèles
  ouverts dont **Ministral 3 8B**, le même type de modèle que celui retenu chez Mistral.
- Non testée : l'accès est ouvert en priorité aux agents de l'État ; la page officielle ne mentionne pas
  les collectivités, qui doivent en faire la demande (délai à prévoir).

**OpenAI (non testé, payant)** – 0,75 $ / 4,50 $ (gpt-5.4-mini). Données de l'API non utilisées pour
l'entraînement ; résidence des données en Europe possible mais avec conditions (rétention réduite,
surcoût de 10 %). Société américaine soumise au Cloud Act.

**Anthropic (non testé, payant)** – 0,10 $ / 0,50 $ (Haiku). Pas d'option de traitement en Europe en
accès direct (seulement « us » ou « global »), donc écarté pour la souveraineté.

**Azure OpenAI (non testé, payant)** – traitement possible dans l'UE (« Data Zone EU »), mais Microsoft
reconnaît être soumis au Cloud Act ; pas de qualification SecNumCloud trouvée ; prix non affichés
publiquement (devis).

### Services non étudiés

| Service | Raison de l'exclusion |
|---|---|
| Outils de veille clés en main avec IA (ex. Feedly AI, Perplexity) | SaaS fermés : pas de paramétrage du modèle, intégration au SI impossible ou payante, données hors de contrôle |
| Plateformes cloud généralistes (AWS Bedrock, Google Vertex AI) | Mise en place disproportionnée (comptes cloud, IAM, facturation) pour le besoin |
| Chatbots grand public utilisés directement par les agents | Pas d'intégration au SI, conditions d'utilisation incompatibles avec un usage public professionnel |
| Entraînement ou affinage d'un modèle maison | Hors périmètre et hors budget : des services existants couvrent le besoin |

### Conclusion

**Services qui répondent au besoin**

| Service | Avantages | Inconvénients |
|---|---|---|
| Mistral AI (offre payante) | Qualité au niveau du meilleur service testé, données dans l'UE, coût dérisoire, empreinte publiée | Pas SecNumCloud ; offre gratuite inadaptée (entraînement) |
| Ollama + gemma3:12b | Souveraineté totale, aucun coût à l'appel | Matériel dédié, plus lent, notation moins fine, exploitation à la charge de la DSI |
| Albert API (sous réserve d'accès) | Souverain, gratuit, même modèle Ministral 8B | Accès non garanti aux collectivités, non testé |

**Services qui ne répondent pas au besoin**

| Service | Raison |
|---|---|
| Google Gemini | Offre gratuite interdite pour des utilisateurs européens ; société soumise au Cloud Act (la qualité mesurée est pourtant bonne) |
| OpenAI, Azure OpenAI | Payants, soumis au Cloud Act ; aucun gain attendu sur un besoin aussi simple |
| Anthropic | Pas de traitement en Europe en accès direct |

**Recommandation**

1. **Service principal : Mistral AI**, offre payante (paiement à l'usage), point d'accès européen
   `api.eu.mistral.ai`, refus de l'utilisation des données pour l'entraînement, ministral-8b pour
   l'analyse et mistral-large-4 pour la synthèse. Coût estimé : moins de 1 € par mois.
2. **Solution de repli : Ollama + gemma3:12b**, déjà configurée et testée : il suffit de lancer
   `veilleia --fournisseur ollama hebdo` en cas d'indisponibilité de Mistral ou de publication sensible.
3. **Piste à instruire : Albert API** — déposer une demande d'accès auprès de la DINUM ; si elle est
   acceptée, la bascule ne demande qu'une clé dans `.env` (le connecteur est déjà prêt).

### Sources de la grille (consultées le 06/11/2026)

- Mistral : https://docs.mistral.ai/inference/pricing · https://docs.mistral.ai/inference/regional-inference ·
  https://help.mistral.ai/en/articles/347617-do-you-use-my-user-data-to-train-your-artificial-intelligence-models ·
  https://legal.mistral.ai/terms/data-processing-addendum/ ·
  https://mistral.ai/news/our-contribution-to-a-global-environmental-standard-for-ai
- Google : https://aistudio.google.com/docs/pricing · https://aistudio.google.com/docs/terms
- Albert : https://ia.numerique.gouv.fr/outils-ia/albert-api/tarifs-et-limites
- OpenAI : https://developers.openai.com/api/docs/pricing · https://developers.openai.com/api/docs/guides/your-data
- Anthropic : https://claude.com/pricing · https://platform.claude.com/docs/en/build-with-claude/data-residency
- Azure : https://learn.microsoft.com/en-us/Azure/ai-foundry/openai/how-to/deployment-types ·
  https://www.microsoft.com/en-us/corporate-responsibility/reports/government-requests/customer-data
- Ollama : https://github.com/ollama/ollama/blob/main/LICENSE · https://ai.google.dev/gemma/terms
- Comparatif indépendant : Artificial Analysis (https://artificialanalysis.ai), indice d'intelligence
  de gemini-3.5-flash-lite = 12 (non publié pour ministral 8B et gemma 3 12B).
