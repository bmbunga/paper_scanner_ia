
import os
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from anthropic import Anthropic
from utils.text_extraction import extract_text_from_pdf, extract_text_from_pubmed_url

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def build_prompt_detaille_fusion(text: str, language="fr", summary_mode="synthetique") -> str:
    lang = language.upper()
    if summary_mode == "detaille":
        summary = (f"Rédige un résumé détaillé de l'article scientifique ci-dessous, en {language}, incluant : "
                   "le contexte, l'objectif, la méthodologie, les résultats et la conclusion.")
    else:
        summary = "Résume le texte suivant dans un style professionnel, synthétique (5 à 8 lignes max)."
    return f"""Tu es un assistant scientifique spécialisé dans les articles biomédicaux.

{summary}

Ensuite, extraits les informations suivantes sous forme de liste :
- Molécules mentionnées
- Pathologies ciblées
- Type d'étude (préclinique, clinique, etc.)
- Auteurs principaux

Réponds en langue : {lang}

Texte :
{text[:3000]}
"""

def get_client(model_name: str):
    if model_name == "GPT-4":
        return openai_client
    elif model_name == "Claude-3":
        return anthropic_client
    else:
        raise ValueError("Modèle non supporté")

def get_model_name(model_choice: str) -> str:
    if model_choice == "GPT-4":
        return "gpt-4"
    elif model_choice == "Claude-3":
        return "claude-3-sonnet-20240229"
    else:
        raise ValueError("Modèle non supporté")

@app.post("/analyze-paper")
async def analyze_paper(
    file: UploadFile = File(...),
    language: str = Form("fr"),
    summary_mode: str = Form("synthetique"),
    model_name: str = Form("GPT-4")
):
    try:
        raw_text = extract_text_from_pdf(file)
        prompt = build_prompt_detaille_fusion(raw_text, language=language, summary_mode=summary_mode)
        client = get_client(model_name)

        if model_name == "Claude-3":
            response = client.messages.create(
                model=get_model_name(model_name),
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            result = response.content[0].text
        else:
            response = client.chat.completions.create(
                model=get_model_name(model_name),
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
    summary_mode: str = Form("synthetique"),
    model_name: str = Form("GPT-4")
):
    try:
        text = extract_text_from_pubmed_url(url)
        prompt = build_prompt_detaille_fusion(text, language=language, summary_mode=summary_mode)
        client = get_client(model_name)

        if model_name == "Claude-3":
            response = client.messages.create(
                model=get_model_name(model_name),
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            result = response.content[0].text
        else:
            response = client.chat.completions.create(
                model=get_model_name(model_name),
                messages=[{"role": "user", "content": prompt}]
            )
            result = response.choices[0].message.content

        return JSONResponse(content={"result": result})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
