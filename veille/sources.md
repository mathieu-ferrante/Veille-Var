# Sources de veille et grille de fiabilité

La veille combine :

- **12 flux RSS collectés automatiquement** par VeilleIA (liste dans `sources.yaml`) ;
- **des sources consultées manuellement** pendant le créneau hebdomadaire, quand l'automatisation
  n'est pas possible ou pas pertinente (réseaux sociaux, comparateurs de modèles).

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

## Sources automatisées (flux RSS)

| Source | Thème | A | B | C | D | E | F | Note | Commentaire |
|---|---|---|---|---|---|---|---|---|---|
| CNIL – Actualités | Réglementaire | | | | | | | | Autorité de contrôle RGPD |
| LINC (CNIL) | Réglementaire | | | | | | | | Laboratoire d'innovation de la CNIL, analyses prospectives |
| Commission européenne – Digital strategy | Réglementaire | | | | | | | | Source officielle de l'AI Act |
| EU AI Act Newsletter (Future of Life Institute) | Réglementaire | | | | | | | | Synthèse experte ; organisation engagée sur la régulation de l'IA : à recouper |
| Mistral AI – Blog | Technique | | | | | | | | Fournisseur testé ; officiel mais promotionnel |
| Hugging Face – Blog | Technique | | | | | | | | Écosystème des modèles open-weight |
| OpenAI – News | Technique | | | | | | | | Fournisseur étudié ; officiel mais promotionnel |
| Google – Blog IA | Technique | | | | | | | | Fournisseur testé (Gemini) ; officiel mais promotionnel |
| Simon Willison's Weblog | Technique | | | | | | | | Développeur indépendant reconnu, recoupe les annonces |
| Next | Presse | | | | | | | | Presse française, couvre bien la réglementation |
| Le Monde Informatique – IA | Presse | | | | | | | | Presse professionnelle française |
| GreenIT.fr | Sobriété | | | | | | | | Éco-conception numérique |

## Sources consultées manuellement

| Source | Usage | Pourquoi pas automatisée |
|---|---|---|
| Liste X (Twitter) « IA officielle » : comptes officiels des fournisseurs d'IA (OpenAI, Mistral AI, Google DeepMind, Anthropic, Hugging Face) et de la CNIL | Annonces à chaud, consultées pendant le créneau du jeudi ; les éléments utiles sont notés dans le journal | API de X payante et limitée en lecture, collecte automatique interdite par les conditions d'utilisation, pas de flux RSS |
| Artificial Analysis (artificialanalysis.ai) | Comparatif indépendant des modèles (qualité, vitesse, prix), utilisé comme source du benchmark (C7) | Pas de flux RSS ; données consultées et citées avec leur date |

Les informations vues sur les réseaux sociaux sont toujours **recoupées** avec la source officielle
(blog, communiqué, texte juridique) avant d'entrer dans une synthèse (critère F).

## Sources écartées

| Source | Raison |
|---|---|
| CERT-FR (ANSSI) | Source très fiable mais centrée sur les vulnérabilités en général, peu sur l'IA : trop de bruit pour le thème |
| ActuIA | Fait largement doublon avec Le Monde Informatique et Next |
| La Gazette des communes, Courrier des maires | Flux RSS refusé aux outils automatisés (HTTP 403) |
| Légifrance | Flux RSS refusé aux outils automatisés (HTTP 403) ; les textes sont suivis via la Commission et la CNIL |
| numerique.gouv.fr (DINUM) | Pas de flux RSS trouvé |
