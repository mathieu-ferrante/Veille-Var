"""Ligne de commande VeilleIA.

    veilleia verifier                 # teste la configuration et l'accès au service d'IA
    veilleia sources                  # liste les sources actives
    veilleia collecter                # récupère les nouvelles publications RSS
    veilleia analyser [--limite N]    # classe, note et résume les publications non analysées
    veilleia synthetiser [--envoyer]  # produit la synthèse hebdomadaire (HTML + Markdown)
    veilleia monitoring               # indicateurs, alertes et tableau de bord
    veilleia hebdo [--envoyer]        # enchaîne collecte, analyse, synthèse et monitoring
    veilleia jeu-test                 # tire 30 publications à annoter pour le benchmark
    veilleia benchmark [--services]   # compare les services d'IA sur le jeu annoté
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime, timedelta

from .analyse import analyser_en_attente
from .benchmark import constituer_jeu_test, lancer_benchmark
from .collecte import charger_sources, collecter
from .config import Config, ErreurConfiguration, charger_config
from .diffusion import envoyer_synthese
from .ia_client import ClientIA, ErreurServiceIA
from .journal import configurer_journal
from .monitoring import produire_rapport
from .stockage import Stockage
from .synthese import ecrire_synthese, generer_synthese, periode_par_defaut

log = logging.getLogger("veilleia")


def _client(config: Config, stockage: Stockage, fournisseur: str | None) -> ClientIA:
    prod = config.production
    return ClientIA(config.fournisseur(fournisseur), stockage, timeout_s=prod["timeout_s"],
                    tentatives=prod["tentatives"])


def cmd_verifier(config: Config, stockage: Stockage, args: argparse.Namespace) -> int:
    f = config.fournisseur(args.fournisseur)
    print(f"Service configuré : {f.libelle}  ({f.base_url})")
    print(f"Modèles : analyse = {f.modele(config.production['modele_analyse'])}, "
          f"synthèse = {f.modele(config.production['modele_synthese'])}")
    print(f"Clé API ({f.cle_env or 'aucune requise'}) : {'présente' if f.est_configure() else 'ABSENTE'}")
    client = _client(config, stockage, args.fournisseur)
    try:
        for taille in ("petit", "grand"):
            rep = client.verifier_acces(taille)
            print(f"  Accès {taille:5s} ({rep.modele}) : OK en {rep.latence_s:.2f}s "
                  f"– réponse « {rep.texte.strip()[:30]} »")
    finally:
        client.fermer()
    return 0


def cmd_sources(config: Config, stockage: Stockage, args: argparse.Namespace) -> int:
    for s in charger_sources(config.chemin(config.collecte["fichier_sources"])):
        print(f"{s.id:18s} {s.theme:13s} fiabilité {s.fiabilite}/5  {s.url}")
    return 0


def cmd_collecter(config: Config, stockage: Stockage, args: argparse.Namespace) -> int:
    sources = charger_sources(config.chemin(config.collecte["fichier_sources"]))
    bilan = collecter(sources, stockage, config.collecte)
    log.info("Collecte : %(sources_ok)d source(s) OK, %(sources_erreur)d en erreur, %(nouveaux)d nouveaux", bilan)
    return 0


def cmd_analyser(config: Config, stockage: Stockage, args: argparse.Namespace) -> int:
    client = _client(config, stockage, args.fournisseur)
    try:
        bilan = analyser_en_attente(client, config, stockage, getattr(args, "limite", None))
    finally:
        client.fermer()
    log.info("Analyse : %(analyses)d réussie(s), %(erreurs)d erreur(s)", bilan)
    return 0 if bilan["erreurs"] == 0 else 1


def date_de_fin(valeur: str | None) -> datetime | None:
    """Interprète --fin. Une date seule (AAAA-MM-JJ) inclut toute la journée indiquée ; un fuseau fourni
    est respecté, sinon UTC."""
    if not valeur:
        return None
    try:
        dt = datetime.fromisoformat(valeur)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"date de fin invalide : {valeur!r} (format AAAA-MM-JJ)") from exc
    if len(valeur) == 10:  # date sans heure : fin de journée
        dt += timedelta(days=1, seconds=-1)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def entier_positif(valeur: str) -> int:
    n = int(valeur)
    if n < 0:
        raise argparse.ArgumentTypeError("doit être positif ou nul")
    return n


def cmd_synthetiser(config: Config, stockage: Stockage, args: argparse.Namespace) -> int:
    debut, fin = periode_par_defaut(getattr(args, "fin", None), getattr(args, "jours", 7))
    client = _client(config, stockage, args.fournisseur)
    try:
        resultat = generer_synthese(client, config, stockage, debut, fin)
    finally:
        client.fermer()
    if resultat is None:
        return 1
    html, md = ecrire_synthese(resultat, config, stockage)
    print(f"Synthèse : {html}")
    if getattr(args, "envoyer", False):
        envoyer_synthese(html, md, f"Veille IA – semaine du {debut:%d/%m} au {fin:%d/%m/%Y}")
    return 0


def cmd_monitoring(config: Config, stockage: Stockage, args: argparse.Namespace) -> int:
    alertes, chemin = produire_rapport(config, stockage)
    print(f"Tableau de bord : {chemin}")
    return 2 if alertes else 0


def cmd_jeu_test(config: Config, stockage: Stockage, args: argparse.Namespace) -> int:
    chemin = config.chemin("benchmark/jeu_test.json")
    if chemin.exists() and not args.ecraser:
        print(f"{chemin} existe déjà (annotations à préserver). Utiliser --ecraser pour le régénérer.")
        return 1
    n = constituer_jeu_test(stockage, chemin, args.taille)
    print(f"{n} publications écrites dans {chemin} : à annoter à la main avant le benchmark.")
    return 0


def cmd_benchmark(config: Config, stockage: Stockage, args: argparse.Namespace) -> int:
    fournisseurs = args.services.split(",") if args.services else None
    resultats, chemin = lancer_benchmark(config, config.chemin("benchmark/jeu_test.json"),
                                         config.chemin("benchmark/resultats"), fournisseurs)
    print(f"{len(resultats)} service(s) évalué(s). Résultats : {chemin}")
    return 0 if resultats else 1


def cmd_hebdo(config: Config, stockage: Stockage, args: argparse.Namespace) -> int:
    """Chaîne complète. Une étape en échec n'empêche pas le monitorage, qui doit justement la signaler."""
    codes = []
    for etape in (cmd_collecter, cmd_analyser, cmd_synthetiser):
        nom = getattr(etape, "__name__", "etape").removeprefix("cmd_")
        try:
            codes.append(etape(config, stockage, args))
        except ErreurServiceIA as exc:
            log.error("Étape %s en échec : %s", nom, exc)
            codes.append(1)
        except Exception:  # erreur imprévue (fichier, réseau…) : on la trace et on poursuit jusqu'au monitorage
            log.exception("Étape %s en échec (erreur inattendue)", nom)
            codes.append(1)
    codes.append(cmd_monitoring(config, stockage, args))
    return max(codes)


def construire_parseur() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="veilleia", description="Veille IA automatisée – DSI du Département")
    p.add_argument("--config", help="Chemin de config.yaml (défaut : racine du projet)")
    p.add_argument("--fournisseur", help="Forcer un fournisseur (défaut : production.fournisseur)")
    p.add_argument("-v", "--verbeux", action="store_true")
    sp = p.add_subparsers(dest="commande", required=True)
    sp.add_parser("verifier", help="Tester la configuration et l'accès au service d'IA")
    sp.add_parser("sources", help="Lister les sources actives")
    sp.add_parser("collecter", help="Collecter les flux RSS")
    a = sp.add_parser("analyser", help="Analyser les publications non traitées")
    a.add_argument("--limite", type=entier_positif, help="Nombre maximum de publications à analyser")
    for nom in ("synthetiser", "hebdo"):
        s = sp.add_parser(nom, help="Produire la synthèse" if nom == "synthetiser" else "Chaîne complète")
        s.add_argument("--jours", type=int, default=7, help="Durée de la période (défaut 7)")
        s.add_argument("--fin", type=date_de_fin, help="Date de fin AAAA-MM-JJ, journée incluse (défaut : maintenant)")
        s.add_argument("--envoyer", action="store_true", help="Envoyer la synthèse par mail (SMTP_* dans .env)")
        if nom == "hebdo":
            s.add_argument("--limite", type=entier_positif)
    sp.add_parser("monitoring", help="Indicateurs, alertes et tableau de bord")
    j = sp.add_parser("jeu-test", help="Constituer le jeu de test du benchmark (à annoter)")
    j.add_argument("--taille", type=int, default=30)
    j.add_argument("--ecraser", action="store_true")
    b = sp.add_parser("benchmark", help="Comparer les services d'IA sur le jeu de test annoté")
    b.add_argument("--services", help="Liste séparée par des virgules (défaut : tous ceux qui ont une clé)")
    return p


COMMANDES = {
    "verifier": cmd_verifier, "sources": cmd_sources, "collecter": cmd_collecter, "analyser": cmd_analyser,
    "synthetiser": cmd_synthetiser, "monitoring": cmd_monitoring, "hebdo": cmd_hebdo,
    "jeu-test": cmd_jeu_test, "benchmark": cmd_benchmark,
}


def main(argv: list[str] | None = None) -> int:
    for flux in (sys.stdout, sys.stderr):  # accents corrects dans la console Windows
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")
    args = construire_parseur().parse_args(argv)
    try:
        config = charger_config(args.config)
    except ErreurConfiguration as exc:
        print(f"Erreur de configuration : {exc}", file=sys.stderr)
        return 3
    configurer_journal(config.chemin("logs"), logging.DEBUG if args.verbeux else logging.INFO)
    stockage = Stockage(config.chemin_bdd)
    try:
        return COMMANDES[args.commande](config, stockage, args)
    except (ErreurServiceIA, ErreurConfiguration) as exc:
        log.error("%s", exc)
        return 1
    finally:
        stockage.fermer()


if __name__ == "__main__":
    sys.exit(main())
