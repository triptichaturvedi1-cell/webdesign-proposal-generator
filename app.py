"""
====================================================================
ARKIDO CLIENT INTAKE SYSTEM  (Version 1)
====================================================================
A simple, beginner-friendly Streamlit app to:
  1. Collect new client requirements through a form
  2. Save every client to a CSV file using Pandas
  3. View, filter, and search all clients on a Dashboard

WHY IT IS BUILT THIS WAY (for a beginner):
  - Streamlit turns a normal Python script into a web app.
    Every time you interact with something (click a button, change
    a dropdown), Streamlit simply re-runs this whole file top to
    bottom. That is why we use "if" checks and session_state.
  - Pandas is used to hold the client data as a table (DataFrame)
    in memory, and to read/write that table to a CSV file on disk.
  - CSV file = our simple "database" for now. Every row is one
    client. Later this can be swapped for a real database without
    changing much of the Streamlit code.
====================================================================
"""

import streamlit as st
import pandas as pd
import os
import json  # used to save/load agency branding settings as a simple settings file
import html as html_escape  # used to safely insert client text into HTML templates
from datetime import datetime, timedelta

# --------------------------------------------------------------
# 1. BASIC SETTINGS
# --------------------------------------------------------------

# Name of the CSV file where all client data is permanently stored.
CSV_FILE = "arkido_clients.csv"

# APP_DIR = the folder this app.py file lives in. Using this instead of a
# plain relative path ("templates") makes file lookup reliable no matter
# what "current folder" the server happens to be running from.
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Folder that holds the fixed HTML demo templates (Modern, Minimal, etc.)
TEMPLATES_DIR = os.path.join(APP_DIR, "templates")

# Folder where generated client demo websites are saved
DEMOS_DIR = os.path.join(APP_DIR, "demos")

# Folder where the uploaded agency logo is stored
BRANDING_DIR = os.path.join(APP_DIR, "branding")

# Folder where generated quotation documents are saved
QUOTATIONS_DIR = os.path.join(APP_DIR, "quotations")

# JSON file that stores your agency's branding & contact details
SETTINGS_FILE = os.path.join(APP_DIR, "agency_settings.json")

# CSV file that holds your editable price list (open it in Excel any time)
PRICING_FILE = os.path.join(APP_DIR, "pricing_config.csv")

# How many pages are included in the base price before "Extra Page" pricing kicks in
INCLUDED_PAGES = 5

# This list defines the exact column order used in the CSV file.
# NOTE: If you add a new form field later, also add its column
# name here (see the "How to add new fields" guide at the bottom
# of the README / instructions).
COLUMNS = [
    "Date Added",
    # Client Information
    "Client Name",
    "Company Name",
    "Phone Number",
    "Email Address",
    "Website URL",
    "Industry",
    "Country",
    # Project Requirements
    "Service Required",
    "Business Description",
    "Target Audience",
    "Main Goal",
    "Number of Pages",
    "Required Features",
    # Domain & Hosting
    "Has Domain",
    "Has Hosting",
    # Budget
    "Budget Range",
    "Timeline",
    # Design Preferences
    "Preferred Style",
    "Inspiration Websites",
    "Additional Notes",
    # Sales Status
    "Lead Source",
    "Lead Status",
]

# Streamlit page configuration (title shown on browser tab, wide layout)
st.set_page_config(page_title="Arkido Client Intake System", layout="wide")


# --------------------------------------------------------------
# 2. HELPER FUNCTIONS (all the Pandas / CSV logic lives here)
# --------------------------------------------------------------

def load_clients():
    """
    Reads the CSV file into a Pandas DataFrame.
    If the CSV file does not exist yet (first time running the app),
    it returns an empty DataFrame with the correct columns instead.
    """
    if os.path.exists(CSV_FILE):
        # Read existing data from disk into a DataFrame
        df = pd.read_csv(CSV_FILE)
        return df
    else:
        # No file yet -> return an empty table with the right columns
        return pd.DataFrame(columns=COLUMNS)


def save_client(new_client_dict):
    """
    Adds one new client (as a dictionary) to the CSV file.

    Steps:
      1. Load whatever clients already exist in the CSV.
      2. Turn the new client dictionary into a one-row DataFrame.
      3. Combine (append) the new row with the existing DataFrame.
      4. Write the combined DataFrame back to the CSV file.
    """
    existing_df = load_clients()

    # Convert the single new client (a dict) into a one-row DataFrame
    new_row_df = pd.DataFrame([new_client_dict])

    # Append the new row underneath the existing data.
    # ignore_index=True just re-numbers the rows cleanly (0,1,2,3...)
    updated_df = pd.concat([existing_df, new_row_df], ignore_index=True)

    # Save the full table back to the CSV file.
    # index=False means we don't write Pandas' row numbers into the file.
    updated_df.to_csv(CSV_FILE, index=False)


def safe_get(row, column_name, default=""):
    """
    Safely reads one value out of a Pandas row (a "Series").
    Returns 'default' if the column is missing or the value is empty (NaN).
    This stops the app from crashing on old rows that don't have every column.
    """
    value = row.get(column_name, default)
    if pd.isna(value):
        return default
    return str(value)


def build_features_list_html(features_text):
    """
    Turns a comma-separated string like "Contact Form, Blog, Chatbot"
    into HTML list items: <li>Contact Form</li><li>Blog</li>...
    Falls back to a friendly default if no features were recorded.
    """
    if not features_text or pd.isna(features_text) or str(features_text).strip() == "":
        return "<li>Custom features tailored to your business</li>"

    items = [item.strip() for item in str(features_text).split(",") if item.strip() != ""]
    if not items:
        return "<li>Custom features tailored to your business</li>"

    # html_escape.escape() protects against any stray HTML characters
    # in the client's data (e.g. < or & symbols) breaking the page.
    return "\n".join(f"<li>{html_escape.escape(item)}</li>" for item in items)


def guess_template_style(preferred_style_text):
    """
    Looks at the client's free-text 'Preferred Style' answer and guesses
    which of our 4 fixed templates matches best. Defaults to 'Modern'.
    """
    text = str(preferred_style_text).lower()
    if "minimal" in text:
        return "Minimal"
    elif "corporate" in text:
        return "Corporate"
    elif "dark" in text:
        return "Dark"
    else:
        return "Modern"


def generate_demo_html(client_row, template_style):
    """
    Builds a ready-to-view demo website (as one HTML string) for a client.

    Steps:
      1. Open the chosen template file (e.g. templates/modern.html).
      2. Replace each {{PLACEHOLDER}} with the client's real data.
      3. Return the finished HTML text.
    """
    template_path = os.path.join(TEMPLATES_DIR, f"{template_style.lower()}.html")
    with open(template_path, "r", encoding="utf-8") as f:
        template_text = f.read()

    # Map every placeholder in the template to a real value from the client's row.
    # html_escape.escape() keeps the client's text from accidentally breaking the HTML.
    replacements = {
        "{{CLIENT_NAME}}": html_escape.escape(safe_get(client_row, "Client Name")),
        "{{COMPANY_NAME}}": html_escape.escape(
            safe_get(client_row, "Company Name", safe_get(client_row, "Client Name"))
        ),
        "{{INDUSTRY}}": html_escape.escape(safe_get(client_row, "Industry", "your industry")),
        "{{DESCRIPTION}}": html_escape.escape(
            safe_get(client_row, "Business Description", "We provide quality products and services.")
        ),
        "{{TARGET_AUDIENCE}}": html_escape.escape(
            safe_get(client_row, "Target Audience", "our valued customers")
        ),
        "{{FEATURES_LIST}}": build_features_list_html(client_row.get("Required Features", "")),
        "{{PHONE}}": html_escape.escape(safe_get(client_row, "Phone Number", "N/A")),
        "{{EMAIL}}": html_escape.escape(safe_get(client_row, "Email Address", "N/A")),
    }

    for placeholder, value in replacements.items():
        template_text = template_text.replace(placeholder, value)

    return template_text


# --------------------------------------------------------------
# 2b. AGENCY BRANDING SETTINGS (logo, name, colors, contact info)
# --------------------------------------------------------------

# Sensible defaults used until the agency fills in their own settings
DEFAULT_SETTINGS = {
    "agency_name": "Arkido",
    "tagline": "Web Design & Digital Marketing",
    "email": "",
    "phone": "",
    "primary_color": "#4f46e5",
    "logo_filename": "",
}


def load_agency_settings():
    """
    Reads agency_settings.json from disk.
    Returns the saved settings, or the defaults if nothing has been saved yet.
    """
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        # Fill in any missing keys with defaults (handy if we add new settings later)
        merged = {**DEFAULT_SETTINGS, **saved}
        return merged
    return DEFAULT_SETTINGS.copy()


def save_agency_settings(settings_dict):
    """Writes the agency settings dictionary to agency_settings.json."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings_dict, f, indent=2)


def get_logo_path(settings_dict):
    """Returns the full path to the saved logo file, or None if no logo was uploaded."""
    filename = settings_dict.get("logo_filename", "")
    if filename:
        path = os.path.join(BRANDING_DIR, filename)
        if os.path.exists(path):
            return path
    return None


# --------------------------------------------------------------
# 2c. PRICING & QUOTATION GENERATOR
# --------------------------------------------------------------

def load_pricing():
    """
    Reads pricing_config.csv into a Pandas DataFrame.
    You can open this CSV in Excel/Google Sheets to update your prices —
    no code changes needed.
    """
    if os.path.exists(PRICING_FILE):
        return pd.read_csv(PRICING_FILE)
    else:
        # Fallback empty pricing table with the right columns
        return pd.DataFrame(columns=["Item", "Type", "Price"])


def lookup_price(pricing_df, item_name, item_type, default_price=0):
    """
    Finds the price for one item (e.g. 'Chatbot', Type='Feature') in the pricing table.
    Returns 'default_price' if the item isn't found in the CSV.
    """
    match = pricing_df[(pricing_df["Item"] == item_name) & (pricing_df["Type"] == item_type)]
    if not match.empty:
        return float(match.iloc[0]["Price"])
    return float(default_price)


def build_quote_line_items(client_row, pricing_df):
    """
    Builds the itemized list of charges for a client, using their saved
    intake answers (Service Required, Number of Pages, Required Features)
    matched against the pricing CSV.

    Returns a Pandas DataFrame with columns: Item, Amount (₹)
    This is the DataFrame shown in the editable table on the Quotation page.
    """
    line_items = []

    # 1. Base price for the main service requested
    service = safe_get(client_row, "Service Required", "Other")
    base_price = lookup_price(pricing_df, service, "Service", default_price=10000)
    line_items.append({"Item": f"{service} (base package, includes {INCLUDED_PAGES} pages)", "Amount (₹)": base_price})

    # 2. Extra pages beyond the included amount
    try:
        pages = int(float(safe_get(client_row, "Number of Pages", INCLUDED_PAGES)))
    except ValueError:
        pages = INCLUDED_PAGES
    extra_pages = max(0, pages - INCLUDED_PAGES)
    if extra_pages > 0:
        extra_page_price = lookup_price(pricing_df, "Extra Page", "Feature", default_price=1000)
        line_items.append({
            "Item": f"Extra Pages x{extra_pages}",
            "Amount (₹)": extra_pages * extra_page_price,
        })

    # 3. Each requested feature (Contact Form, Chatbot, etc.)
    features_text = safe_get(client_row, "Required Features", "")
    features = [f.strip() for f in features_text.split(",") if f.strip() != ""]
    for feature in features:
        feature_price = lookup_price(pricing_df, feature, "Feature", default_price=2000)
        line_items.append({"Item": feature, "Amount (₹)": feature_price})

    return pd.DataFrame(line_items)


def generate_quotation_html(client_row, line_items_df, settings_dict, valid_days=15):
    """
    Builds the final branded quotation document (as one HTML string), using:
      - the client's details
      - the (possibly edited) line items table
      - the agency's branding settings (logo, name, color)
    """
    template_path = os.path.join(TEMPLATES_DIR, "quotation.html")
    with open(template_path, "r", encoding="utf-8") as f:
        template_text = f.read()

    # Build the HTML table rows from the line items DataFrame
    rows_html = ""
    for _, item_row in line_items_df.iterrows():
        item_name = html_escape.escape(str(item_row["Item"]))
        amount = float(item_row["Amount (₹)"])
        rows_html += f"<tr><td>{item_name}</td><td class='amount'>{amount:,.0f}</td></tr>\n"

    total_amount = float(line_items_df["Amount (₹)"].sum())

    # Build the logo <img> tag, or leave it blank if no logo was uploaded
    logo_path = get_logo_path(settings_dict)
    if logo_path:
        # Streamlit Cloud can't reference local file paths from inside an
        # HTML string opened in a browser, so we embed the image directly
        # using base64 — this keeps the quotation a single, portable file.
        import base64
        with open(logo_path, "rb") as img_f:
            encoded = base64.b64encode(img_f.read()).decode("utf-8")
        ext = os.path.splitext(logo_path)[1].replace(".", "")
        logo_tag = f'<img class="logo" src="data:image/{ext};base64,{encoded}">'
    else:
        logo_tag = ""

    today = datetime.now()
    valid_until = today + timedelta(days=valid_days)

    replacements = {
        "{{PRIMARY_COLOR}}": settings_dict.get("primary_color", "#4f46e5"),
        "{{AGENCY_LOGO_TAG}}": logo_tag,
        "{{AGENCY_NAME}}": html_escape.escape(settings_dict.get("agency_name", "Arkido")),
        "{{AGENCY_TAGLINE}}": html_escape.escape(settings_dict.get("tagline", "")),
        "{{AGENCY_CONTACT}}": html_escape.escape(
            f"{settings_dict.get('email', '')}  {settings_dict.get('phone', '')}".strip()
        ),
        "{{QUOTE_DATE}}": today.strftime("%d %b %Y"),
        "{{VALID_UNTIL}}": valid_until.strftime("%d %b %Y"),
        "{{CLIENT_NAME}}": html_escape.escape(safe_get(client_row, "Client Name")),
        "{{COMPANY_NAME}}": html_escape.escape(safe_get(client_row, "Company Name")),
        "{{EMAIL}}": html_escape.escape(safe_get(client_row, "Email Address", "N/A")),
        "{{PHONE}}": html_escape.escape(safe_get(client_row, "Phone Number", "N/A")),
        "{{LINE_ITEM_ROWS}}": rows_html,
        "{{TOTAL_AMOUNT}}": f"{total_amount:,.0f}",
    }

    for placeholder, value in replacements.items():
        template_text = template_text.replace(placeholder, value)

    return template_text, total_amount


# --------------------------------------------------------------
# 3. GLOBAL STYLING + BRANDED SIDEBAR
# --------------------------------------------------------------

# Load the agency's saved branding (logo, name, color) once, so every
# page can use it — the header, sidebar, and generated documents.
agency_settings = load_agency_settings()
PRIMARY_COLOR = agency_settings.get("primary_color", "#4f46e5")

# A small block of custom CSS gives the app a cleaner, more "branded" look
# without needing any extra frontend framework. Streamlit lets us inject
# plain CSS like this using st.markdown + unsafe_allow_html=True.
st.markdown(
    f"""
    <style>
        /* Make the main content area a bit more spacious */
        .block-container {{
            padding-top: 2rem;
            padding-bottom: 2rem;
        }}
        /* Color the main action buttons using the agency's brand color */
        .stButton > button, .stFormSubmitButton > button {{
            background-color: {PRIMARY_COLOR};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 1.2rem;
            font-weight: 600;
        }}
        .stButton > button:hover, .stFormSubmitButton > button:hover {{
            opacity: 0.9;
            color: white;
        }}
        /* Style the metric "cards" on the Dashboard */
        div[data-testid="stMetric"] {{
            background-color: #f8fafc;
            border: 1px solid #e5e7eb;
            border-left: 4px solid {PRIMARY_COLOR};
            border-radius: 10px;
            padding: 12px 16px;
        }}
        /* Give section headers a touch of brand color */
        h2, h3 {{
            color: #1f2937;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------
# 4. SIDEBAR NAVIGATION
# --------------------------------------------------------------
# A simple sidebar radio button lets us switch between "pages"
# without needing Streamlit's multi-page folder setup. This keeps
# everything in one file, which is easier for a beginner to follow.

logo_path = get_logo_path(agency_settings)
if logo_path:
    st.sidebar.image(logo_path, use_container_width=True)

st.sidebar.title(agency_settings.get("agency_name", "ARKIDO"))
if agency_settings.get("tagline"):
    st.sidebar.caption(agency_settings["tagline"])

st.sidebar.divider()

page = st.sidebar.radio(
    "Go to:",
    [
        "📝 New Client Intake",
        "📊 Client Dashboard",
        "🖥️ Website Demo Generator",
        "💰 Quotation Generator",
        "⚙️ Agency Settings",
    ],
)


# ================================================================
# PAGE 1: NEW CLIENT INTAKE FORM
# ================================================================
if page == "📝 New Client Intake":

    st.title("📝 New Client Intake Form")
    st.write("Fill in the details below after speaking with a potential client.")

    # st.form groups all the inputs together so the app only re-runs
    # ONCE, when the "Save Client" button is pressed — not after every
    # single keystroke. This keeps the form fast and clean.
    with st.form("client_intake_form", clear_on_submit=True):

        # ---------------- CLIENT INFORMATION ----------------
        st.subheader("Client Information")
        col1, col2 = st.columns(2)
        with col1:
            client_name = st.text_input("Client Name")
            phone_number = st.text_input("Phone Number")
            website_url = st.text_input("Website URL (if any)")
            country = st.text_input("Country")
        with col2:
            company_name = st.text_input("Company Name")
            email_address = st.text_input("Email Address")
            industry = st.text_input("Industry")

        st.divider()

        # ---------------- PROJECT REQUIREMENTS ----------------
        st.subheader("Project Requirements")

        service_required = st.selectbox(
            "What does the client need?",
            [
                "New Website", "Website Redesign", "Landing Page",
                "E-commerce Website", "SEO", "Local SEO",
                "Digital Marketing", "Branding", "AI Automation", "Other",
            ],
        )

        business_description = st.text_area("Business Description")
        target_audience = st.text_area("Target Audience")

        main_goal = st.selectbox(
            "Main Goal of Website",
            [
                "Generate Leads", "Sell Products", "Build Brand Authority",
                "Book Appointments", "Show Portfolio", "Provide Information", "Other",
            ],
        )

        number_of_pages = st.number_input(
            "Number of Pages Required", min_value=1, max_value=100, value=5, step=1
        )

        required_features = st.multiselect(
            "Required Features",
            [
                "Contact Form", "WhatsApp Integration", "Booking System",
                "Payment Gateway", "E-commerce", "Blog", "Chatbot",
                "Member Login", "Other",
            ],
        )

        st.divider()

        # ---------------- DOMAIN AND HOSTING ----------------
        st.subheader("Domain and Hosting")
        col3, col4 = st.columns(2)
        with col3:
            has_domain = st.radio("Does the client already have a domain?", ["Yes", "No"])
        with col4:
            has_hosting = st.radio("Does the client already have hosting?", ["Yes", "No"])

        st.divider()

        # ---------------- CLIENT BUDGET ----------------
        st.subheader("Client Budget")
        budget_range = st.selectbox(
            "Budget Range",
            [
                "Not Discussed", "Under ₹25,000", "₹25,000 to ₹50,000",
                "₹50,000 to ₹1,00,000", "₹1,00,000 to ₹2,00,000", "Above ₹2,00,000",
            ],
        )
        timeline = st.selectbox(
            "Timeline",
            ["Urgent", "1 to 2 Weeks", "2 to 4 Weeks", "1 to 2 Months", "Flexible"],
        )

        st.divider()

        # ---------------- DESIGN PREFERENCES ----------------
        st.subheader("Design Preferences")
        preferred_style = st.text_input(
            "Preferred Website Style (e.g. Modern, Minimal, Luxury, Corporate, Creative, Dark, Colourful)"
        )
        inspiration_websites = st.text_area("Competitor or Inspiration Websites")
        additional_notes = st.text_area("Additional Notes")

        st.divider()

        # ---------------- SALES STATUS ----------------
        st.subheader("Sales Status")
        col5, col6 = st.columns(2)
        with col5:
            lead_source = st.selectbox(
                "Lead Source",
                [
                    "Referral", "Website", "WhatsApp", "Instagram", "LinkedIn",
                    "Facebook", "Google", "Existing Client", "Other",
                ],
            )
        with col6:
            lead_status = st.selectbox(
                "Lead Status",
                [
                    "New Lead", "Call Completed", "Requirements Collected",
                    "Demo Required", "Proposal Required", "Quote Sent",
                    "Follow Up", "Won", "Lost",
                ],
            )

        st.divider()

        # The Save button for the whole form.
        submitted = st.form_submit_button("💾 SAVE CLIENT")

        if submitted:
            # Basic validation: require at least a client name
            if client_name.strip() == "":
                st.error("Please enter the Client Name before saving.")
            else:
                # Build a dictionary matching our COLUMNS list.
                # This becomes one new row in the CSV file.
                new_client = {
                    "Date Added": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Client Name": client_name,
                    "Company Name": company_name,
                    "Phone Number": phone_number,
                    "Email Address": email_address,
                    "Website URL": website_url,
                    "Industry": industry,
                    "Country": country,
                    "Service Required": service_required,
                    "Business Description": business_description,
                    "Target Audience": target_audience,
                    "Main Goal": main_goal,
                    "Number of Pages": number_of_pages,
                    # Join the list of features into one text string, e.g.
                    # "Contact Form, WhatsApp Integration"
                    "Required Features": ", ".join(required_features),
                    "Has Domain": has_domain,
                    "Has Hosting": has_hosting,
                    "Budget Range": budget_range,
                    "Timeline": timeline,
                    "Preferred Style": preferred_style,
                    "Inspiration Websites": inspiration_websites,
                    "Additional Notes": additional_notes,
                    "Lead Source": lead_source,
                    "Lead Status": lead_status,
                }

                save_client(new_client)
                st.success(f"✅ Client '{client_name}' saved successfully!")


# ================================================================
# PAGE 2: CLIENT DASHBOARD
# ================================================================
elif page == "📊 Client Dashboard":

    st.title("📊 Client Dashboard")

    # Load all clients currently saved in the CSV file
    df = load_clients()

    if df.empty:
        st.info("No clients yet. Add your first client from the 'New Client Intake' page.")
    else:
        # ---------------- TOP STATISTICS ----------------
        st.subheader("Overview")

        total_leads = len(df)
        new_leads = (df["Lead Status"] == "New Lead").sum()
        proposal_required = (df["Lead Status"] == "Proposal Required").sum()
        quotes_sent = (df["Lead Status"] == "Quote Sent").sum()
        won_clients = (df["Lead Status"] == "Won").sum()
        lost_clients = (df["Lead Status"] == "Lost").sum()

        # st.columns lets us show these numbers side by side as neat cards
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total Leads", total_leads)
        c2.metric("New Leads", new_leads)
        c3.metric("Proposal Required", proposal_required)
        c4.metric("Quotes Sent", quotes_sent)
        c5.metric("Won", won_clients)
        c6.metric("Lost", lost_clients)

        st.divider()

        # ---------------- FILTERS ----------------
        st.subheader("Filters")
        f1, f2, f3, f4 = st.columns(4)

        with f1:
            industry_options = ["All"] + sorted(df["Industry"].dropna().unique().tolist())
            industry_filter = st.selectbox("Industry", industry_options)

        with f2:
            service_options = ["All"] + sorted(df["Service Required"].dropna().unique().tolist())
            service_filter = st.selectbox("Service Required", service_options)

        with f3:
            status_options = ["All"] + sorted(df["Lead Status"].dropna().unique().tolist())
            status_filter = st.selectbox("Lead Status", status_options)

        with f4:
            budget_options = ["All"] + sorted(df["Budget Range"].dropna().unique().tolist())
            budget_filter = st.selectbox("Budget Range", budget_options)

        # ---------------- SEARCH ----------------
        search_term = st.text_input("🔍 Search by Client Name or Company Name")

        # ---------------- APPLY FILTERS TO THE DATAFRAME ----------------
        # We start with the full table, then narrow it down step by step.
        filtered_df = df.copy()

        if industry_filter != "All":
            filtered_df = filtered_df[filtered_df["Industry"] == industry_filter]

        if service_filter != "All":
            filtered_df = filtered_df[filtered_df["Service Required"] == service_filter]

        if status_filter != "All":
            filtered_df = filtered_df[filtered_df["Lead Status"] == status_filter]

        if budget_filter != "All":
            filtered_df = filtered_df[filtered_df["Budget Range"] == budget_filter]

        if search_term.strip() != "":
            # str.contains searches text inside a column.
            # case=False makes the search case-insensitive.
            # na=False treats missing values as "no match" instead of an error.
            name_match = filtered_df["Client Name"].str.contains(search_term, case=False, na=False)
            company_match = filtered_df["Company Name"].str.contains(search_term, case=False, na=False)
            filtered_df = filtered_df[name_match | company_match]

        st.divider()

        # ---------------- CLIENT TABLE ----------------
        st.subheader(f"Clients ({len(filtered_df)} shown of {total_leads} total)")
        st.dataframe(filtered_df, use_container_width=True)

        # Optional: let the user download the filtered results as CSV
        csv_data = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download this view as CSV",
            data=csv_data,
            file_name="arkido_clients_filtered.csv",
            mime="text/csv",
        )


# ================================================================
# PAGE 3: WEBSITE DEMO GENERATOR
# ================================================================
elif page == "🖥️ Website Demo Generator":

    st.title("🖥️ Website Demo Generator")
    st.write(
        "Turn a saved client's requirements into a quick, one-page demo website "
        "you can preview here and download to share with them."
    )

    df = load_clients()

    if df.empty:
        st.info("No clients yet. Add a client from the 'New Client Intake' page first.")
    else:
        # Build a readable label for the dropdown, e.g. "Riya Sharma - Riya Bakes (2026-01-05 14:02)"
        client_labels = (
            df["Client Name"].astype(str)
            + " - "
            + df["Company Name"].astype(str)
            + " ("
            + df["Date Added"].astype(str)
            + ")"
        )
        selected_label = st.selectbox("Choose a client", client_labels.tolist())

        # Find the full row of data that matches the label the user picked
        selected_row = df[client_labels == selected_label].iloc[0]

        # Suggest a template based on what the client said they preferred,
        # but still let the user override it with the dropdown below.
        suggested_style = guess_template_style(selected_row.get("Preferred Style", ""))
        style_options = ["Modern", "Minimal", "Corporate", "Dark"]
        default_index = style_options.index(suggested_style) if suggested_style in style_options else 0

        template_choice = st.selectbox("Demo Style Template", style_options, index=default_index)
        st.caption(f"Suggested based on this client's 'Preferred Style' answer: **{suggested_style}**")

        if st.button("⚡ Generate Demo Website"):
            demo_html = generate_demo_html(selected_row, template_choice)

            # Save the demo permanently to the demos/ folder so you can find it again later
            os.makedirs(DEMOS_DIR, exist_ok=True)
            safe_name = "".join(
                c for c in str(selected_row["Client Name"]) if c.isalnum() or c == " "
            ).strip().replace(" ", "_")
            demo_filename = f"{safe_name}_{template_choice.lower()}_demo.html"
            demo_path = os.path.join(DEMOS_DIR, demo_filename)

            with open(demo_path, "w", encoding="utf-8") as f:
                f.write(demo_html)

            st.success(f"Demo generated and saved to demos/{demo_filename}")

            # Show a live preview of the demo website right inside the app
            st.subheader("Live Preview")
            st.components.v1.html(demo_html, height=900, scrolling=True)

            # Let the user download the standalone HTML file to send to the client
            st.download_button(
                "⬇️ Download Demo HTML",
                data=demo_html,
                file_name=demo_filename,
                mime="text/html",
            )


# ================================================================
# PAGE 4: QUOTATION GENERATOR
# ================================================================
elif page == "💰 Quotation Generator":

    st.title("💰 Quotation Generator")
    st.write(
        "Auto-calculate a price quote from a client's saved requirements, "
        "then fine-tune the numbers before generating a branded document."
    )

    df = load_clients()
    pricing_df = load_pricing()

    if df.empty:
        st.info("No clients yet. Add a client from the 'New Client Intake' page first.")
    elif pricing_df.empty:
        st.warning(
            "No pricing found. Make sure 'pricing_config.csv' exists in your project folder."
        )
    else:
        # Pick which client to quote, same pattern as the Demo Generator page
        client_labels = (
            df["Client Name"].astype(str)
            + " - "
            + df["Company Name"].astype(str)
            + " ("
            + df["Date Added"].astype(str)
            + ")"
        )
        selected_label = st.selectbox("Choose a client", client_labels.tolist())
        selected_row = df[client_labels == selected_label].iloc[0]

        st.caption(
            f"Service: **{safe_get(selected_row, 'Service Required')}** | "
            f"Pages: **{safe_get(selected_row, 'Number of Pages')}** | "
            f"Features: **{safe_get(selected_row, 'Required Features', 'None')}**"
        )

        # Auto-calculate the starting line items from the client's saved answers
        auto_line_items = build_quote_line_items(selected_row, pricing_df)

        st.subheader("Line Items (editable)")
        st.write(
            "These amounts were auto-filled from your pricing sheet. "
            "Double-click any cell to adjust it, or use the + row at the "
            "bottom to add a custom line item."
        )

        # st.data_editor turns a DataFrame into an editable table right in
        # the browser — the user can tweak prices before generating the quote.
        edited_line_items = st.data_editor(
            auto_line_items,
            num_rows="dynamic",
            use_container_width=True,
            key="quote_editor",
        )

        # Recalculate the total live as the table is edited
        if not edited_line_items.empty and "Amount (₹)" in edited_line_items.columns:
            current_total = edited_line_items["Amount (₹)"].sum()
        else:
            current_total = 0

        st.metric("Quotation Total", f"₹ {current_total:,.0f}")

        valid_days = st.slider("Quotation valid for (days)", 7, 60, 15)

        if st.button("⚡ Generate Quotation"):
            quotation_html, total_amount = generate_quotation_html(
                selected_row, edited_line_items, agency_settings, valid_days=valid_days
            )

            # Save the quotation permanently so you can find it again later
            os.makedirs(QUOTATIONS_DIR, exist_ok=True)
            safe_name = "".join(
                c for c in str(selected_row["Client Name"]) if c.isalnum() or c == " "
            ).strip().replace(" ", "_")
            date_stamp = datetime.now().strftime("%Y%m%d")
            quote_filename = f"{safe_name}_quotation_{date_stamp}.html"
            quote_path = os.path.join(QUOTATIONS_DIR, quote_filename)

            with open(quote_path, "w", encoding="utf-8") as f:
                f.write(quotation_html)

            st.success(f"Quotation generated and saved to quotations/{quote_filename}")

            st.subheader("Live Preview")
            st.components.v1.html(quotation_html, height=900, scrolling=True)

            st.download_button(
                "⬇️ Download Quotation (HTML)",
                data=quotation_html,
                file_name=quote_filename,
                mime="text/html",
            )
            st.caption(
                "Tip: open the downloaded file in your browser and use "
                "'Print → Save as PDF' to send it as a PDF."
            )


# ================================================================
# PAGE 5: AGENCY SETTINGS (BRANDING)
# ================================================================
elif page == "⚙️ Agency Settings":

    st.title("⚙️ Agency Settings")
    st.write(
        "Set up your agency's branding once — your logo, name, and color "
        "will automatically appear on the sidebar and on every generated "
        "demo and quotation."
    )

    current_settings = load_agency_settings()

    with st.form("agency_settings_form"):
        agency_name = st.text_input("Agency Name", value=current_settings.get("agency_name", ""))
        tagline = st.text_input("Tagline", value=current_settings.get("tagline", ""))

        col1, col2 = st.columns(2)
        with col1:
            email = st.text_input("Contact Email", value=current_settings.get("email", ""))
        with col2:
            phone = st.text_input("Contact Phone", value=current_settings.get("phone", ""))

        primary_color = st.color_picker(
            "Brand Color", value=current_settings.get("primary_color", "#4f46e5")
        )

        logo_file = st.file_uploader(
            "Upload Logo (PNG or JPG)", type=["png", "jpg", "jpeg"]
        )

        # Show the currently saved logo, if any, so the user knows it's already set
        existing_logo_path = get_logo_path(current_settings)
        if existing_logo_path and not logo_file:
            st.caption("Current logo:")
            st.image(existing_logo_path, width=150)

        saved = st.form_submit_button("💾 Save Settings")

        if saved:
            new_settings = {
                "agency_name": agency_name.strip() or "Arkido",
                "tagline": tagline.strip(),
                "email": email.strip(),
                "phone": phone.strip(),
                "primary_color": primary_color,
                "logo_filename": current_settings.get("logo_filename", ""),
            }

            # If a new logo was uploaded, save it to the branding/ folder
            if logo_file is not None:
                os.makedirs(BRANDING_DIR, exist_ok=True)
                file_extension = os.path.splitext(logo_file.name)[1]
                logo_filename = f"logo{file_extension}"
                logo_save_path = os.path.join(BRANDING_DIR, logo_filename)
                with open(logo_save_path, "wb") as f:
                    f.write(logo_file.getbuffer())
                new_settings["logo_filename"] = logo_filename

            save_agency_settings(new_settings)
            st.success("Settings saved! Reload the page to see the new branding everywhere.")
