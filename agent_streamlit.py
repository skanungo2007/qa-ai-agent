import streamlit as st
from google import genai

# ==========================================
# 1. SETUP YOUR API KEY HERE
# ==========================================
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
# ==========================================

# 2. Web Page Setup
st.set_page_config(page_title="AI QA Architect", page_icon="🤖")
st.title("🤖 QA Architect & Test Generator")
st.write("Paste your User Story or Acceptance Criteria below to get test cases and strategy.")

# 3. Dynamic Input
user_ticket = st.text_area("Paste your Story/Ticket details here:", height=200)

# 4. The Action
if st.button("Generate Tests & Strategy"):
    
    if not user_ticket:
        st.warning("Please paste a ticket first!")
    else:
        with st.spinner("Agent is analyzing the ticket and formulating a strategy..."):
            
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # --- THE BRAIN WITH NEW RULES ---
            system_instruction = """
            You are an expert QA Automation Architect. 
            Read the provided User Story and Acceptance Criteria.

            PART 1: TEST CASES
            Generate comprehensive, structured test cases covering positive, negative, and edge cases.
            For each test case, include: Title, Pre-conditions, Steps, and Expected Result.

            PART 2: QA STRATEGY & SUMMARY
            After the test cases, create a distinct section titled "🧠 QA Strategy & Summary". 
            This section MUST include exactly these four sub-headings:
            
            1. Test Strategy: How should we approach testing this specific feature? (e.g., should we focus heavily on APIs, database validation, or UI testing?).
            2. Automation Strategy: 
               - RULE: Unless the ticket mentions "Salesforce" or involves "heavy dynamic elements", you MUST suggest BOTH Selenium and Playwright as viable options and briefly compare how they would handle this specific ticket.
               - If it is Salesforce or highly dynamic, recommend the single best tool (e.g., Playwright) and explain why.
            3. Common QA Mistakes: What edge cases or negative scenarios do testers usually miss for this specific type of feature?
            4. Best Practices: 1 or 2 pro-tips for ensuring the automation scripts for this feature are robust and maintainable.
            """
            
            full_prompt = f"{system_instruction}\n\nHere is the ticket:\n{user_ticket}"
            
            # Call the AI
            response = client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=full_prompt
            )
            
            st.success("Analysis Complete!")
            st.markdown(response.text)