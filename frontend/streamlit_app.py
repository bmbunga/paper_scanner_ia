import streamlit as st
import requests
import re
import os
import json
import traceback
from datetime import datetime
from typing import Dict, Any
from io import BytesIO

# Imports pour la génération de fichiers et leurs dépendances
try:
    from fpdf import FPDF
    from PIL import Image
    from generate_pdf import generate_pdf
    from generate_word import generate_word
    from generate_html import generate_html
    PDF_GENERATION_AVAILABLE = True
    
    # Test rapide des modules pour s'assurer qu'ils fonctionnent
    test_text = "Test"
    _ = generate_pdf("Test", test_text)
    
except ImportError as e:
    st.sidebar.warning(f"⚠️ Modules d'export non disponibles : {e}")
    PDF_GENERATION_AVAILABLE = False
except Exception as e:
    st.sidebar.warning(f"⚠️ Erreur dans les modules d'export : {e}")
    PDF_GENERATION_AVAILABLE = False

# === CONFIGURATION ===
# Pour développement local :
#API_BASE_URL = "http://localhost:8001"
# Pour production (décommentez selon votre déploiement) :
API_BASE_URL = "https://summarize-medical-ym1p.onrender.com"

# === CONFIGURATION STREAMLIT ===
st.set_page_config(
    page_title="Paper Scanner IA", 
    page_icon="🧬", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# === STYLES CSS ===
st.markdown("""
    <style>
        /* Fond dégradé doux */
        .stApp {
            background: linear-gradient(120deg, #fbefff 0%, #fff5ee 100%);
        }
        
        /* Conteneur principal centré */
        .block-container {
            max-width: 900px;
            margin: auto;
            padding-top: 2rem;
        }
        
        /* Titre principal stylé */
        .main-title {
            font-family: 'Montserrat', sans-serif;
            color: #C2309E;
            font-size: 2.5em;
            text-align: center;
            margin-bottom: 1rem;
        }
        
        /* Sous-titre */
        .subtitle {
            text-align: center;
            color: #666;
            font-size: 1.1em;
            margin-bottom: 2rem;
        }
        
        /* Bouton Pro stylé */
        .bouton-pro {
            background: linear-gradient(90deg, #ff5e62, #ff9966);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 28px;
            font-size: 1.15em;
            font-weight: bold;
            box-shadow: 0 3px 14px rgba(200, 0, 80, 0.11);
            cursor: pointer;
            margin: 10px auto;
            display: block;
            text-decoration: none;
            transition: all 0.3s ease;
        }
        
        .bouton-pro:hover {
            opacity: 0.90;
            box-shadow: 0 8px 22px rgba(200, 0, 80, 0.14);
            transform: translateY(-2px);
        }
        
        /* Bloc info analyses restantes */
        .info-box {
            background: #ffe4fa;
            border: 1px solid #ffd6e5;
            color: #B92B6A;
            border-radius: 9px;
            padding: 15px 20px;
            margin-bottom: 20px;
            font-size: 1.1em;
            text-align: center;
        }
        
        /* Bloc info Pro */
        .pro-box {
            background: #e8f5e8;
            border: 1px solid #4caf50;
            color: #2e7d32;
            border-radius: 9px;
            padding: 15px 20px;
            margin-bottom: 20px;
            font-size: 1.1em;
            text-align: center;
        }
        /* Style pour les résultats */
        .result-container {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        /* Style pour les alertes */
        .custom-warning {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
            padding: 12px 16px;
            border-radius: 8px;
            margin: 10px 0;
        }
        
        /* Tabs personnalisés */
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding-left: 20px;
            padding-right: 20px;
            background-color: #f0f2f6;
            border-radius: 8px 8px 0px 0px;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #C2309E;
            color: white;
        }
    </style>
""", unsafe_allow_html=True)

# === PARAMÈTRES ===
MAX_FREE_ANALYSES = 3

# === GESTION DE L'ÉTAT ===
#def init_session_state():
    #"""Initialise les variables de session"""
    #if "free_analyses" not in st.session_state:
        #st.session_state.free_analyses = 0
    #if "analysis_history" not in st.session_state:
        #st.session_state.analysis_history = []
    #if "last_result" not in st.session_state:
        #st.session_state.last_result = None

#init_session_state()

# === FONCTIONS UTILITAIRES ===
# ------- SÉCURITÉ EMAIL -------
#def is_valid_email(email):
    #return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def is_valid_email(email: str) -> bool:
    """Valide le format d'un email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# === FONCTIONS PRO MANQUANTES À AJOUTER ===
# Ajoutez ces fonctions après add_pro_user()

# 1. REMPLACER is_pro_user() par cette version API :
def is_pro_user_api(email: str = None) -> bool:
    """Vérifie le statut Pro via l'API PostgreSQL"""
    if not email:
        email = st.session_state.get("user_email", "")
    
    if not email:
        return False
    
    try:
        # Appel à votre API FastAPI PostgreSQL
        response = requests.get(f"{API_BASE_URL}/check-pro-status/{email}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("is_pro", False)
    except Exception as e:
        st.error(f"Erreur vérification Pro : {e}")
    
    return False

def get_user_status():
    """Retourne le statut utilisateur via API"""
    return "pro" if is_pro_user_api() else "free"


def can_use_analysis(analysis_type="simple") -> tuple:
    """Vérifie si l'utilisateur peut utiliser une analyse
    
    Returns:
        tuple: (can_use: bool, message: str, credits_needed: int)
    """
    user_status = get_user_status()
    
    if user_status == "pro":
        return True, "Utilisateur Pro - Analyses illimitées", 0
    
    # Utilisateur gratuit
    credits_needed = 2 if analysis_type == "batch" else 1
    analyses_restantes = MAX_FREE_ANALYSES - st.session_state.free_analyses
    
    if analyses_restantes >= credits_needed:
        return True, f"Analyse autorisée ({credits_needed} crédit{'s' if credits_needed > 1 else ''})", credits_needed
    else:
        message = f"Crédits insuffisants. Il vous reste {analyses_restantes} crédit{'s' if analyses_restantes > 1 else ''}, mais cette analyse nécessite {credits_needed} crédit{'s' if credits_needed > 1 else ''}."
        return False, message, credits_needed

def use_analysis_credits(analysis_type="simple"):
    """Consomme les crédits pour une analyse"""
    user_status = get_user_status()
    
    if user_status == "pro":
        return  # Pas de limite pour les Pro
    
    credits_needed = 2 if analysis_type == "batch" else 1
    st.session_state.free_analyses += credits_needed

# === MODIFIER init_session_state() ===
# Remplacez votre fonction init_session_state() par :

def init_session_state():
    """Initialise les variables de session"""
    if "free_analyses" not in st.session_state:
        st.session_state.free_analyses = 0
    if "analysis_history" not in st.session_state:
        st.session_state.analysis_history = []
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "user_email" not in st.session_state:
        st.session_state.user_email = ""  # Email vide par défaut
init_session_state()
# === MODIFIER display_usage_info() ===
# Remplacez votre fonction display_usage_info() par :

def display_usage_info():
    """Affiche les informations sur l'usage gratuit/pro (version API)"""
    user_status = get_user_status()
    
    # Affichage du statut
    if user_status == "pro":
        st.markdown("""
        <div class="pro-box">
            👑 <strong>Utilisateur Pro activé !</strong><br>
            ✨ Analyses illimitées • 📚 Analyse batch • 🤖 2 modèles IA • 📥 Export complet
        </div>
        """, unsafe_allow_html=True)
        return True
    
    # Utilisateur gratuit
    analyses_restantes = MAX_FREE_ANALYSES - st.session_state.free_analyses
    
    if analyses_restantes > 0:
        st.markdown(f"""
        <div class="info-box">
            🎁 <strong>Il vous reste {analyses_restantes} analyse{'s' if analyses_restantes > 1 else ''} gratuite{'s' if analyses_restantes > 1 else ''}.</strong><br>
            <small>ℹ️ L'analyse batch coûte 2 crédits</small>
        </div>
        """, unsafe_allow_html=True)
        return True
    else:
        st.markdown("""
        <div class="custom-warning">
            🚦 <strong>Limite gratuite atteinte.</strong> Passez en Pro pour des analyses illimitées !
        </div>
        """, unsafe_allow_html=True)
        
        # Bouton Pro
        st.markdown("""
        <a href="https://buy.stripe.com/bJe4gAbU460G1oEd864ow00" target="_blank">
            <button class="bouton-pro">
                🚀 Débloquer la version Pro (8€/mois)
            </button>
        </a>
        """, unsafe_allow_html=True)
        return False

# ------- UX : SECTION PRO + LIMITE GRATUITE -------
#def display_pro_section():
    analyses_restantes = MAX_FREE_ANALYSES - st.session_state.free_analyses
    # analyses_restantes == 1:
        #st.markdown("🎁 Il vous reste <b>1 analyse gratuite.</b>", unsafe_allow_html=True)
    #elif analyses_restantes > 1:
        #st.markdown(f"🎁 Il vous reste <b>{analyses_restantes} analyses gratuites.</b>", unsafe_allow_html=True)
    #else:
        #st.markdown("🎁 <b>Vous avez atteint la limite gratuite.</b>", unsafe_allow_html=True)
    #st.info("La version gratuite permet de tester toutes les fonctionnalités sans carte bancaire. Passez en Pro pour des analyses illimitées.")

    # Paywall
    if st.session_state.free_analyses >= MAX_FREE_ANALYSES:
        st.warning("🚦 Limite atteinte. Passez en Pro pour continuer !", icon="⚡")
        st.markdown("""
        <a href="https://buy.stripe.com/bJe4gAbU460G1oEd864ow00" target="_blank">
            <button class="bouton-pro" style="background: linear-gradient(90deg,#ff5e62,#ff9966); color:white; border:none; border-radius:8px; padding:12px 24px; font-size:18px; margin: 8px 0;">
                🚀 Débloquer Pro (8€/mois)
            </button>
        </a>
        """, unsafe_allow_html=True)
        with st.expander("Pourquoi passer en Pro ? 🤩", expanded=True):
            st.markdown("""
            - 🔥 Jusqu'à <b>100 analyses/mois</b>
            - 📝 Résumés structurés <b>en français & anglais</b>
            - ⏩ Priorité sur les améliorations
            - 💬 Support email dédié
            - 🥳 Nouveaux modules à venir !
            """, unsafe_allow_html=True)
        st.stop()

#display_pro_section()

 #(email: str) -> bool:
    #"""Valide le format d'un email"""
    #pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    #return re.match(pattern, email) is not None

def is_valid_pubmed_url(url: str) -> bool:
    """Valide qu'une URL est bien un lien PubMed"""
    pubmed_patterns = [
        r'pubmed\.ncbi\.nlm\.nih\.gov',
        r'ncbi\.nlm\.nih\.gov/pubmed',
        r'ncbi\.nlm\.nih\.gov/pmc'
    ]
    return any(re.search(pattern, url.lower()) for pattern in pubmed_patterns)

def add_to_history(analysis_data: Dict[str, Any]):
    """Ajoute une analyse à l'historique"""
    history_entry = {
        "id": len(st.session_state.analysis_history) + 1,
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "type": analysis_data.get("summary_mode", "unknown"),
        "model": analysis_data.get("model", "unknown"),
        "source": analysis_data.get("source", "PDF"),
        "success": analysis_data.get("success", True),
        "error": analysis_data.get("error", None)
    }
    
    # Limite l'historique à 50 entrées
    if len(st.session_state.analysis_history) >= 50:
        st.session_state.analysis_history.pop(0)
    
    st.session_state.analysis_history.append(history_entry)

def check_api_health() -> bool:
    """Vérifie si l'API FastAPI est accessible"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

# === INTERFACE PRINCIPALE ===
def display_header():
    """Affiche l'en-tête de l'application"""
    # Logo (optionnel)
    logo_path = "logo_paper_scanner_ia.png"
    if os.path.exists(logo_path):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(logo_path, width=120)
    
    # Titre principal
    st.markdown('<h1 class="main-title">Paper Scanner IA</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Analyse intelligente d\'articles biomédicaux par IA</p>', unsafe_allow_html=True)

def tab_batch_analysis():
    """Onglet d'analyse batch multi-articles"""
    st.subheader("📚 Analyse Batch Multi-Articles")
    
    # Vérification API
    if not check_api_health():
        st.error("🔌 Le serveur d'analyse n'est pas accessible. Veuillez réessayer plus tard.")
        return
    
    # Info sur la fonctionnalité avec note sur les limitations
    st.info("""
    🎯 **Nouveau !** Analysez plusieurs articles simultanément pour obtenir :
    - Une **synthèse comparative** des résultats
    - Une **méta-analyse structurée** des données
    - Une **vue d'ensemble** des tendances de recherche
    
    📋 **Format supporté :** Upload de fichiers PDF uniquement (2-10 fichiers)
    """)
    
    # Note sur les limitations
    with st.expander("ℹ️ Limitations et conseils", expanded=False):
        st.markdown("""
        **Formats supportés :**
        - ✅ **Fichiers PDF complets** : Analyse complète du texte intégral
        - ❌ **URLs PubMed** : Non supportées pour l'analyse batch (utilisez l'onglet analyse simple)
        
        **Conseils pour de meilleurs résultats :**
        - Privilégiez des articles sur des sujets connexes
        - Évitez les fichiers PDF trop volumineux (>5 Mo chacun)
        - Le modèle Claude est recommandé pour les analyses complexes
        - La méta-analyse nécessite des articles avec des données quantitatives
        """)
    
    # Vérification des crédits pour affichage d'info
    analyses_restantes = MAX_FREE_ANALYSES - st.session_state.free_analyses
    if analyses_restantes < 2:
        if analyses_restantes > 0:
            st.warning(f"⚠️ Il vous reste {analyses_restantes} crédit(s). L'analyse batch nécessite 2 crédits. Considérez passer en Pro ou utilisez les analyses simples.")
        else:
            st.error("🚦 Limite gratuite atteinte. Passez en Pro pour des analyses illimitées !")
            st.markdown("""
            <a href="https://buy.stripe.com/bJe4gAbU460G1oEd864ow00" target="_blank">
                <button class="bouton-pro">
                    🚀 Débloquer la version Pro (8€/mois)
                </button>
            </a>
            """, unsafe_allow_html=True)
            return
    
    # Upload multiple files (toujours permettre l'upload)
    uploaded_files = st.file_uploader(
        "Choisissez plusieurs fichiers PDF (2-10 fichiers)",
        type=["pdf"],
        accept_multiple_files=True,
        help="Sélectionnez entre 2 et 10 articles PDF pour une analyse comparative"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} fichier{'s' if len(uploaded_files) > 1 else ''} chargé{'s' if len(uploaded_files) > 1 else ''}")
        
        # Affichage de la liste des fichiers
        with st.expander(f"📋 Fichiers sélectionnés ({len(uploaded_files)})", expanded=True):
            total_size = 0
            for i, file in enumerate(uploaded_files, 1):
                file_size = file.size / 1024  # en Ko
                total_size += file_size
                st.write(f"**{i}.** {file.name} ({file_size:.1f} Ko)")
            
            st.write(f"**Taille totale :** {total_size:.1f} Ko")
            
            if total_size > 20000:  # 20 Mo
                st.warning("⚠️ Taille importante détectée. L'analyse peut prendre plusieurs minutes.")
    
    # Validation du nombre de fichiers
    if uploaded_files and len(uploaded_files) < 2:
        st.warning("📝 Veuillez sélectionner au moins 2 fichiers pour une analyse batch.")
        return
    
    if uploaded_files and len(uploaded_files) > 10:
        st.error("❌ Maximum 10 fichiers autorisés. Veuillez réduire votre sélection.")
        return
    
    # Options d'analyse
    col1, col2 = st.columns(2)
    
    with col1:
        language = st.selectbox(
            "🌍 Langue de l'analyse",
            options=["fr", "en"],
            format_func=lambda x: "🇫🇷 Français" if x == "fr" else "🇬🇧 Anglais",
            index=0,
            key="lang_batch"
        )
        
        model_choice = st.selectbox(
            "🤖 Modèle IA",
            options=["gpt4", "claude"],
            format_func=lambda x: "GPT-4 (OpenAI)" if x == "gpt4" else "Claude-3.5 (Anthropic)",
            index=0,
            key="model_batch",
            help="Claude recommandé pour les analyses complexes"
        )
    
    with col2:
        analysis_type = st.selectbox(
            "📊 Type d'analyse",
            options=["synthesis", "meta_analysis"],
            format_func=lambda x: "🔍 Synthèse Comparative" if x == "synthesis" else "📈 Méta-Analyse Structurée",
            index=0,
            key="analysis_batch",
            help="Synthèse : vue d'ensemble comparative\nMéta-analyse : analyse statistique approfondie"
        )
    
    # Explication du type d'analyse sélectionné
    if analysis_type == "synthesis":
        st.markdown("""
        **🔍 Synthèse Comparative :**
        - Comparaison des méthodologies et résultats
        - Identification des tendances communes
        - Consolidation des molécules et pathologies
        - Recommandations pratiques
        """)
    else:
        st.markdown("""
        **📈 Méta-Analyse Structurée :**
        - Analyse critique de la qualité des études
        - Synthèse quantitative des résultats
        - Évaluation de l'hétérogénéité
        - Niveau de preuve scientifique
        """)
    
    # Estimation du temps de traitement
    if uploaded_files:
        estimated_time = min(60 + (len(uploaded_files) * 15), 300)  # 1-5 minutes
        st.info(f"⏱️ **Temps estimé :** {estimated_time//60} min {estimated_time%60:02d}s pour {len(uploaded_files)} fichiers")
    
    # Bouton d'analyse avec vérification des crédits AU MOMENT du clic
    if st.button("🚀 Lancer l'Analyse Batch", type="primary", use_container_width=True):
        if not uploaded_files:
            st.error("⚠️ Veuillez d'abord charger des fichiers PDF.")
            return
        
        if len(uploaded_files) < 2:
            st.error("⚠️ Minimum 2 fichiers requis pour une analyse batch.")
            return
        
        # Vérification des crédits AU MOMENT de l'analyse
        analyses_restantes = MAX_FREE_ANALYSES - st.session_state.free_analyses
        if analyses_restantes < 2:
            st.error("❌ Crédits insuffisants pour l'analyse batch (2 crédits requis).")
            st.markdown("""
            **Options disponibles :**
            - Utilisez les analyses simples (1 crédit chacune)
            - Passez en Pro pour des analyses illimitées
            """)
            st.markdown("""
            <a href="https://buy.stripe.com/bJe4gAbU460G1oEd864ow00" target="_blank">
                <button class="bouton-pro">
                    🚀 Débloquer la version Pro (8€/mois)
                </button>
            </a>
            """, unsafe_allow_html=True)
            return
        
        # Préparation des données
        files_data = []
        for file in uploaded_files:
            files_data.append(("files", (file.name, file.getvalue(), "application/pdf")))
        
        data = {
            "language": language,
            "analysis_type": analysis_type,
            "model_name": model_choice
        }
        
        # Barre de progression personnalisée
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Analyse batch avec timeout étendu
            status_text.text("🔄 Extraction du texte en cours...")
            progress_bar.progress(20)
            
            with st.spinner("⏳ Analyse batch en cours... Cela peut prendre plusieurs minutes."):
                status_text.text("🤖 Analyse par IA en cours...")
                progress_bar.progress(60)
                
                response = requests.post(
                    f"{API_BASE_URL}/analyze-batch",
                    data=data,
                    files=files_data,
                    timeout=300  # 5 minutes
                )
                
                progress_bar.progress(90)
                status_text.text("📊 Finalisation des résultats...")
                
                if response.status_code == 200:
                    progress_bar.progress(100)
                    status_text.text("✅ Analyse terminée avec succès !")
                    
                    result_data = response.json()
                    result_text = result_data.get("result", "Aucun résultat obtenu.")
                    metadata = result_data.get("metadata", {})
                    
                    # Succès
                    st.session_state.free_analyses += 2  # Coûte 2 analyses
                    st.session_state.last_result = result_text
                    
                    # Ajout à l'historique
                    add_to_history({
                        "summary_mode": f"batch_{analysis_type}",
                        "model": model_choice,
                        "source": f"Batch ({len(uploaded_files)} fichiers)",
                        "success": True
                    })
                    
                    # Affichage des résultats
                    st.markdown('<div class="result-container">', unsafe_allow_html=True)
                    st.success("✅ **Analyse Batch terminée avec succès :**")
                    
                    # Métadonnées
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📁 Fichiers traités", f"{metadata.get('successful_extractions', 0)}/{metadata.get('total_files', 0)}")
                    with col2:
                        st.metric("🤖 Modèle utilisé", metadata.get('model_used', 'N/A'))
                    with col3:
                        st.metric("📊 Type d'analyse", metadata.get('analysis_type', 'N/A').title())
                    
                    # Résultat principal
                    st.markdown("### 📋 Résultat de l'analyse :")
                    st.markdown(result_text)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Export avec source spécifique
                    file_list = ", ".join([f.name for f in uploaded_files[:3]])
                    if len(uploaded_files) > 3:
                        file_list += f" (+ {len(uploaded_files)-3} autres)"
                    
                    display_result(result_text, f"Batch: {file_list}")
                    
                else:
                    progress_bar.empty()
                    status_text.empty()
                    error_data = response.json() if response.headers.get('content-type') == 'application/json' else {}
                    error_msg = error_data.get("error", f"Erreur HTTP {response.status_code}")
                    st.error(f"❌ {error_msg}")
                    
                    add_to_history({
                        "summary_mode": f"batch_{analysis_type}",
                        "model": model_choice,
                        "source": f"Batch ({len(uploaded_files)} fichiers)",
                        "success": False,
                        "error": error_msg
                    })
        
        except requests.exceptions.Timeout:
            progress_bar.empty()
            status_text.empty()
            st.error("⏰ Délai d'attente dépassé. Les analyses batch peuvent prendre jusqu'à 5 minutes.")
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ Erreur lors de l'analyse : {str(e)}")

def display_usage_info():
    """Affiche les informations sur l'usage gratuit/pro (mise à jour pour le batch)"""
    analyses_restantes = MAX_FREE_ANALYSES - st.session_state.free_analyses
    
    if analyses_restantes > 0:
        st.markdown(f"""
        <div class="info-box">
            🎁 <strong>Il vous reste {analyses_restantes} analyse{'s' if analyses_restantes > 1 else ''} gratuite{'s' if analyses_restantes > 1 else ''}.</strong><br>
            <small>ℹ️ L'analyse batch coûte 2 crédits</small>
        </div>
        """, unsafe_allow_html=True)
        
        # Vérification spéciale pour le batch
        if analyses_restantes < 2:
            st.warning("⚠️ L'analyse batch nécessite 2 crédits. Analyses simples uniquement disponibles.")
            return "simple_only"
        
    else:
        st.markdown("""
        <div class="custom-warning">
            🚦 <strong>Limite gratuite atteinte.</strong> Passez en Pro pour des analyses illimitées !
        </div>
        """, unsafe_allow_html=True)
        
        # Bouton Pro
        st.markdown("""
        <a href="https://buy.stripe.com/bJe4gAbU460G1oEd864ow00" target="_blank">
            <button class="bouton-pro">
                🚀 Débloquer la version Pro (8€/mois)
            </button>
        </a>
        """, unsafe_allow_html=True)
        
        # Avantages Pro (mis à jour)
        with st.expander("🌟 Avantages de la version Pro", expanded=True):
            st.markdown("""
            - **🔥 Analyses illimitées** (jusqu'à 100/mois)
            - **📚 Analyses batch** sans restriction
            - **📝 Résumés détaillés** en français et anglais
            - **🤖 Accès aux 2 modèles IA** (GPT-4 + Claude)
            - **📊 Historique complet** de vos analyses
            - **⚡ Support prioritaire** et nouvelles fonctionnalités
            - **📥 Export** en PDF, Word, HTML
            """)
        
        return False  # Bloque l'utilisation
    
    return True  # Autorise l'utilisation

def make_api_request(endpoint: str, data: dict, files: dict = None) -> tuple:
    """Effectue une requête vers l'API FastAPI"""
    try:
        url = f"{API_BASE_URL}/{endpoint}"
        
        if files:
            # Pour les uploads de fichiers, on utilise files avec le bon format
            response = requests.post(url, data=data, files=files, timeout=60)
        else:
            response = requests.post(url, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json().get("result", "Aucun résultat obtenu.")
            return True, result
        else:
            error_data = response.json() if response.headers.get('content-type') == 'application/json' else {}
            error_msg = error_data.get("error", f"Erreur HTTP {response.status_code}")
            return False, error_msg
            
    except requests.exceptions.Timeout:
        return False, "⏰ Délai d'attente dépassé. Veuillez réessayer."
    except requests.exceptions.ConnectionError:
        return False, "🔌 Impossible de se connecter au serveur. Vérifiez votre connexion."
    except Exception as e:
        return False, f"Erreur inattendue : {str(e)}"

def display_result(result_text: str, source: str = "PDF"):
    """Affiche le résultat d'analyse avec options d'export"""
    st.markdown('<div class="result-container">', unsafe_allow_html=True)
    st.success("✅ **Résumé généré avec succès :**")
    st.markdown(result_text)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Boutons d'export
    st.subheader("📥 Télécharger le résumé")
    
    if PDF_GENERATION_AVAILABLE:
        # Utilisation de vos modules existants
        try:
            # Génération des fichiers avec vos fonctions
            pdf_buffer = generate_pdf("Résumé généré par Paper Scanner IA", result_text, source=source)
            word_buffer = generate_word(result_text)
            html_buffer = generate_html(result_text)
            
            # Interface d'export avec 4 colonnes
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.download_button(
                    label="📄 Télécharger (.txt)",
                    data=result_text,
                    file_name=f"resume_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                    mime="text/plain"
                )
            
            with col2:
                st.download_button(
                    label="📋 Télécharger (.pdf)",
                    data=pdf_buffer,
                    file_name=f"resume_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf"
                )
            
            with col3:
                st.download_button(
                    label="📝 Télécharger (.docx)",
                    data=word_buffer,
                    file_name=f"resume_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            
            with col4:
                st.download_button(
                    label="🌐 Télécharger (.html)",
                    data=html_buffer,
                    file_name=f"resume_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
                    mime="text/html"
                )
            
            # Message de succès
            st.success("✅ Tous les formats d'export sont disponibles !")
            
        except Exception as e:
            st.error(f"❌ Erreur lors de la génération des fichiers : {e}")
            st.text("📄 Mode de secours : export texte uniquement")
            
            # Fallback : export texte seulement
            st.download_button(
                label="📄 Télécharger (.txt)",
                data=result_text,
                file_name=f"resume_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain"
            )
    else:
        # Mode dégradé si les modules ne sont pas disponibles
        st.warning("⚠️ Export avancé non disponible. Téléchargement en mode texte uniquement.")
        st.download_button(
            label="📄 Télécharger (.txt)",
            data=result_text,
            file_name=f"resume_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain"
        )

# === ONGLETS PRINCIPAUX ===
def tab_pdf_analysis():
    """Onglet d'analyse PDF"""
    st.subheader("📄 Analyse de fichier PDF")
    
    # Vérification API
    if not check_api_health():
        st.error("🔌 Le serveur d'analyse n'est pas accessible. Veuillez réessayer plus tard.")
        return
    
    # Upload de fichier
    uploaded_file = st.file_uploader(
        "Choisissez un fichier PDF",
        type=["pdf"],
        help="Formats acceptés : PDF uniquement"
    )
    
    if uploaded_file:
        st.success(f"✅ Fichier chargé : {uploaded_file.name} ({uploaded_file.size/1024:.1f} Ko)")
    
    # Options d'analyse
    col1, col2 = st.columns(2)
    
    with col1:
        language = st.selectbox(
            "🌍 Langue du résumé",
            options=["fr", "en"],
            format_func=lambda x: "🇫🇷 Français" if x == "fr" else "🇬🇧 Anglais",
            index=0
        )
        
        model_choice = st.selectbox(
            "🤖 Modèle IA",
            options=["gpt4", "claude"],
            format_func=lambda x: "GPT-4 (OpenAI)" if x == "gpt4" else "Claude-3.5 (Anthropic)",
            index=0,
            help="Choisissez le modèle d'IA pour l'analyse"
        )
    
    with col2:
        summary_type = st.selectbox(
            "📋 Type de résumé",
            options=["synthetique", "detaille"],
            format_func=lambda x: "📝 Synthétique (5-8 lignes)" if x == "synthetique" else "📚 Détaillé (15-25 lignes)",
            index=0,
            help="Synthétique : résumé court et concis\nDétaillé : analyse complète et structurée"
        )
    
    # Bouton d'analyse
    if st.button("🚀 Analyser le PDF", type="primary", use_container_width=True):
        if not uploaded_file:
            st.error("⚠️ Veuillez d'abord charger un fichier PDF.")
            return
        
        # Vérification du type de fichier
        if not uploaded_file.name.lower().endswith('.pdf'):
            st.error("❌ Le fichier doit être un PDF. Format détecté : " + uploaded_file.name.split('.')[-1])
            return
        
        # Vérification de la taille (optionnel)
        if uploaded_file.size > 10 * 1024 * 1024:  # 10 Mo
            st.warning("⚠️ Fichier volumineux détecté. L'analyse peut prendre plus de temps.")
        
        can_use, message, credits_needed = can_use_analysis("simple")
        if not can_use:
            st.warning(f"⚠️ {message}")
        return
        
        # Préparation des données pour l'API
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
        data = {
            "language": language,
            "summary_type": summary_type,
            "model_name": model_choice
        }
        
        # Analyse
        with st.spinner("⏳ Analyse en cours... Cela peut prendre 30-60 secondes."):
            success, result = make_api_request("analyze-paper", data, files)
            
            if success:
                # Succès
                use_analysis_credits("simple")
                st.session_state.last_result = result
                
                # Ajout à l'historique
                add_to_history({
                    "summary_mode": summary_type,
                    "model": model_choice,
                    "source": "PDF",
                    "success": True
                })
                
                display_result(result, f"PDF: {uploaded_file.name}")
            else:
                # Erreur
                st.error(f"❌ {result}")
                add_to_history({
                    "summary_mode": summary_type,
                    "model": model_choice,
                    "source": "PDF",
                    "success": False,
                    "error": result
                })

def tab_pubmed_analysis():
    """Onglet d'analyse PubMed"""
    st.subheader("🔗 Analyse d'article PubMed")
    
    # Vérification API
    if not check_api_health():
        st.error("🔌 Le serveur d'analyse n'est pas accessible. Veuillez réessayer plus tard.")
        return
    
    # Note explicative sur les articles payants
    st.info("""
    ℹ️ **Note importante :** Pour les articles payants, l'analyse se base sur le titre, 
    l'abstract et les métadonnées disponibles gratuitement sur PubMed. 
    L'abstract contient généralement les informations essentielles (contexte, méthode, résultats, conclusions).
    """)
    
    # Saisie URL
    url = st.text_input(
        "🔗 URL de l'article PubMed",
        placeholder="https://pubmed.ncbi.nlm.nih.gov/12345678/",
        help="Collez ici le lien complet vers l'article PubMed (gratuit ou payant)"
    )
    
    if url and not is_valid_pubmed_url(url):
        st.warning("⚠️ Cette URL ne semble pas être un lien PubMed valide.")
    
    # Options d'analyse
    col1, col2 = st.columns(2)
    
    with col1:
        language = st.selectbox(
            "🌍 Langue du résumé",
            options=["fr", "en"],
            format_func=lambda x: "🇫🇷 Français" if x == "fr" else "🇬🇧 Anglais",
            index=0,
            key="lang_pubmed"
        )
        
        model_choice = st.selectbox(
            "🤖 Modèle IA",
            options=["gpt4", "claude"],
            format_func=lambda x: "GPT-4 (OpenAI)" if x == "gpt4" else "Claude-3.5 (Anthropic)",
            index=0,
            key="model_pubmed"
        )
    
    with col2:
        summary_type = st.selectbox(
            "📋 Type de résumé",
            options=["synthetique", "detaille"],
            format_func=lambda x: "📝 Synthétique (5-8 lignes)" if x == "synthetique" else "📚 Détaillé (15-25 lignes)",
            index=0,
            key="summary_pubmed"
        )
    
    # Bouton d'analyse
    if st.button("🚀 Analyser l'article", type="primary", use_container_width=True):
        if not url:
            st.error("⚠️ Veuillez d'abord saisir une URL PubMed.")
            return
        
        if not is_valid_pubmed_url(url):
            st.error("⚠️ URL PubMed non valide. Vérifiez le lien.")
            return
        
        can_use, message, credits_needed = can_use_analysis("simple")
        if not can_use:
            st.warning(f"⚠️ {message}")
        return
        
        # Préparation des données
        data = {
            "url": url,
            "language": language,
            "summary_type": summary_type,
            "model_name": model_choice
        }
        
        # Analyse
        with st.spinner("⏳ Récupération et analyse en cours..."):
            success, result = make_api_request("analyze-url", data)
            
            if success:
                # Succès
                use_analysis_credits("simple")
                st.session_state.last_result = result
                
                # Ajout à l'historique
                add_to_history({
                    "summary_mode": summary_type,
                    "model": model_choice,
                    "source": "PubMed",
                    "success": True
                })
                
                display_result(result, f"PubMed: {url}")
            else:
                # Erreur
                st.error(f"❌ {result}")
                add_to_history({
                    "summary_mode": summary_type,
                    "model": model_choice,
                    "source": "PubMed",
                    "success": False,
                    "error": result
                })

# === CRÉER UN NOUVEL ONGLET PRO ===
def tab_pro_activation():
    """Onglet d'activation Pro avec API PostgreSQL"""
    st.subheader("👑 Activation Pro")
    
    user_status = get_user_status()
    
    if user_status == "pro":
        # Utilisateur déjà Pro
        st.success("🎉 **Statut Pro activé !**")
        
        current_email = st.session_state.get("user_email", "")
        if current_email:
            st.info(f"📧 Connecté avec : {current_email}")
        
        st.markdown("""
        **🎯 Vos avantages Pro actifs :**
        - ✅ **Analyses illimitées** (jusqu'à 100/mois)
        - ✅ **Analyses batch multi-articles**
        - ✅ **2 modèles IA** (GPT-4 + Claude-3.5)
        - ✅ **Export professionnel** (PDF, Word, HTML)
        - ✅ **Support prioritaire**  
        - ✅ **Nouvelles fonctionnalités** en avant-première
        """)
        
        if st.button("🔓 Se déconnecter"):
            st.session_state.user_email = ""
            st.rerun()
    
    else:
        st.info("🔐 Entrez votre email pour activer le mode Pro après paiement.")
        
        with st.form("pro_activation"):
            pro_email = st.text_input(
                "📧 Email Pro",
                placeholder="mm_blaise@yahoo.fr",
                help="Email utilisé lors du paiement Stripe"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                activate = st.form_submit_button("🔓 Activer Pro", type="primary")
            with col2:
                refresh = st.form_submit_button("🔄 Actualiser")
            
            if activate and pro_email:
                if is_valid_email(pro_email):
                    # Vérification via API PostgreSQL
                    with st.spinner("🔍 Vérification du statut Pro..."):
                        if is_pro_user_api(pro_email):
                            st.session_state.user_email = pro_email
                            st.success("✅ **Activation réussie !**")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("❌ Email non trouvé dans nos abonnements Pro.")
                            st.info("Si vous venez de payer, attendez quelques minutes puis réessayez.")
                            st.info("Support : mmblaise10@gmail.com")
                else:
                    st.error("⚠️ Format d'email invalide.")
        
        # Section achat
        st.markdown("---")
        st.markdown("### 🛒 Devenir Pro")
        
        st.markdown("""
        **💎 Version Pro (8€/mois) :**  
        Un investissement rentable pour votre productivité en recherche !
        """)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **🔥 Fonctionnalités :**
            - Analyses illimitées
            - Analyses batch multi-articles  
            - 2 modèles IA premium
            - Export multi-format
            """)
        with col2:
            st.markdown("""
            **⚡ Avantages :**
            - Support prioritaire
            - Nouvelles fonctionnalités
            - Historique complet
            - Performance optimisée
            """)
        
        st.markdown("""
        <a href="https://buy.stripe.com/bJe4gAbU460G1oEd864ow00" target="_blank">
            <button class="bouton-pro">
                🚀 S'abonner Pro (8€/mois)
            </button>
        </a>
        """, unsafe_allow_html=True)


def tab_contact():
    """Onglet de contact"""
    st.subheader("💬 Contact & Support")
    
    with st.form("contact_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            nom = st.text_input("👤 Nom", placeholder="Votre nom ou pseudo")
            email = st.text_input("📧 Email", placeholder="votre.email@exemple.com")
        
        with col2:
            sujet = st.selectbox(
                "📋 Sujet",
                ["Question générale", "Problème technique", "Suggestion d'amélioration", "Signaler un bug", "Autre"]
            )
        
        message = st.text_area(
            "💬 Message",
            placeholder="Décrivez votre demande...",
            height=150
        )
        
        submitted = st.form_submit_button("📤 Envoyer le message", type="primary", use_container_width=True)
        
        if submitted:
            if not nom or not email or not message:
                st.error("⚠️ Veuillez remplir tous les champs obligatoires.")
            elif not is_valid_email(email):
                st.error("⚠️ Format d'email invalide.")
            else:
                # Simulation d'envoi (remplacez par votre logique)
                with st.spinner("📤 Envoi en cours..."):
                    # Ici vous pouvez ajouter votre logique d'envoi d'email
                    # Par exemple via un webhook, API email, etc.
                    st.success("✅ Message envoyé avec succès ! Nous vous répondrons rapidement.")
                    
                    # Log local simple (optionnel)
                    try:
                        log_data = {
                            "timestamp": datetime.now().isoformat(),
                            "nom": nom,
                            "email": email,
                            "sujet": sujet,
                            "message": message
                        }
                        with open("contact_logs.txt", "a", encoding="utf-8") as f:
                            f.write(json.dumps(log_data, ensure_ascii=False) + "\n")
                    except:
                        pass  # Log silencieux en cas d'erreur
    
    # Informations de contact
    st.markdown("---")
    st.markdown("""
    ### 📞 Autres moyens de contact
    
    - **📧 Email direct :** mmblaise10@gmail.com
    - **⏱️ Délai de réponse :** Généralement sous 24h
    - **🆘 Support technique :** Problèmes urgents prioritaires
    
    ### ❓ Questions fréquentes
    """)
    
    with st.expander("🔍 Comment améliorer la qualité des résumés ?"):
        st.markdown("""
        - Utilisez des PDFs avec un texte de bonne qualité (évitez les scans flous)
        - Pour PubMed, assurez-vous que l'article est complet et accessible
        - Choisissez le mode "Détaillé" pour une analyse plus approfondie
        - Essayez les deux modèles IA pour comparer les résultats
        """)
    
    with st.expander("⚡ Que faire en cas de lenteur ?"):
        st.markdown("""
        - L'analyse peut prendre 30-90 secondes selon la complexité
        - Vérifiez votre connexion internet
        - Évitez les fichiers PDF trop volumineux (>10 Mo)
        - Réessayez si le délai d'attente est dépassé
        """)

def tab_history():
    """Onglet historique"""
    st.subheader("📊 Historique des analyses")
    
    if not st.session_state.analysis_history:
        st.info("🕰️ Aucune analyse effectuée pour le moment.")
        return
    
    # Statistiques rapides
    total_analyses = len(st.session_state.analysis_history)
    successful_analyses = sum(1 for entry in st.session_state.analysis_history if entry.get("success", True))
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📈 Total analyses", total_analyses)
    with col2:
        st.metric("✅ Succès", successful_analyses)
    with col3:
        st.metric("📉 Échecs", total_analyses - successful_analyses)
    
    st.markdown("---")
    
    # Affichage de l'historique
    for i, entry in enumerate(reversed(st.session_state.analysis_history)):
        with st.expander(f"📝 Analyse #{entry['id']} - {entry['timestamp']}", expanded=(i < 3)):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Type :** {entry['type'].title()}")
                st.write(f"**Modèle :** {entry['model']}")
                st.write(f"**Source :** {entry['source']}")
            
            with col2:
                status = "✅ Succès" if entry['success'] else "❌ Échec"
                st.write(f"**Statut :** {status}")
                if not entry['success'] and entry.get('error'):
                    st.error(f"Erreur : {entry['error']}")

# === APPLICATION PRINCIPALE ===
def main():
    """Fonction principale de l'application"""
    display_header()
    
    # Vérification de la santé de l'API
    if not check_api_health():
        st.error("🔌 **Serveur d'analyse indisponible**")
        st.info("Veuillez vérifier que votre serveur FastAPI est démarré et accessible.")
        st.code(f"URL testée : {API_BASE_URL}/health")
        return
    
    # Affichage des informations d'usage
    if not display_usage_info():
        return  # Bloque l'utilisation si limite atteinte
    
    # Onglets principaux (ajout de l'onglet Batch)
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📄 Analyse PDF", "🔗 Analyse PubMed", "📚 Batch Multi-Articles", "👑 Pro", "💬 Contact", "📊 Historique"])
    
    with tab1:
        tab_pdf_analysis()
    
    with tab2:
        tab_pubmed_analysis()
    
    with tab3:
        tab_batch_analysis()
    
    with tab4:
        tab_pro_activation()
    
    with tab5:
        tab_contact()
    
    with tab6:
        tab_history()
    
    # Footer avec informations de version
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; margin-top: 2rem;'>
        <p>🧬 <strong>Paper Scanner IA v2.0</strong> - Analyse intelligente d'articles biomédicaux</p>
        <p style='font-size: 0.9em;'>✨ <strong>Nouveautés :</strong> Analyse batch multi-articles • 2 modèles IA • Export amélioré</p>
        <p style='font-size: 0.8em;'>© 2025 Paper Scanner IA. Tous droits réservés.</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()