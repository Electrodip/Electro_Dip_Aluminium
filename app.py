
import io
import sqlite3
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st

DB_PATH = "electro_dip_aluminium.db"

st.set_page_config(
    page_title="Electro-Dip Aluminium Procurement",
    page_icon="🏭",
    layout="wide",
)

st.markdown("""
<style>
.block-container {padding-top: 1.1rem; padding-bottom: 2rem;}
.titlebar {
    background: linear-gradient(90deg,#17365D,#2F75B5);
    color:white; padding:18px 22px; border-radius:12px;
    font-size:28px; font-weight:700; margin-bottom:16px;
}
.kpi {border:1px solid #d9e2f3; border-radius:12px; padding:15px; background:#f8fbff;}
.kpi-label {font-size:13px;color:#555;}
.kpi-value {font-size:25px;font-weight:700;color:#17365D;}
.buy {background:#e2f0d9;border-left:7px solid #70ad47;padding:18px;border-radius:10px;}
.wait {background:#f4cccc;border-left:7px solid #c00000;padding:18px;border-radius:10px;}
.hold {background:#fff2cc;border-left:7px solid #ffc000;padding:18px;border-radius:10px;}
</style>
""", unsafe_allow_html=True)


def conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    c = conn()
    cur = c.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY CHECK(id=1),
        nalco_base REAL DEFAULT 330,
        ie07 REAL DEFAULT 0,
        freight REAL DEFAULT 4.5,
        handling REAL DEFAULT 1.5,
        gst REAL DEFAULT 18,
        monthly_requirement REAL DEFAULT 25000,
        current_stock REAL DEFAULT 6000,
        safety_stock REAL DEFAULT 3500,
        open_po REAL DEFAULT 5000,
        min_cover REAL DEFAULT 10,
        comfort_cover REAL DEFAULT 25,
        max_booking_pct REAL DEFAULT 70,
        forecast_trigger REAL DEFAULT 3
    )
    """)
    cur.execute("INSERT OR IGNORE INTO settings(id) VALUES(1)")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rate_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        effective_date TEXT,
        nalco_base REAL,
        ie07 REAL,
        lme REAL,
        usd_inr REAL,
        reason TEXT,
        source_ref TEXT,
        entered_by TEXT,
        created_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier TEXT,
        quoted_base REAL,
        ie07 REAL,
        freight REAL,
        other REAL,
        updated_at TEXT
    )
    """)

    if cur.execute("SELECT COUNT(*) FROM rate_history").fetchone()[0] == 0:
        sample = [
            ("2026-04-01",318,0,2850,83.2,"Opening sample","Replace with actual circular","System"),
            ("2026-04-15",322,0,2910,83.4,"Market increase","Replace with actual circular","System"),
            ("2026-05-01",326,0,2980,83.6,"LME strengthening","Replace with actual circular","System"),
            ("2026-05-16",331,0,3050,83.8,"Supply concern","Replace with actual circular","System"),
            ("2026-06-01",336,0,3120,84.0,"International increase","Replace with actual circular","System"),
            ("2026-06-16",335,0,3090,84.1,"Minor correction","Replace with actual circular","System"),
            ("2026-07-01",330,0,3030,84.2,"Sample July rate","Replace with actual circular","System"),
            ("2026-07-16",330,0,3060,84.3,"Sample no change","Replace with actual circular","System"),
        ]
        cur.executemany("""
        INSERT INTO rate_history
        (effective_date,nalco_base,ie07,lme,usd_inr,reason,source_ref,entered_by,created_at)
        VALUES(?,?,?,?,?,?,?,?,?)
        """, [(*r, datetime.now().isoformat(timespec="seconds")) for r in sample])

    if cur.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] == 0:
        sample_suppliers = [
            ("Supplier A",330,0,4.5,1.5),
            ("Supplier B",331,0,3.5,1.0),
            ("Supplier C",329,0,6.0,1.2),
        ]
        cur.executemany("""
        INSERT INTO suppliers(supplier,quoted_base,ie07,freight,other,updated_at)
        VALUES(?,?,?,?,?,?)
        """, [(*r, datetime.now().isoformat(timespec="seconds")) for r in sample_suppliers])

    c.commit()
    c.close()


def load_settings():
    return pd.read_sql_query("SELECT * FROM settings WHERE id=1", conn()).iloc[0].to_dict()


def save_settings(s):
    c = conn()
    c.execute("""
    UPDATE settings SET
    nalco_base=?,ie07=?,freight=?,handling=?,gst=?,monthly_requirement=?,
    current_stock=?,safety_stock=?,open_po=?,min_cover=?,comfort_cover=?,
    max_booking_pct=?,forecast_trigger=? WHERE id=1
    """, (
        s["nalco_base"],s["ie07"],s["freight"],s["handling"],s["gst"],
        s["monthly_requirement"],s["current_stock"],s["safety_stock"],s["open_po"],
        s["min_cover"],s["comfort_cover"],s["max_booking_pct"],s["forecast_trigger"]
    ))
    c.commit()
    c.close()


def load_history():
    df = pd.read_sql_query("SELECT * FROM rate_history ORDER BY effective_date", conn())
    if not df.empty:
        df["effective_date"] = pd.to_datetime(df["effective_date"])
        df["composite"] = df["nalco_base"] + df["ie07"]
        df["change"] = df["composite"].diff().fillna(0)
    return df


def load_suppliers():
    return pd.read_sql_query("SELECT * FROM suppliers ORDER BY supplier", conn())


def round_half(x):
    return round(x * 2) / 2


def forecast_model(s, h, weeks=5):
    current = float(s["nalco_base"] + s["ie07"])
    recent = h.tail(6).copy()
    changes = recent["composite"].diff().dropna()
    avg_change = float(changes.mean()) if len(changes) else 0
    avg_abs = max(float(changes.abs().mean()) if len(changes) else 1, 1)

    lme_effect = 0
    lme_vals = recent["lme"].dropna()
    if len(lme_vals) >= 2 and lme_vals.iloc[-2] != 0:
        lme_effect = ((lme_vals.iloc[-1]-lme_vals.iloc[-2])/lme_vals.iloc[-2])*100*0.18

    fx_effect = 0
    fx_vals = recent["usd_inr"].dropna()
    if len(fx_vals) >= 2 and fx_vals.iloc[-2] != 0:
        fx_effect = ((fx_vals.iloc[-1]-fx_vals.iloc[-2])/fx_vals.iloc[-2])*100*0.12

    drift = round_half(float(np.clip(avg_change*0.55 + lme_effect + fx_effect, -6, 6)))
    monday = date.today() - timedelta(days=date.today().weekday())

    daily = s["monthly_requirement"]/30 if s["monthly_requirement"] else 0
    cover = (s["current_stock"]+s["open_po"])/daily if daily else 0

    rows = []
    for i in range(1, weeks+1):
        expected = round_half(current + drift*i + avg_change*0.15*(i-1))
        low = round_half(expected - avg_abs*(0.8+i*0.2))
        high = round_half(expected + avg_abs*(0.8+i*0.2))
        change = expected-current
        confidence = abs(drift)/max(avg_abs,1) - (i-1)*0.12
        probability = "High" if confidence >= 1.5 else "Medium-High" if confidence >= .8 else "Medium" if confidence >= .3 else "Low"

        if cover < s["min_cover"]:
            action = "BUY NOW – LOW STOCK"
        elif change >= s["forecast_trigger"]:
            action = "BUY / LOCK 50–70%"
        elif low < current-2:
            action = "WAIT FOR LOWER RATE"
        elif change > 0:
            action = "BUY 25–40% GRADUALLY"
        else:
            action = "HOLD / BUY AS REQUIRED"

        ws = monday + timedelta(days=(i-1)*7)
        rows.append({
            "Week Start": ws,
            "Week End": ws+timedelta(days=6),
            "Expected NALCO": expected-s["ie07"],
            "Expected IE-07": s["ie07"],
            "Expected Composite": expected,
            "Low": low,
            "High": high,
            "Expected Change": change,
            "Probability": probability,
            "Action": action,
            "Remarks": f"Trend {avg_change:.2f}; LME {lme_effect:.2f}; FX {fx_effect:.2f}"
        })
    return pd.DataFrame(rows), drift


def metrics(s, f, h):
    composite = s["nalco_base"]+s["ie07"]
    taxable = composite+s["freight"]+s["handling"]
    landed = taxable*(1+s["gst"]/100)
    daily = s["monthly_requirement"]/30 if s["monthly_requirement"] else 0
    available = s["current_stock"]+s["open_po"]
    cover = available/daily if daily else 0
    net_qty = max(0, s["monthly_requirement"]+s["safety_stock"]-available)
    suggested = min(net_qty, s["max_booking_pct"]/100*s["monthly_requirement"])
    avg4 = h["composite"].tail(4).mean() if not h.empty else composite
    next_change = f["Expected Change"].head(2).mean()

    if cover < s["min_cover"]:
        return composite, landed, cover, net_qty, suggested, "BUY NOW – LOW STOCK", "buy"
    if next_change >= s["forecast_trigger"]:
        return composite, landed, cover, net_qty, suggested, "BUY / LOCK RATE", "buy"
    if composite > avg4 + 2:
        return composite, landed, cover, net_qty, suggested, "WAIT / BUY MINIMUM", "wait"
    return composite, landed, cover, net_qty, suggested, "HOLD / STAGGER BUY", "hold"


def export_excel(s,h,f,sup):
    b = io.BytesIO()
    with pd.ExcelWriter(b, engine="openpyxl") as w:
        pd.DataFrame([s]).to_excel(w, sheet_name="Inputs", index=False)
        h.to_excel(w, sheet_name="Rate History", index=False)
        f.to_excel(w, sheet_name="Forecast", index=False)
        sup.to_excel(w, sheet_name="Suppliers", index=False)
    return b.getvalue()


init_db()
s = load_settings()
h = load_history()
f, drift = forecast_model(s,h)
sup = load_suppliers()
composite, landed, cover, net_qty, suggested, decision, cls = metrics(s,f,h)

st.markdown('<div class="titlebar">ELECTRO-DIP | NALCO + IE-07 Aluminium Procurement</div>', unsafe_allow_html=True)

tabs = st.tabs(["Dashboard","Inputs","Rate History","Automatic Forecast","Suppliers","Export"])

with tabs[0]:
    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(f'<div class="kpi"><div class="kpi-label">Current Composite</div><div class="kpi-value">₹{composite:,.2f}/kg</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi"><div class="kpi-label">Landed Rate incl. GST</div><div class="kpi-value">₹{landed:,.2f}/kg</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi"><div class="kpi-label">Stock Cover</div><div class="kpi-value">{cover:,.1f} days</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="kpi"><div class="kpi-label">Net Qty to Buy</div><div class="kpi-value">{net_qty:,.0f} kg</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="{cls}"><b>Recommendation:</b> {decision}<br><b>Suggested booking:</b> {suggested:,.0f} kg<br><b>Forecast drift:</b> ₹{drift:,.2f}/kg per week</div>', unsafe_allow_html=True)

    left,right = st.columns([1.4,1])
    with left:
        st.subheader("Composite Rate Trend")
        st.line_chart(h.set_index("effective_date")[["composite"]])
    with right:
        st.subheader("Next Five Weeks")
        st.dataframe(f[["Week Start","Expected Composite","Low","High","Action"]], use_container_width=True, hide_index=True)

with tabs[1]:
    with st.form("settings"):
        c1,c2,c3 = st.columns(3)
        vals = {}
        with c1:
            vals["nalco_base"] = st.number_input("NALCO Base ₹/kg", value=float(s["nalco_base"]), step=0.5)
            vals["ie07"] = st.number_input("IE-07 ₹/kg", value=float(s["ie07"]), step=0.5)
            vals["freight"] = st.number_input("Freight ₹/kg", value=float(s["freight"]), step=0.1)
            vals["handling"] = st.number_input("Handling ₹/kg", value=float(s["handling"]), step=0.1)
            vals["gst"] = st.number_input("GST %", value=float(s["gst"]), min_value=0.0, max_value=100.0)
        with c2:
            vals["monthly_requirement"] = st.number_input("Monthly Requirement kg", value=float(s["monthly_requirement"]), step=100.0)
            vals["current_stock"] = st.number_input("Current Stock kg", value=float(s["current_stock"]), step=100.0)
            vals["safety_stock"] = st.number_input("Safety Stock kg", value=float(s["safety_stock"]), step=100.0)
            vals["open_po"] = st.number_input("Open PO kg", value=float(s["open_po"]), step=100.0)
        with c3:
            vals["min_cover"] = st.number_input("Minimum Cover days", value=float(s["min_cover"]))
            vals["comfort_cover"] = st.number_input("Comfort Cover days", value=float(s["comfort_cover"]))
            vals["max_booking_pct"] = st.number_input("Maximum Booking %", value=float(s["max_booking_pct"]), min_value=0.0, max_value=100.0)
            vals["forecast_trigger"] = st.number_input("Forecast Trigger ₹/kg", value=float(s["forecast_trigger"]), step=0.5)
        if st.form_submit_button("Save Inputs", type="primary"):
            save_settings(vals)
            st.success("Inputs saved.")
            st.rerun()

with tabs[2]:
    with st.form("history"):
        c1,c2,c3,c4 = st.columns(4)
        d = c1.date_input("Effective Date", value=date.today())
        nb = c2.number_input("NALCO Base", value=float(s["nalco_base"]), step=0.5)
        ie = c3.number_input("IE-07", value=float(s["ie07"]), step=0.5)
        lme = c4.number_input("LME US$/MT", value=float(h["lme"].dropna().iloc[-1]) if h["lme"].notna().any() else 0.0)
        c5,c6,c7 = st.columns(3)
        fx = c5.number_input("USD/INR", value=float(h["usd_inr"].dropna().iloc[-1]) if h["usd_inr"].notna().any() else 0.0)
        reason = c6.text_input("Reason / Circular")
        source = c7.text_input("Source / Reference")
        entered = st.text_input("Entered By")
        if st.form_submit_button("Add Revision", type="primary"):
            c = conn()
            c.execute("""
            INSERT INTO rate_history(effective_date,nalco_base,ie07,lme,usd_inr,reason,source_ref,entered_by,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,(d.isoformat(),nb,ie,lme,fx,reason,source,entered,datetime.now().isoformat(timespec="seconds")))
            c.commit(); c.close()
            st.success("Revision added.")
            st.rerun()
    show = h.copy()
    show["effective_date"] = show["effective_date"].dt.date
    st.dataframe(show[["effective_date","nalco_base","ie07","composite","change","lme","usd_inr","reason","source_ref","entered_by"]],
                 use_container_width=True, hide_index=True)

with tabs[3]:
    st.metric("Calculated Weekly Drift", f"₹{drift:,.2f}/kg")
    st.dataframe(f, use_container_width=True, hide_index=True)
    st.caption("This is planning guidance and not a guaranteed market price.")

with tabs[4]:
    with st.form("supplier"):
        c1,c2,c3,c4,c5 = st.columns(5)
        name = c1.text_input("Supplier")
        qb = c2.number_input("Quoted Base", value=float(s["nalco_base"]), step=0.5)
        sie = c3.number_input("IE-07", value=float(s["ie07"]), step=0.5)
        fr = c4.number_input("Freight", value=0.0, step=0.1)
        oth = c5.number_input("Other Charges", value=0.0, step=0.1)
        if st.form_submit_button("Add Supplier Quote") and name.strip():
            c = conn()
            c.execute("""INSERT INTO suppliers(supplier,quoted_base,ie07,freight,other,updated_at)
                         VALUES(?,?,?,?,?,?)""",
                      (name.strip(),qb,sie,fr,oth,datetime.now().isoformat(timespec="seconds")))
            c.commit(); c.close()
            st.success("Supplier quote added.")
            st.rerun()
    sv = sup.copy()
    sv["Landed Before GST"] = sv["quoted_base"]+sv["ie07"]+sv["freight"]+sv["other"]
    sv["Landed incl. GST"] = sv["Landed Before GST"]*(1+s["gst"]/100)
    st.dataframe(sv, use_container_width=True, hide_index=True)

with tabs[5]:
    st.download_button(
        "Download Complete Excel Report",
        export_excel(s,h,f,sup),
        file_name=f"Electro_Dip_Aluminium_Report_{date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )
    st.info("For online deployment, upload this app to Streamlit Community Cloud, Render, Railway, or your company server.")
