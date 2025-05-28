from fastapi import FastAPI, UploadFile, Form, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
from openai import OpenAI
import uvicorn
import os
import fitz  # PyMuPDF
import requests
import stripe
from fastapi import Request, HTTPException
from send_confirmation_email import send_confirmation_email
from pro_users import add_pro_user
from dotenv import load_dotenv

# 1. Chargement variables d'environnement et configuration
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")  # clé privée Stripe (met ça dans .env)
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")  # à copier du dashboard Stripe Webhook (ou définir en clair pour tester)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 2. Initialise FastAPI
app = FastAPI()

# 3. Endpoints FastAPI (webhook + tous tes autres endpoints)
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Traite le paiement réussi
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_details", {}).get("email", None)
        if customer_email:
            add_pro_user(customer_email)
            send_confirmation_email(customer_email)  # 👈 AJOUTE CETTE LIGNE !
            print(f"✅ Paiement réussi Stripe pour : {customer_email}")
        else:
            print("❌ Impossible de récupérer l'email Stripe.")

    return {"status": "success"}



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def extract_text_from_pdf(file: UploadFile) -> str:
    content = file.file.read()
    with fitz.open(stream=content, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)

def extract_text_from_pubmed_url(url: str) -> str:
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        abstract = soup.find("div", class_="abstract-content")
        if abstract:
            abstract_text = abstract.get_text(strip=True)
        else:
            abstract_text = "[Aucun résumé trouvé]"

        title_tag = soup.find("h1", class_="heading-title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        authors = ", ".join([a.get_text(strip=True) for a in soup.find_all("a", class_="full-name")])

        combined_text = f"Titre: {title}\nRésumé: {abstract_text}\nAuteurs: {authors}"
        return combined_text
    except Exception as e:
        return f"[Erreur de récupération de l'article depuis PubMed] {str(e)}"

def build_prompt(text: str, language="fr", summary_type="medical") -> str:
    style = "professionnel" if summary_type == "medical" else "grand public"
    lang = language.upper()
    return f"""
Tu es un assistant scientifique spécialisé dans les articles biomédicaux.

Résume le texte suivant dans un style {style}, et réponds aux points suivants :
- Résumé synthétique (5 lignes max)
- Molécules mentionnées
- Pathologies ciblées
- Type d'étude (préclinique, clinique, etc.)
- Auteurs principaux

Réponds en langue : {lang}

Texte :
{text[:3000]}
"""

@app.post("/analyze-paper")
async def analyze_paper(
    file: UploadFile = File(...),
    language: str = Form("fr"),
    summary_type: str = Form("medical")
):
    try:
        raw_text = extract_text_from_pdf(file)
        prompt = build_prompt(raw_text, language=language, summary_type=summary_type)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content
        return JSONResponse(content={"result": result})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/analyze-url")
async def analyze_url(
    url: str = Form(...),
    language: str = Form("fr"),
    summary_type: str = Form("medical")
):
    try:
        text = extract_text_from_pubmed_url(url)
        prompt = build_prompt(text, language=language, summary_type=summary_type)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content
        return JSONResponse(content={"result": result})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)