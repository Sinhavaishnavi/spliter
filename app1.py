import streamlit as st
import json, base64, io
import pandas as pd
import altair as alt
from PIL import Image
import qrcode
from dataclasses import dataclass, asdict
from typing import List, Dict
from urllib.parse import urlencode

# ----------------------------- Styling (Aesthetic Improvements) -----------------------------
APP_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
   
    .accent { color: #2563eb; }
    .pill {
        display: inline-block; padding: 6px 12px; border-radius: 999px;
        background: #eef2ff; color: #3730a3; font-weight: 600; font-size: 0.85rem;
        border: 1px solid #e5e7eb;
    }
    .soft-card {
        background: #ffffffcc; border: 1px solid #e5e7eb; border-radius: 16px;
        padding: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.06);
    }
    .primary-btn button {
        background: linear-gradient(90deg,#6366f1,#2563eb) !important;
        color: white !important; border: 0 !important; border-radius: 12px !important;
        box-shadow: 0 8px 18px rgba(99,102,241,0.35) !important; font-weight: 700 !important;
    }
    .ghost-btn button {
        background: #f8fafc !important; color: #0f172a !important;
        border: 1px solid #e2e8f0 !important; border-radius: 12px !important; font-weight: 600 !important;
    }
    textarea[readonly], textarea[disabled] { background-color: #2563eb !important; }
</style>
<div class="app-bg"></div>
"""

# ----------------------------- Serialization for Share Links -----------------------------
def encode_state(d: dict) -> str:
    """Encodes a dictionary into a URL-safe base64 string."""
    raw = json.dumps(d, separators=(",", ":"), ensure_ascii=False)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")

def decode_state(s: str) -> dict:
    """Decodes a URL-safe base64 string back into a dictionary."""
    try:
        raw = base64.urlsafe_b64decode(s.encode("utf-8")).decode("utf-8")
        return json.loads(raw)
    except Exception:
        return {}

def build_share_link(base_url: str, state: dict) -> str:
    """Builds a URL with the app's state encoded in the query parameters."""
    payload = encode_state(state)
    return f"{base_url}/?{urlencode({'state': payload})}"

def qr_code_for_text(text: str) -> Image.Image:
    """Generates a QR code image from a given text string."""
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img

# ----------------------------- Core Settlement Logic -----------------------------
def settle(balances: List[float], names: List[str]) -> str:
    """Calculates and formats the final settlement text."""
    creditors = sorted([[i, bal] for i, bal in enumerate(balances) if bal > 0], key=lambda x: x[1], reverse=True)
    debtors = sorted([[i, -bal] for i, bal in enumerate(balances) if bal < 0], key=lambda x: x[1], reverse=True)
    
    i = j = 0
    lines = []
    while i < len(debtors) and j < len(creditors):
        d_idx, d_amt = debtors[i]
        c_idx, c_amt = creditors[j]
        pay_amt = min(d_amt, c_amt)
        lines.append(f"→ {names[d_idx]} pays ₹{pay_amt:.2f} to {names[c_idx]}")
        debtors[i][1] -= pay_amt
        creditors[j][1] -= pay_amt
        if debtors[i][1] < 0.01: i += 1
        if creditors[j][1] < 0.01: j += 1
    return "🤝 Settlements:\n" + ("\n".join(lines) if lines else "All settled!")

def calc_with_equal_share(total_amount: float, paid: List[float], names: List[str]):
    """Calculates balances based on a simple equal-share split."""
    n = len(names)
    owed_each = [total_amount / n] * n
    balances = [round(p - o, 2) for p, o in zip(paid, owed_each)]
    return owed_each, balances

def calc_with_itemized(items: List[dict], paid: List[float], names: List[str]):
    """Calculates balances based on itemized expenses."""
    n = len(names)
    idx = {name: i for i, name in enumerate(names)}
    owed = [0.0] * n
    total_amount = 0.0
    for it in items:
        amount = float(it["amount"])
        participants = it["participants"]  # list of names
        if amount <= 0 or not participants:
            continue
        total_amount += amount
        share = amount / len(participants)
        for person in participants:
            if person in idx:
                owed[idx[person]] += share
    owed = [round(x, 2) for x in owed]
    balances = [round(p - o, 2) for p, o in zip(paid, owed)]
    return total_amount, owed, balances

# ----------------------------- Data Models -----------------------------
@dataclass
class Item:
    name: str
    amount: float
    participants: List[str]

@dataclass
class AppState:
    stage: int = 1
    people: int = 1
    amount: float = 0.0
    names: List[str] = None
    paid: List[float] = None
    use_itemized: bool = False
    items: List[Item] = None
    owed: List[float] = None
    balances: List[float] = None

# ----------------------------- Groups Persistence -----------------------------
def download_groups_button(groups: Dict[str, List[str]]):
    """Creates a download button for saving groups as a JSON file."""
    buf = io.BytesIO()
    buf.write(json.dumps(groups, indent=2, ensure_ascii=False).encode("utf-8"))
    buf.seek(0)
    st.download_button("Download Groups (.json)", data=buf, file_name="groups.json", mime="application/json")

def upload_groups_from_file():
    """Provides a file uploader to load groups from a JSON file."""
    up = st.file_uploader("Upload Groups JSON", type=["json"], label_visibility="collapsed")
    if up:
        try:
            loaded = json.loads(up.read().decode("utf-8"))
            if isinstance(loaded, dict):
                st.session_state.groups.update(loaded)
                st.success("Groups imported.")
            else:
                st.error("Invalid JSON format. Please upload a dictionary of groups.")
        except Exception as e:
            st.error(f"Invalid JSON: {e}")

# ----------------------------- Charts -----------------------------
def charts_df(names: List[str], paid: List[float], owed: List[float], balances: List[float]) -> pd.DataFrame:
    """Creates a pandas DataFrame for charting."""
    df = pd.DataFrame({
        "Name": names,
        "Paid": paid,
        "Owed": owed,
        "Balance": balances
    })
    return df

def bar_paid_vs_owed(df: pd.DataFrame):
    """Generates an Altair bar chart for paid vs. owed amounts."""
    chart = (alt.Chart(df)
             .transform_fold(["Paid","Owed"], as_=["Type","Amount"])
             .mark_bar()
             .encode(x=alt.X("Name:N", sort=None), y="Amount:Q", color="Type:N", column=alt.Column("Type:N", header=alt.Header(title=None)))
             .properties(height=300))
    st.altair_chart(chart, use_container_width=True)

def bar_net_balance(df: pd.DataFrame):
    """Generates an Altair bar chart for net balances."""
    chart = (alt.Chart(df)
             .mark_bar()
             .encode(x=alt.X("Name:N", sort=None), y=alt.Y("Balance:Q", title="Net Balance (₹)"), color=alt.Color("Balance:Q", scale=alt.Scale(domain=[-1, 1], range=["#ef4444", "#22c55e"])))
             .properties(height=300, title="Net Balance (positive = receives, negative = pays)"))
    st.altair_chart(chart, use_container_width=True)

def pie_paid(df: pd.DataFrame):
    """Generates an Altair pie chart for total paid contributions."""
    base = pd.DataFrame({"Name": df["Name"], "Paid": df["Paid"]})
    total = base["Paid"].sum()
    if total <= 0:
        st.info("No payments to visualize yet.")
        return
    chart = (alt.Chart(base)
             .mark_arc(outerRadius=120)
             .encode(theta="Paid:Q", color="Name:N", tooltip=["Name","Paid"])
             .properties(height=350, title="Contribution to Total Paid"))
    st.altair_chart(chart, use_container_width=True)

# ----------------------------- App -----------------------------
def main():
    st.set_page_config(page_title="Expense Splitter Pro", page_icon="💰", layout="centered", initial_sidebar_state="expanded")
    st.markdown(APP_CSS, unsafe_allow_html=True)
    st.title("💸 Expense Splitter — Pro")
    st.caption("Clean splits • Itemized bills • Saved groups • QR sharing • Visual summaries")

    if "app" not in st.session_state:
        st.session_state.app = AppState(names=[], paid=[], items=[])
    if "groups" not in st.session_state:
        st.session_state.groups = {}

    app = st.session_state.app

    q = st.query_params
    if "state" in q and app.stage == 1:
        decoded = decode_state(q["state"])
        if decoded:
            app.names = decoded.get("names", [])
            app.people = len(app.names) if app.names else 1
            app.paid = decoded.get("paid", [0.0] * app.people)
            app.use_itemized = decoded.get("use_itemized", False)
            app.items = [Item(**i) for i in decoded.get("items", [])]
            app.amount = decoded.get("amount", 0.0)
            app.stage = decoded.get("stage", 2)
            st.success("Loaded state from shared link!")
            if app.stage == 3 and (app.owed is None or app.balances is None):
                if app.use_itemized:
                    app.amount, app.owed, app.balances = calc_with_itemized([asdict(x) for x in app.items], app.paid, app.names)
                else:
                    app.owed, app.balances = calc_with_equal_share(float(app.amount), app.paid, app.names)
            st.rerun()

    # ---------------- Sidebar: Groups ----------------
    with st.sidebar:
        st.markdown("### 👥 Saved Groups")
        if st.session_state.groups:
            chosen = st.selectbox("Load group", ["— Select —"] + list(st.session_state.groups.keys()), key="group_loader")
            if chosen and chosen != "— Select —":
                names = st.session_state.groups[chosen]
                app.names = names
                app.people = len(names)
                app.stage = 2
                st.success(f"Loaded group: {chosen}. Now fill in the amounts and calculate!")
                st.rerun()

        new_group = st.text_input("Group name", key="new_group_name")
        if st.button("Save Current Names as Group"):
            if new_group and app.names:
                st.session_state.groups[new_group] = app.names[:]
                st.success(f"Saved group '{new_group}'")
            else:
                st.warning("Enter a group name and have at least one name entered.")

        download_groups_button(st.session_state.groups)
        upload_groups_from_file()

        st.markdown("---")
        st.markdown("### ⚙️ Options")
        app.use_itemized = st.toggle("Use itemized expenses", value=app.use_itemized, help="Assign specific items to people instead of a simple equal split.", key="itemized_toggle")

        st.markdown("---")
        st.caption("Tip: Use the QR to share a link that restores the exact state.")

    # ---------------- Stage 1: totals (only for equal-share mode) ----------------
    if app.stage == 1 and not app.use_itemized:
        st.subheader("Step 1 · Overall Details")
        colA, colB = st.columns(2)
        with colA:
            people_count = st.number_input("Total People", min_value=1, step=1, value=app.people, key="people_input")
        with colB:
            total_amount = st.number_input("Total Amount (₹)", min_value=0.0, step=1.0, value=float(app.amount), key="amount_input")

        if st.button("➡ Next", use_container_width=True, type="primary"):
            if people_count > 0 and total_amount > 0:
                app.people = int(people_count)
                app.amount = float(total_amount)
                app.stage = 2
                st.rerun()
            else:
                st.error("Please enter valid numbers for people and amount.")

    # ---------------- Stage 2: names + paid (and itemized editor if enabled) ----------------
    if app.stage == 2:
        st.subheader("Step 2 · People & Payments")
        if not app.names or len(app.names) != app.people:
            app.names = [f"Person {i+1}" for i in range(app.people)]
        if not app.paid or len(app.paid) != app.people:
            app.paid = [0.0] * app.people
        
        st.markdown("#### Who is participating?")
        name_cols = st.columns(3)
        for i in range(app.people):
            with name_cols[i % 3]:
                app.names[i] = st.text_input(f"Name {i+1}", value=app.names[i], key=f"name_{i}")
        
        st.markdown("---")
        st.markdown("#### How much did each person pay?")
        paid_cols = st.columns(3)
        for i in range(app.people):
            with paid_cols[i % 3]:
                app.paid[i] = st.number_input(f"{app.names[i]} paid (₹)", min_value=0.0, step=1.0, value=float(app.paid[i]), key=f"paid_{i}")

        if app.use_itemized:
            st.markdown("#### 🧾 Itemized Expenses")
            if app.items is None:
                app.items = []
            
            with st.expander("Add / Edit Items", expanded=True):
                new_item_name = st.text_input("Item name", placeholder="Pizza")
                new_item_amount = st.number_input("Amount (₹)", min_value=0.0, step=1.0, value=0.0)
                part = st.multiselect("Who consumed this item?", options=app.names)
                
                cols = st.columns(2)
                with cols[0]:
                    if st.button("Add Item", use_container_width=True):
                        if new_item_name and new_item_amount > 0 and part:
                            app.items.append(Item(name=new_item_name, amount=float(new_item_amount), participants=part))
                            st.success("Item added.")
                            st.rerun()
                        else:
                            st.warning("Provide a name, positive amount, and at least one participant.")
                with cols[1]:
                    if st.button("Clear All Items", type="secondary", use_container_width=True):
                        app.items = []
                        st.rerun()

                if app.items:
                    df_items = pd.DataFrame([asdict(i) for i in app.items])
                    st.dataframe(df_items, use_container_width=True, height=220)

        nav_cols = st.columns(2)
        with nav_cols[0]:
            if st.button("⬅ Back", use_container_width=True, type="secondary"):
                app.stage = 1
                st.rerun()
        with nav_cols[1]:
            if st.button("💡 Calculate", use_container_width=True, type="primary"):
                if any(not n.strip() for n in app.names):
                    st.error("Please enter a name for every person.")
                else:
                    if app.use_itemized:
                        if not app.items:
                            st.error("Please add at least one item before calculating.")
                        else:
                            total_amount, owed, balances = calc_with_itemized([asdict(x) for x in app.items], app.paid, app.names)
                            app.amount = total_amount
                            app.owed = owed
                            app.balances = balances
                            app.stage = 3
                            st.rerun()
                    else:
                        if app.amount <= 0:
                            st.error("Please go back and enter a positive total amount.")
                        else:
                            app.owed, app.balances = calc_with_equal_share(float(app.amount), app.paid, app.names)
                            app.stage = 3
                            st.rerun()

    # ---------------- Stage 3: results + charts + QR ----------------
    if app.stage == 3:
        st.subheader("Results")
        if app.use_itemized:
            st.info(f"Total bill (itemized): **₹{app.amount:.2f}**")
        else:
            st.success(f"💰 Equal share per person: **₹{(app.amount / max(1, app.people)):.2f}**")

        summary_lines = ["📄 Summary:"]
        for name, paid, owed, bal in zip(app.names, app.paid, app.owed, app.balances):
            status = "receives" if bal > 0 else "pays" if bal < 0 else "is settled"
            summary_lines.append(f"• {name} paid ₹{paid:.2f} | owed ₹{owed:.2f} → {status} ₹{abs(bal):.2f}")
        summary_text = "\n".join(summary_lines)
        settlements_text = settle(app.balances, app.names)
        st.text_area("Results Summary", value=summary_text + "\n\n" + settlements_text, height=280, disabled=True)

        st.markdown("#### 📊 Visual Summary")
        df = charts_df(app.names, app.paid, app.owed, app.balances)
        bar_paid_vs_owed(df)
        bar_net_balance(df)
        pie_paid(df)

        # Fixed: New QR code and sharing UI
        st.markdown("#### 📲 Share")
        # Use a sensible default for local dev
        default_url = "http://localhost:8501"
        st.markdown(f"Copy your app's URL (e.g., `{default_url}`) from the browser's address bar and paste it below.")
        
        base_url = st.text_input("App URL", key="share_url", value=default_url)
        
        if st.button("Generate Share Link & QR", use_container_width=True):
            if base_url:
                share_state = {
                    "stage": 3,
                    "names": app.names,
                    "paid": app.paid,
                    "items": [asdict(x) for x in (app.items or [])],
                    "use_itemized": app.use_itemized,
                    "amount": app.amount,
                }
                link = build_share_link(base_url, share_state)
                st.success("Share link generated!")
                st.code(link, language="text")
                
                qr_img = qr_code_for_text(link)
                qr_buffer = io.BytesIO()
                qr_img.save(qr_buffer, format="PNG")
                qr_buffer.seek(0)
                
                st.image(qr_img, caption="Scan to open results", use_container_width=True)
                st.download_button(
                    label="Download QR Code",
                    data=qr_buffer,
                    file_name="expense_splitter_qr.png",
                    mime="image/png",
                )
            else:
                st.warning("Please enter a valid URL to generate the share link and QR code.")

        cols = st.columns(2)
        with cols[0]:
            if st.button("Start Over", use_container_width=True, type="secondary"):
                st.session_state.app = AppState(stage=1, people=1, amount=0.0, names=[], paid=[], items=[])
                st.rerun()
        with cols[1]:
            if st.button("Edit Details", use_container_width=True, type="primary"):
                app.stage = 2
                st.rerun()

    st.markdown("<div class='soft-card'><span class='pill'>Tip</span> You can save your usual friends as a group in the sidebar and load them next time in one click.</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
