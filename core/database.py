import motor.motor_asyncio
from config import Config

class CipherDB:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(Config.MONGO_URL)
        self.db = self.client["CipherGodDB"] # data base name
        self.settings = self.db["settings"]  # Table lasting

    async def get_key(self, key):
        """read data from database"""
        data = await self.settings.find_one({"_id": key})
        return data["value"] if data else None

    async def set_key(self, key, value):
        """update & write in the database"""
        await self.settings.update_one(
            {"_id": key}, 
            {"$set": {"value": value}}, 
            upsert=True
        )

    async def delete_key(self, key):
        await self.settings.delete_one({"_id": key})

db = CipherDB()
