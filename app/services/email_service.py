# Remplacez le contenu de app/services/email_service.py par :

# IMPORTANT: Forcer le chargement .env
from dotenv import load_dotenv
load_dotenv()

import os
import logging
from typing import Optional
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.models.contact import ContactForm

# Configuration
FROM_EMAIL = os.getenv("FROM_EMAIL", "mmblaise10@gmail.com")
FROM_NAME = os.getenv("FROM_NAME", "Paper Scanner IA")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "mmblaise10@gmail.com")

# Configuration Gmail - FORCE la variable temporairement
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
if not GMAIL_PASSWORD:
    GMAIL_PASSWORD = "hjhy rjpb gsbe bcaz"  # Force temporaire pour test

# Debug
print(f"🔍 GMAIL_PASSWORD configuré: {bool(GMAIL_PASSWORD)}")
print(f"🔍 GMAIL_PASSWORD longueur: {len(GMAIL_PASSWORD)}")
print(f"🔍 GMAIL_PASSWORD value: {repr(GMAIL_PASSWORD[:10])}...")  # Premiers caractères

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        if GMAIL_PASSWORD:
            logger.info("Service email configuré avec Gmail SMTP")
        else:
            logger.warning("Service email en mode simulation - configurez GMAIL_APP_PASSWORD")
    
    async def send_contact_notification(self, contact: ContactForm, contact_id: int) -> bool:
        """Envoie une notification à l'admin"""
        try:
            subject = f"📧 Nouveau contact Paper Scanner IA #{contact_id}"
            
            body = f"""
Nouveau message de contact reçu !

👤 Nom: {contact.nom}
📧 Email: {contact.email}
📋 Sujet: {contact.sujet}
🕐 Date: {datetime.now().strftime('%d/%m/%Y à %H:%M')}

💬 Message:
{contact.message}

---
Répondre directement à: {contact.email}
Référence: #{contact_id}
Paper Scanner IA - Système de contact automatisé
            """
            
            success = self._send_email(ADMIN_EMAIL, subject, body)
            if success:
                logger.info(f"Email notification envoyé à l'admin pour contact #{contact_id}")
            return success
            
        except Exception as e:
            logger.error(f"Erreur envoi notification: {e}")
            return False
    
    async def send_confirmation_email(self, contact: ContactForm, contact_id: int) -> bool:
        """Envoie un accusé de réception au client"""
        try:
            subject = f"✅ Votre message a bien été reçu - Paper Scanner IA #{contact_id}"
            
            body = f"""
Bonjour {contact.nom},

Merci pour votre message concernant "{contact.sujet}".

Nous avons bien reçu votre demande et nous vous répondrons dans les plus brefs délais (généralement sous 24-48h).

📝 Votre message:
"{contact.message[:200]}{'...' if len(contact.message) > 200 else ''}"

Si votre demande est urgente, vous pouvez nous contacter directement à: {ADMIN_EMAIL}

Cordialement,
L'équipe Paper Scanner IA

---
Référence: #{contact_id}
Date: {datetime.now().strftime('%d/%m/%Y à %H:%M')}

🧬 Paper Scanner IA - Analyse intelligente d'articles biomédicaux
            """
            
            success = self._send_email(contact.email, subject, body)
            if success:
                logger.info(f"Email confirmation envoyé à {contact.email}")
            return success
            
        except Exception as e:
            logger.error(f"Erreur envoi confirmation: {e}")
            return False
    
    def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Méthode interne pour envoyer un email via Gmail SMTP"""
        if not GMAIL_PASSWORD:
            logger.info(f"Mode simulation - Email non envoyé à {to_email}")
            return True
        
        try:
            # Création du message
            msg = MIMEMultipart()
            msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Corps du message
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Connexion SMTP Gmail
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(FROM_EMAIL, GMAIL_PASSWORD)
            
            # Envoi
            text = msg.as_string()
            server.sendmail(FROM_EMAIL, to_email, text)
            server.quit()
            
            logger.info(f"Email envoyé avec succès à {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur envoi email SMTP: {e}")
            return False

# Instance globale
email_service = EmailService()

# Fonction de test
async def test_email_configuration():
    """Test la configuration email"""
    try:
        test_contact = ContactForm(
            nom="Test User",
            email="mmblaise10@gmail.com",
            sujet="Question générale",
            message="Ceci est un test de configuration email."
        )
        
        result = await email_service.send_confirmation_email(test_contact, 9999)
        return result
    except Exception as e:
        logger.error(f"Erreur test email: {e}")
        return False