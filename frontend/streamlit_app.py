import streamlit as st
import requests
from datetime import datetime
from db_utils import init_db, save_summary, load_summaries
from fpdf import FPDF
from PIL import Image
from io import BytesIO
from generate_pdf import generate_pdf
from generate_word import generate_word
from generate_html import generate_html
import base64
import os
import json
import traceback

# Pour développement local (décommente la ligne ci-dessous si besoin) :
# API_BASE_URL = "http://localhost:8001"
# Pour le cloud (décommente la ligne ci-dessous pour déploiement) :
API_BASE_URL = "https://summarize-medical-ym1p.onrender.com"

st.set_page_config(page_title="Paper Scanner IA", page_icon="🧬", layout="wide")
st.markdown("""<style> /* (ton bloc CSS ici) */ </style>""", unsafe_allow_html=True)

st.markdown("""
    <style>
    #body, div, label, input, select, textarea, span {
    #font-size: 1.08em !important;
    #}
    body {
        background: linear-gradient(120deg, #c471f5 0%, #fa71cd 100%) !important;
    }
    .stApp {
        background: linear-gradient(120deg, #f5e9ff 0%, #fce7f3 100%) !important;
        font-family: 'Segoe UI', 'Helvetica Neue', Arial, 'sans-serif';
    }
    .fun-box {
        background: #fff9c4;
        color: #2e1065;
        border-radius: 12px;
        padding: 16px;
        margin: 12px 0;
        font-size: 18px;
        border: 2px solid #f3e8ff;
        box-shadow: 0 2px 8px #f9c5d1;
    }
    .stButton button {
        background: linear-gradient(90deg, #635bff 0%, #f44f8c 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 28px;
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 6px;
        transition: transform 0.07s;
        box-shadow: 0 4px 14px 0 rgba(244,79,140,0.12);
    }
    .stButton button:hover {
        background: linear-gradient(90deg, #f44f8c 0%, #635bff 100%);
        transform: scale(1.04);
        box-shadow: 0 6px 24px 0 rgba(99,91,255,0.16);
    }
    .stDownloadButton button {
        background: linear-gradient(90deg, #43e97b 0%, #38f9d7 100%);
        color: #222;
        font-weight: bold;
        border-radius: 8px;
        border: none;
        font-size: 16px;
        padding: 10px 22px;
        margin-bottom: 7px;
        box-shadow: 0 4px 10px 0 rgba(67,233,123,0.10);
        transition: transform 0.09s;
    }
    .stDownloadButton button:hover {
        background: linear-gradient(90deg, #38f9d7 0%, #43e97b 100%);
        color: #222;
        transform: scale(1.03);
    }
    /* Custom info box */
    .gift-info {
        background: #f3e8ff;
        color: #8f38f9;
        border-radius: 14px;
        padding: 14px 18px;
        font-size: 19px;
        font-weight: 500;
        margin: 18px 0;
        box-shadow: 0 2px 12px 0 #e0d7ff70;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONFIG & STYLE ---
#st.set_page_config(page_title="Paper Scanner IA", page_icon="🧬", layout="wide")
#st.markdown("""<style> /* (ton bloc CSS ici) */ </style>""", unsafe_allow_html=True)

MAX_FREE_ANALYSES = 3
if "free_analyses" not in st.session_state:
    st.session_state.free_analyses = 0

logo_path = "frontend/logo_paper_scanner_ia.png"
if os.path.exists(logo_path):
    st.image(logo_path, width=120)

st.title("Paper Scanner IA")
st.write("Analyse intelligente d'articles biomédicaux par GPT-4")

# --- GESTION LIMITE GRATUITE ---
def display_pro_section():
    st.markdown(f'<div class="bloc-info">🎁 Il vous reste <b>{MAX_FREE_ANALYSES - st.session_state.free_analyses}</b> analyses gratuites.</div>', unsafe_allow_html=True)
    if st.session_state.free_analyses >= MAX_FREE_ANALYSES:
        st.warning("🚦 Limite atteinte. Passez en Pro pour continuer !", icon="⚡")
        st.markdown("""
        <a href="https://buy.stripe.com/bJe4gAbU460G1oEd864ow00" target="_blank">
            <button class="bouton-pro">
                🚀 Débloquer Pro (8€/mois)
            </button>
        </a>
        """, unsafe_allow_html=True)
        with st.expander("Pourquoi passer en Pro ? 🤩", expanded=True):
            st.markdown("""
            - 🔥 Jusqu’à <b>100 analyses/mois</b>
            - 📝 Résumés structurés <b>en français & anglais</b>
            - ⏩ Priorité sur les améliorations
            - 💬 Support email dédié
            - 🥳 Nouveaux modules à venir !
            """, unsafe_allow_html=True)
        st.stop()

display_pro_section()

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📄 PDF", "🔗 Lien PubMed", "Contact"])

def export_buttons(result_text, source=None):
    try:
        pdf_buffer = generate_pdf("Résumé généré par Paper Scanner IA", result_text, source=source)
        word_buffer = generate_word(result_text)
        html_buffer = generate_html(result_text)
        st.download_button("📥 Télécharger le résumé en .txt", data=result_text, file_name="resume.txt")
        st.toast("✅ Résumé téléchargé avec succès !")
        st.download_button("📥 Télécharger le résumé en PDF", data=pdf_buffer, file_name="resume.pdf", mime="application/pdf")
        st.toast("✅ Résumé téléchargé avec succès !")
        st.download_button("📥 Télécharger le résumé en Word", data=word_buffer, file_name="resume.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        st.toast("✅ Résumé téléchargé avec succès !")
        st.download_button("🌈 Télécharger le résumé en HTML", data=html_buffer, file_name="resume.html", mime="text/html")
        st.toast("✅ Résumé téléchargé avec succès !")
    
    except Exception as e:
        st.error(f"Erreur lors de la génération des fichiers : {e}")
        st.text(traceback.format_exc())

with tab1:
    st.subheader("Analyse via PDF")
    file = st.file_uploader("Chargez un fichier PDF", type=["pdf"])
    language = st.selectbox("Langue du résumé", ["fr", "en"], index=0, key="lang_pdf")
    summary_type = st.radio("Type de résumé", ["medical", "simple"], horizontal=True, key="type_pdf")
    extract_mesh = st.checkbox("🔎 Extraire concepts MeSH & codes ICD-10", help="Activez pour enrichir le résumé avec des concepts médicaux reconnus internationalement.", key="extract_mesh_checkbox")


    result_text = ""
    if st.button("Analyser le PDF") and file:
        files = {"file": file.getvalue()}
        data = {
            "language": language,
            "summary_type": summary_type,
            "extract_mesh": json.dumps(extract_mesh)
        }

        with st.spinner("⏳ Analyse en cours, patientez quelques secondes..."):
            res = requests.post(f"{API_BASE_URL}/analyze-paper", files=files, data=data)
            if res.status_code == 200:
                result_text = res.json().get("result", "Aucun résultat.")
                st.success("✅ Résumé généré :")
                st.markdown(result_text)
                st.session_state.free_analyses += 1
                export_buttons(result_text)

with tab2:
    st.subheader("Analyse via URL PubMed")
    url = st.text_input("Collez un lien PubMed valide")
    language = st.selectbox("Langue du résumé", ["fr", "en"], key="lang_url")
    summary_type = st.radio("Type de résumé", ["medical", "simple"], key="type_url", horizontal=True)
    extract_mesh = st.checkbox("🔎 Extraire concepts MeSH & codes ICD-10", help="Activez pour enrichir le résumé avec des concepts médicaux reconnus internationalement.", key="extract_mesh_checkbox_footer")
    result_text = ""
    if st.button("Analyser le lien") and url:
        data = {
            "url": url,
            "language": language,
            "summary_type": summary_type,
            "extract_mesh": json.dumps(extract_mesh)
        }

        with st.spinner("⏳ Analyse en cours, patientez quelques secondes..."):
            res = requests.post(f"{API_BASE_URL}/analyze-url", data=data)
            if res.status_code == 200:
                result_text = res.json().get("result", "Aucun résultat.")
                st.success("✅ Résumé généré :")
                st.markdown(result_text)
                st.session_state.free_analyses += 1
                export_buttons(result_text, source=url)

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

    st.markdown("---")
    st.subheader("📝 Donnez votre avis ou suggérez une amélioration !")
    feedback = st.text_area("Votre retour", placeholder="Un bug, une idée, une suggestion ? Dites-nous tout !")
    if st.button("Envoyer mon feedback"):
    
    # Pour commencer : sauvegarde locale, ou envoi par email (à voir après)
        with open("feedback.txt", "a", encoding="utf-8") as f:
            f.write(feedback + "\n---\n")
            st.success("Merci pour votre feedback, il sera pris en compte !")

    
    st.markdown("""
    ---
    <div style='text-align: center; font-size: 14px; color: #555; margin-top: 40px;'>
    📧 Contact : <a href="mailto:contact@paper-scanner-ia.com">contact@paper-scanner-ia.com</a> &nbsp; | &nbsp;
    <a href="https://tonsite.com/faq" target="_blank">FAQ</a> &nbsp; | &nbsp;
    <a href="https://tonsite.com/mentions-legales" target="_blank">Mentions légales</a>
    <br>
    <span style='font-size:12px; color: #aaa'>© 2025 Paper Scanner IA. Tous droits réservés.</span>
    </div>
    """, 
    unsafe_allow_html=True
    )


