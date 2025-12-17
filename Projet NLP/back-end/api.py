# ===================== IMPORTS =====================
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Dict, Any
from pathlib import Path
import io, json, zipfile, re, logging

from annotator import annotate_html, PATTERNS

# ===================== LOGGING =====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("juridic-annotator")

# ===================== INITIALISATION =====================
app = FastAPI(title="API Références juridiques", version="1.0.0")

# Autorisation CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# CORRECTION ICI : Chemin absolu basé sur la position du fichier api.py
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Vérifier que templates existe
if not TEMPLATES_DIR.exists():
    logger.warning(f"⚠️ Le dossier templates n'existe pas : {TEMPLATES_DIR}")
    TEMPLATES_DIR.mkdir(exist_ok=True)
    logger.info(f"✅ Dossier templates créé : {TEMPLATES_DIR}")
else:
    logger.info(f"✅ Dossier templates trouvé : {TEMPLATES_DIR}")

# Initialiser Jinja2Templates avec le bon chemin
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Servir les fichiers statiques si le dossier existe
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    logger.info(f"✅ Dossier static monté : {STATIC_DIR}")

# ===================== MODÈLES DE DONNÉES =====================
class AnnotateIn(BaseModel):
    html: str

class AnnotateOut(BaseModel):
    html: str
    references: List[Dict[str, Any]]

class DirIn(BaseModel):
    path: str

# ===================== ENDPOINTS SIMPLES =====================
@app.get("/health")
def health():
    """Vérifie que l'API est vivante"""
    return {"status": "ok", "version": "1.0.0"}

@app.get("/patterns")
def patterns():
    """Retourne tous les types de références supportés"""
    return {"supported": sorted(list({p[0] for p in PATTERNS}))}

@app.post("/annotate", response_model=AnnotateOut)
def annotate(payload: AnnotateIn):
    """Annoter un HTML envoyé en body"""
    annotated, refs = annotate_html(payload.html)
    return {"html": annotated, "references": refs}

@app.post("/annotate-file", response_model=AnnotateOut)
async def annotate_file(file: UploadFile = File(...)):
    """Annoter un fichier HTML uploadé"""
    html = (await file.read()).decode("utf-8", errors="ignore")
    annotated, refs = annotate_html(html)
    return {"html": annotated, "references": refs}

# ==== Endpoint classification ====
# Variables globales pour l'index
INDEX_BUILT = False
ITEMS: Dict[int, Dict[str, Any]] = {}
TREE: Dict[str, list] = {}
NEXT_ID = 1

@app.get("/classification")
def classification():
    if not INDEX_BUILT:
        raise HTTPException(400, "Index non construit. Appelle d'abord /index-dir.")
    
    classification_dict = {}
    for item in ITEMS.values():
        type_text = item.get("type") or "Autres"
        classification_dict.setdefault(type_text, []).append({
            "id": item["id"],
            "file": item["file"],
            "text": item["text"],
            "date": item["date"]
        })
    return classification_dict

@app.get("/classification/{arrete_type}")
def classification_items(arrete_type: str):
    if not INDEX_BUILT:
        raise HTTPException(400, "Index non construit.")
    
    items_list = [i for i in ITEMS.values() if i.get("type") == arrete_type]
    return items_list

# ===================== INDEXATION =====================
def _parse_date(text: str):
    """Extrait une date depuis un texte"""
    mois = ("janvier|février|fevrier|mars|avril|mai|juin|juillet|août|"
            "aout|septembre|octobre|novembre|décembre|decembre")
    date_re = re.compile(rf"(1er|[0-3]?\d)\s+({mois})\s+\d{{4}}", re.IGNORECASE)
    m = date_re.search(text or "")
    return m.group(0) if m else None

def _build_index(input_dir: Path):
    """Construit un index des références juridiques dans un dossier"""
    global INDEX_BUILT, ITEMS, TREE, NEXT_ID
    INDEX_BUILT, ITEMS, TREE, NEXT_ID = False, {}, {}, 1

    html_files = [
        p for p in input_dir.rglob("*.html")
        if "__MACOSX" not in str(p) and not p.name.startswith("._")
    ]

    for f in html_files:
        raw = f.read_text(encoding="utf-8", errors="ignore")
        annotated, refs = annotate_html(raw)

        for r in refs:
            start, end = r["start"], r["end"]
            snippet = raw[max(0, start-100):end+100].replace("\n", " ")

            item = {
                "id": NEXT_ID,
                "type": r["type"],
                "text": r["text"],
                "normalized": r.get("normalized", r["text"]),
                "file": str(f),
                "date": _parse_date(r.get("text")) or _parse_date(r.get("normalized")),
                "snippet": snippet,
                "href": r.get("href", ""),
            }

            ITEMS[NEXT_ID] = item
            TREE.setdefault(r["type"], []).append({
                "id": NEXT_ID,
                "text": r["text"],
                "file": str(f),
                "date": item["date"],
            })

            NEXT_ID += 1

    INDEX_BUILT = True

@app.post("/index-dir")
def index_dir(payload: DirIn):
    """Construire l'index pour un dossier donné"""
    p = Path(payload.path)
    if not p.exists() or not p.is_dir():
        raise HTTPException(404, f"Dossier introuvable: {p}")
    _build_index(p)
    total = sum(len(v) for v in TREE.values())
    return {"ok": True, "types": list(TREE.keys()), "count": total}

@app.get("/tree")
def tree():
    """Retourne l'arborescence par type de référence"""
    if not INDEX_BUILT:
        raise HTTPException(400, "Index non construit. Appelle d'abord /index-dir.")
    return TREE

@app.get("/item/{item_id}")
def item(item_id: int):
    """Retourne le détail d'une référence par ID"""
    if not INDEX_BUILT:
        raise HTTPException(400, "Index non construit.")
    if item_id not in ITEMS:
        raise HTTPException(404, "Item introuvable")
    return ITEMS[item_id]

# ===================== TRAITEMENT ZIP =====================
def _process_dir_to_zip(input_dir: Path) -> bytes:
    """Traite tous les fichiers HTML d'un dossier et génère un ZIP annoté"""
    out_root = input_dir.parent / (input_dir.name + "_annotated")
    if out_root.exists():
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

    html_files = [
        p for p in input_dir.rglob("*.html")
        if "__MACOSX" not in str(p) and not p.name.startswith("._")
    ]

    for f in html_files:
        raw = f.read_text(encoding="utf-8", errors="ignore")
        annotated, refs = annotate_html(raw)
        rel = f.relative_to(input_dir)
        target_dir = (out_root / rel).parent
        target_dir.mkdir(parents=True, exist_ok=True)

        (target_dir / (f.stem + "_annotated.html")).write_text(
            annotated, encoding="utf-8"
        )
        (target_dir / (f.stem + "_refs.json")).write_text(
            json.dumps(refs, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in out_root.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(out_root))
    buf.seek(0)
    return buf.getvalue()

@app.post("/annotate-dir-zip")
def annotate_dir_zip(payload: DirIn):
    """Traite un dossier complet et renvoie un ZIP annoté"""
    p = Path(payload.path)
    if not p.exists() or not p.is_dir():
        raise HTTPException(404, f"Dossier introuvable: {p}")

    zip_bytes = _process_dir_to_zip(p)
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=annotated.zip"}
    )

# ===================== MINI UI =====================
@app.get("/ui", response_class=HTMLResponse)
def ui(request: Request):
    """Rend le template index.html pour navigation"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/annotate.html", response_class=HTMLResponse)
def annotate_page(request: Request):
    return templates.TemplateResponse("annotate.html", {"request": request})

@app.get("/annotate_file.html", response_class=HTMLResponse)
def annotate_file_page(request: Request):
    return templates.TemplateResponse("annotate_file.html", {"request": request})

@app.get("/index_dir.html", response_class=HTMLResponse)
def index_dir_page(request: Request):
    return templates.TemplateResponse("index_dir.html", {"request": request})

@app.get("/classification.html", response_class=HTMLResponse)
def classification_page(request: Request):
    return templates.TemplateResponse("classification.html", {"request": request})

@app.get("/annotate_dir_zip.html", response_class=HTMLResponse)
def annotate_dir_zip_page(request: Request):
    return templates.TemplateResponse("annotate_dir_zip.html", {"request": request})

@app.get("/demo_annotate.html", response_class=HTMLResponse)
def demo_annotate_page(request: Request):
    return templates.TemplateResponse("demo_annotate.html", {"request": request})

@app.get("/documentation.html", response_class=HTMLResponse)
def documentation_page(request: Request):
    return templates.TemplateResponse("documentation.html", {"request": request})

# ===================== LANCEMENT =====================
if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Lancement de l'API Références Juridiques")
    logger.info(f"📁 Templates directory: {TEMPLATES_DIR}")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)