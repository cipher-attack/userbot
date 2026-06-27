import sys
import glob
import importlib
import logging
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from config import Config

# Logger setup
logging.basicConfig(format='[%(levelname)s] %(asctime)s - %(message)s', level=logging.INFO)
logger = logging.getLogger("CipherKernel")
if Config.SESSION:
    session = StringSession(Config.SESSION)
else:
    session = "cipher_bot_session"

client = TelegramClient(session, Config.API_ID, Config.API_HASH)
async def load_plugins():
    path = "plugins/*.py"
    files = glob.glob(path)

    logger.info(f"🧩 {len(files)} Plugin Files Detected. Starting DEBUG Scan...")

    for file in files:
        module_name = file.replace(".py", "").replace("\\", ".").replace("/", ".")

        try:
            # Import module
            module = importlib.import_module(module_name)

            # Debug output
            logger.info(f"🔎 Scanning Module: {module_name}")
            found_funcs = []

            # Inspect module members
            for name, obj in vars(module).items():
                # Skip private attributes
                if name.startswith("__"): continue
                if hasattr(obj, 'event'):
                    client.add_event_handler(obj, obj.event)
                    found_funcs.append(name)
                    logger.info(f"   ✅ Attached Command: {name}")
                elif "engine" in name or "god" in name: 
                    # Warn on missing event tag
                    logger.warning(f"   ⚠️ Found function '{name}' but it has NO 'event' tag!")

            if found_funcs:
                logger.info(f"🚀 Loaded {module_name} with: {found_funcs}")
            else:
                logger.error(f"❌ {module_name} is EMPTY or INVALID. Contents: {dir(module)}")

        except Exception as e:
            logger.error(f"❌ Crash loading {module_name}: {e}")
async def main():
    logger.info("CIPHER: good mode [DEBUG SYSTEM BOOT]")
    await client.start()
    await load_plugins()

    me = await client.get_me()
    logger.info(f"🌌 {me.first_name} IS ONLINE! Waiting for orders.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    client.loop.run_until_complete(main())