import streamlit as st
import json, base64, io
import pandas as pd
import altair as alt
from PIL import Image
import qrcode
from dataclasses import dataclass, asdict
from typing import List, Dict
from urllib.parse import urlencode

# ----------------------------- Styling (High-Contrast Cute Theme) -----------------------------
APP_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@500;600;700&display=swap');
    
    html, body, [class*="css"] { 
        font-family: 'Quicksand', sans-serif; 
        color: #000000 !important; 
    }
    
    /* Custom Button Styling */
    .stButton > button {
        background-color: #A8E6CF !important; /* Mint Green */
        color: #000000 !important; /* Force black text */
        border-radius: 25px !important;
        border: none !important;
        box-shadow: 0 4px 10px rgba(168, 230, 207, 0.4) !important;
        font-weight: 700 !important;
        transition: all 0.3s ease !important;
    }
    .stButton > button:hover {
        background-color: #FFAAA5 !important; /* Soft Pink on hover */
        box-shadow: 0 6px 14px rgba(255, 170, 165, 0.5) !important;
        transform: translateY(-2px);
    }
    
    /* Soft Cards for groupings */
    .soft-card {
        background: #ffffff; 
        border: 2px solid #F6E7D8; 
        border-radius: 24px;
        padding: 20px; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.03);
        margin-bottom: 20px;
    }
    
    /* Cute pill badges */
    .pill {
        display: inline-block; padding: 6px 14px; border-radius: 20px;
        background: #FFAAA5; color: #000000; font-weight: 700; font-size: 0.85rem;
        box-shadow: 0 2px 5px rgba(255, 170, 165, 0.3);
    }
    
    /* Live Total Badge */
    .live-total-badge {
        display: inline-block; padding: 8px 18px; border-radius: 20px;
        background: #A8E6CF; color: #000000; font-weight: 700; font-size: 1rem;
        box-shadow: 0 2px 5px rgba(168, 230, 207, 0.4);
        border: 2px solid #000000;
        margin-top: 10px;
    }
    
    /* Text area styling - FORCED BLACK TEXT */
    textarea[readonly], textarea[disabled], .stTextArea textarea { 
        background-color: #F2EBE5 !important; 
        border: 2px solid #F6E7D8 !important;
        border-radius: 16px !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important; 
        font-weight: 700 !important;
        font-size: 1.05rem !important;
        opacity: 1 !important; 
    }
    
    /* Inputs - Scoped to avoid weird phantom shapes */
    .stTextInput input, .stNumberInput input {
        border-radius: 12px !important;
        color: #000000 !important;
        font-weight: 600 !important;
    }
</style>
"""

# ----------------------------- Serialization for Share Links -----------------------------
def encode_state(d: dict) -> str:
    raw = json.dumps(d, separators=(",", ":"), ensure_ascii=False)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")

def decode_state(s: str) -> dict:
    try:
        raw = base64.urlsafe_b64decode(s.encode("utf-8")).decode("utf-8")
        return json.loads(raw)
    except Exception:
        return {}

def build_share_link(base_url: str, state: dict) -> str:
    payload = encode_state(state)
    return f"{base_url}/?{urlencode({'state': payload})}"

def qr_code_for_text(text: str) -> Image.Image:
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#000000", back_color="#FFFDF9").convert("RGB")
    return img

# ----------------------------- Core Settlement Logic -----------------------------
def settle(balances: List[float], names: List[str]) -> str:
    creditors = sorted([[i, bal] for i, bal in enumerate(balances) if bal > 0], key=lambda x: x[1], reverse=True)
    debtors = sorted([[i, -bal] for i, bal in enumerate(balances) if bal < 0], key=lambda x: x[1], reverse=True)
    
    i = j = 0
    lines = []
    while i < len(debtors) and j < len(creditors):
        d_idx, d_amt = debtors[i]
        c_idx, c_amt = creditors[j]
        pay_amt = min(d_amt, c_amt)
        lines.append(f"✨ {names[d_idx]} pays ₹{pay_amt:.2f} to {names[c_idx]}")
        debtors[i][1] -= pay_amt
        creditors[j][1] -= pay_amt
        if debtors[i][1] < 0.01: i += 1
        if creditors[j][1] < 0.01: j += 1
    return "🤝 Settlements:\n" + ("\n".join(lines) if lines else "All settled! 🎉")

def calc_with_equal_share(total_amount: float, paid: List[float], names: List[str]):
    n = len(names)
    owed_each = [total_amount / n] * n
    balances = [round(p - o, 2) for p, o in zip(paid, owed_each)]
    return owed_each, balances

def calc_with_itemized(items: List[dict], paid: List[float], names: List[str]):
    n = len(names)
    idx = {name: i for i, name in enumerate(names)}
    owed = [0.0] * n
    total_amount = 0.0
    for it in items:
        amount = float(it["amount"])
        participants = it["participants"]
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
    buf = io.BytesIO()
    buf.write(json.dumps(groups, indent=2, ensure_ascii=False).encode("utf-8"))
    buf.seek(0)
    st.download_button("Download Groups 📥", data=buf, file_name="groups.json", mime="application/json")

def upload_groups_from_file():
    up = st.file_uploader("Upload Groups JSON", type=["json"], label_visibility="collapsed")
    if up:
        try:
            loaded = json.loads(up.read().decode("utf-8"))
            if isinstance(loaded, dict):
                st.session_state.groups.update(loaded)
                st.success("Groups imported! 🌸")
            else:
                st.error("Oops! Invalid format.")
        except Exception as e:
            st.error(f"Invalid JSON: {e}")

# ----------------------------- Charts -----------------------------
def charts_df(names: List[str], paid: List[float], owed: List[float], balances: List[float]) -> pd.DataFrame:
    df = pd.DataFrame({"Name": names, "Paid": paid, "Owed": owed, "Balance": balances})
    return df

def apply_chart_theme(chart):
    return chart.configure_axis(
        labelColor='#000000', titleColor='#000000', labelFontSize=12, titleFontSize=14
    ).configure_title(
        color='#000000', fontSize=16
    ).configure_legend(
        labelColor='#000000', titleColor='#000000', labelFontSize=12, titleFontSize=14
    )

def dual_pie_charts(df: pd.DataFrame):
    """Creates side-by-side pie charts for Paid and Owed amounts."""
    col1, col2 = st.columns(2)
    
    with col1:
        base_paid = pd.DataFrame({"Name": df["Name"], "Value": df["Paid"]})
        if base_paid["Value"].sum() > 0:
            chart_paid = (alt.Chart(base_paid)
                         .mark_arc(innerRadius=40, outerRadius=110)
                         .encode(
                             theta="Value:Q", 
                             color=alt.Color("Name:N", scale=alt.Scale(scheme="pastel1")), 
                             tooltip=["Name", "Value"]
                         )
                         .properties(height=300, title="Amount Paid (₹)"))
            st.altair_chart(apply_chart_theme(chart_paid), use_container_width=True)
        else:
            st.info("No payments recorded.")
            
    with col2:
        base_owed = pd.DataFrame({"Name": df["Name"], "Value": df["Owed"]})
        if base_owed["Value"].sum() > 0:
            chart_owed = (alt.Chart(base_owed)
                         .mark_arc(innerRadius=40, outerRadius=110)
                         .encode(
                             theta="Value:Q", 
                             color=alt.Color("Name:N", scale=alt.Scale(scheme="pastel2")), 
                             tooltip=["Name", "Value"]
                         )
                         .properties(height=300, title="Amount Owed (₹)"))
            st.altair_chart(apply_chart_theme(chart_owed), use_container_width=True)

def bar_net_balance(df: pd.DataFrame):
    chart = (alt.Chart(df)
             .mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8)
             .encode(
                 x=alt.X("Name:N", sort=None, axis=alt.Axis(labelAngle=0)), 
                 y=alt.Y("Balance:Q", title="Net Balance (₹)"), 
                 color=alt.Color("Balance:Q", scale=alt.Scale(domain=[-1, 1], range=["#FFAAA5", "#A8E6CF"]))
             ).properties(height=300, title="Net Balance (Green = Receives, Pink = Pays)"))
    st.altair_chart(apply_chart_theme(chart), use_container_width=True)

# ----------------------------- App -----------------------------
def main():
    st.set_page_config(page_title="Splitter Pro", page_icon="🍡", layout="centered", initial_sidebar_state="collapsed")
    st.markdown(APP_CSS, unsafe_allow_html=True)
    
    st.markdown("<h1 style='text-align: center; color: #FFAAA5; text-shadow: 1px 1px 2px rgba(0,0,0,0.1);'>💸 Splitter Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #000000; font-weight: 600;'>Clean splits • QR sharing • Cute visual summaries</p>", unsafe_allow_html=True)

    if "app" not in st.session_state:
        st.session_state.app = AppState(names=[], paid=[], items=[])
    if "groups" not in st.session_state:
        st.session_state.groups = {}

    app = st.session_state.app
    q = st.query_params

    # Check for Shared Link
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
            if app.stage == 3 and (app.owed is None or app.balances is None):
                if app.use_itemized:
                    app.amount, app.owed, app.balances = calc_with_itemized([asdict(x) for x in app.items], app.paid, app.names)
                else:
                    app.owed, app.balances = calc_with_equal_share(float(app.amount), app.paid, app.names)
            st.rerun()

    # ---------------- Sidebar ----------------
    with st.sidebar:
        st.markdown("### 👯‍♀️ Saved Groups")
        if st.session_state.groups:
            chosen = st.selectbox("Load group", ["— Select —"] + list(st.session_state.groups.keys()), key="group_loader")
            if chosen and chosen != "— Select —":
                names = st.session_state.groups[chosen]
                app.names = names
                app.people = len(names)
                app.stage = 2
                st.rerun()

        new_group = st.text_input("Group name", key="new_group_name")
        if st.button("Save Group 🌸"):
            if new_group and app.names:
                st.session_state.groups[new_group] = app.names[:]
                st.success("Group saved!")
            else:
                st.warning("Enter a name first!")

        download_groups_button(st.session_state.groups)
        upload_groups_from_file()

    # ---------------- Stage 1 ----------------
    if app.stage == 1:
        st.markdown("<div class='soft-card'>", unsafe_allow_html=True)
        st.subheader("Step 1 · The Basics")
        
        with st.expander("⚙️ Settings & Mode"):
            app.use_itemized = st.toggle("🧾 Use Itemized Expenses (Split line-by-line)", value=app.use_itemized)
            st.caption("Turn this on if you need to split specific items (like meals) unevenly.")
            
        if not app.use_itemized:
            colA, colB = st.columns(2)
            with colA:
                people_count = st.number_input("How many people?", min_value=1, step=1, value=app.people)
            with colB:
                total_amount = st.number_input("Total Amount (₹)", min_value=0.0, step=1.0, value=float(app.amount))

            if st.button("Let's Go! ✨", use_container_width=True):
                if people_count > 0 and total_amount > 0:
                    app.people, app.amount, app.stage = int(people_count), float(total_amount), 2
                    st.rerun()
                else:
                    st.error("Please enter valid numbers.")
        else:
            people_count = st.number_input("How many people?", min_value=1, step=1, value=app.people)
            if st.button("Let's Go! ✨", use_container_width=True):
                app.people, app.stage = int(people_count), 2
                st.rerun()
                
        st.markdown("</div>", unsafe_allow_html=True)

    # ---------------- Stage 2 ----------------
    if app.stage == 2:
        st.markdown("<div class='soft-card'>", unsafe_allow_html=True)
        st.subheader("Step 2 · Who Paid What?")
        
        if not app.names or len(app.names) != app.people:
            app.names = [f"Friend {i+1}" for i in range(app.people)]
        if not app.paid or len(app.paid) != app.people:
            app.paid = [0.0] * app.people
        
        name_cols = st.columns(3)
        for i in range(app.people):
            with name_cols[i % 3]:
                app.names[i] = st.text_input(f"Name {i+1}", value=app.names[i], key=f"name_{i}")
        
        st.markdown("---")
        paid_cols = st.columns(3)
        for i in range(app.people):
            with paid_cols[i % 3]:
                app.paid[i] = st.number_input(f"{app.names[i]} paid (₹)", min_value=0.0, step=1.0, value=float(app.paid[i]), key=f"paid_{i}")
        
        # --- NEW: Live Total Paid by Friends ---
        total_paid_by_friends = sum(app.paid)
        st.markdown(f"<div style='text-align: right; margin-top: 10px;'><span class='live-total-badge'>💸 Total Paid Entered: ₹{total_paid_by_friends:.2f}</span></div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        if app.use_itemized:
            st.markdown("<div class='soft-card'>", unsafe_allow_html=True)
            
            # --- Live Running Total for Items ---
            current_total = sum(item.amount for item in (app.items or []))
            
            # Display Side-by-Side Header and Total
            header_col1, header_col2 = st.columns([1, 1])
            with header_col1:
                st.subheader("🧾 Itemized Bill")
            with header_col2:
                st.markdown(f"<div style='text-align: right; padding-top: 5px;'><span class='live-total-badge'>🛒 Item Total: ₹{current_total:.2f}</span></div>", unsafe_allow_html=True)
            
            if app.items is None: app.items = []
            
            with st.expander("Add New Item ✨", expanded=True):
                new_item_name = st.text_input("Item name (e.g., Pizza)")
                new_item_amount = st.number_input("Amount (₹)", min_value=0.0, step=1.0, value=0.0)
                part = st.multiselect("Who shared this?", options=app.names)
                
                cols = st.columns(2)
                with cols[0]:
                    if st.button("Add Item", use_container_width=True):
                        if new_item_name and new_item_amount > 0 and part:
                            app.items.append(Item(name=new_item_name, amount=float(new_item_amount), participants=part))
                            st.rerun()
                with cols[1]:
                    if st.button("Clear Items", use_container_width=True):
                        app.items = []
                        st.rerun()

            if app.items:
                st.dataframe(pd.DataFrame([asdict(i) for i in app.items]), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        nav_cols = st.columns(2)
        with nav_cols[0]:
            if st.button("⬅ Back", use_container_width=True):
                app.stage = 1
                st.rerun()
        with nav_cols[1]:
            if st.button("Calculate! 🪄", use_container_width=True):
                if app.use_itemized:
                    total_amount, owed, balances = calc_with_itemized([asdict(x) for x in app.items], app.paid, app.names)
                    app.amount, app.owed, app.balances, app.stage = total_amount, owed, balances, 3
                else:
                    app.owed, app.balances = calc_with_equal_share(float(app.amount), app.paid, app.names)
                    app.stage = 3
                st.rerun()

    # ---------------- Stage 3 ----------------
    if app.stage == 3:
        st.markdown("<div class='soft-card'>", unsafe_allow_html=True)
        st.subheader("🎉 The Results")
        if app.use_itemized:
            st.markdown(f"**Total bill:** ₹{app.amount:.2f}")
        else:
            st.markdown(f"**Equal share per person:** ₹{(app.amount / max(1, app.people)):.2f}")

        summary_lines = []
        for name, paid, owed, bal in zip(app.names, app.paid, app.owed, app.balances):
            status = "receives" if bal > 0 else "pays" if bal < 0 else "is settled"
            summary_lines.append(f"• {name} paid ₹{paid:.2f} | owed ₹{owed:.2f} → {status} ₹{abs(bal):.2f}")
        
        st.text_area("Summary", value="\n".join(summary_lines) + "\n\n" + settle(app.balances, app.names), height=250, disabled=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("#### 📊 Visual Summary")
        df = charts_df(app.names, app.paid, app.owed, app.balances)
        
        # --- NEW: Side-by-Side Pie Charts for Paid and Owed ---
        dual_pie_charts(df) 
        
        bar_net_balance(df)

        st.markdown("<div class='soft-card'>", unsafe_allow_html=True)
        st.markdown("#### 📲 Share with Friends")
        
        base_url = st.text_input("App URL (paste your deployed link here)", value="http://localhost:8501")
        
        if st.button("Generate Magic Link & QR 🪄", use_container_width=True):
            share_state = {
                "stage": 3, "names": app.names, "paid": app.paid,
                "items": [asdict(x) for x in (app.items or [])],
                "use_itemized": app.use_itemized, "amount": app.amount,
            }
            link = build_share_link(base_url, share_state)
            st.code(link, language="text")
            
            qr_img = qr_code_for_text(link)
            qr_buffer = io.BytesIO()
            qr_img.save(qr_buffer, format="PNG")
            
            st.image(qr_img, caption="Scan to see results!", width=200)
            st.download_button("Download QR 📱", data=qr_buffer.getvalue(), file_name="split_qr.png", mime="image/png")
        st.markdown("</div>", unsafe_allow_html=True)

        cols = st.columns(2)
        with cols[0]:
            if st.button("Start Over 🔄", use_container_width=True):
                st.session_state.app = AppState(stage=1, people=1, amount=0.0, names=[], paid=[], items=[])
                st.rerun()
        with cols[1]:
            if st.button("Edit Details ✏️", use_container_width=True):
                app.stage = 2
                st.rerun()

if __name__ == "__main__":
    main()
