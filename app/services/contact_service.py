# app/services/contact_service.py
import logging
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from app.models.contact import ContactForm, ContactMessage, ContactStatus

logger = logging.getLogger(__name__)

class ContactService:
    def __init__(self, db_pool):
        self.db_pool = db_pool
    
    async def create_contact_tables(self):
        """Crée les tables contact si elles n'existent pas"""
        try:
            async with self.db_pool.acquire() as connection:
                # Table principale des messages de contact
                await connection.execute("""
                    CREATE TABLE IF NOT EXISTS contact_messages (
                        id SERIAL PRIMARY KEY,
                        nom VARCHAR(100) NOT NULL,
                        email VARCHAR(150) NOT NULL,
                        sujet VARCHAR(200) NOT NULL,
                        message TEXT NOT NULL,
                        status VARCHAR(20) DEFAULT 'nouveau',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_at TIMESTAMP NULL,
                        ip_address INET NULL,
                        user_agent TEXT NULL,
                        response_sent BOOLEAN DEFAULT FALSE
                    );
                """)
                
                # Index pour performance
                await connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_contact_email ON contact_messages(email);
                """)
                await connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_contact_status ON contact_messages(status);
                """)
                await connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_contact_created ON contact_messages(created_at DESC);
                """)
                
                # Table analytics pour reporting
                await connection.execute("""
                    CREATE TABLE IF NOT EXISTS contact_analytics (
                        id SERIAL PRIMARY KEY,
                        date_contact DATE NOT NULL,
                        sujet VARCHAR(200) NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        response_time_hours INTEGER NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Index unique pour éviter les doublons analytics
                await connection.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_analytics_unique 
                    ON contact_analytics(date_contact, sujet, status);
                """)
                
                logger.info("Tables contact créées/vérifiées avec succès")
        
        except Exception as e:
            logger.error(f"Erreur création tables contact: {e}")
            raise
    
    async def save_contact_message(
        self, 
        contact: ContactForm, 
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> int:
        """Sauvegarde un message de contact et retourne l'ID"""
        try:
            async with self.db_pool.acquire() as connection:
                # Vérification anti-spam simple (même email dans les 5 dernières minutes)
                recent_spam_check = await connection.fetchval("""
                    SELECT COUNT(*) FROM contact_messages 
                    WHERE email = $1 AND created_at > NOW() - INTERVAL '5 minutes'
                """, contact.email)
                
                if recent_spam_check >= 3:
                    logger.warning(f"Tentative spam détectée pour {contact.email}")
                    raise ValueError("Trop de messages récents. Veuillez patienter.")
                
                # Insertion du message
                contact_id = await connection.fetchval("""
                    INSERT INTO contact_messages (
                        nom, email, sujet, message, ip_address, user_agent
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                """, 
                contact.nom, contact.email, contact.sujet.value, 
                contact.message, ip_address, user_agent)
                
                # Mise à jour analytics
                await self._update_analytics(connection, contact.sujet.value, "nouveau")
                
                logger.info(f"Contact sauvegardé avec ID: {contact_id}")
                return contact_id
        
        except Exception as e:
            logger.error(f"Erreur sauvegarde contact: {e}")
            raise
    
    async def get_contact_by_id(self, contact_id: int) -> Optional[ContactMessage]:
        """Récupère un message de contact par ID"""
        try:
            async with self.db_pool.acquire() as connection:
                row = await connection.fetchrow("""
                    SELECT * FROM contact_messages WHERE id = $1
                """, contact_id)
                
                if row:
                    return ContactMessage(**dict(row))
                return None
        
        except Exception as e:
            logger.error(f"Erreur récupération contact {contact_id}: {e}")
            return None
    
    async def get_recent_contacts(self, limit: int = 50) -> List[ContactMessage]:
        """Récupère les messages récents"""
        try:
            async with self.db_pool.acquire() as connection:
                rows = await connection.fetch("""
            SELECT * FROM contact_messages 
                ORDER BY created_at DESC 
                LIMIT $1
            """, limit)
            
            # CORRECTION: Convertir IPv4Address en string avant création du modèle
            contacts = []
            for row in rows:
                row_dict = dict(row)
                
                # Convertir IP en string si nécessaire
                if row_dict.get('ip_address') and not isinstance(row_dict['ip_address'], str):
                    row_dict['ip_address'] = str(row_dict['ip_address'])
                
                contacts.append(ContactMessage(**row_dict))
            
            return contacts
    
        except Exception as e:
            logger.error(f"Erreur récupération contacts récents: {e}")
            return []
    
    async def update_contact_status(
        self, 
        contact_id: int, 
        new_status: ContactStatus,
        mark_response_sent: bool = False
    ) -> bool:
        """Met à jour le statut d'un contact"""
        try:
            async with self.db_pool.acquire() as connection:
                # Mise à jour du statut
                query = """
                    UPDATE contact_messages 
                    SET status = $1, processed_at = $2
                """
                params = [new_status.value, datetime.now()]
                
                if mark_response_sent:
                    query += ", response_sent = $3"
                    params.append(True)
                
                query += " WHERE id = $" + str(len(params) + 1)
                params.append(contact_id)
                
                result = await connection.execute(query, *params)
                
                if result == "UPDATE 1":
                    logger.info(f"Contact {contact_id} mis à jour: {new_status.value}")
                    return True
                else:
                    logger.warning(f"Contact {contact_id} non trouvé pour mise à jour")
                    return False
        
        except Exception as e:
            logger.error(f"Erreur mise à jour contact {contact_id}: {e}")
            return False
    
    async def get_contact_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Récupère les analytics des contacts"""
        try:
            async with self.db_pool.acquire() as connection:
                # Stats générales
                total_contacts = await connection.fetchval("""
                    SELECT COUNT(*) FROM contact_messages 
                    WHERE created_at >= NOW() - INTERVAL '%s days'
                """ % days)
                
                # Répartition par sujet
                subject_stats = await connection.fetch("""
                    SELECT sujet, COUNT(*) as count
                    FROM contact_messages 
                    WHERE created_at >= NOW() - INTERVAL '%s days'
                    GROUP BY sujet 
                    ORDER BY count DESC
                """ % days)
                
                # Répartition par statut
                status_stats = await connection.fetch("""
                    SELECT status, COUNT(*) as count
                    FROM contact_messages 
                    WHERE created_at >= NOW() - INTERVAL '%s days'
                    GROUP BY status
                """ % days)
                
                # Évolution quotidienne (7 derniers jours)
                daily_evolution = await connection.fetch("""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM contact_messages 
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                """)
                
                return {
                    "total_contacts": total_contacts,
                    "by_subject": [{"sujet": row["sujet"], "count": row["count"]} for row in subject_stats],
                    "by_status": [{"status": row["status"], "count": row["count"]} for row in status_stats],
                    "daily_evolution": [{"date": row["date"].isoformat(), "count": row["count"]} for row in daily_evolution],
                    "period_days": days
                }
        
        except Exception as e:
            logger.error(f"Erreur récupération analytics: {e}")
            return {
                "total_contacts": 0,
                "by_subject": [],
                "by_status": [],
                "daily_evolution": [],
                "period_days": days
            }
    
    async def _update_analytics(self, connection, sujet: str, status: str):
        """Met à jour les analytics (fonction interne)"""
        try:
            today = date.today()
            await connection.execute("""
                INSERT INTO contact_analytics (date_contact, sujet, status)
                VALUES ($1, $2, $3)
                ON CONFLICT (date_contact, sujet, status) 
                DO NOTHING
            """, today, sujet, status)
        
        except Exception as e:
            logger.error(f"Erreur mise à jour analytics: {e}")
    
    async def search_contacts(
        self, 
        email: Optional[str] = None,
        sujet: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[ContactMessage]:
        """Recherche des contacts avec filtres"""
        try:
            async with self.db_pool.acquire() as connection:
                query = "SELECT * FROM contact_messages WHERE 1=1"
                params = []
                param_count = 0
                
                if email:
                    param_count += 1
                    query += f" AND email ILIKE ${param_count}"
                    params.append(f"%{email}%")
                
                if sujet:
                    param_count += 1
                    query += f" AND sujet ILIKE ${param_count}"
                    params.append(f"%{sujet}%")
                
                if status:
                    param_count += 1
                    query += f" AND status = ${param_count}"
                    params.append(status)
                
                query += f" ORDER BY created_at DESC LIMIT ${param_count + 1}"
                params.append(limit)
                
                rows = await connection.fetch(query, *params)
                return [ContactMessage(**dict(row)) for row in rows]
        
        except Exception as e:
            logger.error(f"Erreur recherche contacts: {e}")
            return []

# Utilitaires pour l'anti-spam
async def is_potential_spam(contact: ContactForm, contact_service: ContactService) -> bool:
    """Détecte les potentiels spams - DÉSACTIVÉ TEMPORAIREMENT"""
    # Vérifications basiques
    spam_indicators = [
        len(contact.honeypot) > 0,  # Honeypot rempli
        # "http://" in contact.message.lower() or "https://" in contact.message.lower(),  # URLs suspectes - DÉSACTIVÉ
        # len(contact.message.split()) < 3,  # Message trop court - DÉSACTIVÉ
        contact.nom.lower() in ["admin", "test", "robot", "bot"],  # Noms suspects
    ]
    
    return any(spam_indicators)