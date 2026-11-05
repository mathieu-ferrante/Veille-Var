# Sources de veille et grille de fiabilité

> **Statut : à arrêter ensemble.** La liste de `sources.yaml` est provisoire (flux vérifiés
> techniquement le 05/11/2026). Chaque source doit être évaluée avec la grille ci-dessous avant
> d'être retenue.

## Grille de fiabilité (critères du référentiel)

| Code | Critère |
|---|---|
| A | L'auteur de la page est identifié |
| B | Des informations sur l'auteur confirment sa compétence, sa notoriété et l'absence d'intérêt personnel |
| C | Le contenu est valable : date récente, sources indiquées, niveau de langue correct |
| D | Le site ou le document est structuré |
| E | Le site respecte les normes d'accessibilité (à privilégier) |
| F | L'information peut être confirmée par d'autres sites de confiance |

Notation : ✔ (oui), ~ (partiellement), ✘ (non). Note globale sur 5 reportée dans `sources.yaml`.

## Évaluation des sources

| Source | Thème | A | B | C | D | E | F | Note | Retenue ? | Commentaire |
|---|---|---|---|---|---|---|---|---|---|---|
| CNIL – Actualités | Réglementaire | | | | | | | | | |
| LINC (CNIL) | Réglementaire | | | | | | | | | |
| Commission européenne – Digital strategy | Réglementaire | | | | | | | | | |
| EU AI Act Newsletter (FLI) | Réglementaire | | | | | | | | | |
| CERT-FR (ANSSI) | Sécurité | | | | | | | | | |
| Mistral AI – Blog | Technique | | | | | | | | | Source officielle mais promotionnelle |
| Hugging Face – Blog | Technique | | | | | | | | | |
| OpenAI – News | Technique | | | | | | | | | Source officielle mais promotionnelle |
| Google – Blog IA | Technique | | | | | | | | | Source officielle mais promotionnelle |
| Simon Willison's Weblog | Technique | | | | | | | | | |
| Next | Presse | | | | | | | | | |
| ActuIA | Presse | | | | | | | | | |
| Le Monde Informatique – IA | Presse | | | | | | | | | |
| GreenIT.fr | Sobriété | | | | | | | | | |

## Sources écartées

| Source | Raison |
|---|---|
| La Gazette des communes, Courrier des maires | Flux RSS refusé aux outils automatisés (HTTP 403) : lecture manuelle via l'agrégateur |
| Légifrance | Flux RSS refusé aux outils automatisés (HTTP 403) |
| numerique.gouv.fr (DINUM) | Pas de flux RSS trouvé : suivi manuel |
