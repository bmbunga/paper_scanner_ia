import streamlit as st
import requests
from datetime import datetime
from db_utils import init_db, save_summary, load_summaries
from fpdf import FPDF
from PIL import Image
from io import BytesIO
from generate_pdf import generate_pdf
import base64
import os
import json

# Pour développement local (décommente la ligne ci-dessous si besoin) :
API_BASE_URL = "http://localhost:8001"
# Pour le cloud (décommente la ligne ci-dessous pour déploiement) :
# API_BASE_URL = "https://paper-scanner-ia.onrender.com"


# Config générale
st.set_page_config(
    page_title="Paper Scanner IA",
    page_icon="🧬",
    layout="wide"
)

# 📌 Affichage du logo et titre
logo_path = "frontend/logo_paper_scanner_ia.png"
if os.path.exists(logo_path):
    st.image(logo_path, width=120)

st.markdown("""
# **Paper Scanner IA**
### Analyse intelligente d'articles biomédicaux par GPT-4
""")

st.markdown("""
## 🧬 **Paper Scanner IA – Analyse d'articles biomédicaux**
Ce prototype permet d'analyser un article scientifique via un fichier PDF ou un lien PubMed, et d'en extraire un résumé structuré par IA (GPT-4).
""")


# 📁 Tabs PDF ou URL
tab1, tab2, tab3 = st.tabs(["📄 PDF", "🔗 Lien PubMed", "Contact"])

with tab1:
    st.subheader("Analyse via PDF")
    file = st.file_uploader("Chargez un fichier PDF", type=["pdf"])
    language = st.selectbox("Langue du résumé", ["fr", "en"], index=0)
    summary_type = st.radio("Type de résumé", ["medical", "simple"], horizontal=True)
    extract_mesh = st.checkbox("🔎 Extraire concepts MeSH & codes ICD-10")

    if st.button("Analyser le PDF") and file:
        files = {"file": file.getvalue()}
        data = {
            "language": language,
            "summary_type": summary_type,
            "extract_mesh": json.dumps(extract_mesh)
        }
        res = requests.post(f"{API_BASE_URL}/analyze-paper", files=files, data=data)
        
        if res.status_code == 200:
            result_text = res.json().get("result", "Aucun résultat.")
            st.success("✅ Résumé généré :")
            st.markdown(result_text)

            st.download_button(
                label="📥 Télécharger le résumé en .txt",
                data=result_text,
                file_name="resume_article.txt",
                mime="text/plain"
            )
            
            pdf_buffer = generate_pdf("Résumé généré par Paper Scanner IA", result_text, source=None)
            st.download_button("📄 Télécharger le résumé en PDF", data=pdf_buffer, file_name="resume_article.pdf", mime="application/pdf")
            


with tab2:
    st.subheader("Analyse via URL PubMed")
    url = st.text_input("Collez un lien PubMed valide")
    language = st.selectbox("Langue du résumé", ["fr", "en"], key="lang_url")
    summary_type = st.radio("Type de résumé", ["medical", "simple"], key="type_url", horizontal=True)
    extract_mesh = st.checkbox("🔎 Extraire concepts MeSH & codes ICD-10", key="mesh_url")

    if st.button("Analyser le lien") and url:
        data = {
            "url": url,
            "language": language,
            "summary_type": summary_type,
            "extract_mesh": json.dumps(extract_mesh)
        }
        res = requests.post(f"{API_BASE_URL}/analyze-url", data=data)

        if res.status_code == 200:
            result_text = res.json().get("result", "Aucun résultat.")
            st.success("✅ Résumé généré :")
            st.markdown(result_text)

            st.download_button(
                label="📥 Télécharger le résumé en .txt",
                data=result_text,
                file_name="resume_article.txt",
                mime="text/plain"
            )


            pdf_buffer = generate_pdf("Résumé généré par Paper Scanner IA", result_text, source=url)
            st.download_button("📄 Télécharger le résumé en PDF", data=pdf_buffer, file_name="resume_article.pdf", mime="application/pdf")

with tab3:
    st.subheader("💬 Contact & Feedback")
    st.write("Merci de remplir ce formulaire pour nous transmettre vos suggestions, bugs ou demandes d'accès pro !")
    st.markdown(
        '''
        <iframe src="https://docs.google.com/forms/d/e/1FAIpQLSds3qCqfdVp_J1t_pBQ4A2O4jr4OmSDmMLZ08--ZS7ygh97Sw/viewform?embedded=true"
        width="700" height="900" frameborder="0" marginheight="0" marginwidth="0">
        Chargement…</iframe>
        ''',
        unsafe_allow_html=True
    )            

    st.markdown(
    "[Ouvrir le formulaire dans un nouvel onglet](https://docs.google.com/forms/d/e/1FAIpQLSds3qCqfdVp_J1t_pBQ4A2O4jr4OmSDmMLZ08--ZS7ygh97Sw/viewform)",
    unsafe_allow_html=True
    )


