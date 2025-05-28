import smtplib
from email.mime.text import MIMEText

def send_confirmation_email(user_email):
    # Paramètres de ton compte Gmail
    GMAIL_USER = 'mmblaise10@gmail.com'
    GMAIL_APP_PASSWORD = 'qush qrnw ognv cyqd'

    # Création du message
    subject = "Confirmation de paiement - Accès Pro Paper Scanner IA"
    body = f"""
    Bonjour,

    Merci pour votre paiement. Vous avez maintenant accès à la version Pro de Paper Scanner IA.

    Si vous avez la moindre question, répondez à ce mail.

    À bientôt !
    """
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = user_email

    # Connexion et envoi
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_USER, user_email, msg.as_string())
        print(f"Email de confirmation envoyé à {user_email}")
    except Exception as e:
        print(f"Erreur d'envoi d'email: {e}")
