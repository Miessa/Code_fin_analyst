# -*- coding: utf-8 -*-
"""
collecter_libelles.py — COLLECTE EXHAUSTIVE des libellés (rapide).

PERFORMANCE : en mode read_only, openpyxl est rapide pour lire les lignes EN
SÉQUENCE (iter_rows) mais très lent pour les accès dispersés (ws.cell). Ce
collecteur lit donc chaque ligne UNE fois, sous forme de tableau de valeurs,
et y trouve libellé + 1re valeur voisine sans aucun accès cellule ponctuel.
"""
import warnings; warnings.filterwarnings("ignore")
import re
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from .unit_semantics import decompose_unit

FEUILLES_DEFAUT = [
    "InpC",
    "InpS",
    "InpS-M",
    "Summary",
    "Results",
    "Output",
    "Oper",
    "FS_Ann",
]


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _libelle_admis(texte, lmin=3, lmax=80):
    """Accepte notamment les acronymes financiers courts tels que EPC/IRR."""
    return lmin <= len(texte) < lmax


UNIT_RE = re.compile(
    r"(?:%|usd|eur|xaf|fcfa|cfa|gwh|mwh|kwh|mw|kw|years?|ans?|mois|months?|/kwh|/kw)",
    re.IGNORECASE,
)


def _contexte_superieur(lignes_precedentes, colonne, rayon=2):
    textes = []
    for entree in reversed(lignes_precedentes[-8:]):
        ligne = entree[1] if isinstance(entree, tuple) else entree
        for index in range(max(0, colonne - rayon), min(len(ligne), colonne + rayon + 1)):
            valeur = ligne[index]
            if isinstance(valeur, str) and valeur.strip() and valeur.strip() not in textes:
                textes.append(valeur.strip())
    unite = next((texte for texte in textes if UNIT_RE.search(texte)), None)
    return textes[:8], unite


def _unit_candidate(text, sheet, row, column, relation, row_distance, column_distance):
    semantics = decompose_unit(text)
    if not semantics:
        return None
    relation_base = {
        "same_row_left": 0.96,
        "same_row_right": 0.98,
        "same_cell": 1.0,
        "upper_header": 0.86,
        "number_format": 0.92,
    }.get(relation, 0.5)
    distance = row_distance + column_distance
    confidence = max(0.1, relation_base - 0.035 * max(0, distance - 1))
    return {
        "source_text": str(text).strip(),
        "source_cell": f"{sheet}!{get_column_letter(column + 1)}{row}",
        "spatial_relation": relation,
        "row_distance": row_distance,
        "column_distance": column_distance,
        "attachment_confidence": round(confidence, 3),
        "semantics": semantics,
    }


def _spatial_unit_candidates(vals, previous_rows, sheet, row, label_col, value_col, number_format=None):
    """Collect unit hypotheses left, right and above without choosing one."""
    candidates = []
    seen = set()

    def add(text, source_row, source_col, relation):
        if not isinstance(text, str) or not text.strip():
            return
        item = _unit_candidate(
            text, sheet, source_row, source_col, relation,
            abs(row - source_row), abs(value_col - source_col),
        )
        if not item:
            return
        key = (item["source_cell"], item["semantics"]["unit_expression"])
        if key not in seen:
            seen.add(key)
            candidates.append(item)

    # Same row: retain both sides of the numeric value.  The label cell is
    # included because units are sometimes written inside the label itself.
    for col in range(max(0, label_col - 2), min(len(vals), value_col + 5)):
        if col == value_col:
            continue
        relation = "same_row_left" if col < value_col else "same_row_right"
        add(vals[col], row, col, relation)

    # Headers: scan the eight buffered rows, favouring the same value column.
    for source_row, previous in reversed(previous_rows):
        for col in range(max(0, value_col - 2), min(len(previous), value_col + 3)):
            add(previous[col], source_row, col, "upper_header")

    if number_format and number_format != "General":
        add(number_format, row, value_col, "number_format")

    candidates.sort(key=lambda c: c["attachment_confidence"], reverse=True)
    return candidates


def _feuilles_a_parcourir(workbook, feuilles=None):
    """Choisit les feuilles sans dépendre des noms propres à un modèle."""
    disponibles = list(workbook.sheetnames)
    if feuilles is not None:
        return [nom for nom in feuilles if nom in disponibles]
    prioritaires = [nom for nom in FEUILLES_DEFAUT if nom in disponibles]
    restantes = [nom for nom in disponibles if nom not in prioritaires]
    return prioritaires + restantes


def collecter(
    fichier, feuilles=None, max_lignes=None, lmin=3, lmax=80,
    rapport=None,
):
    """Catalogue : [{libelle, cellule_libelle, adresse_valeur, valeur}].
    Lecture 100% séquentielle : chaque ligne est convertie en liste de valeurs,
    puis on cherche dans cette liste (en mémoire) — pas d'accès cellule dispersé."""
    wv = load_workbook(fichier, data_only=True, read_only=True)
    catalogue = []
    feuilles_disponibles = list(wv.sheetnames)
    feuilles_parcourues = _feuilles_a_parcourir(wv, feuilles)
    if rapport is not None:
        rapport.update({
            "feuilles_disponibles": feuilles_disponibles,
            "feuilles_parcourues": feuilles_parcourues,
            "nombre_feuilles_disponibles": len(feuilles_disponibles),
            "nombre_feuilles_parcourues": len(feuilles_parcourues),
        })
    for nom in feuilles_parcourues:
        ws = wv[nom]
        dernier_texte_par_colonne = {}
        lignes_precedentes = []
        for ri, row in enumerate(ws.iter_rows(max_row=max_lignes), start=1):
            vals = [cell.value for cell in row]
            n = len(vals)
            for i, v in enumerate(vals):
                if isinstance(v, str):
                    s = v.strip()
                    if _libelle_admis(s, lmin=lmin, lmax=lmax):
                        # 1re valeur numérique à droite, dans la MÊME ligne déjà lue
                        adr_val = val = None
                        for j in range(i + 1, n):
                            if _num(vals[j]):
                                adr_val = f"{nom}!{get_column_letter(j+1)}{ri}"
                                val = vals[j]
                                break
                        if adr_val is not None:
                            contexte_haut, _ = _contexte_superieur(
                                lignes_precedentes, j
                            )
                            unit_candidates = _spatial_unit_candidates(
                                vals,
                                lignes_precedentes,
                                nom,
                                ri,
                                i,
                                j,
                                getattr(row[j], "number_format", None),
                            )
                            unite_detectee = (
                                unit_candidates[0]["semantics"]["unit_expression"]
                                if unit_candidates else None
                            )
                            voisins_textuels = [
                                str(vals[j]).strip()
                                for j in range(max(0, i - 4), min(n, i + 5))
                                if j != i
                                and isinstance(vals[j], str)
                                and vals[j].strip()
                            ]
                            catalogue.append({
                                "libelle": s,
                                "cellule_libelle": f"{nom}!{get_column_letter(i+1)}{ri}",
                                "adresse_valeur": adr_val,
                                "valeur": val,
                                "feuille": nom,
                                "section": dernier_texte_par_colonne.get(i),
                                "contexte": " | ".join(voisins_textuels),
                                "contexte_haut": " | ".join(contexte_haut),
                                "unite_detectee": unite_detectee,
                                "unit_candidates": unit_candidates,
                            })
            # Mettre à jour après la collecte afin que ``section`` désigne un
            # texte d'une ligne précédente, jamais le libellé lui-même.
            for i, valeur in enumerate(vals):
                if isinstance(valeur, str) and valeur.strip():
                    dernier_texte_par_colonne[i] = valeur.strip()
            lignes_precedentes.append((ri, vals))
            if len(lignes_precedentes) > 8:
                lignes_precedentes.pop(0)
    wv.close()
    return catalogue


if __name__ == "__main__":
    import sys, time
    f = sys.argv[1] if len(sys.argv) > 1 else "kikot.xlsm"
    t = time.time()
    cat = collecter(f)
    print(f"{len(cat)} libellés en {time.time()-t:.1f}s")


    for e in cat[:5]:
        print(f"  {e['cellule_libelle']} «{e['libelle'][:40]}» -> {e['adresse_valeur']}={e['valeur']}")
