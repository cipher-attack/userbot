import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 1. CORE VARS
    API_ID = int(os.getenv("API_ID") or 0)
    API_HASH = os.getenv("API_HASH")
    SESSION = os.getenv("SESSION")
    MONGO_URL = os.getenv("MONGO_URL")

    # 2. SMART KEY LOADER
    GEMINI_KEYS = []
    raw_secret = os.getenv("GEMINI_KEYS")
    
    if raw_secret:
        clean_secret = raw_secret.replace("[", "").replace("]", "").replace('"', "").replace("'", "")
        
        if "," in clean_secret:
            items = clean_secret.split(",")
        else:
            items = clean_secret.split()
            
        for k in items:
            clean_k = k.strip()
            if len(clean_k) > 10:
                GEMINI_KEYS.append(clean_k)
    for i in range(1, 11):
        k = os.getenv(f"GEMINI_KEY{i}")
        if k and len(k) > 10 and k not in GEMINI_KEYS:
            GEMINI_KEYS.append(k)
    fallback = os.getenv("GEMINI_API_KEY")
    if fallback and len(fallback) > 10 and fallback not in GEMINI_KEYS:
        GEMINI_KEYS.append(fallback)
    print(f"\n🔍 DEBUG CONFIG:")
    print(f"   API_ID: {API_ID}")
    print(f"   SESSION Found: {bool(SESSION)}")
    if raw_secret:
        print(f"   Raw Secret Length: {len(raw_secret)} chars")
        print(f"   Raw Secret Preview: {raw_secret[:5]}...{raw_secret[-5:]}")
    else:
        print("   Raw Secret 'GEMINI_KEYS': NOT FOUND or EMPTY")

    print(f"   ✅ Parsed Valid Keys: {len(GEMINI_KEYS)}")
    print("----------------------------------------\n")

    @classmethod
    def check_integrity(cls):
        if not cls.API_ID or not cls.API_HASH or not cls.SESSION:
            print("❌ CRITICAL: Telegram Credentials Missing!")
            return False
        if not cls.GEMINI_KEYS:
            print("⚠️ WARNING: AI Module will fail (No Keys Parsed).")
        return True

# Run at startup
Config.check_integrity()