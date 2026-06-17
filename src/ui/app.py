import os
import sys
import streamlit as st

# Append parent directory to sys.path so we can import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.engine.generator import MutualFundFAQAssistant
from src import config

# Page configurations
st.set_page_config(
    page_title="Mutual Fund Facts-Only FAQ Assistant",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom Premium CSS Injection
st.html(
    """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
    .stApp {
        background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, #090d16 100%);
        color: #f3f4f6;
        font-family: 'Inter', sans-serif;
    }
    h1, h2, h3 {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem !important;
    }
    
    /* Disclaimer Card with Pulsing Glow */
    .disclaimer-card {
        background: rgba(245, 158, 11, 0.04);
        border: 1px solid rgba(245, 158, 11, 0.25);
        border-radius: 14px;
        padding: 1rem 1.25rem;
        margin-bottom: 2rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        box-shadow: 0 0 15px rgba(245, 158, 11, 0.05);
        animation: pulse-border 3s infinite alternate;
    }
    @keyframes pulse-border {
        0% {
            border-color: rgba(245, 158, 11, 0.2);
            box-shadow: 0 0 10px rgba(245, 158, 11, 0.03);
        }
        100% {
            border-color: rgba(245, 158, 11, 0.45);
            box-shadow: 0 0 25px rgba(245, 158, 11, 0.15);
        }
    }
    .disclaimer-title {
        color: #f59e0b;
        font-family: 'Outfit', sans-serif;
        font-weight: 600;
        font-size: 0.95rem;
        margin: 0;
    }
    .disclaimer-text {
        color: #d1d5db;
        font-size: 0.85rem;
        margin: 0;
    }
    
    /* Welcome Container */
    .welcome-container {
        background: rgba(17, 24, 39, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 2rem;
        backdrop-filter: blur(20px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    }
    
    /* Override Streamlit Buttons to make them Premium & Interactive */
    div.stButton > button {
        background: rgba(255, 255, 255, 0.03) !important;
        color: #e5e7eb !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 10px !important;
        padding: 0.6rem 1rem !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
    }
    div.stButton > button:hover {
        background: linear-gradient(135deg, rgba(96, 165, 250, 0.15) 0%, rgba(167, 139, 250, 0.15) 100%) !important;
        border-color: rgba(167, 139, 250, 0.5) !important;
        color: #ffffff !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(167, 139, 250, 0.2) !important;
    }
    div.stButton > button:active {
        transform: translateY(1px) !important;
    }
    
    /* Message Cards */
    .msg-user {
        background: rgba(30, 27, 75, 0.6);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-left: 4px solid #6366f1;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        animation: slide-up 0.4s ease-out;
    }
    .msg-assistant-factual {
        background: rgba(16, 185, 129, 0.03);
        border: 1px solid rgba(16, 185, 129, 0.2);
        border-radius: 14px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(16, 185, 129, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        animation: slide-up 0.5s ease-out;
    }
    .msg-assistant-refusal {
        background: rgba(239, 68, 68, 0.03);
        border: 1px solid rgba(239, 68, 68, 0.2);
        border-radius: 14px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(239, 68, 68, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        animation: slide-up 0.5s ease-out;
    }
    @keyframes slide-up {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    /* Footer Metadata */
    .meta-block {
        margin-top: 0.8rem;
        padding-top: 0.6rem;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
        font-size: 0.8rem;
        color: #9ca3af;
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
    }
    .meta-link a {
        color: #60a5fa !important;
        text-decoration: none;
        font-weight: 500;
        transition: color 0.2s;
    }
    .meta-link a:hover {
        color: #a78bfa !important;
        text-decoration: underline;
    }
    
    /* Styled list */
    ul {
        margin-top: 0.5rem;
        padding-left: 1.2rem;
        color: #d1d5db;
        font-size: 0.9rem;
    }
    li {
        margin-bottom: 0.4rem;
    }
    </style>
    """
)

# Initialize Assistant
@st.cache_resource
def get_assistant():
    return MutualFundFAQAssistant()

assistant = get_assistant()

# Header Section
st.markdown("<h1>Mutual Fund FAQ Assistant</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#9ca3af; font-size:1.05rem; margin-top:-0.5rem;'>Groww Scheme Reference Context</p>", unsafe_allow_html=True)

# High-Visibility Compliance Disclaimer Banner
st.markdown(
    """
    <div class="disclaimer-card">
        <div>
            <p class="disclaimer-title">⚠️ Compliance Disclaimer</p>
            <p class="disclaimer-text">Facts-only. No investment advice, suggestions, or comparison opinions are provided. Every response is sourced exclusively from official AMC filings.</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Welcome greeting and scope definition
st.markdown(
    """
    <div class="welcome-container">
        <p style='margin-top:0; font-family:"Outfit", sans-serif; font-size:1.15rem; font-weight:600; color:#60a5fa;'>Welcome Investor,</p>
        <p style='color:#d1d5db; font-size:0.92rem; line-height:1.5;'>
            This assistant retrieves verified factual details for the <b>5 HDFC Mutual Fund schemes</b> currently in scope. You can query about <i>NAV, exit loads, expense ratios, benchmark indexes, tax rules,</i> or <i>current fund managers</i>.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

# Sample Clickable Questions Section
st.markdown("<h3 style='font-size:1.1rem; color:#f3f4f6;'>Quick Example Queries:</h3>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

example_query = None

with col1:
    if st.button("📈 What is the exit load of HDFC Gold ETF?", use_container_width=True):
        example_query = "What is the exit load of HDFC Gold ETF?"
with col2:
    if st.button("👥 Who runs the HDFC Defence Fund?", use_container_width=True):
        example_query = "Who runs the HDFC Defence Fund?"
with col3:
    if st.button("⚠️ Should I buy HDFC Mid-Cap Fund?", use_container_width=True):
        example_query = "Should I buy HDFC Mid-Cap Fund?"

# Active query input handling
user_input = st.chat_input("Ask about HDFC schemes (e.g. exit load, managers, expense ratio)...")

# Trigger query execution if an example question button was clicked
active_query = example_query if example_query else user_input

if active_query:
    # Render user query card
    st.markdown(f'<div class="msg-user"><b>Query:</b> {active_query}</div>', unsafe_allow_html=True)
    
    # Process query
    with st.spinner("Retrieving verified facts..."):
        response = assistant.process_query(active_query)
    
    # Differentiate visual styling based on classification/refusal
    is_refusal = "I can only assist with objective" in response or "For security and privacy" in response or "I can only provide factual details" in response or "Please specify which HDFC" in response
    
    if is_refusal:
        # Refusal response layout
        st.markdown(
            f"""
            <div class="msg-assistant-refusal">
                <p style="margin-top:0; color:#ef4444; font-weight:600; font-family:'Outfit';">⛔ Request Refused</p>
                <p style="color:#f3f4f6; font-size:0.92rem; line-height:1.5; margin:0;">{response}</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        # Factual compliance response layout
        # Parse links and date footer for customized visual blocks
        lines = [line.strip() for line in response.split("\n") if line.strip()]
        
        main_text = ""
        source_url = ""
        footer_date = ""
        
        for line in lines:
            if "source:" in line.lower():
                source_url = line.replace("Source:", "").replace("source:", "").strip()
            elif "last updated" in line.lower():
                footer_date = line
            else:
                main_text = line
        
        st.markdown(
            f"""
            <div class="msg-assistant-factual">
                <p style="margin-top:0; color:#10b981; font-weight:600; font-family:'Outfit';">✅ Factual Answer</p>
                <p style="color:#f3f4f6; font-size:0.95rem; line-height:1.5; margin-bottom:0.8rem;">{main_text}</p>
                <div class="meta-block">
                    <span class="meta-link"><b>Official Source:</b> <a href="{source_url}" target="_blank">{source_url}</a></span>
                    <span>🕒 {footer_date}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
