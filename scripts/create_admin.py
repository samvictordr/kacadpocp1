#!/usr/bin/env python3
"""
Script to create an admin user in MongoDB.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import uuid
import bcrypt

# MongoDB URI
MONGO_URI = "mongodb+srv://generic_db_user:testpasswordnotimp@cluster0.lnbsonv.mongodb.net/academy_identity?retryWrites=true&w=majority&appName=Cluster0"

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


async def create_admin(email: str, password: str, name: str):
    print(f"Connecting to MongoDB...")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client.academy_identity
    
    # Check if user already exists
    existing = await db.users.find_one({"email": email})
    if existing:
        print(f"⚠️ User with email {email} already exists!")
        print(f"   User ID: {existing.get('user_id')}")
        print(f"   Role: {existing.get('role')}")
        await client.close()
        return False
    
    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)
    
    user_doc = {
        "_id": user_id,
        "user_id": user_id,
        "email": email,
        "name": name,
        "full_name": name,
        "role": "admin",
        "status": "active",
        "auth": {
            "password_hash": password_hash,
            "password_last_changed": datetime.utcnow()
        },
        "associations": {},
        "metadata": {
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    }
    
    await db.users.insert_one(user_doc)
    print(f"✅ Admin user created successfully!")
    print(f"   Email: {email}")
    print(f"   User ID: {user_id}")
    print(f"   Role: admin")
    
    await client.close()
    return True


if __name__ == "__main__":
    # Create the admin user
    asyncio.run(create_admin(
        email="venu.kas@kaust.edu.sa",
        password="kaustactual141",
        name="Venu KAS"
    ))
