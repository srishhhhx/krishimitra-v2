from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["krishi_mitra"]
users_collection = db["users"]

# Create unique index on email
try:
    users_collection.create_index("email", unique=True)
    print("✅ Email index created successfully!")
except Exception as e:
    print("⚠️ Email index creation failed (might already exist):", e)

# Test connection
try:
    client.server_info()
    print("✅ MongoDB connected successfully!")
except Exception as e:
    print("❌ MongoDB connection failed:", e)

