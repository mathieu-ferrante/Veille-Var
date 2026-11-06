# Documentation du service d'IA (C8)

Service paramétré : **Mistral AI – La Plateforme**, recommandé par le benchmark (`benchmark/README.md`),
via le point d'accès européen `https://api.eu.mistral.ai/v1`. Solution de repli : modèle local Ollama +
gemma3:12b. Le connecteur étant commun à tous les fournisseurs, changer de service consiste à modifier
`production.fournisseur` dans `config.yaml` (ou à passer `--fournisseur <id>`) et à fournir la clé
correspondante.

## 1. Gestion des accès

| Élément | Règle |
|---|---|
| Compte | Compte d'organisation au nom de la DSI (pas un compte personnel) |
| Clé API | Une clé dédiée au projet VeilleIA, nommée `veilleia-<environnement>` dans la console du fournisseur |
| Stockage de la clé | Variable d'environnement dans `.env` (exclu du dépôt par `.gitignore`), jamais dans le code |
| Droits | Clé limitée à l'inférence ; plafond de dépense configuré dans la console quand c'est possible |
| Rotation | Tous les 6 mois et immédiatement en cas de fuite supposée : créer la nouvelle clé, mettre à jour `.env`, lancer `veilleia verifier`, révoquer l'ancienne |
| Journalisation | Les clés sont masquées dans tous les journaux (`journal.masquer_secrets`), testé automatiquement |
| Authentification | En-tête `Authorization: Bearer <clé>` sur chaque requête HTTPS |

## 2. Installation

Prérequis : Python 3.11 ou plus, accès Internet sortant en HTTPS vers l'API du fournisseur et vers les
flux RSS (à autoriser sur le proxy de la DSI).

```bash
git clone https://github.com/mathieu-ferrante/Veille-Var.git
cd Veille-Var
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS : source .venv/bin/activate)
pip install -e ".[dev]"
copy .env.example .env          # puis renseigner la clé API du service retenu
veilleia verifier               # test d'accès au service
```

Planification hebdomadaire (Windows) : `powershell -ExecutionPolicy Bypass -File scripts\planifier_tache_windows.ps1`.

## 3. Paramétrage

Fichier `config.yaml`, section `production` :

| Paramètre | Valeur | Justification |
|---|---|---|
| `fournisseur` | `mistral` | Recommandation du benchmark (score 4,55/5) |
| `base_url` (section `fournisseurs.mistral`) | `https://api.eu.mistral.ai/v1` | Inférence garantie dans l'UE |
| `modele_analyse` | `petit` = `ministral-8b-latest` | F1 à F4 sont des tâches simples : un petit modèle suffit, plus sobre et moins cher |
| `modele_synthese` | `grand` = `mistral-large-4` | F5 demande plus de qualité rédactionnelle, une seule fois par semaine |
| `temperature` | 0,1 | Réponses stables et factuelles |
| `response_format` | `json_object` | Sortie structurée, validée ensuite par un schéma Pydantic |
| `max_tokens_analyse` / `_synthese` | 400 / 16 000 | mistral-large-4 raisonne avant de répondre : son raisonnement compte dans le plafond (2 500 → réponse vide, 8 000 → JSON coupé, mesuré) |
| `timeout_s` | 180 | La synthèse dure environ 2 minutes |
| `tentatives` | 3 | Nouvelles tentatives sur 429, 5xx et erreurs réseau, avec attente croissante (respect de `Retry-After`) ; jamais sur 401/403 |
| `pause_entre_appels_s` | 0,5 | Respect des limites de débit |
| `requetes_par_minute` (par fournisseur) | 10 pour Gemini | Respect du quota des offres gratuites ; l'attente est exclue de la latence mesurée |
| `prix` (par modèle) | tarifs officiels du 06/11/2026 | Calcul du coût de chaque appel pour le monitorage |

Modèles de l'offre gratuite Mistral : quota nul sur `mistral-small` et `mistral-medium` (lu dans les
en-têtes `x-ratelimit-*` des réponses), d'où le choix de `ministral-8b` et `mistral-large-4`. En
production, l'offre payante est requise : en offre gratuite, Mistral peut utiliser les données pour
entraîner ses modèles (refus possible dans la console).

Mesures de sobriété : dédoublonnage des articles (jamais analysés deux fois), contenu tronqué à
2 500 caractères, publications de plus de 8 jours ignorées, plafond de 30 publications par source.

Sécurité des prompts (OWASP Top 10 LLM – injection de prompt) : contenu des articles isolé entre
balises et neutralisé (quelle que soit la casse), consigne système explicite, validation stricte du JSON
en sortie.

Autres protections : seuls les liens http(s) des flux sont conservés (pas de lien « javascript: » dans
une synthèse diffusée) ; envoi de mail chiffré (STARTTLS sur 587, SMTPS sur 465) avec vérification du
certificat et du nom du serveur ; une publication dont l'analyse échoue 3 fois n'est plus renvoyée au
service (pas de refacturation sans fin) ; un point de synthèse sans source valide est retiré.

## 4. Tests

| Commande | Ce qui est vérifié |
|---|---|
| `veilleia verifier` | Clé présente, accès réel aux deux modèles, latence |
| `pytest` | 56 tests automatisés sans appel réel : format des requêtes, authentification, nouvelles tentatives, erreurs 401, validation JSON, masquage des secrets, calcul du coût, limite de débit, modèles à raisonnement, réponse coupée, collecte, dédoublonnage, accessibilité de la synthèse, alertes, benchmark (erreurs de service séparées du JSON non conforme), envoi de mail chiffré avec certificat vérifié, liens non web écartés, points non sourcés retirés de la synthèse |
| `veilleia analyser --limite 3` | Test de bout en bout sur 3 publications réelles |
| CI GitHub Actions | `ruff` (qualité et règles de sécurité) et `pytest` à chaque push |

## 5. Monitorage

Deux niveaux complémentaires :

1. **Console du fournisseur** : consommation, facturation, plafonds de dépense.
2. **Monitorage propre au projet** : chaque appel est enregistré dans la table `appels_ia` (horodatage,
   modèle, tâche, statut, code HTTP, latence, tokens, coût, validité du JSON, tentatives, erreur).
   `veilleia monitoring` calcule les indicateurs, les compare aux seuils et produit
   `sorties/monitoring/tableau_de_bord.html` et `indicateurs.json`. Code de sortie 2 en cas d'alerte.

| Indicateur | Seuil d'alerte (fenêtre de 7 jours) |
|---|---|
| Taux d'erreur | > 5 % |
| Dernière synthèse en échec | dès un échec (la synthèse de la semaine n'est pas produite) |
| Latence 95e centile | > 15 s |
| Réponses JSON non conformes | > 5 % |
| Coût estimé | > 7,50 € (≈ 30 €/mois) |
| Tokens consommés | > 2 000 000 |
| Sources RSS en erreur | > 2 |

Journal applicatif : `logs/veilleia.jsonl` (JSON Lines, sans donnée personnelle ni secret).

`veilleia hebdo` lance toujours le monitorage, même si une étape précédente a échoué (une synthèse
en échec doit justement être signalée). Les limites de débit restantes sont aussi renvoyées par Mistral
dans les en-têtes `x-ratelimit-*` de chaque réponse.

## 5 bis. Solution de repli : modèle local

1. Installer Ollama (https://ollama.com), puis `ollama pull gemma3:12b` (8 Go ; carte graphique de
   12 Go de mémoire recommandée).
2. Lancer `veilleia --fournisseur ollama verifier`, puis `veilleia --fournisseur ollama hebdo`.

Aucune clé n'est nécessaire et aucune donnée ne quitte le poste. Le modèle a été choisi par essai sur
le jeu de test (voir `benchmark/README.md`).

## 6. Dépendances et interconnexions

```
Flux RSS publics ──HTTPS──► collecte.py ──► SQLite (data/veilleia.db)
                                                │
                       analyse.py / synthese.py ▼
                     ia_client.py ──HTTPS──► API du service d'IA (chat completions)
                                                │
             syntheses/*.html, *.md ◄───────────┘──► diffusion.py ──SMTP──► listes de diffusion
             sorties/monitoring/    ◄── monitoring.py (lit la table appels_ia)
```

| Dépendance | Rôle |
|---|---|
| `httpx` | Client HTTP (API et flux RSS) |
| `feedparser` | Lecture des flux RSS/Atom |
| `pydantic` | Validation des réponses du modèle |
| `python-dotenv` | Lecture des secrets dans `.env` |
| `pyyaml` | Lecture de la configuration |
| SQLite (bibliothèque standard) | Stockage local |
| Serveur SMTP de la collectivité (facultatif) | Diffusion de la synthèse |

## 7. Données impliquées

| Donnée | Origine | Envoyée au service d'IA ? | Données personnelles ? | Conservation |
|---|---|---|---|---|
| Titre, extrait (≤ 2 500 caractères), source des publications | Flux RSS publics | Oui | Non (contenu public éditorial) | Base locale, purge possible à 12 mois |
| Résultats d'analyse et synthèses | Service d'IA | — | Non | Base locale et dossier `syntheses/` |
| Métriques d'appel | Connecteur | Non | Non | Base locale |
| Destinataires des mails | `.env` | **Non** | Adresses de listes de service | `.env` uniquement, jamais journalisées |
| Clé API | `.env` | En en-tête d'authentification uniquement | — | `.env` uniquement |

Aucune donnée d'usager ni d'agent n'est transmise au service d'IA. Avant une mise en service réelle :
inscription au registre des traitements et avis du DPO, vérification des conditions contractuelles
du fournisseur (localisation, réutilisation des données, contrat de sous-traitance).
