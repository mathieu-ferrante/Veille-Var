# Documentation du service d'IA (C8)

Service paramétré : **service retenu par le benchmark** (hypothèse de départ : Mistral AI – La Plateforme,
à confirmer). Le connecteur étant commun à tous les fournisseurs, changer de service consiste à modifier
`production.fournisseur` dans `config.yaml` et à fournir la clé correspondante.

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
| `fournisseur` | `mistral` (à confirmer) | Recommandation du benchmark |
| `modele_analyse` | `petit` | F1 à F4 sont des tâches simples : un petit modèle suffit, plus sobre et moins cher |
| `modele_synthese` | `grand` | F5 demande plus de qualité rédactionnelle, une seule fois par semaine |
| `temperature` | 0,1 | Réponses stables et factuelles |
| `response_format` | `json_object` | Sortie structurée, validée ensuite par un schéma Pydantic |
| `max_tokens_analyse` / `_synthese` | 400 / 2500 | Borne la consommation |
| `timeout_s` | 60 | Évite les blocages |
| `tentatives` | 3 | Nouvelles tentatives sur 429, 5xx et erreurs réseau, avec attente croissante (respect de `Retry-After`) |
| `pause_entre_appels_s` | 0,5 | Respect des limites de débit |

Mesures de sobriété : dédoublonnage des articles (jamais analysés deux fois), contenu tronqué à
2 500 caractères, publications de plus de 8 jours ignorées, plafond de 30 publications par source.

Sécurité des prompts (OWASP Top 10 LLM – injection de prompt) : contenu des articles isolé entre
balises et neutralisé, consigne système explicite, validation stricte du JSON en sortie.

## 4. Tests

| Commande | Ce qui est vérifié |
|---|---|
| `veilleia verifier` | Clé présente, accès réel aux deux modèles, latence |
| `pytest` | 34 tests automatisés sans appel réel : format des requêtes, authentification, nouvelles tentatives, erreurs 401, validation JSON, masquage des secrets, calcul du coût, collecte, dédoublonnage, accessibilité de la synthèse, alertes |
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
| Latence 95e centile | > 15 s |
| Réponses JSON non conformes | > 5 % |
| Coût estimé | > 7,50 € (≈ 30 €/mois) |
| Tokens consommés | > 2 000 000 |
| Sources RSS en erreur | > 2 |

Journal applicatif : `logs/veilleia.jsonl` (JSON Lines, sans donnée personnelle ni secret).

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
