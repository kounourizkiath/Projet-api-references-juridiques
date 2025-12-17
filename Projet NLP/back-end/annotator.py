

# annotator.py
"""
Module de détection et annotation des références juridiques.
Exporte :
 - PATTERNS : liste de patterns (type, regex, normalizer)
 - annotate_html(html) -> (annotated_html, list_of_refs)
"""

import re
from typing import List, Dict, Any, Tuple
from html import escape

# Mois français (gère variantes OCR)
MOIS = (
    "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    "septembre|octobre|novembre|décembre|decembre"
)

# Patterns de base
DATE = rf"(?:1er|[0-3]?\d)\s+(?:{MOIS})\s+\d{{4}}"
NUM = r"(?:n[°ºo]\s*)?\d{{2,4}}(?:[-/.]\d+)*(?:/[A-Z]{{1,3}})?"

# ============================================================================
# PATTERNS V3 FINAL - COMPLETS ET ÉQUILIBRÉS
# ============================================================================

PATTERNS = [
    # CODE
    ("code",
     re.compile(r"\b[Cc]ode\s+de\s+l['’]?>?environnement\b", re.IGNORECASE),
     lambda m: "code de l'environnement"),
    ("code",
     re.compile(r"\b[Cc]ode\s+du\s+[Tt]ravail\b", re.IGNORECASE),
     lambda m: "code du travail"),
    ("code",
     re.compile(r"\b[Ll]ivre\s+[IVX]+\s+du\s+[Cc]ode\s+(?:de\s+l['’]?environnement|du\s+[Tt]ravail)",
                re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    ("code",
     re.compile(r"\barticle[s]?\s+[LRD]\.?\s*\d+(?:[-\.]\d+)*", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    # DIRECTIVE
    ("directive",
     re.compile(rf"\bdirective\s+\d{{4}}/\d{{1,4}}/(?:UE|CE|CEEA)(?:\s+du\s+{DATE})?", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).upper())),
    ("directive",
     re.compile(r"\bdirective\s+européenne\s+n[°ºo]?\s*\d{4}/\d+", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    # LOI
    ("loi",
     re.compile(rf"\bloi\s+n[°ºo]\s*\d{{2,4}}[-–]\d+\s+du\s+{DATE}", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    ("loi",
     re.compile(rf"\bloi\s+du\s+{DATE}", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    ("loi",
     re.compile(r"\b(?:la\s+)?loi\s+sur\s+(?:les\s+|l['’])[\w\s,'-]+?(?=\s+lui\s+sont|\s+sont\s+applicables|[,;.])",
                re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    # ARRETE MINISTERIEL
    ("arrete_ministeriel",
     re.compile(rf"\b(?:arrêté|arrete)\s+(?:ministériel|ministeriel)\s+(?:n[°ºo]\s*[\d/-]+\s+)?du\s+{DATE}",
                re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    ("arrete_ministeriel",
     re.compile(rf"\b(?:arrêté|arrete)\s+du\s+[Mm]inistre\s+(?:de\s+|d['’]|des\s+)[\w\s]+?\s+du\s+{DATE}",
                re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    ("arrete_ministeriel",
     re.compile(r"\b(?:arrêtés?|arretes?)[-\s]types?\s+n[°ºo]\s*\d+(?:\s+et\s+\d+)*", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    # DECRET
    ("decret",
     re.compile(rf"\b(?:décret|decret)\s+n[°ºo]\s*\d{{2,4}}[-–\s]\d+\s+du\s+{DATE}", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    ("decret",
     re.compile(rf"\b(?:décret|decret)\s+du\s+{DATE}", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    ("decret",
     re.compile(rf"\barticle[s]?\s+\d+\s+du\s+(?:décret|decret)\s+n[°ºo]\s*\d+[-–\s]\d+", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    # CIRCULAIRE / INSTRUCTION
    ("circulaire",
     re.compile(rf"\bcirculaire\s+(?:ministérielle|ministerielle)\s+(?:n[°ºo]\s*[\d/-]+\s+)?du\s+{DATE}",
                re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    ("circulaire",
     re.compile(rf"\bcirculaire\s+(?:n[°ºo]\s*[\d/-]+\s+)?du\s+{DATE}", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    ("circulaire",
     re.compile(rf"\binstruction\s+(?:ministérielle|ministerielle)\s+(?:n[°ºo]\s*[\d/-]+\s+)?du\s+{DATE}",
                re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    ("circulaire",
     re.compile(rf"\binstruction\s+du\s+[Mm]inistère\s+de\s+[\w\s'’]+?\s+du\s+{DATE}", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    # ARRETE PREFECTORAL
    ("arrete_prefectoral",
     re.compile(rf"\b(?:arrêté|arrete)\s+(?:préfectoral|prefectoral)\s+n[°ºo]\s*[\d/IC\-A-Z]+\s+du\s+{DATE}",
                re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    ("arrete_prefectoral",
     re.compile(rf"\b(?:arrêté|arrete)\s+(?:préfectoral|prefectoral)\s+du\s+{DATE}", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    ("arrete_prefectoral",
     re.compile(r"\b(?:le\s+)?présent\s+(?:arrêté|arrete)\s+(?:préfectoral|prefectoral)?", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    # NORME
    ("norme",
     re.compile(r"\bnorme\s+française\s+[A-Z]+\s*\d+(?:[-\s]\d+)*", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    ("norme",
     re.compile(r"\bnorme\s+(?:NF|ISO|EN)\s+[\w\s-]+", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    # ARRETE GENERIQUE
    ("arrete",
     re.compile(rf"\b(?:arrêté|arrete)\s+du\s+{DATE}(?!\s+(?:préfectoral|prefectoral))", re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
    ("arrete",
     re.compile(r"\b(?:le\s+)?présent\s+(?:arrêté|arrete)(?!\s+(?:ministériel|ministeriel|préfectoral|prefectoral))",
                re.IGNORECASE),
     lambda m: re.sub(r"\s+", " ", m.group(0).lower())),
]

# -----------------------
# Helpers
# -----------------------
def _slugify(s: str) -> str:
    """Transforme une chaîne en slug URL-friendly"""
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# -----------------------
# Fonction principale
# -----------------------
def annotate_html(html: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Prend du HTML en entrée et renvoie (html_annoté, liste_références)
    Chaque référence renvoyée contient : start, end, type, text, normalized, href
    """
    matches: List[Dict[str, Any]] = []
    s = html

    # Étape 1 : Collecte brute de toutes les correspondances
    for typ, reg, normf in PATTERNS:
        for m in reg.finditer(s):
            try:
                normalized = normf(m)
            except Exception:
                normalized = m.group(0)
            matches.append({
                "start": m.start(),
                "end": m.end(),
                "type": typ,
                "text": m.group(0),
                "normalized": normalized,
            })

    # Étape 2 : Résolution des chevauchements
    # Tri : position croissante, puis longueur décroissante
    matches.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))

    filtered: List[Dict[str, Any]] = []
    last_end = -1

    for m in matches:
        if m["start"] >= last_end:
            filtered.append(m)
            last_end = m["end"]

    # Étape 3 : Reconstruction HTML avec insertion des <a>
    out_parts: List[str] = []
    cur = 0

    for m in filtered:
        out_parts.append(s[cur:m["start"]])

        href = f"#ref:{m['type']}:{_slugify(m['normalized'])}"
        a = (
            '<a href="{href}" data-ref-type="{typ}" '
            'data-ref-normalized="{norm}">{text}</a>'
        ).format(
            href=href,
            typ=m["type"],
            norm=escape(m["normalized"]),
            text=escape(m["text"]),
        )
        out_parts.append(a)
        cur = m["end"]

        m["href"] = href

    out_parts.append(s[cur:])

    annotated_html = "".join(out_parts)
    return annotated_html, filtered


# Si besoin : démonstration rapide
if __name__ == "__main__":
    example = "<p>Vu le décret n° 77-1133 du 21 septembre 1977 et la loi du 12 janvier 2010.</p>"
    ann, refs = annotate_html(example)
    print(ann)
    print(refs)
