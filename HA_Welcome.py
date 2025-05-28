import streamlit as st
from openai import OpenAI
import os
import json
from datetime import datetime
import pandas as pd
from openpyxl import load_workbook
from fpdf import FPDF
import ast
import PyPDF2
import docx




# Configuration
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])  # Use Streamlit secrets or env vars

st.set_page_config(page_title="Onboarding Form", layout="centered")

st.title("Welcome to Heyman Advisors!")
st.text("This is your Heyman Advisors onboarding Form. Please fill this out prior to your onboarding meeting.")

# Functions

def extract_and_clean_vendors(field_label, raw_text):
    prompt = f"""
You are a data cleaning assistant. Your job is to extract and standardize vendor names from text fields.
Field: {field_label}
Raw Input: "{raw_text}"

Return a list of clean, distinct vendor names mentioned in the input. Use proper casing and official names when possible.
Example output format: ["SmartCAMA", "EagleView", "Tyler Technologies"]
Only output the list.
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content.strip()

def extract_text_from_file(uploaded_file):
    if uploaded_file.name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(uploaded_file)
        return "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
    elif uploaded_file.name.endswith(".docx"):
        doc = docx.Document(uploaded_file)
        return "\n".join([para.text for para in doc.paragraphs])
    else:
        return f"[Unsupported file type: {uploaded_file.name}]"

def save_to_excel(data_dict, file_path="submissions/onboarding_data.xlsx"):
        df = pd.DataFrame([data_dict])
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        if not os.path.exists(file_path):
            # New file with headers
            df.to_excel(file_path, index=False)
        else:
            book = load_workbook(file_path)
            writer = pd.ExcelWriter(file_path, engine='openpyxl')
            writer.book = book
            writer.sheets = {ws.title: ws for ws in book.worksheets}
            existing_df = pd.read_excel(file_path)

            # Add missing columns (from new vendor types)
            for col in df.columns:
                if col not in existing_df.columns:
                    existing_df[col] = None  # initialize new column

            # Ensure all submission columns are aligned
            for col in existing_df.columns:
                if col not in df.columns:
                    df[col] = None

            final_df = pd.concat([existing_df, df], ignore_index=True)
            final_df.to_excel(writer, index=False)
            writer.close()


def clean_vendor_name(vendor_name):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You're a data cleaner that standardizes and deduplicates vendor names."},
            {"role": "user", "content": f"Clean and standardize this vendor name: '{vendor_name}'"}
        ]
    )
    return response.choices[0].message.content.strip()

def generate_pdf(roadmap_text, output_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.multi_cell(0, 10, roadmap_text)
    pdf.output(output_path)

def categorize_vendors_with_ai(all_vendor_text):
    prompt = f"""
You're an AI assistant helping categorize vendor types from onboarding form submissions. 
Below is a block of text from multiple vendor fields. Return a dictionary mapping **vendor category** 
(e.g., "CAMA Vendor", "Imagery Vendor", "Website Vendor", "Other") to a list of vendor names.

Input:
{all_vendor_text}

Output format:
{{
  "CAMA Vendor": ["SmartCAMA"],
  "Imagery Vendor": ["EagleView"],
  "Website Vendor": ["Revize"],
  "Other Vendor": ["GISinc", "Spatial Data Logic"],
  "Mapping Vendor": ["MapLogic"]
}}
Only return a valid Python dictionary.
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )

    # Safely evaluate the string response as a Python dictionary
    try:
        return ast.literal_eval(response.choices[0].message.content.strip())
    except Exception as e:
        st.error(f"AI returned malformed dictionary: {e}")
        return {}

# --- 1. Office Info ---
st.header("Office Information")
office_name = st.text_input ("Office Name")
office_cnty = st.text_input("Office County/Parish")
# Office State dropdown
states = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
    "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan",
    "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina",
    "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
    "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"
]

office_state = st.selectbox("Office State", states)
contact_person = st.text_input("Primary Contact Person")
email = st.text_input("Email Address")
phone = st.text_input("Phone Number")

# --- 2. Current Technology Stack ---
st.header("Current Technology and Products")
software_CAMA = st.text_input("What CAMA Sytem does your office use (company and product)? If custom system please enter 'custom.'")
software_imagery = st.text_input("What Imagery products (Aerial, Oblique, Street-Level, etc) do you use?")
provider_web = st.text_input("Who does your website? If done in-house, enter 'in-house.'")
other_providers = st.text_area("What other providers does your office contract with that you want us to be aware of? Please list and describe.")
other_issues = st.text_area("What issues or concerns would you like to make sure we cover on our first meeting?")
# --- 3. File Uploads ---
st.header("Vendor Contracts")
uploaded_files = st.file_uploader("Please share any current vendor contracts you'd like to put on our radar. This will help is familiarize ourselves with renewal dates, costs, products, etc.", accept_multiple_files=True)

# --- 4. Submit ---
if st.button("Submit"):

    # Use AI to extract texts from uploaded files
    uploaded_file_text = ""

    if uploaded_files:
        st.info(f"{len(uploaded_files)} file(s) uploaded. Analyzing...")
        for file in uploaded_files:
            uploaded_file_text += f"\n\n--- Content from {file.name} ---\n"
            uploaded_file_text += extract_text_from_file(file)

    # Use AI to extract and clean vendor names from open-ended fields
    cleaned_CAMA = extract_and_clean_vendors("CAMA System", software_CAMA)
    cleaned_imagery = extract_and_clean_vendors("Imagery", software_imagery)
    cleaned_web = extract_and_clean_vendors("Website Vendor", provider_web)
    cleaned_other = extract_and_clean_vendors("Other Providers", other_providers)

    def list_str_to_string(vendor_list_str):
        try:
            vendor_list = ast.literal_eval(vendor_list_str)
            return ", ".join(vendor_list)
        except:
            return vendor_list_str  # fallback if parsing fails
        
    # Step 1: Combine all vendor-related inputs into one blob
    combined_vendors_text = f"""
    CAMA: {software_CAMA}
    Imagery: {software_imagery}
    Website: {provider_web}
    Other: {other_providers}
    """    
    # Step 2: Let AI categorize vendors by type
    vendor_categories = categorize_vendors_with_ai(combined_vendors_text)
    
    # Step 3: Convert all fields to plain text for Excel entry
    flat_vendor_data = {k: ", ".join(v) for k, v in vendor_categories.items()}
    
    # Save input data
    submission = {
        "timestamp": datetime.now().isoformat(),
        "office_cnty" : office_cnty,
        "office_state": office_state,
        "contact_person": contact_person,
        "email": email,
        "phone": phone,
        "software_CAMA": list_str_to_string(cleaned_CAMA),
        "software_imagery": list_str_to_string(cleaned_imagery),
        "provider_web": list_str_to_string(cleaned_web),
        "other_providers": list_str_to_string(cleaned_other),
        "other_issues" : other_issues,
        "uploaded_files": [file.name for file in uploaded_files]
    }

    # Step 5: Merge the vendor columns into submission
    submission.update(flat_vendor_data)

    st.success("Form submitted successfully! An advisor will follow up shortly.")

    # AI Summary Generation
    with st.spinner("Generating roadmap..."):
        prompt = f"""You are a consulting AI working for a firm that helps local appraiser offices. 
        The office '{office_name}' has reported the following pain points: {other_issues}. 
        They use: {(software_CAMA, software_imagery, provider_web, other_providers)}. Their key contracts are {uploaded_files}.
        Draft a roadmap summary of what they have so far, with key areas for improvement. f"Based on the following onboarding information and attached documents, create a high-level technology roadmap "
        f"for a county appraisal district. Be sure to consider contract terms, current vendors, challenges, and opportunities.\n\n"
        f"Form submission data:\n{json.dumps(submission, indent=2)}\n\n"
        f"Contract and document contents:\n{uploaded_file_text}"""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        roadmap = response.choices[0].message.content.strip()
        st.subheader("Draft Roadmap")

        pdf_filename = f"roadmap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = f"submissions/{pdf_filename}"
        generate_pdf(roadmap, output_path=pdf_path)
        st.success(f"PDF roadmap saved to {pdf_path}")


