# app/database.py
# from dotenv import load_dotenv
# load_dotenv()  # IMPORTANT: Force le chargement du .env

import os
import asyncpg
import logging
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # IMPORTANT: Force le chargement du .env

logger = logging.getLogger(__name__)

# Configuration de la base de données
DATABASE_URL = os.getenv("DATABASE_URL")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# Pool de connexions global
_db_pool: Optional[asyncpg.Pool] = None

async def init_db_pool():
    """Initialise le pool de connexions PostgreSQL"""
    global _db_pool
    
    try:
        if DATABASE_URL:
            # Utilisation de DATABASE_URL (format Render/Heroku)
            logger.info("Connexion DB via DATABASE_URL")
            _db_pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
        else:
            # Utilisation des variables séparées
            logger.info(f"Connexion DB via variables séparées: {DB_HOST}:{DB_PORT}")
            _db_pool = await asyncpg.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
        
        # Test de connexion
        async with _db_pool.acquire() as connection:
            version = await connection.fetchval("SELECT version()")
            logger.info(f"✅ Connexion PostgreSQL réussie: {version[:50]}...")
        
        return _db_pool
    
    except Exception as e:
        logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
        raise

async def get_db_pool() -> asyncpg.Pool:
    """Retourne le pool de connexions (l'initialise si nécessaire)"""
    global _db_pool
    
    if _db_pool is None:
        await init_db_pool()
    
    return _db_pool

async def close_db_pool():
    """Ferme le pool de connexions"""
    global _db_pool
    
    if _db_pool:
        await _db_pool.close()
        _db_pool = None
        logger.info("Pool PostgreSQL fermé")

# Fonction utilitaire pour tester la DB
async def test_database_connection() -> bool:
    """Test simple de la connexion database"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as connection:
            result = await connection.fetchval("SELECT 1")
            return result == 1
    except Exception as e:
        logger.error(f"Test DB échoué: {e}")
        return False

# Fonction pour créer les tables de base (si nécessaire)
async def create_base_tables():
    """Crée les tables de base si elles n'existent pas"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as connection:
            # Table users (si vous en avez besoin)
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(150) UNIQUE NOT NULL,
                    is_pro BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Index sur email pour performance
            await connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            """)
            
            logger.info("✅ Tables de base créées/vérifiées")
    
    except Exception as e:
        logger.error(f"❌ Erreur création tables de base: {e}")
        raise