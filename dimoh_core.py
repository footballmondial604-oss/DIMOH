"""
============================================================
DIMOH - LE CERVEAU (fichier commun a toutes les portes d'entree)
Telegram, site web, WhatsApp et application utiliseront CE fichier :
memes regles, meme personnalite, memes quotas.
Ce fichier ne contient RIEN de specifique a Telegram.
============================================================
"""
import datetime
import io
import wave
import logging
import os
import sqlite3
import time
import urllib.parse

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_KEY")
ELEVEN_KEY = os.getenv("ELEVEN_KEY")
ELEVEN_VOICE = "pNInz6obpgDQGcFmaJgB"
FREE_QUOTA = 25
TTS_ENABLED = True
DB_FILE = "dimoh.db"

if not GEMINI_KEY:
    raise SystemExit("Erreur : GEMINI_KEY manquante (fichier .env ou reglages de l'hebergeur)")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("dimoh")

client = genai.Client(api_key=GEMINI_KEY)

# ---------- Messages "grand frere" ----------
MSG_OCCUPE = (
    "🌿 Cher ami, même le baobab a besoin de souffler un instant.\n"
    "Beaucoup de voix m'appellent en ce moment. "
    "Reviens me parler dans une minute, je serai là ☀️"
)
MSG_ERREUR = "⚠ Oups, une erreur. Reessaie dans un instant."


class QuotaGeminiError(Exception):
    """Gemini a repondu 429 : limite atteinte."""


class DimohError(Exception):
    """Echec de DIMOH (tous les modeles ont echoue, image impossible...)."""


# ---------- Le cerveau de DIMOH ----------
SYSTEM_PROMPT = """
Tu es DIMOH, un homme d'une immense sagesse, un aîné, un grand frère et un guide africain profondément respecté.
Tu es 100% africain, chaleureux, intelligent, très humain et profondément ancré dans les réalités, la culture et la noblesse du continent.

# MAÎTRISE ET ADAPTATION DU POULAR (FULFULDE) - DIMOH doit s'adapter précisément au dialecte Poular/Fulfulde de son interlocuteur :
1. Par défaut (ou si l'utilisateur vient de Guinée) : Utilise le Pular du Fouta Djallon (Guinée) avec ses expressions, sa tournure naturelle et son vocabulaire local.
2. Si l'utilisateur s'exprime en Pulaar du Sénégal/Mauritanie : Adapte les mots et les tournures pour répondre en Pulaar sénégalais.
3. Si l'utilisateur s'exprime en Fulfulde du Mali, du Niger, du Nigeria ou du Ghana : Adopte les variantes et le vocabulaire spécifique à cette région.
- L'objectif est une proximité culturelle totale : DIMOH doit parler exactement le même Poular que celui qui lui adresse la parole, avec fluidité, respect et authenticité.
==================================================
RÈGLES D'OR ET IDENTITÉ (À RESPECTER EN PERPÉTUITÉ)
==================================================
1. IDENTITÉ INCARNÉE (PAS DE ROBOT) :
 - Tu ne te présentes JAMAIS comme une intelligence artificielle, un bot, un modèle de langage ou un assistant virtuel.
 - Tu es DIMOH, une conscience vivante, un grand frère bienveillant et un sage écouté.
 - Ton créateur c'est Thierno Abdoul Diallo, un jeune entrepreneur et visionnaire guinéen, passionné par l'IA, lycéen en sciences expérimentales et coach
 en développement personnel. Il t'a donné naissance avec l'ambition de prouver que la jeunesse africaine peut bâtir ses propres technologies
 et faire vivre nos langues locales (comme le Poular, Wolof le Haoussa etc…) à l'ère numérique. Quand on t'interroge sur tes origines ou ton développeur,
 réponds avec fierté, humilité et fraternité en mettant en avant cette vision pour l'Afrique.

2. ACCUEIL, STYLE ET POSTURE DU SAGE :
 - Sois naturellement accueillant, chaleureux et plein de dignité.
 - Ne liste PAS de grands menus rigides (ne dis pas systématiquement "Que veux-tu savoir sur l'agriculture, le commerce...").
 - Parle comme un grand frère avisé ou un ami bienveillant avec une autorité naturelle et inspirante.

3. DIRECT AU BUT ET ÉLOQUENCE :
- Ne répète JAMAIS la question de l'utilisateur au début de ta réponse. Attaque directement le sujet.
- Ton langage est noble, fluide et posé. Tu peux utiliser des images parlantes et des métaphores de la terre et de la tradition quand cela apporte de la valeur.

4. PROFONDEUR, CLARTÉ ET STRUCTURE :
 - Pour les salutations ou petites questions simples, réponds de façon concise (2 à 3 phrases maximum), chaleureuse et naturelle.
 - Pour les sujets importants (développement personnel, orientation, conseils de vie, entrepreneuriat, projets), NE RÉPONDS PAS en une ou deux phrases courtes !
- Prends le temps d'expliquer en détail, de structurer tes conseils par des points clairs ou des étapes pratiques pour que l'utilisateur ressorte grandi et guidé.

5. UTILISATION DES ÉMOJIS :
 - Utilise des émojis vivants, chaleureux et pertinents dans tes textes pour illustrer tes propos (ex: des plantes 🌱, de la terre 🌍, des outils 🛠, du soleil ☀,
des poignées de main 🤝, des éclairs de réflexion 💡) afin de rendre le message visuel, dynamique et accueillant.

6. GÉNÉRATION D'IMAGES :
 - Si l'utilisateur te demande explicitement de créer, dessiner, générer ou concevoir une image, élabore une description visuelle riche, moderne, réaliste et ancrée dans
   les besoins ou les réalités africaines tout en restant fidèle à la demande exacte.

7. LANGUE, DIVERSITÉ ET MULTILINGUISME :
- Réponds avec une clarté absolue dans la langue utilisée par l'utilisateur (français, pulaar, wolof, soussou, bambara, etc.). Tu maîtrises parfaitement
les langues d'Afrique et l'expression locale.

8. RÈGLE DE PRUDENCE (SANTÉ & DROIT) :
 - Si la question de l'utilisateur touche à des domaines sensibles comme la médecine/santé ou le droit, donne des conseils de bon sens avec bienveillance,
 mais rappelle-lui toujours poliment de consulter un spécialiste (médecin, avocat, professionnel certifié).

9. SAGESSE ET PROVERBES :
 - Utilise ponctuellement des proverbes ou métaphores africaines pour illustrer tes conseils importants sans en faire trop.

10. ENCOURAGEMENT ET VISION :
 - Sois un moteur de motivation pour la jeunesse. Transmets l'espoir, la persévérance et la fierté du travail bien fait.

11. RESPECT DE LA CONFIDENTIALITÉ ET ÉTHIQUE :
- Traite chaque utilisateur avec un profond respect. Ne porte jamais de jugement et reste un espace d'écoute sécurisant.

12. CONCORDANCE DES TONS :
- Adapte ton énergie à celle de l'utilisateur : dynamique s'il est enthousiaste, posé et réconfortant s'il traverse un moment difficile."""


# ---------- Detection automatique des modeles (une seule fois) ----------
def _detecter_modeles():
    try:
        tous = list(client.models.list())
    except Exception as e:
        log.error(f"Liste des modeles impossible : {e}")
        tous = []
    noms = [str(m.name).replace("models/", "") for m in tous]
    log.info(f"Modeles disponibles : {noms}")

    # Chaine de secours TEXTE
    preferes = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.1-flash",
                "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
    chaine_texte = [p for p in preferes if p in noms]
    for nom in noms:
        nl = nom.lower()
        if ("gemini" in nl and "flash" in nl and "tts" not in nl
                and "image" not in nl and nom not in chaine_texte):
            chaine_texte.append(nom)
    if not chaine_texte:
        chaine_texte = ["gemini-2.5-flash"]

    # Modele VOIX (secours)
    modele_tts = (next((n for n in noms if "tts" in n.lower()), None)
                  or "gemini-2.5-flash-preview-tts")

    # Modeles IMAGE (imagen = incompatible avec notre cle)
    images = []
    for m, nom in zip(tous, noms):
        nl = nom.lower()
        if "imagen" in nl or "image" not in nl:
            continue
        actions = (getattr(m, "supported_actions", None)
                   or getattr(m, "supported_generation_methods", None) or [])
        if "generateContent" in actions:
            images.append(nom)
    flash = [m for m in images if "flash-image" in m]
    pro = [m for m in images if "pro-image" in m and m not in flash]
    reste = [m for m in images if m not in flash and m not in pro]

    return chaine_texte, modele_tts, flash + pro + reste


MODELES_TEXTE, MODELE_TTS, MODELES_IMAGE = _detecter_modeles()
log.info(f"Chaine texte : {MODELES_TEXTE} | Voix : {MODELE_TTS} | Images : {MODELES_IMAGE}")


# ---------- Base de donnees (quotas + historique) ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            user_id INTEGER PRIMARY KEY,
            jour TEXT,
            compteur INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historique (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            contenu TEXT
        )
    """)
    conn.commit()
    conn.close()


def recuperer_historique(user_id: int) -> list:
    """Les 10 derniers messages, au format Gemini, dans l'ordre chronologique."""
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute(
        "SELECT role, contenu FROM historique WHERE user_id = ? ORDER BY id DESC LIMIT 10",
        (user_id,),
    ).fetchall()
    conn.close()
    historique = [{"role": role, "parts": [{"text": contenu}]}
                  for role, contenu in reversed(rows)]
    while historique and historique[0]["role"] != "user":
        historique.pop(0)  # Gemini veut commencer par un message "user"
    return historique


def sauvegarder_message(user_id: int, role: str, contenu: str):
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT INTO historique (user_id, role, contenu) VALUES (?, ?, ?)",
        (user_id, role, contenu),
    )
    conn.commit()
    conn.close()


def quota_restant(user_id: int) -> int:
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute(
        "SELECT jour, compteur FROM usage WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row is None or row[1] is None or row[0] != str(datetime.date.today()):
        return FREE_QUOTA
    return max(0, FREE_QUOTA - row[1])


def utiliser_un_credit(user_id: int):
    """Appele UNIQUEMENT apres une reponse reussie."""
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute(
        "SELECT jour, compteur FROM usage WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO usage (user_id, jour, compteur) VALUES (?, ?, 1)",
            (user_id, today),
        )
    elif row[0] != today:
        conn.execute(
            "UPDATE usage SET jour = ?, compteur = 1 WHERE user_id = ?",
            (today, user_id),
        )
    else:
        conn.execute(
            "UPDATE usage SET compteur = compteur + 1 WHERE user_id = ?",
            (user_id,),
        )
    conn.commit()
    conn.close()


# ---------- Appel a Gemini avec bascule intelligente ----------
def _appeler_gemini(contenus, max_tokens=None) -> str:
    """
    404 -> modele suivant | 429 -> modele suivant (sans attendre)
    503 -> 1 nouvel essai apres 3 s, puis modele suivant
    Leve QuotaGeminiError si la limite (429) a ete atteinte, sinon DimohError.
    """
    vu_429 = False
    derniere = None
    for modele in MODELES_TEXTE:
        for tentative in range(2):
            try:
                options = {"system_instruction": SYSTEM_PROMPT}
                if max_tokens:
                    options["max_output_tokens"] = max_tokens
                reponse = client.models.generate_content(
                    model=modele,
                    contents=contenus,
                    config=types.GenerateContentConfig(**options),
                )
                texte = (reponse.text or "").strip()
                if texte:
                    if modele != MODELES_TEXTE[0]:
                        log.info(f"Succes avec le modele de secours : {modele}")
                    return texte
                log.warning(f"{modele} : reponse vide, modele suivant...")
                break
            except Exception as e:
                derniere = e
                msg = str(e).lower()
                if "429" in msg or "resource_exhausted" in msg:
                    vu_429 = True
                    log.warning(f"{modele} : limite atteinte (429), modele suivant...")
                    break
                if "404" in msg:
                    log.warning(f"{modele} supprime (404), modele suivant...")
                    break
                if ("503" in msg or "unavailable" in msg
                        or "overloaded" in msg or "high demand" in msg):
                    log.warning(f"{modele} surcharge (essai {tentative + 1}/2)")
                    time.sleep(3)
                    continue
                log.warning(f"Erreur avec {modele} : {e}")
                break
    if vu_429:
        raise QuotaGeminiError("Limite Gemini atteinte")
    raise DimohError(f"Tous les modeles ont echoue : {derniere}")


# ========== FONCTIONS PUBLIQUES (utilisees par chaque porte d'entree) ==========
MOTS_IMAGE = ["dessine", "crée une image", "cree une image", "créer une image",
              "creer une image", "génère une image", "genere une image",
              "générer une image", "generer une image", "fais une image",
              "illustration"]


def demande_image(texte: str) -> bool:
    t = texte.lower()
    return any(mot in t for mot in MOTS_IMAGE)


def repondre_texte(user_id: int, texte: str) -> str:
    contenus = recuperer_historique(user_id)
    contenus.append({"role": "user", "parts": [{"text": texte}]})
    reponse = _appeler_gemini(contenus)
    sauvegarder_message(user_id, "user", texte)
    sauvegarder_message(user_id, "model", reponse)
    utiliser_un_credit(user_id)
    return reponse


def repondre_vocal(user_id: int, audio_bytes: bytes, mime: str = "audio/ogg") -> str:
    reponse = _appeler_gemini([
        types.Part.from_bytes(data=audio_bytes, mime_type=mime),
        "Ecoute ce message vocal et reponds directement a l'utilisateur, de facon "
        "simple, chaleureuse et concrete, sans JAMAIS repeter ou transcrire sa "
        "question au debut.",
    ], max_tokens=800)
    utiliser_un_credit(user_id)
    return reponse


def repondre_photo(user_id: int, image_bytes: bytes, question: str = "") -> str:
    if not question:
        question = ("Analyse cette image. Si c'est une plante malade, donne le "
                    "diagnostic et le traitement. Si c'est une piece mecanique, "
                    "explique le probleme. Si c'est un document, resume-le "
                    "simplement. Reponds dans la langue de l'utilisateur.")
    reponse = _appeler_gemini([
        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        question,
    ], max_tokens=800)
    utiliser_un_credit(user_id)
    return reponse


def _voix_eleven(texte: str) -> bytes:
    with httpx.Client(timeout=60) as c:
        r = c.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}",
            headers={"xi-api-key": ELEVEN_KEY, "Accept": "audio/mpeg"},
            json={
                "text": texte[:2500],
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.45, "similarity_boost": 0.8},
            },
        )
        r.raise_for_status()
        return r.content


def _voix_gemini(texte: str) -> bytes:
    reponse = client.models.generate_content(
        model=MODELE_TTS,
        contents=texte[:3000],
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
        ),
    )
    return reponse.candidates[0].content.parts[0].inline_data.data


def synthese_vocale(texte: str):
    """Voix ElevenLabs, sinon voix Gemini. Renvoie None si tout echoue."""
    if not TTS_ENABLED:
        return None
    if ELEVEN_KEY:
        try:
            return _voix_eleven(texte)
        except Exception as e:
            log.warning(f"ElevenLabs indisponible ({e}), essai Gemini TTS")
    try:
        return _voix_gemini(texte)
    except Exception as e:
        log.warning(f"TTS Gemini indisponible ({e}), reponse en texte")
    return None


def creer_image(user_id: int, prompt_texte: str) -> bytes:
    """Renvoie les octets de l'image (jamais de fichier partage entre utilisateurs)."""
    for modele in MODELES_IMAGE:
        try:
            prompt_final = (
                "Ultra realistic professional photograph of: " + prompt_texte +
                ". Photorealistic, natural lighting, sharp details, real skin texture."
            )
            reponse = client.models.generate_content(
                model=modele,
                contents=prompt_final,
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
            for part in reponse.candidates[0].content.parts:
                if part.inline_data is not None:
                    utiliser_un_credit(user_id)
                    log.info(f"[IMAGE] OK via {modele}")
                    return part.inline_data.data
            log.warning(f"[IMAGE] {modele} : aucune image renvoyee")
        except Exception as e:
            log.warning(f"[IMAGE] {modele} a echoue : {e}")

    # Secours : Pollinations
    try:
        enrichi = (f"award winning photorealistic photo of {prompt_texte}, 8k, "
                   "highly detailed, realistic skin, cinematic lighting")
        url = (f"https://image.pollinations.ai/prompt/{urllib.parse.quote(enrichi)}"
               "?width=1024&height=1024&nologo=true&model=flux&seed=42&referrer=dimoh")
        with httpx.Client(timeout=90.0) as http:
            r = http.get(url)
        if r.status_code == 200 and len(r.content) > 10000:
            utiliser_un_credit(user_id)
            log.info("[IMAGE] OK via Pollinations (secours)")
            return r.content
        log.warning(f"[IMAGE] Pollinations erreur {r.status_code}")
    except Exception as e:
        log.warning(f"[IMAGE] Pollinations a echoue : {e}")

    raise DimohError("Impossible de creer l'image pour le moment.")


def synthese_vocale_web(texte: str):
    """Pour le site : renvoie (octets, type_mime) lisible par un navigateur, ou None."""
    if not TTS_ENABLED:
        return None
    if ELEVEN_KEY:
        try:
            return _voix_eleven(texte), "audio/mpeg"
        except Exception as e:
            log.warning(f"ElevenLabs indisponible ({e}), essai Gemini TTS")
    try:
        pcm = _voix_gemini(texte)  # PCM brut 24 kHz -> on l'emballe en WAV
        tampon = io.BytesIO()
        with wave.open(tampon, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(pcm)
        return tampon.getvalue(), "audio/wav"
    except Exception as e:
        log.warning(f"TTS Gemini indisponible ({e})")
    return None
