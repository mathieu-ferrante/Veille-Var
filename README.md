# VeilleIA – Veille IA automatisée pour la DSI du Département du Var

Outil de veille technique et réglementaire sur l'intelligence artificielle. Il collecte les
publications de sources fiables, les fait **classer, noter et résumer en français par un service
d'IA**, puis produit chaque semaine une **synthèse accessible (RGAA)** pour la DSI, le DPO, le service
juridique et le RSSI.

> Projet réalisé pour l'épreuve **E2** du titre professionnel *Développeur en intelligence artificielle*
> (RNCP37827, bloc 2 – compétences C6, C7, C8). **Scénario prospectif** : le besoin est formalisé à
> partir d'une situation plausible au Département ; il n'a pas fait l'objet d'une commande officielle.

## Fonctionnement

```
Flux RSS ─► Collecte + dédoublonnage ─► Service d'IA (F1 classer, F2 noter, F3 résumer, F4 extraire)
        ─► Synthèse hebdomadaire (F5) HTML accessible + Markdown ─► Diffusion
Monitorage : chaque appel est mesuré (latence, tokens, coût, erreurs) ─► tableau de bord + alertes
```

## Démarrage rapide

```bash
python -m venv .venv
.venv\Scripts\activate                 # Linux/macOS : source .venv/bin/activate
pip install -e ".[dev]"
copy .env.example .env                 # renseigner la clé du service retenu
veilleia verifier                      # teste l'accès au service d'IA
veilleia hebdo                         # collecte + analyse + synthèse + monitorage
```

## Commandes

| Commande | Rôle |
|---|---|
| `veilleia verifier` | Teste la configuration et l'accès réel au service d'IA |
| `veilleia sources` | Liste les sources actives |
| `veilleia collecter` | Récupère les nouvelles publications RSS |
| `veilleia analyser [--limite N]` | Analyse les publications pas encore traitées |
| `veilleia synthetiser [--envoyer]` | Produit la synthèse de la semaine dans `syntheses/` |
| `veilleia monitoring` | Indicateurs, alertes et tableau de bord (`sorties/monitoring/`) |
| `veilleia hebdo [--envoyer]` | Chaîne complète (utilisée par la tâche planifiée) |
| `veilleia jeu-test` | Tire 30 publications à annoter pour le benchmark |
| `veilleia benchmark [--services a,b]` | Compare les services d'IA sur le jeu annoté |

Option globale `--fournisseur <id>` pour utiliser ponctuellement un autre service.

## Organisation du dépôt

| Chemin | Contenu | Compétence |
|---|---|---|
| `veille/` | Organisation, sources et grille de fiabilité, journal de veille | C6 |
| `syntheses/` | Synthèses hebdomadaires produites | C6 |
| `benchmark/` | Méthode, grille documentaire, jeu de test, résultats | C7 |
| `veilleia/` | Code : collecte, connecteur IA, analyse, synthèse, monitorage | C8 |
| `docs/documentation_service.md` | Accès, installation, paramétrage, tests, monitorage, dépendances, données | C8 |
| `tests/` | Tests automatisés (sans appel réel au service) | C8 |
| `config.yaml`, `sources.yaml` | Paramétrage et sources | C8 |

## Service retenu

Le benchmark (`benchmark/README.md`) recommande **Mistral AI** (score pondéré 4,55/5), via le point
d'accès européen `api.eu.mistral.ai` : `ministral-8b-latest` pour l'analyse, `mistral-large-4` pour la
synthèse. Solution de repli déjà configurée et testée : modèle local **Ollama + gemma3:12b**
(`veilleia --fournisseur ollama hebdo`). Coût mesuré en production : environ 0,04 $ par semaine.

## Choix techniques

- **Un seul connecteur** pour tous les fournisseurs, via l'interface « chat completions » compatible
  OpenAI : les services sont comparés dans des conditions identiques, et en changer revient à modifier
  une ligne de configuration.
- **Sortie JSON validée** (Pydantic) : une réponse non conforme est rejetée et comptée par le monitorage.
- **Sobriété** : dédoublonnage, contenu tronqué, petit modèle pour le tri, grand modèle seulement pour
  la synthèse.
- **Sécurité** : secrets hors du dépôt et masqués dans les journaux, protection contre l'injection de
  prompt, analyse statique `ruff` (règles de sécurité Bandit) en intégration continue.
- **Accessibilité** : synthèse HTML structurée (langue, titres, liens explicites, tableaux avec en-têtes,
  contrastes, mode sombre).
- **Transparence (AI Act)** : chaque synthèse indique qu'elle est générée par IA et relue par un agent.

## Tests

```bash
pytest          # 56 tests
ruff check .    # qualité et sécurité
```
