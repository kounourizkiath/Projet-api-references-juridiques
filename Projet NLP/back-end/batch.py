# batch.py
"""
Utilitaire CLI pour traitement batch de dossiers HTML :
 - indexer un dossier (utilise annotator.annotate_html)
 - produire un zip annoté (utilise api._process_dir_to_zip logic)
Usage :
    python batch.py index /chemin/vers/dossier
    python batch.py zip   /chemin/vers/dossier -o out.zip
"""

import sys
from pathlib import Path
import argparse
import json
import zipfile
import io
from annotator import annotate_html

def build_index(input_dir: Path):
    items = {}
    tree = {}
    next_id = 1
    html_files = [p for p in input_dir.rglob("*.html") if "__MACOSX" not in str(p) and not p.name.startswith("._")]

    for f in html_files:
        raw = f.read_text(encoding="utf-8", errors="ignore")
        annotated, refs = annotate_html(raw)
        for r in refs:
            start, end = r["start"], r["end"]
            snippet = raw[max(0, start-100):end+100].replace("\n", " ")
            item = {
                "id": next_id,
                "type": r["type"],
                "text": r["text"],
                "normalized": r.get("normalized", r["text"]),
                "file": str(f),
                "snippet": snippet,
                "href": r.get("href", ""),
            }
            items[next_id] = item
            tree.setdefault(r["type"], []).append({
                "id": next_id,
                "text": r["text"],
                "file": str(f)
            })
            next_id += 1

    return items, tree

def create_zip(input_dir: Path, out_path: Path):
    out_root = input_dir.parent / (input_dir.name + "_annotated")
    if out_root.exists():
        # nettoyage simple
        for p in out_root.rglob("*"):
            if p.is_file():
                p.unlink()
        for p in sorted(out_root.rglob("*"), reverse=True):
            if p.is_dir():
                try:
                    p.rmdir()
                except OSError:
                    pass
    out_root.mkdir(exist_ok=True)

    html_files = [p for p in input_dir.rglob("*.html") if "__MACOSX" not in str(p) and not p.name.startswith("._")]

    for f in html_files:
        raw = f.read_text(encoding="utf-8", errors="ignore")
        annotated, refs = annotate_html(raw)
        rel = f.relative_to(input_dir)
        target_dir = (out_root / rel).parent
        target_dir.mkdir(parents=True, exist_ok=True)

        (target_dir / (f.stem + "_annotated.html")).write_text(annotated, encoding="utf-8")
        (target_dir / (f.stem + "_refs.json")).write_text(json.dumps(refs, ensure_ascii=False, indent=2), encoding="utf-8")

    # créer zip final
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in out_root.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(out_root))

    print(f"Zip créé: {out_path}")

def main(argv=None):
    parser = argparse.ArgumentParser(description="Batch processor for legal references annotation")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="Index a directory")
    p_index.add_argument("path", type=str, help="Directory to index")

    p_zip = sub.add_parser("zip", help="Produce annotated zip")
    p_zip.add_argument("path", type=str, help="Directory to process")
    p_zip.add_argument("-o", "--out", type=str, default="annotated.zip", help="Output zip file")

    args = parser.parse_args(argv)

    path = Path(args.path)
    if not path.exists() or not path.is_dir():
        print("Le chemin indiqué n'existe pas ou n'est pas un dossier.")
        sys.exit(1)

    if args.cmd == "index":
        items, tree = build_index(path)
        print(json.dumps({"count": len(items), "types": list(tree.keys())}, ensure_ascii=False, indent=2))
    elif args.cmd == "zip":
        out = Path(args.out)
        create_zip(path, out)

if __name__ == "__main__":
    main()
