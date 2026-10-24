"""
============================================================
DIMOH v5 - Porte d'entree TELEGRAM
Toute l'intelligence est dans dimoh_core.py (cerveau commun).
Ce fichier ne fait que parler avec Telegram.
============================================================
"""
import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.helpers import escape_markdown

import dimoh_core as core

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise SystemExit("Erreur : TELEGRAM_TOKEN manquant (fichier .env ou reglages de l'hebergeur)")

log = logging.getLogger("dimoh")


# ---------- Outils ----------
async def envoyer_texte(update: Update, texte: str):
    """Telegram refuse les messages de plus de 4096 caracteres : on decoupe."""
    for i in range(0, len(texte), 4000):
        await update.message.reply_text(texte[i:i + 4000])


async def verifier_quota(update: Update) -> bool:
    user_id = update.message.from_user.id
    if core.quota_restant(user_id) <= 0:
        await update.message.reply_text(
            f"🛑 Tu as utilisé tes {core.FREE_QUOTA} questions gratuites d'aujourd'hui !\n\n"
            "💰 Passe en abonnement PRO (bientôt disponible) ou reviens demain.\n"
            "Merci d'utiliser DIMOH 🌍"
        )
        return False
    return True


# ---------- Commandes ----------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prenom = update.message.from_user.first_name or "mon ami"
    texte = (
        f"Salutation à toi, {escape_markdown(prenom, version=1)} ! 🌿\n\n"
        "Je suis *DIMOH*, ton grand frère et guide digital.\n"
        "Je suis là pour échanger avec toi par texte ou par message vocal, "
        "te donner des conseils ou t'aider dans tes réflexions.\n\n"
        "Pose-moi une question ou envoie-moi un vocal en Français ou en Poular !"
    )
    await update.message.reply_text(texte, parse_mode="Markdown")


async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texte = (
        "🌍 *À propos de DIMOH*\n\n"
        "DIMOH est un assistant IA panafricain vocal et textuel, conçu pour accompagner "
        "la jeunesse et valoriser nos langues locales (Poular, Français...).\n\n"
        "👤 *Créateur :* Thierno Abdoul Diallo\n"
        "📍 *Origine :* Guinée\n\n"
        "💡 *Mission :* Prouver que la jeunesse africaine peut bâtir ses propres "
        "technologies et créer des outils adaptés à nos réalités."
    )
    await update.message.reply_text(texte, parse_mode="Markdown")


async def cmd_quota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    restant = core.quota_restant(update.message.from_user.id)
    await update.message.reply_text(
        f"📊 Il te reste {restant} question(s) gratuite(s) aujourd'hui."
    )


async def cmd_abonnement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 *Abonnements DIMOH*\n\n"
        "🆓 *Gratuit* : " + str(core.FREE_QUOTA) + " questions/jour\n"
        "⭐ *PRO* : illimité + priorité - 500 FCFA/mois _(bientôt)_\n"
        "🏢 *BUSINESS* : API + dashboard _(bientôt)_\n\n"
        "Le paiement Mobile Money arrive très vite !",
        parse_mode="Markdown",
    )


async def envoyer_image(update: Update, prompt: str):
    await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
    try:
        image = await asyncio.to_thread(
            core.creer_image, update.message.from_user.id, prompt[:500]
        )
    except Exception as e:
        log.error(f"Erreur image : {e}")
        await update.message.reply_text(
            "⚠ La création d'image n'est pas disponible pour le moment. Réessaie plus tard !"
        )
        return
    await update.message.reply_photo(photo=image, caption=f"🎨 {prompt[:200]}")
    log.info(f"[IMAGE] user={update.message.from_user.id} OK")


async def cmd_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cree une image : /image un champ de mil au coucher du soleil"""
    prompt = " ".join(context.args).strip()
    if not prompt:
        await update.message.reply_text(
            "🎨 Crée une image avec DIMOH\n\n"
            "Écris : /image suivi de ta description\n\n"
            "Exemples :\n"
            "/image un jeune agriculteur africain avec son téléphone\n"
            "/image un marché africain animé"
        )
        return
    if not await verifier_quota(update):
        return
    await envoyer_image(update, prompt)


# ---------- Messages ----------
async def message_texte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verifier_quota(update):
        return
    user_id = update.message.from_user.id
    texte = update.message.text

    if core.demande_image(texte):
        await envoyer_image(update, texte)
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        reponse = await asyncio.to_thread(core.repondre_texte, user_id, texte)
    except core.QuotaGeminiError:
        await update.message.reply_text(core.MSG_OCCUPE)
        return
    except Exception as e:
        log.error(f"Erreur texte : {e}")
        await update.message.reply_text(core.MSG_ERREUR)
        return
    await envoyer_texte(update, reponse)
    log.info(f"[TEXTE] user={user_id} OK")


async def message_vocal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verifier_quota(update):
        return
    user_id = update.message.from_user.id
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        fichier = await update.message.voice.get_file()
        audio = await fichier.download_as_bytearray()
        reponse = await asyncio.to_thread(core.repondre_vocal, user_id, bytes(audio))
    except core.QuotaGeminiError:
        await update.message.reply_text(core.MSG_OCCUPE)
        return
    except Exception as e:
        log.error(f"Erreur vocal : {e}")
        await update.message.reply_text("⚠ Je n'ai pas compris le vocal. Réessaie.")
        return

    await update.message.chat.send_action(ChatAction.RECORD_VOICE)
    voix = await asyncio.to_thread(core.synthese_vocale, reponse)
    if voix:
        try:
            await update.message.reply_voice(voice=voix)
            log.info(f"[VOCAL->VOIX] user={user_id} OK")
            return
        except Exception as e:
            log.warning(f"Envoi de la voix impossible ({e}), reponse en texte")
    await envoyer_texte(update, reponse)
    log.info(f"[VOCAL->TEXTE] user={user_id} OK")


async def message_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verifier_quota(update):
        return
    user_id = update.message.from_user.id
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        fichier = await update.message.photo[-1].get_file()
        image = await fichier.download_as_bytearray()
        legende = update.message.caption or ""
        reponse = await asyncio.to_thread(core.repondre_photo, user_id, bytes(image), legende)
    except core.QuotaGeminiError:
        await update.message.reply_text(core.MSG_OCCUPE)
        return
    except Exception as e:
        log.error(f"Erreur photo : {e}")
        await update.message.reply_text("⚠ Erreur lors de l'analyse de la photo.")
        return
    await envoyer_texte(update, reponse)
    log.info(f"[PHOTO] user={user_id} OK")


# ---------- Lancement ----------
def main():
    core.init_db()
    log.info("Demarrage de DIMOH v5...")
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("about", cmd_about))
    app.add_handler(CommandHandler("a_propos", cmd_about))
    app.add_handler(CommandHandler("quota", cmd_quota))
    app.add_handler(CommandHandler("abonnement", cmd_abonnement))
    app.add_handler(CommandHandler("image", cmd_image))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_texte))
    app.add_handler(MessageHandler(filters.VOICE, message_vocal))
    app.add_handler(MessageHandler(filters.PHOTO, message_photo))
    log.info("DIMOH v5 est en ligne ! Envoie /start a ton bot sur Telegram.")
    app.run_polling()


if __name__ == "__main__":
    main()
