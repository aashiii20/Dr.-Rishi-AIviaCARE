import streamlit as st
import pandas as pd
from openai import AzureOpenAI
import os
from dotenv import load_dotenv
from datetime import datetime
import pymongo
import certifi
from bson.objectid import ObjectId

# Load environment variables
load_dotenv()

# --- 1. DATABASE SETUP ---
MONGO_URI = os.getenv("MONGO_URI")

@st.cache_resource
def init_connection():
    return pymongo.MongoClient(MONGO_URI, tlsCAFile=certifi.where())

try:
    if not MONGO_URI:
        st.error("❌ MONGO_URI not found! Check your .env file.")
    else:
        client_db = init_connection()
        db = client_db["aiviacare_db"]
        sessions_col = db["clinical_sessions"]
except Exception as e:
    st.error(f"⚠️ Connection Error: {e}")

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-01",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# --- 2. DYNAMIC COLOR & THEME LOGIC ---
def apply_dynamic_theme():
    bg_color = "#FFFFFF"
    text_color = "#31333F"
    
    if st.session_state.get("calm_mode"):
        bg_color = "#E0F2F1"  
        text_color = "#004D40"
    elif "current_severity" in st.session_state:
        sev = st.session_state.current_severity
        if sev <= 3: bg_color = "#E8F5E9"
        elif sev <= 7: bg_color = "#FFFDE7"
        else: bg_color = "#FFEBEE"
            
    st.markdown(f"""
        <style>
        .stApp {{ background-color: {bg_color} !important; color: {text_color} !important; transition: background-color 0.5s ease; }}
        [data-testid="stSidebar"] {{ background-color: #F0F2F6; }}
        .stMarkdown, p, span, label {{ color: {text_color} !important; }}
        </style>
    """, unsafe_allow_html=True)

# --- 3. LANGUAGE SUPPORT ---
LANG_DATA = {
    "English": {
        "consent_header": "📜 Digital Consent & Disclaimer",
        "consent_body": "I understand that Dr. Rishi is an AI assistant and NOT a replacement for a real doctor.",
        "consent_check": "I agree and understand the terms.",
        "intake_header": "🏥 Patient Intake Form",
        "symptoms_label": "Describe your symptoms",
        "btn_start": "Start Consultation",
        "chat_placeholder": "Describe your symptoms or ask a question...",
        "assessment_header": "📊 Symptom Assessment",
        "severity_label": "Severity (1 = Mild, 10 = Severe)",
        "duration_label": "Duration (Days)",
        "btn_confirm": "Confirm Assessment & Get Advice",
        "btn_new": "New Query"
    },
    "Hindi (हिन्दी)": {
        "consent_header": "📜 डिजिटल सहमति और अस्वीकरण",
        "consent_body": "मैं समझता हूँ कि डॉ. ऋषि एक एआई सहायक हैं।",
        "consent_check": "मैं शर्तों को स्वीकार करता हूँ।",
        "intake_header": "🏥 रोगी जानकारी फॉर्म",
        "symptoms_label": "अपने लक्षणों का वर्णन करें",
        "btn_start": "परामर्श शुरू करें",
        "chat_placeholder": "अपने लक्षणों का वर्णन करें...",
        "assessment_header": "📊 लक्षण मूल्यांकन",
        "severity_label": "तीव्रता",
        "duration_label": "अवधि",
        "btn_confirm": "पुष्टि करें",
        "btn_new": "नया प्रश्न"
    }
}

@st.dialog("📄 Clinical Perception", width="large")
def perception_modal(r):
    rec_id = str(r['_id'])
    st.subheader(f"Patient: {r.get('name', 'Unknown')}")
    v1, v2, v3, v4 = st.columns(4)
    v1.metric("BMI", r.get('bmi', 'N/A'))
    v2.metric("Sugar", f"{r.get('sugar', 'N/A')} mg/dL")
    v3.metric("BP", r.get('bp', 'N/A'))
    v4.metric("Specialty", r.get('specialty', 'GP'))
    st.divider()
    if st.button("✨ Generate AI Patient Handoff", key=f"handoff_{rec_id}"):
        with st.spinner("Summarizing..."):
            prompt = f"Summarize: {r.get('current_complaint')}"
            res = client.chat.completions.create(model=deployment_name, messages=[{"role":"user","content":prompt}])
            st.info(res.choices[0].message.content)
    if st.button("Close View", key=f"close_{rec_id}"): 
        st.rerun()

st.set_page_config(page_title="Dr. Rishi Saxena | AIviaCARE", layout="wide")
apply_dynamic_theme()

specialties = ["General Physician", "Cardiologist", "Dermatologist", "Psychiatrist", "Pediatrician", "Dietitian", "Endocrinologist"]

with st.sidebar:
    st.title("👨‍⚕️ Dr. Rishi Saxena")
    lang_choice = st.radio("🌐 Language / भाषा चुनें", ["English", "Hindi (हिन्दी)"])
    L = LANG_DATA[lang_choice]
    st.divider()
    st.session_state.calm_mode = st.toggle("🌿 Healthy Calm Mode", value=False)
    with st.container(border=True):
        st.image("https://cdn-icons-png.flaticon.com/512/387/387561.png", width=70)
        st.metric("Total Consultations", sessions_col.count_documents({}))
    portal = st.selectbox("Navigation", ["Patient Portal", "Doctor Dashboard"])
    active_specialty = st.selectbox("Switch AI Specialty", specialties)
    if st.button("🔄 Reset Session", key="sidebar_reset_btn"):
        st.session_state.clear()
        st.rerun()

# --- 6. PORTAL LOGIC ---
if portal == "Patient Portal":
    top_col1, top_col2, top_col3 = st.columns([6, 2, 2])
    with top_col2:
        st.link_button("🚑 Call Ambulance", "tel:102", use_container_width=True, type="primary")
    with top_col3:
        st.link_button("🏥 Nearby Hospitals", "https://www.google.com/maps/search/hospitals+near+me", use_container_width=True)

    st.title(f"👨‍⚕️ Consulting: {active_specialty}")

    if "consent_signed" not in st.session_state:
        st.subheader(L['consent_header'])
        with st.container(border=True):
            st.write(L['consent_body'])
            agree = st.checkbox(L['consent_check'])
            if st.button("Proceed", key="consent_proceed_btn") and agree:
                st.session_state.consent_signed = True
                st.rerun()

    elif "p_info" not in st.session_state:
        with st.form("intake_form"):
            st.subheader(L['intake_header'])
            name = st.text_input("Full Name")
            c1, c2 = st.columns(2)
            weight = c1.number_input("Weight (kg)", 1.0, 300.0, 70.0)
            height = c2.number_input("Height (cm)", 50.0, 250.0, 170.0)
            sugar = c1.number_input("Sugar (mg/dL)", 40, 500, 100)
            bp = c2.text_input("BP (e.g. 120/80)", "120/80")
            meds = st.text_area("Current Medications")
            surgeries = st.text_area("Past History")
            allergies = st.text_input("Allergies")
            if st.form_submit_button(L['btn_start']):
                st.session_state.p_info = {
                    "name": name, "bmi": round(weight / ((height/100)**2), 1),
                    "sugar": sugar, "bp": bp, "med_history": meds,
                    "surgeries": surgeries, "allergies": allergies,
                    "specialty": active_specialty, "language": lang_choice
                }
                st.rerun()

    else:
        # CHECK IF WE ALREADY HAVE ADVICE TO SHOW
        if st.session_state.get("last_advice"):
            st.success("### Dr. Rishi's Analysis")
            st.markdown(st.session_state.last_advice)
            if st.button(L['btn_new']):
                st.session_state.last_advice = None
                st.rerun()
        else:
            user_input = st.chat_input(L['chat_placeholder'])
            if user_input:
                st.session_state.current_symptom = user_input
                st.session_state.assessment_pending = True

            if st.session_state.get("assessment_pending"):
                st.info(f"**{L['symptoms_label']}:** {st.session_state.current_symptom}")
                with st.form("assessment_sliders"):
                    st.subheader(L['assessment_header'])
                    sev = st.slider(L['severity_label'], 1, 10, 5)
                    dur = st.slider(L['duration_label'], 1, 30, 1)
                    
                    if st.form_submit_button(L['btn_confirm']):
                        st.session_state.current_severity = sev 
                        with st.spinner("Dr. Rishi is analyzing..."):
                            full_context = f"Patient says: {st.session_state.current_symptom}. Severity: {sev}/10. Duration: {dur} days."
                            prompt_content = f"You are Dr. Rishi, a {active_specialty}. Analyze: {full_context}."
                            res = client.chat.completions.create(
                                model=deployment_name, 
                                messages=[{"role":"system","content":prompt_content}, {"role":"user","content":full_context}]
                            )
                            advice = res.choices[0].message.content
                            
                            # SAVE ADVICE TO SESSION STATE SO IT PERSISTS
                            st.session_state.last_advice = advice
                            
                            sessions_col.insert_one({
                                **st.session_state.p_info, 
                                "current_complaint": st.session_state.current_symptom,
                                "user_severity": sev, "user_duration": dur,
                                "summary": advice, "timestamp": datetime.now()
                            })
                            st.session_state.assessment_pending = False
                            st.rerun()

# --- 7. DOCTOR DASHBOARD ---
else:
    st.title("👨‍⚕️ Doctor Dashboard")
    try:
        all_records = list(sessions_col.find().sort("timestamp", -1))
        if all_records:
            tab_all, tab_cardio, tab_derma, tab_psych = st.tabs(["All Cases", "Cardiology", "Dermatology", "Psychiatry"])
            def render_dashboard(data_list, tab_id):
                st.markdown(f"### 🏥 Patient Waiting Room ({tab_id})")
                if not data_list:
                    st.write("No cases in this department.")
                    return
                for record in data_list:
                    rec_id = str(record['_id'])
                    with st.expander(f"{record.get('name', 'Unknown')} - Severity: {record.get('user_severity', 'N/A')}/10"):
                        c1, c2, c3 = st.columns([1, 1, 2])
                        if c1.button("👁️ View", key=f"v_{tab_id}_{rec_id}"):
                            perception_modal(record)
                        if c2.button("📋 SOAP", key=f"s_{tab_id}_{rec_id}"):
                            st.info(f"**Subjective:** {record.get('current_complaint')}")
                        with c3.popover("🗑️ Delete"):
                            if st.button("Confirm Delete", key=f"d_{tab_id}_{rec_id}"):
                                sessions_col.delete_one({"_id": ObjectId(rec_id)})
                                st.rerun()

            with tab_all: render_dashboard(all_records, "All")
            with tab_cardio: render_dashboard([r for r in all_records if r.get('specialty') == 'Cardiologist'], "Cardio")
            with tab_derma: render_dashboard([r for r in all_records if r.get('specialty') == 'Dermatologist'], "Derma")
            with tab_psych: render_dashboard([r for r in all_records if r.get('specialty') == 'Psychiatrist'], "Psych")
        else:
            st.info("No clinical sessions found.")
    except Exception as e:
        st.error(f"Dashboard Error: {e}")