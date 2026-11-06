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
| CNIL – Actualités | Réglementaire | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 5 | Autorité de contrôle RGPD ; source primaire |
| LINC (CNIL) | Réglementaire | ✔ | ✔ | ✔ | ✔ | ~ | ✔ | 5 | Laboratoire d'innovation de la CNIL, analyses prospectives signées |
| Commission européenne – Digital strategy | Réglementaire | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 5 | Source officielle de l'AI Act ; en anglais |
| EU AI Act Newsletter (Future of Life Institute) | Réglementaire | ✔ | ~ | ✔ | ✔ | ~ | ✔ | 4 | Synthèse experte et sourcée ; organisation engagée pour la régulation de l'IA : à recouper |
| Mistral AI – Blog | Technique | ~ | ~ | ~ | ✔ | ~ | ~ | 3 | Fournisseur testé ; officiel mais promotionnel, chiffres non sourcés |
| Hugging Face – Blog | Technique | ✔ | ~ | ✔ | ✔ | ~ | ✔ | 4 | Billets signés, souvent avec code et résultats reproductibles |
| OpenAI – News | Technique | ~ | ~ | ~ | ✔ | ~ | ~ | 3 | Fournisseur étudié ; officiel mais promotionnel |
| Google – Blog IA | Technique | ✔ | ~ | ~ | ✔ | ~ | ~ | 3 | Fournisseur testé (Gemini) ; officiel mais promotionnel |
| Simon Willison's Weblog | Technique | ✔ | ✔ | ✔ | ✔ | ~ | ✔ | 4 | Développeur indépendant reconnu ; teste et recoupe les annonces, cite ses sources |
| Next | Presse | ✔ | ✔ | ✔ | ✔ | ~ | ✔ | 4 | Presse française indépendante (sans publicité), couvre bien la réglementation et la sécurité |
| Le Monde Informatique – IA | Presse | ✔ | ✔ | ✔ | ✔ | ~ | ✔ | 4 | Presse professionnelle française ; reprend parfois des communiqués |
| GreenIT.fr | Sobriété | ✔ | ~ | ✔ | ✔ | ~ | ✔ | 4 | Référence de l'éco-conception ; animé par un cabinet de conseil (intérêt possible) |

Évaluation du 06/11/2026, à revoir lors de la revue mensuelle des sources. Le critère E est noté
✔ seulement quand le site publie une déclaration d'accessibilité (obligation des organismes publics) ;
sinon ~ : pas d'audit RGAA réalisé dans le cadre de ce projet.

**Bilan.** Les sources institutionnelles (CNIL, Commission) sont des sources primaires : elles servent de
référence pour la réglementation. Les blogs des fournisseurs sont gardés pour suivre leurs offres, mais
toute information qui en vient est recoupée avant d'entrer dans une décision.

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
