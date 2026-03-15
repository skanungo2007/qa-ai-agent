import os
import time
import requests
import PyPDF2
import docx
from bs4 import BeautifulSoup
import streamlit as st
from google import genai
from dotenv import load_dotenv

# Load local .env file if it exists (ignored by Streamlit Cloud)
load_dotenv()

# ==========================================
# 1. SETUP YOUR API KEY HERE
# ==========================================
# Try fetching from Streamlit Cloud Secrets first
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except (KeyError, FileNotFoundError):
    # If it fails (meaning you are running locally), fallback to .env
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error("🚨 API Key Missing! Please add it to Streamlit Secrets or your local .env file.")
    st.stop()
# ==========================================

# 2. Web Page Setup & Custom Enterprise CSS
st.set_page_config(page_title="QA-360", page_icon="🤖", layout="wide")

st.markdown("""
<style>
/* Main Headers & Titles */
h1 { color: #1E88E5; padding-bottom: 10px; border-bottom: 2px solid #1E88E5; font-weight: 700; }
h2 { color: #00897B; margin-top: 20px; font-weight: 600; }
h3 { color: #E53935; margin-top: 15px; font-weight: 600; }

/* Justified text for strategy */
.justified-text { 
    text-align: justify; 
    text-justify: inter-word; 
    font-size: 16px; 
    line-height: 1.6;
    color: #333333;
}

/* --- DYNAMIC COLUMN TABLE STYLING --- */
table { 
    width: 100% !important; 
    border-collapse: collapse; 
    margin: 20px 0; 
    font-size: 15px; 
    table-layout: auto !important; /* Changed from fixed to auto to fix vertical stretching */
}

th { 
    background-color: #1E88E5 !important; 
    color: white !important; 
    padding: 12px; 
    text-align: left; 
    white-space: nowrap; /* Keeps headers from wrapping awkwardly */
}

td { 
    padding: 10px; 
    border-bottom: 1px solid #ddd; 
    vertical-align: top; 
    word-wrap: break-word; 
    overflow-wrap: break-word;
    white-space: normal; 
}

/* Specific Column Proportions using min-width for stability */
th:nth-child(1), td:nth-child(1) { min-width: 65px; width: 5%; }   /* Test ID */
th:nth-child(2), td:nth-child(2) { min-width: 150px; width: 20%; }  /* Test Title */
th:nth-child(3), td:nth-child(3) { min-width: 120px; width: 15%; }  /* Pre-conditions */
th:nth-child(4), td:nth-child(4) { min-width: 250px; width: 30%; }  /* Steps */
th:nth-child(5), td:nth-child(5) { min-width: 250px; width: 30%; }  /* Expected Result */

tr:hover { background-color: #f5f5f5; }

/* Subtle background for success messages */
.stSuccess { background-color: #E8F5E9; border-left: 5px solid #4CAF50; }

/* ========================================= */
/* MOBILE & LANDSCAPE SPECIFIC CSS */
/* ========================================= */
.mobile-banner { display: none; }

@media (max-width: 992px) {
    .mobile-banner { 
        display: block !important; 
        background-color: #E3F2FD; 
        color: #0D47A1;
        padding: 12px; 
        border-radius: 8px; 
        margin-bottom: 15px; 
        border-left: 5px solid #1E88E5; 
        font-size: 14px;
    }

    .justified-text { 
        text-align: left !important; 
        font-size: 14px; 
    }

    /* Force horizontal scroll on mobile to maintain readability */
    table { 
        display: block; 
        overflow-x: auto; 
        -webkit-overflow-scrolling: touch;
    }
}
</style>
""", unsafe_allow_html=True)

# Initialize Session State Variables for Memory & Intelligence
if "generated_strategy_output" not in st.session_state:
    st.session_state.generated_strategy_output = None
if "module1_chat_history" not in st.session_state:
    st.session_state.module1_chat_history = []
if "module1_reqs" not in st.session_state:
    st.session_state.module1_reqs = ""

# Initialize Session State Variables for Memory & Intelligence
if "generated_framework" not in st.session_state:
    st.session_state.generated_framework = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "base_url" not in st.session_state:
    st.session_state.base_url = ""
if "automation_desc" not in st.session_state:
    st.session_state.automation_desc = ""
if "page_context" not in st.session_state:
    st.session_state.page_context = ""

# 3. Welcome Message & Navigation
st.title("🤖 QA-360 Command Center")

# --- SMART MOBILE BANNER (Only renders visually on phone screens) ---
st.markdown('<div class="mobile-banner">📱 <b>Mobile View Active:</b> Swipe left and right on tables or code blocks to view the full content!</div>', unsafe_allow_html=True)

st.markdown("### Welcome to your intelligent QA Architect. Select a capability below:")

app_mode = st.radio(
    "Select an action:",
    ("Generate Test Cases and Test Strategy", "Generate Automation Framework (Cucumber/Java)"),
    label_visibility="collapsed"
)

st.write("---")

client = genai.Client(api_key=GEMINI_API_KEY)

# =====================================================================
# MODULE 1: Generate Test Cases and Test Strategy
# =====================================================================
if app_mode == "Generate Test Cases and Test Strategy":
    st.header("📝 Test Cases & QA Strategy")
    st.write("Provide the requirements using any of the methods below.")

    # 1. NEW UI: Three columns for the three input methods
    col1, col2, col3 = st.columns(3)
    with col1:
        uploaded_file = st.file_uploader("Upload Document (.txt, .pdf, .docx)", type=["txt", "pdf", "docx"])
    with col2:
        user_ticket = st.text_area("Paste Ticket Details:", height=100)
    with col3:
        jira_link = st.text_input("Jira Ticket URL (Requires API Setup):", placeholder="https://company.atlassian.net/browse/PROJ-123")

    # --- NEW FUNCTION: Secure Jira API Fetcher ---
    def fetch_jira_ticket(url):
        jira_token = os.environ.get("JIRA_API_TOKEN")
        jira_email = os.environ.get("JIRA_EMAIL")
        
        if not jira_token or not jira_email:
            return "JIRA_AUTH_MISSING"
            
        try:
            # Extract the base URL and the Issue Key (e.g., PROJ-123) from the link
            base_url = url.split('/browse/')[0]
            issue_key = url.split('/browse/')[1].split('?')[0] # Strips any URL parameters
            api_url = f"{base_url}/rest/api/2/issue/{issue_key}"
            
            headers = {"Accept": "application/json"}
            # The API call using Basic Auth
            response = requests.get(api_url, auth=(jira_email, jira_token), headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                summary = data['fields'].get('summary', 'No Summary')
                description = data['fields'].get('description', 'No Description')
                return f"Jira Summary: {summary}\n\nJira Description: {description}"
            elif response.status_code == 401 or response.status_code == 403:
                return "Error: Authentication failed. Check your Jira API Token and Email."
            else:
                return f"Error: Could not fetch Jira ticket. Status {response.status_code}"
        except Exception as e:
            return f"Error connecting to Jira: {str(e)}"

    # 2. Check if strategy is already generated to disable the button
    is_strategy_generated = st.session_state.generated_strategy_output is not None
    
    if st.button("Generate Strategy & Test Cases", type="primary", disabled=is_strategy_generated):
        document_text = ""
        
        # Process Uploaded File
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
                st.toast(f"Successfully read: {uploaded_file.name}", icon="✅")
            except Exception as e:
                st.error(f"Could not read the file. Error: {e}")
                
        # Process Jira Link
        jira_content = ""
        jira_error = False
        if jira_link.startswith("http"):
            result = fetch_jira_ticket(jira_link)
            if result == "JIRA_AUTH_MISSING":
                st.warning("⚠️ Jira Integration Warning: JIRA_API_TOKEN or JIRA_EMAIL is missing. Skipping Jira fetch.")
                jira_error = True
            elif result.startswith("Error"):
                st.error(f"⚠️ {result}")
                jira_error = True
            else:
                jira_content = result
                st.toast("Successfully fetched Jira ticket data!", icon="✅")

        # Combine all inputs
        final_input = f"Document Context:\n{document_text}\n\nPasted Ticket:\n{user_ticket}\n\nJira Data:\n{jira_content}".strip()
        
        clean_input = final_input.replace("Document Context:", "").replace("Pasted Ticket:", "").replace("Jira Data:", "").strip()
        
        if len(clean_input) < 10 or clean_input.replace(" ", "").replace("\n", "").isdigit(): 
            if not jira_error:
                st.error("❌ Validation Failed: Please upload a valid document, paste detailed requirements, or provide a configured Jira link.")
        else:
            # Save original requirements to memory for the chat
            st.session_state.module1_reqs = final_input
            st.session_state.module1_chat_history = []
            
            with st.status("🧠 QA-360 is analyzing requirements...", expanded=True) as status:
                progress_bar = st.progress(0, text="Initializing Analysis Engines... (ETA: ~60 seconds)")
                
                try:
                    st.write("⏳ Parsing document, tickets, and user stories...")
                    progress_bar.progress(20, text="Cross-referencing multiple data sources... (ETA: ~30 seconds)")
                    time.sleep(0.8)
                    
                    st.write("⏳ Hunting for requirement contradictions...")
                    progress_bar.progress(40, text="Formulating Deep Automation Strategy... (ETA: ~30 seconds)")
                    time.sleep(0.8)
                    
                    st.write("⏳ Drafting Exhaustive Test Cases...")
                    progress_bar.progress(75, text="Awaiting AI Architect & Business Analyst... (ETA: ~30-60 seconds depending on complexity)")
                    
                    # --- UPGRADED AI BRAIN: CONTRADICTION ENGINE & PRO QA STANDARDS ---
                    system_instruction = """
                    You are QA-360, a Senior QA Automation Architect and Lead Business Analyst.
                    
                    CRITICAL VALIDATION STEP:
                    Before doing anything else, read the provided requirements. If the text is obvious gibberish, random keyboard mashing, a random string of unrelated words, or completely lacks any coherent software/system context, you MUST immediately output exactly this:
                    ### ❌ Validation Failed
                    **The provided text or document does not contain coherent software requirements or user stories. Please provide valid details to generate test cases.**
                    
                    CROSS-REFERENCE & CONTRADICTION CHECK:
                    The user might provide requirements from multiple sources (a Document, a Pasted Ticket, and a Jira Data pull). 
                    1. You MUST cross-reference all provided data.
                    2. Look for any conflicting information.
                    3. If contradictions exist, you MUST start your response with a highly visible `⚠️ REQUIREMENT CONFLICTS` header and explicitly list the discrepancies found. 
                    4. If no contradictions exist, proceed normally without mentioning this check.
                    
                    If the input IS valid, formulate a bulletproof QA approach and follow this STRICT OUTPUT ORDER using these exact formatting headers:

                    ## 🧠 Section 1: User Intent & Analyst Review
                    - Explain exactly what the user is asking to test.
                    - Briefly summarize the core features, the target audience, and the main goal of the testing effort.

                    ## 📝 Section 2: Comprehensive Test Cases
                    Create exhaustive test cases separated into THREE distinct Markdown Tables (Positive, Negative, Edge).
                    
                    STRICT NAMING, PERMUTATION & QUALITY RULES:
                    1. Test IDs: You MUST use a sequential ID format starting with `TC-01`, `TC-02`, etc. Do not restart the numbering for the next table.
                    2. Professional Titles: The 'Test Title' MUST clearly state the objective and begin with "Verify that...". 
                    3. SMART BOUNDARY VALUE ANALYSIS (BVA): When given a constraint range (e.g., 8-16 characters), intelligently test both VALID boundaries (e.g., exactly 8, exactly 16) AND INVALID boundaries (e.g., 7, 17). Title them intelligently (e.g., "Verify registration fails when password is below minimum length of 8 chars").
                    4. EXHAUSTIVE PERMUTATION TESTING: Isolate variables. If a password needs uppercase, lowercase, special, and number, write separate negative tests for missing each one individually.
                    5. Volume Mandate: Generate at least 15 to 20 total test cases when specific constraints are provided. Do not be lazy.

                    CRITICAL STEP & RESULT MAPPING RULES (ZERO AMNESIA RULE):
                    1. 1-to-1 Mapping: For EVERY single step in the 'Steps' column, there MUST be exactly one corresponding numbered entry in the 'Expected Result' column.
                    2. NO SHORTCUTS: Every single test case MUST start from the absolute beginning. Step 1 MUST ALWAYS be "1. Open browser and navigate to URL". Step 2 MUST be the next navigational click (e.g., "2. Click on Profile Icon"). NEVER start a test step with "Enter data" without navigating there first. You will be heavily penalized for skipping foundational steps in later test cases.
                    3. Formatting: Inside the 'Steps' and 'Expected Result' columns, you MUST use HTML `<br>` tags to separate the numbered items (e.g., `1. Open Browser <br> 2. Click Login`). Do NOT write multiple steps on a single line.

                    ### ✅ Positive Scenarios
                    | Test ID | Test Title | Pre-conditions | Steps | Expected Result |
                    
                    ### ❌ Negative Scenarios
                    | Test ID | Test Title | Pre-conditions | Steps | Expected Result |
                    
                    ### ⚠️ Edge Cases
                    | Test ID | Test Title | Pre-conditions | Steps | Expected Result |

                    ## ♟️ Section 3: Deep Enterprise QA Strategy
                    Include exactly these sub-sections:
                    1. Functional Test Strategy
                    2. Automation Feasibility & Approach
                    3. Risk Assessment & Blind Spots
                    4. Test Data Requirements

                    ## 💡 Section 4: Testing Best Practices
                    - Provide a concise list of 4-5 professional best practices specific to testing this feature.
                    """

                    full_prompt = f"{system_instruction}\n\nHere are the requirements:\n{final_input}"
                    
                    response = client.models.generate_content(
                        model="gemini-3-flash-preview", 
                        contents=full_prompt
                    )
                    
                    st.session_state.generated_strategy_output = response.text
                    
                    progress_bar.progress(100, text="✅ Analysis Complete! (ETA: 0s)")
                    status.update(label="✅ Strategy & Test Cases Generated!", state="complete", expanded=False)

                    # Force Streamlit to redraw the page instantly
                    st.rerun()
                    
                except Exception as e:
                    status.update(label="❌ API Error", state="error", expanded=True)
                    if 'progress_bar' in locals():
                        progress_bar.empty()
                    error_msg = str(e)
                    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                        st.error("⏳ **API Rate Limit Reached!** QA-360 is processing too much data. Please wait a moment or check your API billing plan.")
                    else:
                        st.error(f"❌ An error occurred: {error_msg}")
            

   # ==========================================
    # DISPLAY OUTPUT & INTELLIGENT CHAT (MODULE 1)
    # ==========================================
    if st.session_state.generated_strategy_output:
        st.markdown(f'<div class="justified-text">\n\n{st.session_state.generated_strategy_output}\n\n</div>', unsafe_allow_html=True)
        
        st.markdown("<br><hr><br>", unsafe_allow_html=True)
        st.header("💬 Refine & Modify QA Strategy")
        st.write("I remember your original requirements. Ask me to add new scenarios, change the strategy, or explain a test case!")

        for msg in st.session_state.module1_chat_history:
            with st.chat_message(msg["role"]):
                # --- CHANGE 1: Apply CSS to chat history so previous tables don't shrink ---
                if msg["role"] == "assistant":
                    st.markdown(f'<div class="justified-text">\n\n{msg["content"]}\n\n</div>', unsafe_allow_html=True)
                else:
                    st.markdown(msg["content"])

        if prompt := st.chat_input("E.g., Add 3 more edge cases for the session timeout scenario."):
            clean_prompt = prompt.strip()
            if len(clean_prompt) < 4 or clean_prompt.replace(" ", "").isdigit():
                st.warning("⚠️ Validation Failed: Please provide a clear, meaningful request. Random characters or numbers are not accepted.")
            else:
                with st.chat_message("user"):
                    st.markdown(prompt)
                st.session_state.module1_chat_history.append({"role": "user", "content": prompt})

                with st.chat_message("assistant"):
                    try:
                        chat_progress = st.progress(0, text="QA-360 is analyzing your request... 0%")
                        
                        for percent in range(10, 86, 15):
                            time.sleep(0.15)
                            chat_progress.progress(percent, text=f"QA-360 is updating the strategy... {percent}%")

                        # YOUR INSTRUCTIONS REMAIN UNTOUCHED BELOW
                        chat_context = f"""
                        You are QA-360, a Senior QA Automation Architect and Lead Business Analyst.
                        The user originally provided these requirements: 
                        {st.session_state.module1_reqs}

                        Here is the QA Strategy and Test Cases you previously generated:
                        {st.session_state.generated_strategy_output}

                        The user has follow-up requests. 

                        CRITICAL INSTRUCTIONS FOR YOUR RESPONSE:
                        1. Contradiction Check: Analyze if the user's new request contradicts the original requirements. If it does, you MUST explicitly warn them with a `⚠️ REQUIREMENT CONFLICT` note, but proceed to update the test cases/strategy based on their new instructions anyway.
                        2. Updates: Only regenerate the sections that need changing. Do not rewrite the entire document unless asked.
                        3. Strict Formatting & Zero Amnesia: Maintain the EXACT same formatting rules as before. If the user adds constraints, you MUST use Smart Boundary Value Analysis (testing valid and invalid boundaries) and isolate variables. EVERY test case must start with "1. Open browser and navigate to URL". Do not take shortcuts. Test IDs must be sequential (TC-01, etc.), steps/results must be 1-to-1 using `<br>` tags, and tables must be split into Positive, Negative, and Edge.
                        
                        STRICT OUTPUT FORMATTING:
                        You MUST format your response using these exact markdown headers:

                        ### 🧠 User Intent & Analyst Review
                        (Explain what the user is asking. Detail any contradictions here if found.)

                        ### 📝 Updated Test Cases (Only output this if test cases were added/modified)
                        (Provide the updated Markdown tables here using the exact columns and `<br>` rules.)

                        ### ♟️ Updated QA Strategy (Only output this if the strategy was modified)
                        (Provide the updated strategy here.)

                        Conversation History:
                        """
                        for msg in st.session_state.module1_chat_history:
                            chat_context += f"{msg['role'].capitalize()}: {msg['content']}\n"
                        
                        chat_response = client.models.generate_content(
                            model="gemini-3-flash-preview", 
                            contents=chat_context
                        )
                        
                        chat_progress.progress(100, text="✅ Update Complete! 100%")
                        time.sleep(0.5)
                        chat_progress.empty()
                        
                        # --- CHANGE 2: Apply CSS to the brand new chat response ---
                        st.markdown(f'<div class="justified-text">\n\n{chat_response.text}\n\n</div>', unsafe_allow_html=True)
                        st.session_state.module1_chat_history.append({"role": "assistant", "content": chat_response.text})
                        

                    except Exception as e:
                        if 'chat_progress' in locals():
                            chat_progress.empty()
                        st.error(f"Chat error occurred: {e}")



# =====================================================================
# MODULE 2: Generate Automation Framework Code + Intelligent Chat
# =====================================================================
elif app_mode == "Generate Automation Framework (Cucumber/Java)":
    st.header("☕ BDD Automation Framework Builder")
    st.write("Provide the target URL and describe the user flow to generate a complete framework.")

    base_url = st.text_input("Base URL:", placeholder="e.g., https://opensource-demo.orangehrmlive.com/")
    automation_desc = st.text_area(
        "Description of flow to automate:", 
        height=100, 
        placeholder="e.g., Navigate to login, enter valid credentials, verify the dashboard appears."
    )

    def is_url_valid(url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5, verify=False)
            return True 
        except requests.exceptions.RequestException:
            return False

    # --- NEW FUNCTION: Fetch the HTML and extract visible text/links ---
    # --- UPGRADED FUNCTION: Fetch HTML and extract ALL interactive elements ---
    def get_page_context(url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            requests.packages.urllib3.disable_warnings() 
            response = requests.get(url, headers=headers, timeout=10, verify=False)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title = soup.title.string if soup.title else "No Title Found"
            elements = []
            
            # 1. Grab Links and Buttons
            for a in soup.find_all('a'):
                text = a.get_text(strip=True)
                if text: elements.append(f"Link: {text}")
                
            for btn in soup.find_all('button'):
                text = btn.get_text(strip=True)
                if text: elements.append(f"Button: {text}")
                
            # 2. Grab Input Fields (Text boxes, Checkboxes, Radio buttons)
            for input_tag in soup.find_all('input'):
                i_type = input_tag.get('type', 'text')
                i_id = input_tag.get('id', '')
                i_name = input_tag.get('name', '')
                i_placeholder = input_tag.get('placeholder', '')
                
                # Try to find a meaningful name for the input
                desc = next((x for x in [i_placeholder, i_name, i_id] if x), "unnamed")
                elements.append(f"Input ({i_type}): {desc}")
                
            # 3. Grab Dropdowns
            for select in soup.find_all('select'):
                s_id = select.get('id', select.get('name', 'unnamed'))
                elements.append(f"Dropdown: {s_id}")
                
            # 4. Grab Text Areas
            for textarea in soup.find_all('textarea'):
                t_id = textarea.get('id', textarea.get('name', textarea.get('placeholder', 'unnamed')))
                elements.append(f"Text Box: {t_id}")

            # Remove duplicates to keep the list clean
            unique_elements = list(dict.fromkeys(elements))
            
            context = f"Page Title: {title}\nInteractive Elements on Page:\n" + "\n".join(unique_elements)
            
            # Expand the limit to 15,000 characters to capture massive enterprise pages
            return context[:15000] 
            
        except Exception as e:
            return "Could not extract page context. The page might be heavily JavaScript-rendered or protected."

    # Check if a framework has already been generated
    is_generated = st.session_state.generated_framework is not None

    # Pass the disabled state to the button
    if st.button("Generate Framework Code", type="primary", disabled=is_generated):
        if len(automation_desc.split()) < 5:
            st.error("❌ Validation Failed: Your description is too short. Please provide a detailed flow.")
        elif not base_url.startswith("http"):
            st.error("❌ Validation Failed: Please provide a valid URL starting with http:// or https://")
        elif not is_url_valid(base_url):
             st.error(f"❌ Validation Failed: The URL '{base_url}' is not reachable or timed out. Please check the link.")
        else:
            st.session_state.base_url = base_url
            st.session_state.automation_desc = automation_desc
            st.session_state.chat_history = []
            
            # --- THE RESTORED STATUS BOX WITH PROGRESS BAR & ETA ---
            with st.status("🏗️ QA-360 is building your framework...", expanded=True) as status:
                # 1. Add the progress bar at the very top of the status box
                progress_bar = st.progress(0, text="Initializing Engines... (ETA: ~90 seconds)")
                
                try:
                    # Step 1: Scrape
                    st.write("⏳ Fetching live page context for validation...")
                    progress_bar.progress(15, text="Validating URL & Scraping UI Elements... (ETA: ~20 seconds)")
                    scraped_context = get_page_context(base_url)
                    st.session_state.page_context = scraped_context 
                    time.sleep(0.5) # Tiny pause for visual flow
                    
                    # Step 2: Setup
                    st.write("⏳ Initializing Base Class and Utilities...")
                    progress_bar.progress(35, text="Configuring WebDriver & Hooks... (ETA: ~20 seconds)")
                    time.sleep(0.5)
                    
                    # Step 3: Drafting
                    st.write("⏳ Drafting Feature files and Step Definitions...")
                    progress_bar.progress(65, text="Mapping Scraped Elements to Locators... (ETA: ~20 seconds)")
                    time.sleep(0.5)
                    
                    # Step 4: AI Generation
                    st.write("⏳ Creating Page Objects with Selenium 4 locators...")
                    progress_bar.progress(85, text="Awaiting AI Architect... (ETA: ~30-90 seconds depending on complexity)")
                    
                    system_instruction_code = """
                You are QA-360, an Expert Automation Architect.
                Generate a complete, production-ready Java/Selenium/Cucumber framework. 
                Use Markdown code blocks and label filenames clearly.

                CRITICAL RULE - STRICT OUTPUT ORDER:
                You MUST generate your response in the exact sequential order of the sections listed below (Section 0 through Section 11). Do NOT output dependencies or setup instructions at the top.

                SECTION 1: Intent Analysis & Element Mapping
                - First, analyze the 'User Flow Description' and clearly explain the user's overall intent.
                - Second, cross-reference the user's requested actions with the 'Live Page Context'.
                - Explicitly list out how you are mapping their requests to the actual scraped elements (e.g., "User wants to click 'Profile' -> Mapping to the 'User Account' link found on page").
                - If a requested element clearly does NOT exist in the Live Page Context, you MUST throw a highly visible `⚠️ VALIDATION WARNING` in this section.

                CRITICAL TECHNOLOGY STACK RULES:
                - You MUST generate code using Selenium 4 methods and syntax.
                - Do not use deprecated Selenium 3 approaches.

                SECTION 2: config.properties
                - Define `browser` and `url`.

                SECTION 3: BaseClass.java
                - ThreadLocal WebDriver implementation.
                - Method to read config.properties.
                - `initializeDriver()` (read browser, launch, maximize, set implicit wait).
                - `getDriver()` and `quitDriver()`.

                SECTION 4: Utilities.java (Helper Class)
                - Provide comprehensive methods: waitForElementVisible(), scrollToElement(), scrollPageDown(), clickElement(), enterText(), uploadFile(), waitAndClick(), clickViaJS(), waitForElementInvisible(), and selectDropdown().

                SECTION 5: Hooks.java
                - Connect to BaseClass for setup (@Before) and teardown/screenshots (@After).

                SECTION 6: BDD Feature File (.feature)
                - Professional Gherkin file covering the user flow. Include tags (e.g., @smoke).

                SECTION 7: Page Object Model Classes (Java)
                - Use @FindBy (PageFactory). Utilize Utilities.java for all actions. Ensure locators match the analysis from Section 0.

                SECTION 8: Step Definitions (Java)
                - Map to Feature file. Instantiate POM using BaseClass.getDriver().

                SECTION 9: TestRunner.java
                - Extend AbstractTestNGCucumberTests. Include plugins for HTML and JSON reporting.

                SECTION 10: Framework Directory Structure
                - Provide a dynamic ASCII text tree diagram.
                - STRICT RULES: 
                  1. The root node MUST be the project name (e.g., `QA360_Automation_Framework`). Do NOT use a dot (`.`).
                  2. Use proper nested indentation (`├──` and `└──`). Do not flatten the tree.
                  3. Every single generated file must be on its own line. Do NOT use commas.

                SECTION 11: Setup & Execution Guidelines
                Format exactly as follows:
                
                1. Add Dependencies (pom.xml)
                First, output exactly this text:
                "Add the following to your Maven project:
                - selenium-java
                - cucumber-java
                - cucumber-testng
                - maven-surefire-plugin (for CLI execution)"
                
                Then, output the actual `<dependencies>` XML block containing these specific dependencies (use Java 17+, Maven 3.8.5+, Selenium 4+).
                
                2. Setup 
                - Install Java 17+ and Maven 3.8.5+.
                - Open the project in IntelliJ or Eclipse as a Maven project.
                - Provide instructions regarding how to create the project structure shown in SECTION 10 in IntelliJ and Eclipse
                
                3. Execution & Reporting
                - Option A: IDE (Right-click TestRunner.java and select "Run").
                - Option B: Terminal -> `mvn clean install`
                - Option C: Specific Tag -> `mvn clean test -Dcucumber.filter.tags="@smoke"`
                
                4. Framework Best Practices
                - Provide 4-5 professional guidelines.

                SECTION 12: README.md
                - Generate a comprehensive, professional `README.md` file in a Markdown code block.
                """
                    
                    full_prompt_code = f"{system_instruction_code}\n\nLive Page Context:\n{scraped_context}\n\nBase URL: {base_url}\n\nUser Flow Description:\n{automation_desc}"
                    
                    response_code = client.models.generate_content(
                        model="gemini-3-flash-preview", 
                        contents=full_prompt_code
                    )
                    
                    st.session_state.generated_framework = response_code.text
                    
                    # Finalize the progress and status
                    progress_bar.progress(100, text="✅ Generation Complete! (ETA: 0s)")
                    status.update(label="✅ Framework Generation Complete!", state="complete", expanded=False)

                    # 2. Force Streamlit to redraw the page instantly
                    st.rerun()
                    
                except Exception as e:
                    status.update(label="❌ Error occurred", state="error", expanded=True)
                    progress_bar.empty() # Hide the progress bar if it crashes
                    st.error(f"An error occurred: {e}")
            
                
        

    # ==========================================
    # DISPLAY GENERATED CODE & INTELLIGENT CHAT
    # ==========================================
    if st.session_state.generated_framework:
        st.markdown(st.session_state.generated_framework)
        
        st.markdown("<br><hr><br>", unsafe_allow_html=True)
        st.header("💬 Refine & Modify with QA-360")
        st.write("I remember your original URL, requirements, and the live page context. Ask me to modify the code, add new methods, or explain any section!")

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("E.g., Update the POM class to include a 'Forgot Password' locator and method."):
            with st.chat_message("user"):
                st.markdown(prompt)
            st.session_state.chat_history.append({"role": "user", "content": prompt})

            with st.chat_message("assistant"):
                try:
                    # 1. Initialize the clean progress bar
                    chat_progress = st.progress(0, text="QA-360 is analyzing your request... 0%")
                    
                    # 2. Simulate rapid progress to 85% to show activity
                    for percent in range(10, 86, 15):
                        time.sleep(0.15)
                        chat_progress.progress(percent, text=f"QA-360 is updating the framework... {percent}%")

                    # THE INTELLIGENT CONTEXT INJECTION FOR CHAT
                        chat_context = f"""
                        You are QA-360, an Expert Automation Architect.
                        The user originally provided this Base URL: {st.session_state.base_url}
                        The user originally provided this Flow Description: {st.session_state.automation_desc}
                        The Live Page Context extracted from that URL is: {st.session_state.page_context}

                        Here is the framework code you previously generated for them:
                        {st.session_state.generated_framework}

                        The user has follow-up requests. 
                        
                        CRITICAL INSTRUCTIONS FOR YOUR RESPONSE:
                        1. Intent & Mapping: First, analyze the user's new request. If they ask to interact with a new element, cross-reference it with the Live Page Context and explicitly state how you mapped it (or warn them if it's missing).
                        2. Code Generation: Provide the updated or new code blocks based on Selenium 4 standards.
                        3. Directory Structure: If your updates involve adding, splitting, or renaming any classes/files, you MUST regenerate "SECTION 9: Framework Directory Structure" at the end. The root node MUST be the project name (no dots). Draw the tree dynamically using `├──` and `└──` with proper nesting. Do not flatten the tree. Do not use commas. Only include the actual files currently in the framework. Each file on its own line.
                        4. Maintain the Selenium 4 and Java 17+ standards unless anything else is specified by user.

                        STRICT OUTPUT FORMATTING:
                        To ensure maximum clarity, you MUST format your response using these exact markdown headers in this exact order:
                        
                        ### 🧠 User Intent Analysis
                        (Provide your analysis from Instruction 1 here. Always show this section.)
                        
                        ### 💻 Code Updates
                        (Provide your generated code from Instruction 2 here.)
                        
                        ### 📂 Updated Directory Structure
                        (Provide the updated tree from Instruction 3 here, only if files were added or changed.)
                        
                        Conversation History:
                        """
                        for msg in st.session_state.chat_history:
                            chat_context += f"{msg['role'].capitalize()}: {msg['content']}\n"
                    
                    # 3. Make the actual AI call
                    chat_response = client.models.generate_content(
                        model="gemini-3-flash-preview", 
                        contents=chat_context
                    )
                    
                    # 4. Snap to 100%, wait a half-second, then clear the bar
                    chat_progress.progress(100, text="✅ Update Complete! 100%")
                    time.sleep(0.5)
                    chat_progress.empty()
                    
                    # 5. Display the final response
                    st.markdown(chat_response.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": chat_response.text})
                    
                except Exception as e:
                    if 'chat_progress' in locals():
                        chat_progress.empty() # Hide the bar if it crashes
                    st.error(f"Chat error occurred: {e}")
