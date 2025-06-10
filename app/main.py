import os
from fastapi import FastAPI, UploadFile, Form, File, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
from openai import OpenAI
from anthropic import Anthropic
import uvicorn
import fitz  # PyMuPDF
import requests
import stripe
from app.send_confirmation_email import send_confirmation_email
from app.pro_users import add_pro_user
from dotenv import load_dotenv
from typing import List
import asyncio

# 1. Chargement variables d'environnement et configuration
load_dotenv()

# Configuration des API clients
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Initialisation des clients IA
openai_client = None
anthropic_client = None

# Initialisation conditionnelle des clients
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    
if ANTHROPIC_API_KEY:
    try:
        anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    except Exception as e:
        print(f"⚠️ Erreur initialisation client Anthropic: {e}")
        anthropic_client = None

# 2. Initialise FastAPI
app = FastAPI()

# 3. Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Webhook Stripe
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """Gestion du webhook Stripe pour les paiements réussis"""
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
            send_confirmation_email(customer_email)
            print(f"✅ Paiement réussi Stripe pour : {customer_email}")
        else:
            print("❌ Impossible de récupérer l'email Stripe.")

    return {"status": "success"}

# 5. Fonctions utilitaires
def extract_text_from_pdf(file: UploadFile) -> str:
    """Extraction du texte d'un PDF avec PyMuPDF"""
    content = file.file.read()
    with fitz.open(stream=content, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)

def extract_text_from_multiple_pdfs(files: List[UploadFile]) -> List[dict]:
    """Extraction du texte de plusieurs PDFs pour l'analyse batch"""
    results = []
    for i, file in enumerate(files):
        try:
            content = file.file.read()
            with fitz.open(stream=content, filetype="pdf") as doc:
                text = "\n".join(page.get_text() for page in doc)
            
            results.append({
                "index": i,
                "filename": file.filename,
                "text": text,
                "success": True,
                "error": None
            })
            # Reset file position pour usage ultérieur si nécessaire
            file.file.seek(0)
        except Exception as e:
            results.append({
                "index": i,
                "filename": file.filename,
                "text": "",
                "success": False,
                "error": str(e)
            })
    return results

def extract_text_from_pubmed_url(url: str) -> str:
    """Extraction du contenu d'un article PubMed à partir de son URL"""
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        # Extraction du résumé
        abstract = soup.find("div", class_="abstract-content")
        if abstract:
            abstract_text = abstract.get_text(strip=True)
        else:
            abstract_text = "[Aucun résumé trouvé]"

        # Extraction du titre
        title_tag = soup.find("h1", class_="heading-title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Extraction des auteurs
        authors = ", ".join([a.get_text(strip=True) for a in soup.find_all("a", class_="full-name")])

        combined_text = f"Titre: {title}\nRésumé: {abstract_text}\nAuteurs: {authors}"
        return combined_text
    except Exception as e:
        return f"[Erreur de récupération de l'article depuis PubMed] {str(e)}"

def build_prompt_optimized(text: str, language="fr", summary_mode="synthetique") -> str:
    """Construction du prompt optimisé selon le mode de résumé choisi"""
    lang = language.upper()
    
    if summary_mode == "detaille":
        summary_instruction = (
            f"Rédige un résumé EXHAUSTIF et structuré de l'article ci-dessous, en {language}, en détaillant :\n"
            "- Le contexte scientifique ou médical\n"
            "- Les objectifs précis de l'étude\n"
            "- La méthodologie (population, interventions, analyses…)\n"
            "- Les principaux résultats, données chiffrées et tendances\n"
            "- Les conclusions et implications pratiques\n"
            "- Limites et perspectives éventuelles\n\n"
            "Le résumé doit faire 15 à 25 lignes, utiliser un style académique, être fidèle à l'article et complet."
        )
    else:
        summary_instruction = (
            f"Résume l'article ci-dessous en {language}, dans un style professionnel et très synthétique : "
            "5 à 8 lignes maximum, en insistant sur l'essentiel (but, méthode, résultat principal, conclusion)."
        )
    
    return f"""Tu es un assistant scientifique spécialisé dans les articles biomédicaux.

{summary_instruction}

À la fin du résumé, extrais et liste séparément les informations suivantes :
- Molécules mentionnées
- Pathologies ciblées
- Type d'étude (préclinique, clinique, revue systématique, etc.)
- Auteurs principaux

Réponds en langue : {lang}

ARTICLE :
{text[:3000]}
"""

def build_batch_prompt(articles_data: List[dict], language="fr", analysis_type="synthesis") -> str:
    """Construction du prompt pour l'analyse batch"""
    lang = language.upper()
    
    # Préparation du contenu des articles
    articles_content = ""
    for i, article in enumerate(articles_data, 1):
        if article["success"]:
            articles_content += f"\n\n=== ARTICLE {i}: {article['filename']} ===\n"
            articles_content += article["text"][:2000]  # Limite par article
        else:
            articles_content += f"\n\n=== ARTICLE {i}: {article['filename']} (ERREUR) ===\n"
            articles_content += f"Erreur de lecture: {article['error']}\n"
    
    if analysis_type == "synthesis":
        instruction = f"""Tu es un expert en recherche biomédicale. Analyse ces {len(articles_data)} articles scientifiques et produis une SYNTHÈSE COMPARATIVE complète en {language}.

STRUCTURE DEMANDÉE :

1. **RÉSUMÉ EXÉCUTIF** (3-4 lignes)
   - Vue d'ensemble des sujets traités
   - Tendances principales identifiées

2. **ANALYSE COMPARATIVE**
   - Points communs entre les études
   - Différences méthodologiques importantes
   - Convergences et divergences des résultats

3. **SYNTHÈSE DES RÉSULTATS CLÉS**
   - Résultats les plus significatifs
   - Données chiffrées importantes
   - Implications cliniques

4. **MOLÉCULES ET PATHOLOGIES**
   - Molécules mentionnées (consolidées)
   - Pathologies ciblées (consolidées)
   - Mécanismes d'action identifiés

5. **PERSPECTIVES ET RECOMMANDATIONS**
   - Lacunes identifiées dans la recherche
   - Directions futures prometteuses
   - Recommandations pour la pratique clinique

Réponds en langue : {lang}
Sois rigoureux, objectif et scientifique."""

    else:  # meta_analysis
        instruction = f"""Tu es un expert en méta-analyse biomédicale. Analyse ces {len(articles_data)} articles et produis une MÉTA-ANALYSE STRUCTURÉE en {language}.

STRUCTURE DEMANDÉE :

1. **OBJECTIF DE LA MÉTA-ANALYSE**
   - Question de recherche principale
   - Critères d'inclusion des études

2. **CARACTÉRISTIQUES DES ÉTUDES**
   - Types d'études incluses
   - Populations étudiées
   - Méthodologies utilisées
   - Qualité méthodologique

3. **RÉSULTATS POOLÉS**
   - Synthèse quantitative des résultats
   - Mesures d'effet principales
   - Hétérogénéité entre études

4. **ANALYSE DE SOUS-GROUPES**
   - Variations selon populations
   - Différences méthodologiques
   - Facteurs de confusion identifiés

5. **CONCLUSIONS ET NIVEAU DE PREUVE**
   - Strength of evidence
   - Limites de l'analyse
   - Implications pour la pratique

Réponds en langue : {lang}
Sois méthodique et critique."""

    return f"""{instruction}

ARTICLES À ANALYSER :
{articles_content[:15000]}  # Limite globale pour éviter les tokens excessifs
"""

def get_ai_response(prompt: str, model_name: str) -> str:
    """Génération de la réponse IA selon le modèle choisi"""
    try:
        if model_name.lower() == "claude":
            if not anthropic_client:
                raise Exception("Client Anthropic non disponible. Vérifiez votre clé API.")
            
            # Utilisation du modèle Claude 3.5 Sonnet (le plus récent et disponible)
            response = anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        else:  # GPT-4 par défaut
            if not openai_client:
                raise Exception("Client OpenAI non disponible. Vérifiez votre clé API.")
                
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000
            )
            return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"Erreur lors de la génération de la réponse IA: {str(e)}")

async def process_batch_analysis(articles_data: List[dict], language: str, analysis_type: str, model_name: str) -> str:
    """Traitement asynchrone de l'analyse batch"""
    try:
        prompt = build_batch_prompt(articles_data, language, analysis_type)
        
        # Utilisation du même système que pour les analyses simples
        result = get_ai_response(prompt, model_name)
        return result
    except Exception as e:
        raise Exception(f"Erreur lors de l'analyse batch: {str(e)}")

# 6. Endpoints principaux
@app.post("/analyze-paper")
async def analyze_paper(
    file: UploadFile = File(...),
    language: str = Form("fr"),
    summary_type: str = Form("synthetique"),
    model_name: str = Form("gpt4")
):
    """Analyse d'un PDF téléchargé"""
    try:
        # Validation du fichier (commentée car elle pose problème avec Streamlit)
        # if not file.filename.lower().endswith('.pdf'):
        #     return JSONResponse(
        #         content={"error": "Le fichier doit être un PDF"}, 
        #         status_code=400
        #     )
        
        # Extraction du texte
        raw_text = extract_text_from_pdf(file)
        
        if not raw_text.strip():
            return JSONResponse(
                content={"error": "Impossible d'extraire le texte du PDF"}, 
                status_code=400
            )
        
        # Construction du prompt et génération de la réponse
        prompt = build_prompt_optimized(raw_text, language=language, summary_mode=summary_type)
        result = get_ai_response(prompt, model_name)
        
        return JSONResponse(content={"result": result})
        
    except Exception as e:
        return JSONResponse(
            content={"error": f"Erreur lors de l'analyse : {str(e)}"}, 
            status_code=500
        )

@app.post("/analyze-url")
async def analyze_url(
    url: str = Form(...),
    language: str = Form("fr"),
    summary_type: str = Form("synthetique"),
    model_name: str = Form("gpt4")
):
    """Analyse d'un article PubMed via URL"""
    try:
        # Validation de l'URL
        if not ("pubmed.ncbi.nlm.nih.gov" in url or "ncbi.nlm.nih.gov" in url):
            return JSONResponse(
                content={"error": "L'URL doit être un lien PubMed valide"}, 
                status_code=400
            )
        
        # Extraction du contenu
        text = extract_text_from_pubmed_url(url)
        
        if "[Erreur de récupération" in text:
            return JSONResponse(
                content={"error": "Impossible de récupérer le contenu de l'article"}, 
                status_code=400
            )
        
        # Construction du prompt et génération de la réponse
        prompt = build_prompt_optimized(text, language=language, summary_mode=summary_type)
        result = get_ai_response(prompt, model_name)
        
        return JSONResponse(content={"result": result})
        
    except Exception as e:
        return JSONResponse(
            content={"error": f"Erreur lors de l'analyse : {str(e)}"}, 
            status_code=500
        )

@app.get("/health")
async def health_check():
    """Endpoint de vérification de santé de l'API"""
    return {"status": "healthy", "message": "Paper Scanner IA API is running"}

@app.post("/analyze-batch")
async def analyze_batch(
    files: List[UploadFile] = File(...),
    language: str = Form("fr"),
    analysis_type: str = Form("synthesis"),  # synthesis ou meta_analysis
    model_name: str = Form("gpt4")
):
    """Analyse batch de plusieurs articles PDF"""
    try:
        # Validation du nombre de fichiers
        if len(files) < 2:
            return JSONResponse(
                content={"error": "Minimum 2 fichiers requis pour une analyse batch"}, 
                status_code=400
            )
        
        if len(files) > 10:  # Limite pour éviter la surcharge
            return JSONResponse(
                content={"error": "Maximum 10 fichiers autorisés par batch"}, 
                status_code=400
            )
        
        # Extraction du texte de tous les PDFs
        articles_data = extract_text_from_multiple_pdfs(files)
        
        # Vérification qu'au moins un fichier a été lu avec succès
        successful_extractions = [a for a in articles_data if a["success"]]
        if len(successful_extractions) < 2:
            return JSONResponse(
                content={"error": "Au moins 2 fichiers doivent être lisibles pour l'analyse batch"}, 
                status_code=400
            )
        
        # Analyse batch asynchrone
        result = await process_batch_analysis(articles_data, language, analysis_type, model_name)
        
        # Métadonnées sur le traitement
        metadata = {
            "total_files": len(files),
            "successful_extractions": len(successful_extractions),
            "failed_extractions": len(articles_data) - len(successful_extractions),
            "analysis_type": analysis_type,
            "model_used": model_name,
            "files_processed": [{"name": a["filename"], "success": a["success"]} for a in articles_data]
        }
        
        return JSONResponse(content={
            "result": result,
            "metadata": metadata
        })
        
    except Exception as e:
        return JSONResponse(
            content={"error": f"Erreur lors de l'analyse batch : {str(e)}"}, 
            status_code=500
        )

# 7. Point d'entrée
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)