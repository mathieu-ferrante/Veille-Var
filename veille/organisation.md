# Organisation de la veille

## Thématiques

- **Réglementaire** : obligations de l'AI Act pour une administration « déployeuse » de systèmes d'IA,
  RGPD appliqué à l'IA, recommandations de la CNIL, sécurité des SI (ANSSI).
- **Technique** : services d'IA générative (API, offres souveraines pour le secteur public, modèles
  open-weight) et outils de monitorage — c'est-à-dire le type de service paramétré dans le projet.

Ces deux thèmes portent directement sur l'outil et la réglementation mobilisés dans le cas pratique.

## Outils d'agrégation

| Outil | Rôle | Coût |
|---|---|---|
| Flux RSS collectés par VeilleIA (`veilleia collecter`) | Agrégation automatique de toutes les sources | Gratuit |
| Service d'IA (`veilleia analyser`) | Tri, notation, résumé en français | Selon fournisseur (≤ 30 €/mois) |
| Agrégateur RSS en ligne (Inoreader ou Feedly, offre gratuite) | Lecture manuelle, sources sans traitement IA | Gratuit |
| Newsletters (ex. EU AI Act Newsletter) | Analyse d'experts, recoupement | Gratuit |
| Liste X (Twitter) « IA officielle » | Flux réseau social : annonces à chaud des fournisseurs et de la CNIL, consultées manuellement | Gratuit |
| Artificial Analysis | Comparatif indépendant des modèles, pour le benchmark | Gratuit |

Choix cohérent avec le budget : uniquement des outils gratuits, sauf le service d'IA, dont le coût est
suivi par le monitorage.

## Rythme

| Quand | Quoi |
|---|---|
| Mercredi 18 h (automatique) | `veilleia hebdo` : collecte, analyse, synthèse, monitorage (tâche planifiée) |
| **Jeudi 9 h – 10 h (1 h)** | Relecture de la synthèse, vérification des points clés dans les sources, consultation de la liste X et ajout des informations lues hors outil (après recoupement), diffusion, mise à jour du journal |
| 1er jeudi du mois | Revue des sources (flux en erreur, nouvelles sources, fiabilité) |

## Diffusion

- Synthèse HTML accessible (RGAA) envoyée par mail aux listes de diffusion de la DSI, du DPO, du
  service juridique et du RSSI (`veilleia synthetiser --envoyer`).
- Archive dans `syntheses/` (versionnée dans le dépôt).
