import io
import fitz  # PyMuPDF
import pandas as pd
import streamlit as st
import datetime

# ----------------- PAGE CONFIGURATION -----------------
st.set_page_config(
    page_title="General 35 A | OT Generator", 
    page_icon="📄", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better button styling and cleaner layout
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; background-color: #0068c9; color: white; height: 50px; }
    .stDownloadButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 50px; border: 2px solid #0068c9; color: #0068c9; }
    .stDownloadButton>button:hover { background-color: #0068c9; color: white; }
    </style>
""", unsafe_allow_html=True)

# ----------------- HELPER FUNCTIONS -----------------
def number_to_words(amount):
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
             "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def _convert_below_thousand(n):
        if n == 0: return ""
        elif n < 20: return units[n]
        elif n < 100: return tens[n // 10] + (" " + units[n % 10] if n % 10 != 0 else "")
        else: return units[n // 100] + " Hundred" + (" " + _convert_below_thousand(n % 100) if n % 100 != 0 else "")

    def _convert(n):
        if n == 0: return "Zero"
        parts = []
        if n >= 1_000_000:
            parts.append(_convert_below_thousand(n // 1_000_000) + " Million")
            n %= 1_000_000
        if n >= 1_000:
            parts.append(_convert_below_thousand(n // 1_000) + " Thousand")
            n %= 1_000
        if n > 0:
            parts.append(_convert_below_thousand(n))
        return " ".join(parts)

    rupees = int(amount)
    cents = int(round((amount - rupees) * 100))
    rupees_words = _convert(rupees) + (" Rupee" if rupees == 1 else " Rupees")
    
    if cents > 0:
        cents_words = _convert(cents) + (" Cent" if cents == 1 else " Cents")
        return f"{rupees_words} and {cents_words}"
    else:
        return f"{rupees_words} Only"

def format_time_no_seconds(time_val):
    s = str(time_val).strip()
    if pd.isna(time_val) or s in ["nan", "None", ""]: return ""
    if ":" in s:
        parts = s.split(":")
        if len(parts) >= 2: return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return s

# ----------------- UI: APP HEADER -----------------
st.markdown("<h2 style='text-align: center;'>📄 General 35 A Overtime Voucher Generator</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>Automate your OT calculations and generate ready-to-print vouchers instantly.</p>", unsafe_allow_html=True)
st.divider()

# ----------------- DATA PROCESSING -----------------
df_raw = pd.DataFrame()
auto_name, auto_dept, auto_pos = "A. B. Perera", "Vavuniya North DS Office", "ICT Assistant"

# UI: Step 1 - File Upload
with st.container():
    st.markdown("#### 📂 Step 1: Upload Timesheet")
    st.info("💡 The template `gen-35a.pdf` is loaded automatically from your project folder.")
    uploaded_excel = st.file_uploader("Upload Excel Timesheet / Attendance Log", type=["xlsx", "xls", "csv"], label_visibility="collapsed")
    st.caption("Supported formats: `.xlsx`, `.csv`. Requires `Start_Time` & `Out_Time`, or `First-In`, `Last-Out`, or pre-calculated `OT` column.")

if uploaded_excel is not None:
    if uploaded_excel.name.endswith(".csv"):
        df_raw = pd.read_csv(uploaded_excel)
    else:
        df_raw = pd.read_excel(uploaded_excel)
    df_raw.columns = df_raw.columns.astype(str).str.strip()

    if not df_raw.empty:
        if "Name" in df_raw.columns and pd.notna(df_raw["Name"].iloc[0]): auto_name = str(df_raw["Name"].iloc[0])
        if "Department" in df_raw.columns and pd.notna(df_raw["Department"].iloc[0]): auto_dept = str(df_raw["Department"].iloc[0])
        if "Position" in df_raw.columns and pd.notna(df_raw["Position"].iloc[0]): auto_pos = str(df_raw["Position"].iloc[0])

st.write("") # Spacer

# UI: Step 2 - Employee Details & Form Details
st.markdown("#### 👤 Step 2: Employee & Form Details")
with st.expander("View / Edit Details", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        name = st.text_input("Name", value=auto_name)
        pay_unit = st.text_input("Pay Unit / Station")
    with col2:
        designation = st.text_input("Designation", value=auto_pos)
        salary_per_month = st.number_input("Salary Per Month (LKR)", value=45000.0, step=1000.0)
    with col3:
        place_of_work = st.text_input("Place of Work", value=auto_dept)
        ot_divisor = st.number_input("OT Rate Divisor", value=244.0)

    ot_rate_per_hour = (salary_per_month / ot_divisor) if ot_divisor > 0 else 0.0
    st.success(f"**Calculated OT Rate:** LKR {ot_rate_per_hour:.2f} per hour")

    # New Section: Form Specific Fields
    st.markdown("##### 📅 Overtime Request Details")
    date_col1, date_col2, hours_col = st.columns(3)
    
    # Calculate default first and last day of the current month
    today = datetime.date.today()
    first_day = today.replace(day=1)
    next_month = first_day.replace(day=28) + datetime.timedelta(days=4)
    last_day = next_month - datetime.timedelta(days=next_month.day)

    with date_col1:
        req_start_date = st.date_input("OT Month First Date", value=first_day)
    with date_col2:
        req_end_date = st.date_input("OT Month Last Date", value=last_day)
    with hours_col:
        approved_hours = st.number_input("No. of Hours Approved", value=0.0, step=1.0)
    
    task_description = st.text_area(
        "Task Description (Applies to all rows if no 'Task' column exists)",
        value="System maintenance and technical support",
        height=68
    )

st.write("") # Spacer

# ----------------- TIMESHEET MATH -----------------
df = pd.DataFrame()
total_hours = 0.0
total_amount = 0.0

if not df_raw.empty:
    df = df_raw.copy()

    if "OT" in df.columns:
        df["Hours"] = pd.to_numeric(df["OT"], errors="coerce").fillna(0.0)
        df = df[df["Hours"] > 0].copy()
    elif "Start_Time" in df.columns and "Out_Time" in df.columns:
        def calc_hours(row):
            try:
                t1 = pd.to_datetime(str(row["Start_Time"]).strip(), format="%H:%M")
                t2 = pd.to_datetime(str(row["Out_Time"]).strip(), format="%H:%M")
                return max(0.0, (t2 - t1).total_seconds() / 3600.0)
            except:
                return 0.0
        df["Hours"] = df.apply(calc_hours, axis=1)
        df = df[df["Hours"] > 0].copy()

# UI: Step 3 - Preview & Generate
if not df.empty:
    df["OT_Amount"] = df["Hours"] * ot_rate_per_hour
    total_hours = df["Hours"].sum()
    total_amount = df["OT_Amount"].sum()

    st.markdown("#### 📊 Step 3: Calculation Summary")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Valid OT Entries", f"{len(df)} Days")
    m2.metric("Total OT Hours", f"{total_hours:.2f} hrs")
    m3.metric("Total Payment", f"LKR {total_amount:,.2f}")

    st.dataframe(df, use_container_width=True, hide_index=True)

    if st.button("🚀 Generate Filled General 35 A Voucher"):
        try:
            doc = fitz.open("gen-35a.pdf")
            page = doc[0]

            # 1. Standard Header Information
            page.insert_text(fitz.Point(165, 85), name, fontsize=10)
            page.insert_text(fitz.Point(432, 93), designation, fontsize=10)
            page.insert_text(fitz.Point(157, 120), place_of_work, fontsize=10)
            page.insert_text(fitz.Point(410, 118), pay_unit, fontsize=10)
            page.insert_text(fitz.Point(157, 148), f"Rs. {salary_per_month:,.2f}", fontsize=10)
            page.insert_text(fitz.Point(445, 147), f"Rs. {ot_rate_per_hour:.2f} / hr", fontsize=10)

            # 2. NEWLY ADDED: Additional Form Items
            # Formats date as DD/MM/YYYY (e.g. 01/08/2026)
            page.insert_textbox(fitz.Rect(46, 277, 71, 305), req_start_date.strftime("%d/%m/%Y"), fontsize=9, align=fitz.TEXT_ALIGN_LEFT)
            page.insert_textbox(fitz.Rect(75, 277, 99, 305), req_end_date.strftime("%d/%m/%Y"), fontsize=9, align=fitz.TEXT_ALIGN_LEFT)
            page.insert_textbox(fitz.Rect(102, 280, 167, 305), f"{approved_hours}", fontsize=9, align=fitz.TEXT_ALIGN_CENTER)
            
            # Secondary Task Textbox
            task_rect_secondary = fitz.Rect(172, 277, 365, 305)
            page.insert_textbox(task_rect_secondary, task_description, fontsize=9, align=fitz.TEXT_ALIGN_LEFT)

            # 3. Table Rows
            current_y = 427
            row_height = 16.35
            for idx, row in df.iterrows():
                date_str = str(row.get("Date", ""))[:10]
                in_time = format_time_no_seconds(row.get("Start_Time", row.get("First-In", "")))
                out_time = format_time_no_seconds(row.get("Out_Time", row.get("Last-Out", "")))
                hrs = f"{row.get('Hours', 0):.2f}"

                page.insert_text(fitz.Point(45, current_y), date_str, fontsize=9)
                page.insert_text(fitz.Point(98, current_y), in_time, fontsize=9)
                page.insert_text(fitz.Point(134, current_y), out_time, fontsize=9)
                page.insert_text(fitz.Point(175, current_y), hrs, fontsize=9)
                current_y += row_height

            # 4. Primary Task & Totals
            task_rect_primary = fitz.Rect(221, (412 + (current_y - 412)/2), 369, max(current_y, 440))
            page.insert_textbox(task_rect_primary, task_description, fontsize=9, align=fitz.TEXT_ALIGN_LEFT)
            page.insert_text(fitz.Point(170, 724), f"{total_hours:.2f} hrs", fontsize=10)
            
            amount_words = number_to_words(total_amount)
            amount_rect = fitz.Rect(230, 740, 550, 780)
            page.insert_textbox(amount_rect, f"Rs. {total_amount:,.2f} ({amount_words})", fontsize=9, align=fitz.TEXT_ALIGN_LEFT)

            output_buffer = io.BytesIO()
            doc.save(output_buffer)
            doc.close()

            st.session_state["pdf_bytes"] = output_buffer.getvalue()
            
        except FileNotFoundError:
            st.error("❌ Error: 'gen-35a.pdf' not found. Ensure it is uploaded to the root directory.")

elif uploaded_excel is not None:
    st.warning("⚠️ The uploaded timesheet contains no valid overtime records (No 'Hours' > 0 found).")

# ----------------- PREVIEW & DOWNLOAD -----------------
if "pdf_bytes" in st.session_state:
    st.divider()
    st.markdown("#### ✅ Success! Document Ready")
    
    dl_col, space = st.columns([1, 2])
    with dl_col:
        st.download_button(
            label="⬇️ Download Completed Voucher",
            data=st.session_state["pdf_bytes"],
            file_name=f"General_35A_{name.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )
    
    st.write("")

    # RESPONSIVE PREVIEW
    st.subheader("Document Preview")
    preview_doc = fitz.open(stream=st.session_state["pdf_bytes"], filetype="pdf")
    preview_page = preview_doc[0]
    pix = preview_page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    preview_doc.close()

    st.markdown(
        """
        <style>
        .doc-preview img {
            border: 1px solid #ddd;
            border-radius: 4px;
            box-shadow: 0px 4px 15px rgba(0,0,0,0.1);
        }
        </style>
        """, 
        unsafe_allow_html=True
    )
    
    st.markdown('<div class="doc-preview">', unsafe_allow_html=True)
    st.image(img_bytes, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)