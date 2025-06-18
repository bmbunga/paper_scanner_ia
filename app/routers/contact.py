# app/routers/contact.py - VERSION CORRIGÉE
from fastapi import APIRouter, HTTPException, Request, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
import logging
from typing import Optional, List
from datetime import datetime
import os
import asyncpg

from app.models.contact import ContactForm, ContactResponse, ContactMessage, ContactStatus
from app.services.contact_service import ContactService, is_potential_spam
from app.services.email_service import email_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["contact"])

# CORRECTION 1: Utilisation directe de DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")

# Pool de connexions global
_db_pool = None

async def get_db_pool():
    """Crée et retourne le pool de connexions"""
    global _db_pool
    if _db_pool is None:
        if not DATABASE_URL:
            raise Exception("DATABASE_URL non configurée")
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _db_pool

# Dependency pour le service contact
async def get_contact_service():
    """Retourne le service contact avec le pool DB"""
    db_pool = await get_db_pool()
    return ContactService(db_pool)

@router.post("/contact", response_model=ContactResponse)
async def submit_contact_form(
    contact: ContactForm,
    request: Request,
    background_tasks: BackgroundTasks,
    contact_service: ContactService = Depends(get_contact_service)
):
    """
    Endpoint principal pour soumettre un formulaire de contact
    """
    try:
        # Récupération des métadonnées de la requête
        client_ip = str(request.client.host) if request.client else "unknown"  # CORRECTION 2: Force string
        user_agent = request.headers.get("user-agent", "Unknown")
        
        logger.info(f"Nouveau contact de {contact.email} - IP: {client_ip}")
        
        # Vérification anti-spam
        if contact.honeypot:
            logger.warning(f"Honeypot détecté pour {contact.email}")
            raise HTTPException(
                status_code=400, 
                detail="Requête non autorisée"
            )
        
        # Vérification spam avancée
        if await is_potential_spam(contact, contact_service):
            logger.warning(f"Spam potentiel détecté: {contact.email}")
            # Pas d'erreur pour ne pas aider les spammeurs
            return ContactResponse(
                status="success",
                message="Message reçu et en cours de traitement"
            )
        
        # Sauvegarde en base de données
        contact_id = await contact_service.save_contact_message(
            contact=contact,
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        # Envoi des emails en arrière-plan pour ne pas bloquer la réponse
        background_tasks.add_task(
            send_contact_emails, 
            contact, 
            contact_id
        )
        
        return ContactResponse(
            status="success",
            message="Votre message a été envoyé avec succès ! Nous vous répondrons sous 24-48h.",
            contact_id=contact_id,
            estimated_response_time="24-48h"
        )
        
    except ValueError as ve:
        # Erreurs de validation ou anti-spam
        logger.warning(f"Erreur validation contact: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    
    except Exception as e:
        logger.error(f"Erreur inattendue submit_contact_form: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erreur interne. Veuillez réessayer ou nous contacter directement."
        )

async def send_contact_emails(contact: ContactForm, contact_id: int):
    """Fonction background pour envoyer les emails"""
    try:
        # Email de notification à l'admin
        notification_sent = await email_service.send_contact_notification(contact, contact_id)
        
        # Email de confirmation au client
        confirmation_sent = await email_service.send_confirmation_email(contact, contact_id)
        
        if notification_sent and confirmation_sent:
            logger.info(f"Emails envoyés avec succès pour contact #{contact_id}")
        else:
            logger.warning(f"Problème envoi emails pour contact #{contact_id}")
    
    except Exception as e:
        logger.error(f"Erreur envoi emails background: {e}")

@router.get("/contact/analytics")
async def get_contact_analytics(
    days: int = 30,
    contact_service: ContactService = Depends(get_contact_service)
):
    """
    Récupère les analytics des contacts (admin uniquement en production)
    """
    try:
        analytics_data = await contact_service.get_contact_analytics(days)
        return {
            "status": "success",
            "data": analytics_data
        }
    
    except Exception as e:
        logger.error(f"Erreur récupération analytics: {e}")
        raise HTTPException(status_code=500, detail="Erreur récupération analytics")

@router.get("/contact/recent")
async def get_recent_contacts(
    limit: int = 20,
    contact_service: ContactService = Depends(get_contact_service)
):
    """
    Récupère les contacts récents (admin uniquement en production)
    """
    try:
        contacts = await contact_service.get_recent_contacts(limit)
        return {
            "status": "success",
            "contacts": [contact.dict() for contact in contacts],
            "count": len(contacts)
        }
    
    except Exception as e:
        logger.error(f"Erreur récupération contacts récents: {e}")
        raise HTTPException(status_code=500, detail="Erreur récupération contacts")

@router.put("/contact/{contact_id}/status")
async def update_contact_status(
    contact_id: int,
    new_status: ContactStatus,
    mark_response_sent: bool = False,
    contact_service: ContactService = Depends(get_contact_service)
):
    """
    Met à jour le statut d'un contact (admin uniquement)
    """
    try:
        updated = await contact_service.update_contact_status(
            contact_id=contact_id,
            new_status=new_status,
            mark_response_sent=mark_response_sent
        )
        
        if updated:
            return {
                "status": "success",
                "message": f"Contact #{contact_id} mis à jour: {new_status.value}"
            }
        else:
            raise HTTPException(status_code=404, detail="Contact non trouvé")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur mise à jour statut contact: {e}")
        raise HTTPException(status_code=500, detail="Erreur mise à jour")

@router.get("/contact/search")
async def search_contacts(
    email: Optional[str] = None,
    sujet: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    contact_service: ContactService = Depends(get_contact_service)
):
    """
    Recherche de contacts avec filtres (admin uniquement)
    """
    try:
        contacts = await contact_service.search_contacts(
            email=email,
            sujet=sujet,
            status=status,
            limit=limit
        )
        
        return {
            "status": "success",
            "contacts": [contact.dict() for contact in contacts],
            "count": len(contacts),
            "filters": {
                "email": email,
                "sujet": sujet,
                "status": status,
                "limit": limit
            }
        }
    
    except Exception as e:
        logger.error(f"Erreur recherche contacts: {e}")
        raise HTTPException(status_code=500, detail="Erreur recherche")

@router.get("/contact/test-email")
async def test_email_service():
    """
    Test de la configuration email (développement uniquement)
    """
    try:
        from app.services.email_service import test_email_configuration
        
        result = await test_email_configuration()
        
        return {
            "status": "success" if result else "error",
            "message": "Configuration email testée",
            "email_configured": result
        }
    
    except Exception as e:
        logger.error(f"Erreur test email: {e}")
        return {
            "status": "error",
            "message": f"Erreur test: {str(e)}",
            "email_configured": False
        }

@router.get("/contact/health")
async def contact_health_check(
    contact_service: ContactService = Depends(get_contact_service)
):
    """
    Vérification de la santé du système de contact
    """
    try:
        # Test de connexion à la base
        recent_count = len(await contact_service.get_recent_contacts(1))
        
        # CORRECTION 3: Vérification email corrigée
        from app.services.email_service import GMAIL_PASSWORD
        email_configured = bool(GMAIL_PASSWORD)
        
        return {
            "status": "healthy",
            "message": "Système de contact opérationnel",
            "database_connected": True,
            "email_service": email_configured,
            "email_type": "Gmail SMTP",
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Erreur health check contact: {e}")
        return {
            "status": "unhealthy", 
            "message": f"Problème détecté: {str(e)}",
            "database_connected": False,
            "email_service": False,
            "timestamp": datetime.now().isoformat()
        }