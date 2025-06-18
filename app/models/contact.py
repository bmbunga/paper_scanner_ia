# app/models/contact.py
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime
from enum import Enum

class ContactStatus(str, Enum):
    NOUVEAU = "nouveau"
    EN_COURS = "en_cours"
    RESOLU = "resolu"
    SPAM = "spam"

class ContactSubject(str, Enum):
    QUESTION_GENERALE = "Question générale"
    PROBLEME_TECHNIQUE = "Problème technique"
    SUGGESTION = "Suggestion d'amélioration"
    BUG = "Signaler un bug"
    DEMANDE_PRO = "Demande Pro"
    AUTRE = "Autre"

class ContactForm(BaseModel):
    nom: str
    email: EmailStr
    sujet: ContactSubject
    message: str
    honeypot: Optional[str] = ""  # Protection anti-spam
    
    @validator('nom')
    def validate_nom(cls, v):
        if len(v.strip()) < 2:
            raise ValueError('Le nom doit contenir au moins 2 caractères')
        if len(v) > 100:
            raise ValueError('Le nom ne peut pas dépasser 100 caractères')
        return v.strip()
    
    @validator('message')
    def validate_message(cls, v):
        if len(v.strip()) < 10:
            raise ValueError('Le message doit contenir au moins 10 caractères')
        if len(v) > 2000:
            raise ValueError('Le message ne peut pas dépasser 2000 caractères')
        return v.strip()

class ContactResponse(BaseModel):
    status: str
    message: str
    contact_id: Optional[int] = None
    estimated_response_time: str = "24-48h"

class ContactMessage(BaseModel):
    id: int
    nom: str
    email: str
    sujet: str
    message: str
    status: ContactStatus
    created_at: datetime
    processed_at: Optional[datetime]
    ip_address: Optional[str]  # Changé pour accepter string IP
    user_agent: Optional[str]
    response_sent: bool = False
    
    class Config:
        from_attributes = True
        # Convertit automatiquement les types IP en string
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }