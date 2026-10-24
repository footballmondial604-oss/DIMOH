# DIMOH - dossier complet
- dimoh_core.py : le cerveau (prompt, Gemini, quotas, voix, images)
- dimoh_bot.py  : porte TELEGRAM   -> python dimoh_bot.py
- api.py + web/ : porte WEB (site + appli installable) -> python -m uvicorn api:app --port 8000
Cles : copie .env.example en .env et remplis-le (ne jamais partager .env).
