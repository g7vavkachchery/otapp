import io
import base64
import fitz  # PyMuPDF
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="General 35 A Overtime Automation", layout="wide"
)
st.title("General 35 A Overtime Voucher Generator")

# Helper function to convert total amount numbers to currency words
def number_to_words(amount):
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
             "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def _convert_below_thousand(n):
        if n == 0:
            return ""
        elif n < 20:
            return units[n]
        elif n < 100:
            return tens[n // 10] + (" " + units[n % 10] if n % 10 != 0 else "")
        else:
            return units[n // 100] + " Hundred" + (" " + _convert_below_thousand(n % 100) if n % 100 != 0 else "")

    def _convert(n):
        if n == 0:
            return "Zero"
        parts = []
        if n >= 1_000_000:
            millions = n // 1_000_000
            parts.append(_convert_below_thousand(millions) + " Million")
            n %= 1_000_000
        if n >= 1_000:
            thousands = n // 1_000
            parts.append(_convert_below_thousand(thousands) + " Thousand")
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

# Helper function to remove seconds from time strings (HH:MM)
def format_time_no_seconds(time_val):
    s = str(time_val).strip()
    if pd.isna(time_val) or s in ["nan", "None", ""]:
        return ""
    if ":" in s:
        parts = s.split(":")
        if len(parts) >= 2:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return s

# File Uploaders
col1, col2 = st.columns(2)
with col1:
    uploaded_pdf = st.file_uploader(
        "Upload Blank General 35 A PDF", type=["pdf"]
    )
with col2:
    uploaded_excel = st.file_uploader(
        "Upload Excel Timesheet / Attendance Log", type=["xlsx", "xls", "csv"]
    )
    st.caption(
        "Supports standard timesheets (`Start_Time`, `Out_Time`) or Attendance Reports (`First-In`, `Last-Out`, `OT`)."
    )

# Pre-process uploaded file & auto-extract metadata if present
df_raw = pd.DataFrame()
auto_name, auto_dept, auto_pos = "A. B. Perera", "Vavuniya North DS Office", "ICT Assistant"

if uploaded_excel is not None:
    if uploaded_excel.name.endswith(".csv"):
        df_raw = pd.read_csv(uploaded_excel)
    else:
        df_raw = pd.read_excel(uploaded_excel)

    df_raw.columns = df_raw.columns.astype(str).str.strip()

    # Auto-populate sidebar fields if attendance report contains employee info
    if not df_raw.empty:
        if "Name" in df_raw.columns and pd.notna(df_raw["Name"].iloc[0]):
            auto_name = str(df_raw["Name"].iloc[0])
        if "Department" in df_raw.columns and pd.notna(df_raw["Department"].iloc[0]):
            auto_dept = str(df_raw["Department"].iloc[0])
        if "Position" in df_raw.columns and pd.notna(df_raw["Position"].iloc[0]):
            auto_pos = str(df_raw["Position"].iloc[0])

# Sidebar for Employee Metadata
st.sidebar.header("Employee Details")
name = st.sidebar.text_input("Name", value=auto_name)
designation = st.sidebar.text_input("Designation", value=auto_pos)
place_of_work = st.sidebar.text_input("Place of Work", value=auto_dept)
pay_unit = st.sidebar.text_input("Pay Unit / Station")
salary_per_month = st.sidebar.number_input(
    "Salary Per Month (LKR)", value=45000.0, step=1000.0
)
ot_divisor = st.sidebar.number_input("OT Rate Divisor", value=244.0)

# Calculate OT Rate per hour
ot_rate_per_hour = (
    (salary_per_month / ot_divisor) if ot_divisor > 0 else 0.0
)
st.sidebar.metric(
    label="Calculated OT Rate", value=f"LKR {ot_rate_per_hour:.2f} / hr"
)

task_description = st.text_area(
    "What did you do? (Applies to all rows if your Excel lacks a 'Task' column)",
    value="System maintenance and technical support",
)

# Timesheet Math & Processing
df = pd.DataFrame()
total_hours = 0.0
total_amount = 0.0

if not df_raw.empty:
    df = df_raw.copy()

    # Case 1: Attendance Log format with pre-calculated 'OT' column
    if "OT" in df.columns:
        df["Hours"] = pd.to_numeric(df["OT"], errors="coerce").fillna(0.0)
        df = df[df["Hours"] > 0].copy()

    # Case 2: Standard timesheet calculating duration from Start_Time & Out_Time
    elif "Start_Time" in df.columns and "Out_Time" in df.columns:
        def calc_hours(row):
            try:
                t1 = pd.to_datetime(str(row["Start_Time"]).strip(), format="%H:%M")
                t2 = pd.to_datetime(str(row["Out_Time"]).strip(), format="%H:%M")
                return max(0.0, (t2 - t1).total_seconds() / 3600.0)
            except Exception:
                return 0.0

        df["Hours"] = df.apply(calc_hours, axis=1)
        df = df[df["Hours"] > 0].copy()

    if "Hours" in df.columns and not df.empty:
        df["OT_Amount"] = df["Hours"] * ot_rate_per_hour
        total_hours = df["Hours"].sum()
        total_amount = df["OT_Amount"].sum()

        st.subheader("Timesheet Preview & Calculations")
        st.dataframe(df, use_container_width=True)

        col_a, col_b = st.columns(2)
        col_a.metric("Total OT Hours", f"{total_hours:.2f} hrs")
        col_b.metric("Total Payment", f"LKR {total_amount:,.2f}")
    else:
        st.warning("No valid overtime entries (Hours > 0) were found in the uploaded file.")

# PDF Generation
if st.button("Generate Filled General 35 A Voucher"):
    if uploaded_pdf is None or uploaded_excel is None:
        st.error("Please upload both the PDF template and the Excel timesheet.")
    elif df.empty:
        st.error("The uploaded timesheet contains no valid overtime records.")
    else:
        pdf_bytes = uploaded_pdf.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        # 1. Header Information (Custom Calibrated Coordinates)
        page.insert_text(fitz.Point(165, 85), name, fontsize=10)
        page.insert_text(fitz.Point(432, 93), designation, fontsize=10)
        page.insert_text(fitz.Point(157, 120), place_of_work, fontsize=10)

        page.insert_text(fitz.Point(410, 118), pay_unit, fontsize=10)
        page.insert_text(
            fitz.Point(157, 148), f"Rs. {salary_per_month:,.2f}", fontsize=10
        )
        page.insert_text(
            fitz.Point(445, 147), f"Rs. {ot_rate_per_hour:.2f} / hr", fontsize=10
        )

        # 2. Table Rows (Times without seconds)
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

        # Task Description in a Bounded Box (Auto-wraps across lines like Word)
        task_rect = fitz.Rect(221, (412 + (current_y - 412)/2), 369, max(current_y, 440))
        page.insert_textbox(task_rect, task_description, fontsize=9, align=fitz.TEXT_ALIGN_LEFT)

        # 3. Totals Row
        page.insert_text(
            fitz.Point(170, 724), f"{total_hours:.2f} hrs", fontsize=10
        )
        
        # Total Amount in Numbers & Words inside Bounded Box (Auto-wraps)
        amount_words = number_to_words(total_amount)
        full_amount_str = f"Rs. {total_amount:,.2f} ({amount_words})"
        amount_rect = fitz.Rect(230, 740, 550, 780)
        page.insert_textbox(amount_rect, full_amount_str, fontsize=9, align=fitz.TEXT_ALIGN_LEFT)

        # Save Buffer to Session State
        output_buffer = io.BytesIO()
        doc.save(output_buffer)
        doc.close()

        st.session_state["pdf_bytes"] = output_buffer.getvalue()

# Preview & Download Workflow
if "pdf_bytes" in st.session_state:
    st.success("Voucher generated successfully!")

    st.subheader("Document Preview")
    base64_pdf = base64.b64encode(st.session_state["pdf_bytes"]).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

    st.download_button(
        label="Download Completed Voucher PDF",
        data=st.session_state["pdf_bytes"],
        file_name="Completed_General_35A_Voucher.pdf",
        mime="application/pdf",
    )