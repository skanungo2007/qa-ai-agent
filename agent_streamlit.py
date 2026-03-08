import streamlit as st
from google import genai

# ==========================================
# 1. SETUP YOUR API KEY HERE
# ==========================================
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
# ==========================================

# 2. Web Page Setup & CSS for Justified Text
st.set_page_config(page_title="AI QA Architect", page_icon="🤖")

# This hidden block of CSS forces the text in our results to be justified
st.markdown("""
<style>
.justified-text {
    text-align: justify;
    text-justify: inter-word;
}
</style>
""", unsafe_allow_html=True)

st.title("🤖 QA Architect & Test Generator")
st.write("Upload a requirements document or paste your User Story below.")

# 3. Dynamic Inputs: Upload OR Paste
st.write("### Option 1: Upload Document")
uploaded_file = st.file_uploader("Upload a .txt, .pdf, or .docx file", type=["txt", "pdf", "docx"])

st.write("### Option 2: Paste Ticket Details")
user_ticket = st.text_area("Paste your text here:", height=150)

# 4. The Action
if st.button("Generate Tests Cases & Strategy"):
    
    # Extract text from the uploaded file (if there is one)
    document_text = ""
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.txt'):
                document_text = uploaded_file.read().decode('utf-8')
            elif uploaded_file.name.endswith('.pdf'):
                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                for page in pdf_reader.pages:
                    document_text += page.extract_text() + "\n"
            elif uploaded_file.name.endswith('.docx'):
                doc = docx.Document(uploaded_file)
                for para in doc.paragraphs:
                    document_text += para.text + "\n"
            st.success(f"Successfully read: {uploaded_file.name}")
        except Exception as e:
            st.error(f"Could not read the file. Error: {e}")
            
    # Combine the uploaded file text and the pasted text
    final_input = f"Document Context:\n{document_text}\n\nPasted Ticket:\n{user_ticket}".strip()
    
    # Check if they provided ANY input at all
    if len(final_input) < 20: # Make sure they didn't just type one word
        st.warning("Please upload a document or paste a detailed ticket first!")
    else:
        with st.spinner("Agent is analyzing the requirements and formulating a strategy..."):
            
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # --- THE BRAIN ---
            system_instruction = """
            You are an expert QA Automation Architect. 
            Read the provided User Story, requirements document, or Acceptance Criteria.

            PART 1: TEST CASES
            Generate comprehensive, structured test cases covering positive, negative, and edge cases.
            For each test case, include: Title, Pre-conditions, Steps, and Expected Result.

            PART 2: QA STRATEGY & SUMMARY
            After the test cases, create a distinct section titled "🧠 QA Strategy & Summary". 
            This section MUST include exactly these four sub-headings:
            
            1. Test Strategy: How should we approach testing this specific feature? 
            2. Automation Strategy: 
               - RULE: Unless the ticket mentions "Salesforce" or involves "heavy dynamic elements", you MUST suggest BOTH Selenium and Playwright as viable options and briefly compare them.
               - If it is Salesforce or highly dynamic, recommend the single best tool (e.g., Playwright) and explain why.
            3. Common QA Mistakes: What edge cases or negative scenarios do testers usually miss for this feature?
            4. Best Practices: 1 or 2 pro-tips for ensuring the automation scripts are robust.
            """
            
            full_prompt = f"{system_instruction}\n\nHere is the input data:\n{final_input}"
            
            # Call the AI
            response = client.models.generate_content(
                model="gemini-3-flash-preview", 
                contents=full_prompt
            )
            
            # 5. Display the result wrapped in our Justified CSS class
            st.success("Analysis Complete!")
            
            # Using HTML div to wrap the markdown ensures the text stretches evenly
            st.markdown(f'<div class="justified-text">\n\n{response.text}\n\n</div>', unsafe_allow_html=True)
