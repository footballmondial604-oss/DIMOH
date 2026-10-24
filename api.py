"""DIMOH - Porte d'entree WEB (site + application installable). Utilise dimoh_core.py."""
import asyncio, base64, hashlib, os, time
from collections import defaultdict, deque

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import dimoh_core as core

core.init_db()
app = FastAPI(title="DIMOH")
APPELS = defaultdict(deque)


def id_web(visiteur: str) -> int:
    """Id negatif : ne peut jamais se confondre avec un id Telegram (positif)."""
    if not 16 <= len(visiteur or "") <= 64:
        raise HTTPException(400, "Visiteur invalide")
    return -1 - int(hashlib.sha256(visiteur.encode()).hexdigest()[:12], 16)


def limiter(request: Request):
    """Maximum 20 requetes par minute et par adresse IP."""
    ip = request.client.host if request.client else "?"
    f, now = APPELS[ip], time.time()
    while f and now - f[0] > 60:
        f.popleft()
    if len(f) >= 20:
        raise HTTPException(429, "Doucement mon ami, réessaie dans une minute 🌿")
    f.append(now)


async def traiter(request, visiteur, fonction, *args):
    uid = id_web(visiteur)
    limiter(request)
    if core.quota_restant(uid) <= 0:
        raise HTTPException(429, f"🛑 Tu as utilisé tes {core.FREE_QUOTA} questions gratuites d'aujourd'hui. Reviens demain 🌍")
    try:
        return await asyncio.to_thread(fonction, uid, *args)
    except core.QuotaGeminiError:
        raise HTTPException(503, core.MSG_OCCUPE)
    except Exception as e:
        core.log.error(f"[WEB] {e}")
        raise HTTPException(500, core.MSG_ERREUR)


def _image(octets):
    mime = "image/png" if octets[:4] == b"\x89PNG" else "image/jpeg"
    return {"type": "image", "mime": mime, "data": base64.b64encode(octets).decode()}


def _texte(uid, texte):
    if core.demande_image(texte):
        return _image(core.creer_image(uid, texte[:500]))
    return {"type": "texte", "texte": core.repondre_texte(uid, texte)}


def _vocal(uid, audio):
    texte = core.repondre_vocal(uid, audio, "audio/wav")
    rep = {"type": "texte", "texte": texte}
    voix = core.synthese_vocale_web(texte)
    if voix:
        rep["audio"], rep["audio_mime"] = base64.b64encode(voix[0]).decode(), voix[1]
    return rep


def _photo(uid, image, question):
    return {"type": "texte", "texte": core.repondre_photo(uid, image, question)}


class Msg(BaseModel):
    visiteur: str
    texte: str


@app.post("/api/message")
async def message(m: Msg, request: Request):
    if not m.texte.strip() or len(m.texte) > 2000:
        raise HTTPException(400, "Message vide ou trop long")
    return await traiter(request, m.visiteur, _texte, m.texte)


@app.post("/api/vocal")
async def vocal(request: Request, visiteur: str = Form(...), audio: UploadFile = File(...)):
    data = await audio.read()
    if not data or len(data) > 6_000_000:
        raise HTTPException(400, "Audio invalide ou trop long")
    return await traiter(request, visiteur, _vocal, data)


@app.post("/api/photo")
async def photo(request: Request, visiteur: str = Form(...), question: str = Form(""),
                image: UploadFile = File(...)):
    data = await image.read()
    if not data or len(data) > 8_000_000:
        raise HTTPException(400, "Photo invalide ou trop lourde")
    return await traiter(request, visiteur, _photo, data, question[:500])


@app.get("/api/quota")
async def quota(visiteur: str):
    return {"restant": core.quota_restant(id_web(visiteur))}


@app.get("/api/health")
async def health():
    return {"ok": True}


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "web"), html=True), name="web")
