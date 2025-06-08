import os
from dotenv import load_dotenv

load_dotenv()

ADSTERRA_API_KEY = os.getenv("ADSTERRA_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# User credentials (in production, use proper database)
USER_DB = {
    "tonxmedia": "Sukses2026"
}

# Domain list (can be fetched from API, but hardcoded for reliability)
DOMAINS = {
    1597430: "DIRECTLINK (1597430)",
    4638075: "asupankitasemua.xyz (4638075)"
}