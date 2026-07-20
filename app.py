
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

st.markdown(
    """
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    .titlebar {
        background: linear-gradient(90deg,#17365D,#2F75B5);
        color:white; padding:18px 22px; border-radius:12px;
        font-size:28px; font-weight:700; margin-bottom:16px;
    }
    .kpi {
        border:1px solid #d9e2f3; border-radius:12px;
        padding:15px; background:#f8fbff;
    }
    .kpi-label {font-size:13px;color:#555;}
    .kpi-value {font-size:25px;font-weight:700;color:#17365D;}
    .buy {background:#e2f0d9;border-left:7px solid #70ad47;padding:18px;border-radius:10px;}
    .wait {background:#f4cccc;border-left:7px solid #c00000;padding:18px;border-radius:10px;}
    .hold {background:#fff2cc;border-left:7px solid #ffc000;padding:18px;border-radius:10px;}

    .compact-cell {
        display:flex;
        align-items:center;
        min-height:30px;
        padding:3px 6px;
        border-radius:6px;
        font-size:0.92rem;
        line-height:1.1;
        white-space:normal;
    }
    .cell-up {
        background:#d9ead3;
        color:#166534;
        font-weight:700;
        border:1px solid #b6d7a8;
    }
    .cell-down {
        background:#f4cccc;
        color:#991b1b;
        font-weight:700;
        border:1px solid #e6b8af;
    }
    .cell-flat {
        background:#fff2cc;
        color:#7f6000;
        font-weight:700;
        border:1px solid #f1d98a;
    }
    .cell-latest {
        background:#fff2cc;
        color:#7f6000;
        font-weight:700;
        border:1px solid #f1d98a;
    }
    .cell-best {
        background:#d9ead3;
        color:#166534;
        font-weight:700;
        border:1px solid #93c47d;
    }
    .cell-worst {
        background:#f4cccc;
        color:#991b1b;
        font-weight:700;
        border:1px solid #e06666;
    }
    div[data-testid="stHorizontalBlock"] {
        gap:0.35rem;
    }
    div.stButton > button {
        min-height:30px;
        height:30px;
        padding:0.1rem 0.45rem;
        line-height:1;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def cell_html(text, css_class=""):
    return (
        f'<div class="compact-cell {css_class}">{text}</div>'
    )


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
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
        """
    )
    cur.execute("INSERT OR IGNORE INTO settings(id) VALUES(1)")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rate_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            effective_date TEXT NOT NULL,
            nalco_base REAL NOT NULL,
            ie07 REAL NOT NULL DEFAULT 0,
            lme REAL DEFAULT 0,
            usd_inr REAL DEFAULT 0,
            reason TEXT DEFAULT '',
            source_ref TEXT DEFAULT '',
            entered_by TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier TEXT NOT NULL,
            quoted_base REAL NOT NULL,
            ie07 REAL NOT NULL DEFAULT 0,
            freight REAL NOT NULL DEFAULT 0,
            other REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
        """
    )

    if cur.execute("SELECT COUNT(*) FROM rate_history").fetchone()[0] == 0:
        sample = [
            ("2026-04-01", 318, 0, 2850, 83.2, "Opening sample", "Replace with actual circular", "System"),
            ("2026-04-15", 322, 0, 2910, 83.4, "Market increase", "Replace with actual circular", "System"),
            ("2026-05-01", 326, 0, 2980, 83.6, "LME strengthening", "Replace with actual circular", "System"),
            ("2026-05-16", 331, 0, 3050, 83.8, "Supply concern", "Replace with actual circular", "System"),
            ("2026-06-01", 336, 0, 3120, 84.0, "International increase", "Replace with actual circular", "System"),
            ("2026-06-16", 335, 0, 3090, 84.1, "Minor correction", "Replace with actual circular", "System"),
            ("2026-07-01", 330, 0, 3030, 84.2, "Sample July rate", "Replace with actual circular", "System"),
            ("2026-07-16", 330, 0, 3060, 84.3, "Sample no change", "Replace with actual circular", "System"),
        ]
        cur.executemany(
            """
            INSERT INTO rate_history(
                effective_date,nalco_base,ie07,lme,usd_inr,
                reason,source_ref,entered_by,created_at
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            [(*row, datetime.now().isoformat(timespec="seconds")) for row in sample],
        )

    if cur.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] == 0:
        sample_suppliers = [
            ("Supplier A", 330, 0, 4.5, 1.5),
            ("Supplier B", 331, 0, 3.5, 1.0),
            ("Supplier C", 329, 0, 6.0, 1.2),
        ]
        cur.executemany(
            """
            INSERT INTO suppliers(
                supplier,quoted_base,ie07,freight,other,updated_at
            )
            VALUES(?,?,?,?,?,?)
            """,
            [(*row, datetime.now().isoformat(timespec="seconds")) for row in sample_suppliers],
        )

    conn.commit()
    conn.close()


def load_settings():
    return pd.read_sql_query(
        "SELECT * FROM settings WHERE id=1", get_conn()
    ).iloc[0].to_dict()


def save_settings(values):
    conn = get_conn()
    conn.execute(
        """
        UPDATE settings SET
            nalco_base=?,ie07=?,freight=?,handling=?,gst=?,
            monthly_requirement=?,current_stock=?,safety_stock=?,open_po=?,
            min_cover=?,comfort_cover=?,max_booking_pct=?,forecast_trigger=?
        WHERE id=1
        """,
        (
            values["nalco_base"],
            values["ie07"],
            values["freight"],
            values["handling"],
            values["gst"],
            values["monthly_requirement"],
            values["current_stock"],
            values["safety_stock"],
            values["open_po"],
            values["min_cover"],
            values["comfort_cover"],
            values["max_booking_pct"],
            values["forecast_trigger"],
        ),
    )
    conn.commit()
    conn.close()


def load_history():
    df = pd.read_sql_query(
        "SELECT * FROM rate_history ORDER BY effective_date, id", get_conn()
    )
    if not df.empty:
        df["effective_date"] = pd.to_datetime(df["effective_date"])
        df["composite"] = df["nalco_base"] + df["ie07"]
        df["change"] = df["composite"].diff().fillna(0)
    return df


def load_suppliers():
    return pd.read_sql_query(
        "SELECT * FROM suppliers ORDER BY supplier, id", get_conn()
    )


def round_half(value):
    return round(value * 2) / 2


def generate_forecast(settings, history, weeks=5):
    current = float(settings["nalco_base"] + settings["ie07"])

    if len(history) < 3:
        raise ValueError("At least three Rate History records are required.")

    recent = history.tail(6).copy()
    changes = recent["composite"].diff().dropna()
    average_change = float(changes.mean()) if len(changes) else 0.0
    average_absolute_change = max(
        float(changes.abs().mean()) if len(changes) else 1.0,
        1.0,
    )

    lme_effect = 0.0
    lme_values = recent["lme"].dropna()
    if len(lme_values) >= 2 and lme_values.iloc[-2] != 0:
        lme_effect = (
            (lme_values.iloc[-1] - lme_values.iloc[-2])
            / lme_values.iloc[-2]
            * 100
            * 0.18
        )

    fx_effect = 0.0
    fx_values = recent["usd_inr"].dropna()
    if len(fx_values) >= 2 and fx_values.iloc[-2] != 0:
        fx_effect = (
            (fx_values.iloc[-1] - fx_values.iloc[-2])
            / fx_values.iloc[-2]
            * 100
            * 0.12
        )

    weekly_drift = round_half(
        float(
            np.clip(
                average_change * 0.55 + lme_effect + fx_effect,
                -6,
                6,
            )
        )
    )

    monday = date.today() - timedelta(days=date.today().weekday())
    daily_consumption = (
        settings["monthly_requirement"] / 30
        if settings["monthly_requirement"]
        else 0
    )
    stock_cover = (
        (settings["current_stock"] + settings["open_po"]) / daily_consumption
        if daily_consumption
        else 0
    )

    rows = []
    for week_number in range(1, weeks + 1):
        expected = round_half(
            current
            + weekly_drift * week_number
            + average_change * 0.15 * (week_number - 1)
        )
        low_case = round_half(
            expected
            - average_absolute_change * (0.8 + week_number * 0.2)
        )
        high_case = round_half(
            expected
            + average_absolute_change * (0.8 + week_number * 0.2)
        )
        expected_change = expected - current

        confidence = (
            abs(weekly_drift) / max(average_absolute_change, 1)
            - (week_number - 1) * 0.12
        )
        if confidence >= 1.5:
            probability = "High"
        elif confidence >= 0.8:
            probability = "Medium-High"
        elif confidence >= 0.3:
            probability = "Medium"
        else:
            probability = "Low"

        if stock_cover < settings["min_cover"]:
            action = "BUY NOW – LOW STOCK"
        elif expected_change >= settings["forecast_trigger"]:
            action = "BUY / LOCK 50–70%"
        elif low_case < current - 2:
            action = "WAIT FOR LOWER RATE"
        elif expected_change > 0:
            action = "BUY 25–40% GRADUALLY"
        else:
            action = "HOLD / BUY AS REQUIRED"

        week_start = monday + timedelta(days=(week_number - 1) * 7)

        rows.append(
            {
                "Week Start": week_start,
                "Week End": week_start + timedelta(days=6),
                "Expected NALCO": expected - settings["ie07"],
                "Expected IE-07": settings["ie07"],
                "Expected Composite": expected,
                "Low": low_case,
                "High": high_case,
                "Expected Change": expected_change,
                "Probability": probability,
                "Action": action,
                "Remarks": (
                    f"Trend {average_change:.2f}; "
                    f"LME effect {lme_effect:.2f}; "
                    f"FX effect {fx_effect:.2f}"
                ),
            }
        )

    return pd.DataFrame(rows), weekly_drift


def calculate_metrics(settings, forecast, history):
    composite = settings["nalco_base"] + settings["ie07"]
    taxable = composite + settings["freight"] + settings["handling"]
    landed = taxable * (1 + settings["gst"] / 100)

    daily_consumption = (
        settings["monthly_requirement"] / 30
        if settings["monthly_requirement"]
        else 0
    )
    available = settings["current_stock"] + settings["open_po"]
    cover = available / daily_consumption if daily_consumption else 0

    net_qty = max(
        0,
        settings["monthly_requirement"]
        + settings["safety_stock"]
        - available,
    )
    suggested_qty = min(
        net_qty,
        settings["max_booking_pct"]
        / 100
        * settings["monthly_requirement"],
    )

    average_four = (
        history["composite"].tail(4).mean()
        if not history.empty
        else composite
    )
    next_change = forecast["Expected Change"].head(2).mean()

    if cover < settings["min_cover"]:
        return (
            composite,
            landed,
            cover,
            net_qty,
            suggested_qty,
            "BUY NOW – LOW STOCK",
            "buy",
        )

    if next_change >= settings["forecast_trigger"]:
        return (
            composite,
            landed,
            cover,
            net_qty,
            suggested_qty,
            "BUY / LOCK RATE",
            "buy",
        )

    if composite > average_four + 2:
        return (
            composite,
            landed,
            cover,
            net_qty,
            suggested_qty,
            "WAIT / BUY MINIMUM",
            "wait",
        )

    return (
        composite,
        landed,
        cover,
        net_qty,
        suggested_qty,
        "HOLD / STAGGER BUY",
        "hold",
    )


def export_excel(settings, history, forecast, suppliers):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([settings]).to_excel(
            writer, sheet_name="Inputs", index=False
        )
        history.to_excel(
            writer, sheet_name="Rate History", index=False
        )
        forecast.to_excel(
            writer, sheet_name="Forecast", index=False
        )
        suppliers.to_excel(
            writer, sheet_name="Suppliers", index=False
        )
    return output.getvalue()


init_db()

settings = load_settings()
history = load_history()
suppliers = load_suppliers()
forecast, drift = generate_forecast(settings, history)

(
    composite,
    landed,
    cover,
    net_qty,
    suggested_qty,
    decision,
    decision_class,
) = calculate_metrics(settings, forecast, history)

st.markdown(
    '<div class="titlebar">ELECTRO-DIP | NALCO + IE-07 Aluminium Procurement</div>',
    unsafe_allow_html=True,
)

tabs = st.tabs(
    [
        "Dashboard",
        "Inputs",
        "Rate History",
        "Automatic Forecast",
        "Suppliers",
        "Export",
    ]
)

with tabs[0]:
    col1, col2, col3, col4 = st.columns(4)

    col1.markdown(
        f"""
        <div class="kpi">
            <div class="kpi-label">Current Composite</div>
            <div class="kpi-value">₹{composite:,.2f}/kg</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col2.markdown(
        f"""
        <div class="kpi">
            <div class="kpi-label">Landed Rate incl. GST</div>
            <div class="kpi-value">₹{landed:,.2f}/kg</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col3.markdown(
        f"""
        <div class="kpi">
            <div class="kpi-label">Stock Cover</div>
            <div class="kpi-value">{cover:,.1f} days</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col4.markdown(
        f"""
        <div class="kpi">
            <div class="kpi-label">Net Qty to Buy</div>
            <div class="kpi-value">{net_qty:,.0f} kg</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="{decision_class}">
            <b>Recommendation:</b> {decision}<br>
            <b>Suggested booking:</b> {suggested_qty:,.0f} kg<br>
            <b>Forecast drift:</b> ₹{drift:,.2f}/kg per week
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.4, 1])

    with left:
        st.subheader("Composite Rate Trend")
        st.line_chart(
            history.set_index("effective_date")[["composite"]]
        )

    with right:
        st.subheader("Next Five Weeks")
        st.dataframe(
            forecast[
                [
                    "Week Start",
                    "Expected Composite",
                    "Low",
                    "High",
                    "Action",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

with tabs[1]:
    st.subheader("Master Inputs")

    with st.form("settings_form"):
        col1, col2, col3 = st.columns(3)
        values = {}

        with col1:
            values["nalco_base"] = st.number_input(
                "NALCO Base ₹/kg",
                value=float(settings["nalco_base"]),
                step=0.5,
            )
            values["ie07"] = st.number_input(
                "IE-07 ₹/kg",
                value=float(settings["ie07"]),
                step=0.5,
            )
            values["freight"] = st.number_input(
                "Freight ₹/kg",
                value=float(settings["freight"]),
                step=0.1,
            )
            values["handling"] = st.number_input(
                "Handling ₹/kg",
                value=float(settings["handling"]),
                step=0.1,
            )
            values["gst"] = st.number_input(
                "GST %",
                value=float(settings["gst"]),
                min_value=0.0,
                max_value=100.0,
            )

        with col2:
            values["monthly_requirement"] = st.number_input(
                "Monthly Requirement kg",
                value=float(settings["monthly_requirement"]),
                min_value=0.0,
                step=100.0,
            )
            values["current_stock"] = st.number_input(
                "Current Stock kg",
                value=float(settings["current_stock"]),
                min_value=0.0,
                step=100.0,
            )
            values["safety_stock"] = st.number_input(
                "Safety Stock kg",
                value=float(settings["safety_stock"]),
                min_value=0.0,
                step=100.0,
            )
            values["open_po"] = st.number_input(
                "Open PO kg",
                value=float(settings["open_po"]),
                min_value=0.0,
                step=100.0,
            )

        with col3:
            values["min_cover"] = st.number_input(
                "Minimum Cover days",
                value=float(settings["min_cover"]),
                min_value=0.0,
            )
            values["comfort_cover"] = st.number_input(
                "Comfort Cover days",
                value=float(settings["comfort_cover"]),
                min_value=0.0,
            )
            values["max_booking_pct"] = st.number_input(
                "Maximum Booking %",
                value=float(settings["max_booking_pct"]),
                min_value=0.0,
                max_value=100.0,
            )
            values["forecast_trigger"] = st.number_input(
                "Forecast Trigger ₹/kg",
                value=float(settings["forecast_trigger"]),
                min_value=0.0,
                step=0.5,
            )

        if st.form_submit_button("Save Inputs", type="primary"):
            save_settings(values)
            st.success("Inputs saved successfully.")
            st.rerun()

with tabs[2]:
    st.subheader("NALCO / IE-07 Rate History")

    add_tab, edit_tab, delete_tab = st.tabs(
        ["Add Revision", "Edit Revision", "Delete Revision"]
    )

    with add_tab:
        with st.form("add_revision_form"):
            col1, col2, col3, col4 = st.columns(4)

            effective_date = col1.date_input(
                "Effective Date",
                value=date.today(),
            )
            nalco_base = col2.number_input(
                "NALCO Base",
                value=float(settings["nalco_base"]),
                step=0.5,
            )
            ie07 = col3.number_input(
                "IE-07",
                value=float(settings["ie07"]),
                step=0.5,
            )
            lme = col4.number_input(
                "LME US$/MT",
                value=(
                    float(history["lme"].dropna().iloc[-1])
                    if history["lme"].notna().any()
                    else 0.0
                ),
            )

            col5, col6, col7 = st.columns(3)

            usd_inr = col5.number_input(
                "USD/INR",
                value=(
                    float(history["usd_inr"].dropna().iloc[-1])
                    if history["usd_inr"].notna().any()
                    else 0.0
                ),
            )
            reason = col6.text_input("Reason / Circular")
            source_ref = col7.text_input("Source / Reference")
            entered_by = st.text_input("Entered By")

            if st.form_submit_button(
                "Add Revision",
                type="primary",
            ):
                conn = get_conn()
                conn.execute(
                    """
                    INSERT INTO rate_history(
                        effective_date,nalco_base,ie07,lme,usd_inr,
                        reason,source_ref,entered_by,created_at
                    )
                    VALUES(?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        effective_date.isoformat(),
                        nalco_base,
                        ie07,
                        lme,
                        usd_inr,
                        reason,
                        source_ref,
                        entered_by,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                conn.commit()
                conn.close()
                st.success("Revision added successfully.")
                st.rerun()

    if history.empty:
        with edit_tab:
            st.info("No records are available to edit.")
        with delete_tab:
            st.info("No records are available to delete.")
    else:
        record_options = {}
        for _, row in history.sort_values(
            "effective_date",
            ascending=False,
        ).iterrows():
            label = (
                f"{row['effective_date'].date()} | "
                f"NALCO ₹{row['nalco_base']:.2f} | "
                f"IE-07 ₹{row['ie07']:.2f} | "
                f"Composite ₹{row['composite']:.2f} | "
                f"ID {int(row['id'])}"
            )
            record_options[label] = int(row["id"])

        with edit_tab:
            selected_edit_label = st.selectbox(
                "Select revision to edit",
                options=list(record_options.keys()),
                key="edit_record",
            )
            selected_edit_id = record_options[selected_edit_label]
            selected_edit_row = history.loc[
                history["id"] == selected_edit_id
            ].iloc[0]

            with st.form("edit_revision_form"):
                col1, col2, col3, col4 = st.columns(4)

                edited_date = col1.date_input(
                    "Effective Date",
                    value=selected_edit_row["effective_date"].date(),
                    key="edited_date",
                )
                edited_nalco = col2.number_input(
                    "NALCO Base",
                    value=float(selected_edit_row["nalco_base"]),
                    step=0.5,
                    key="edited_nalco",
                )
                edited_ie07 = col3.number_input(
                    "IE-07",
                    value=float(selected_edit_row["ie07"]),
                    step=0.5,
                    key="edited_ie07",
                )
                edited_lme = col4.number_input(
                    "LME US$/MT",
                    value=float(selected_edit_row["lme"] or 0),
                    key="edited_lme",
                )

                col5, col6, col7 = st.columns(3)

                edited_usd = col5.number_input(
                    "USD/INR",
                    value=float(selected_edit_row["usd_inr"] or 0),
                    key="edited_usd",
                )
                edited_reason = col6.text_input(
                    "Reason / Circular",
                    value=str(selected_edit_row["reason"] or ""),
                    key="edited_reason",
                )
                edited_source = col7.text_input(
                    "Source / Reference",
                    value=str(selected_edit_row["source_ref"] or ""),
                    key="edited_source",
                )
                edited_by = st.text_input(
                    "Entered By",
                    value=str(selected_edit_row["entered_by"] or ""),
                    key="edited_by",
                )

                if st.form_submit_button(
                    "Save Changes",
                    type="primary",
                ):
                    conn = get_conn()
                    conn.execute(
                        """
                        UPDATE rate_history SET
                            effective_date=?,
                            nalco_base=?,
                            ie07=?,
                            lme=?,
                            usd_inr=?,
                            reason=?,
                            source_ref=?,
                            entered_by=?
                        WHERE id=?
                        """,
                        (
                            edited_date.isoformat(),
                            edited_nalco,
                            edited_ie07,
                            edited_lme,
                            edited_usd,
                            edited_reason,
                            edited_source,
                            edited_by,
                            selected_edit_id,
                        ),
                    )
                    conn.commit()
                    conn.close()
                    st.success("Revision updated successfully.")
                    st.rerun()

        with delete_tab:
            selected_delete_label = st.selectbox(
                "Select revision to delete",
                options=list(record_options.keys()),
                key="delete_record",
            )
            selected_delete_id = record_options[selected_delete_label]
            selected_delete_row = history.loc[
                history["id"] == selected_delete_id
            ].iloc[0]

            st.warning(
                f"""
Selected record:

**Date:** {selected_delete_row['effective_date'].date()}  
**NALCO:** ₹{selected_delete_row['nalco_base']:.2f}/kg  
**IE-07:** ₹{selected_delete_row['ie07']:.2f}/kg  
**Composite:** ₹{selected_delete_row['composite']:.2f}/kg  
**Record ID:** {int(selected_delete_row['id'])}
                """
            )

            confirm_delete = st.checkbox(
                "I confirm that this revision should be permanently deleted.",
                key="confirm_delete",
            )

            if st.button(
                "Delete Selected Revision",
                type="primary",
                disabled=not confirm_delete,
            ):
                conn = get_conn()
                conn.execute(
                    "DELETE FROM rate_history WHERE id=?",
                    (selected_delete_id,),
                )
                conn.commit()
                conn.close()
                st.success("Revision deleted successfully.")
                st.rerun()

    st.divider()

    st.subheader("Rate History Records")
    search_text = st.text_input(
        "Search Rate History",
        placeholder="Search date, reason, reference or entered-by name",
        key="rate_search",
    )

    display_history = history.copy()

    if search_text.strip():
        search_value = search_text.strip().lower()
        mask = (
            display_history["effective_date"]
            .dt.strftime("%Y-%m-%d")
            .str.lower()
            .str.contains(search_value, na=False)
            |
            display_history["reason"]
            .fillna("")
            .str.lower()
            .str.contains(search_value, na=False)
            |
            display_history["source_ref"]
            .fillna("")
            .str.lower()
            .str.contains(search_value, na=False)
            |
            display_history["entered_by"]
            .fillna("")
            .str.lower()
            .str.contains(search_value, na=False)
        )
        display_history = display_history.loc[mask]

    header_cols = st.columns([0.6, 1.15, 1, 0.8, 1, 0.8, 0.8, 1.6, 1.8, 1.2, 1.4])
    headers = [
        "ID", "Date", "NALCO", "IE-07", "Composite",
        "Change", "LME", "Reason", "Reference", "Entered By", "Actions"
    ]
    for col, title in zip(header_cols, headers):
        col.markdown(f"**{title}**")

    for _, row in display_history.sort_values(
        ["effective_date", "id"], ascending=[False, False]
    ).iterrows():
        row_id = int(row["id"])
        cols = st.columns([0.6, 1.15, 1, 0.8, 1, 0.8, 0.8, 1.6, 1.8, 1.2, 1.4])

        latest_id = int(
            display_history.sort_values(
                ["effective_date", "id"]
            ).iloc[-1]["id"]
        )
        change_value = float(row["change"])
        if change_value > 0:
            movement_class = "cell-up"
            change_text = f"▲ ₹{change_value:.2f}"
        elif change_value < 0:
            movement_class = "cell-down"
            change_text = f"▼ ₹{abs(change_value):.2f}"
        else:
            movement_class = "cell-flat"
            change_text = "→ ₹0.00"

        nalco_class = movement_class
        latest_class = "cell-latest" if row_id == latest_id else ""

        cols[0].markdown(
            cell_html(str(row_id), latest_class),
            unsafe_allow_html=True,
        )
        cols[1].markdown(
            cell_html(str(row["effective_date"].date()), latest_class),
            unsafe_allow_html=True,
        )
        cols[2].markdown(
            cell_html(f"₹{row['nalco_base']:.2f}", nalco_class),
            unsafe_allow_html=True,
        )
        cols[3].markdown(
            cell_html(f"₹{row['ie07']:.2f}"),
            unsafe_allow_html=True,
        )
        cols[4].markdown(
            cell_html(f"₹{row['composite']:.2f}", movement_class),
            unsafe_allow_html=True,
        )
        cols[5].markdown(
            cell_html(change_text, movement_class),
            unsafe_allow_html=True,
        )
        cols[6].markdown(
            cell_html(f"{row['lme']:.2f}"),
            unsafe_allow_html=True,
        )
        cols[7].markdown(
            cell_html(str(row["reason"] or "")),
            unsafe_allow_html=True,
        )
        cols[8].markdown(
            cell_html(str(row["source_ref"] or "")),
            unsafe_allow_html=True,
        )
        cols[9].markdown(
            cell_html(str(row["entered_by"] or "")),
            unsafe_allow_html=True,
        )

        edit_col, delete_col = cols[10].columns(2)

        if edit_col.button(
            "✏️",
            key=f"rate_edit_button_{row_id}",
            help="Edit this revision",
        ):
            st.session_state["edit_rate_id"] = row_id

        if delete_col.button(
            "🗑️",
            key=f"rate_delete_button_{row_id}",
            help="Delete this revision",
        ):
            st.session_state["delete_rate_id"] = row_id

        if st.session_state.get("edit_rate_id") == row_id:
            with st.container(border=True):
                st.markdown(f"### Edit Rate Revision #{row_id}")
                with st.form(f"inline_edit_rate_{row_id}"):
                    c1, c2, c3, c4 = st.columns(4)
                    new_date = c1.date_input(
                        "Effective Date",
                        value=row["effective_date"].date(),
                        key=f"rate_date_{row_id}",
                    )
                    new_nalco = c2.number_input(
                        "NALCO Base",
                        value=float(row["nalco_base"]),
                        step=0.5,
                        key=f"rate_nalco_{row_id}",
                    )
                    new_ie07 = c3.number_input(
                        "IE-07",
                        value=float(row["ie07"]),
                        step=0.5,
                        key=f"rate_ie07_{row_id}",
                    )
                    new_lme = c4.number_input(
                        "LME US$/MT",
                        value=float(row["lme"] or 0),
                        key=f"rate_lme_{row_id}",
                    )

                    c5, c6, c7 = st.columns(3)
                    new_usd = c5.number_input(
                        "USD/INR",
                        value=float(row["usd_inr"] or 0),
                        key=f"rate_usd_{row_id}",
                    )
                    new_reason = c6.text_input(
                        "Reason / Circular",
                        value=str(row["reason"] or ""),
                        key=f"rate_reason_{row_id}",
                    )
                    new_source = c7.text_input(
                        "Source / Reference",
                        value=str(row["source_ref"] or ""),
                        key=f"rate_source_{row_id}",
                    )
                    new_entered_by = st.text_input(
                        "Entered By",
                        value=str(row["entered_by"] or ""),
                        key=f"rate_entered_by_{row_id}",
                    )

                    save_col, cancel_col = st.columns(2)
                    save_clicked = save_col.form_submit_button(
                        "Save Changes",
                        type="primary",
                    )
                    cancel_clicked = cancel_col.form_submit_button("Cancel")

                    if save_clicked:
                        conn = get_conn()
                        conn.execute(
                            """
                            UPDATE rate_history SET
                                effective_date=?,nalco_base=?,ie07=?,lme=?,
                                usd_inr=?,reason=?,source_ref=?,entered_by=?
                            WHERE id=?
                            """,
                            (
                                new_date.isoformat(),
                                new_nalco,
                                new_ie07,
                                new_lme,
                                new_usd,
                                new_reason,
                                new_source,
                                new_entered_by,
                                row_id,
                            ),
                        )
                        conn.commit()
                        conn.close()
                        st.session_state.pop("edit_rate_id", None)
                        st.success("Rate revision updated.")
                        st.rerun()

                    if cancel_clicked:
                        st.session_state.pop("edit_rate_id", None)
                        st.rerun()

        if st.session_state.get("delete_rate_id") == row_id:
            with st.container(border=True):
                st.error(
                    f"Delete revision #{row_id}: "
                    f"{row['effective_date'].date()} | "
                    f"NALCO ₹{row['nalco_base']:.2f} | "
                    f"IE-07 ₹{row['ie07']:.2f}?"
                )
                confirm_col, cancel_col = st.columns(2)

                if confirm_col.button(
                    "Confirm Delete",
                    type="primary",
                    key=f"confirm_rate_delete_{row_id}",
                ):
                    conn = get_conn()
                    conn.execute(
                        "DELETE FROM rate_history WHERE id=?",
                        (row_id,),
                    )
                    conn.commit()
                    conn.close()
                    st.session_state.pop("delete_rate_id", None)
                    st.success("Rate revision deleted.")
                    st.rerun()

                if cancel_col.button(
                    "Cancel",
                    key=f"cancel_rate_delete_{row_id}",
                ):
                    st.session_state.pop("delete_rate_id", None)
                    st.rerun()

        st.markdown("<hr style=\"margin:4px 0\">", unsafe_allow_html=True)

with tabs[3]:
    st.subheader("Automatically Generated Weekly Forecast")
    st.metric(
        "Calculated Weekly Drift",
        f"₹{drift:,.2f}/kg",
    )
    st.dataframe(
        forecast,
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "Forecast is procurement-planning guidance and not a guaranteed market price."
    )

with tabs[4]:
    st.subheader("Supplier Comparison")

    with st.form("supplier_form"):
        col1, col2, col3, col4, col5 = st.columns(5)

        supplier_name = col1.text_input("Supplier")
        quoted_base = col2.number_input(
            "Quoted Base",
            value=float(settings["nalco_base"]),
            step=0.5,
        )
        supplier_ie07 = col3.number_input(
            "IE-07",
            value=float(settings["ie07"]),
            step=0.5,
        )
        supplier_freight = col4.number_input(
            "Freight",
            value=0.0,
            step=0.1,
        )
        supplier_other = col5.number_input(
            "Other Charges",
            value=0.0,
            step=0.1,
        )

        if st.form_submit_button("Add Supplier Quote"):
            if not supplier_name.strip():
                st.error("Enter the supplier name.")
            else:
                conn = get_conn()
                conn.execute(
                    """
                    INSERT INTO suppliers(
                        supplier,quoted_base,ie07,freight,other,updated_at
                    )
                    VALUES(?,?,?,?,?,?)
                    """,
                    (
                        supplier_name.strip(),
                        quoted_base,
                        supplier_ie07,
                        supplier_freight,
                        supplier_other,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                conn.commit()
                conn.close()
                st.success("Supplier quote added successfully.")
                st.rerun()

    supplier_view = suppliers.copy()
    supplier_view["Landed Before GST"] = (
        supplier_view["quoted_base"]
        + supplier_view["ie07"]
        + supplier_view["freight"]
        + supplier_view["other"]
    )
    supplier_view["Landed incl. GST"] = (
        supplier_view["Landed Before GST"]
        * (1 + settings["gst"] / 100)
    )

    st.subheader("Supplier Records")
    supplier_search = st.text_input(
        "Search Supplier",
        placeholder="Enter supplier name",
        key="supplier_search",
    )

    if supplier_search.strip():
        supplier_view = supplier_view[
            supplier_view["supplier"]
            .fillna("")
            .str.lower()
            .str.contains(supplier_search.strip().lower(), na=False)
        ]

    header_cols = st.columns([0.6, 1.5, 1, 0.8, 0.9, 0.9, 1.25, 1.25, 1.4])
    headers = [
        "ID", "Supplier", "Base", "IE-07", "Freight",
        "Other", "Before GST", "Incl. GST", "Actions"
    ]
    for col, title in zip(header_cols, headers):
        col.markdown(f"**{title}**")

    for _, row in supplier_view.sort_values(
        ["supplier", "id"]
    ).iterrows():
        supplier_id = int(row["id"])
        cols = st.columns([0.6, 1.5, 1, 0.8, 0.9, 0.9, 1.25, 1.25, 1.4])

        min_landed = float(supplier_view["Landed incl. GST"].min())
        max_landed = float(supplier_view["Landed incl. GST"].max())
        landed_value = float(row["Landed incl. GST"])

        if landed_value == min_landed:
            landed_class = "cell-best"
            supplier_text = f"★ {row['supplier']}"
        elif landed_value == max_landed and max_landed != min_landed:
            landed_class = "cell-worst"
            supplier_text = str(row["supplier"])
        else:
            landed_class = ""
            supplier_text = str(row["supplier"])

        cols[0].markdown(
            cell_html(str(supplier_id)),
            unsafe_allow_html=True,
        )
        cols[1].markdown(
            cell_html(supplier_text, landed_class),
            unsafe_allow_html=True,
        )
        cols[2].markdown(
            cell_html(f"₹{row['quoted_base']:.2f}"),
            unsafe_allow_html=True,
        )
        cols[3].markdown(
            cell_html(f"₹{row['ie07']:.2f}"),
            unsafe_allow_html=True,
        )
        cols[4].markdown(
            cell_html(f"₹{row['freight']:.2f}"),
            unsafe_allow_html=True,
        )
        cols[5].markdown(
            cell_html(f"₹{row['other']:.2f}"),
            unsafe_allow_html=True,
        )
        cols[6].markdown(
            cell_html(f"₹{row['Landed Before GST']:.2f}", landed_class),
            unsafe_allow_html=True,
        )
        cols[7].markdown(
            cell_html(f"₹{row['Landed incl. GST']:.2f}", landed_class),
            unsafe_allow_html=True,
        )

        edit_col, delete_col = cols[8].columns(2)

        if edit_col.button(
            "✏️",
            key=f"supplier_edit_button_{supplier_id}",
            help="Edit supplier quote",
        ):
            st.session_state["edit_supplier_id"] = supplier_id

        if delete_col.button(
            "🗑️",
            key=f"supplier_delete_button_{supplier_id}",
            help="Delete supplier quote",
        ):
            st.session_state["delete_supplier_id"] = supplier_id

        if st.session_state.get("edit_supplier_id") == supplier_id:
            with st.container(border=True):
                st.markdown(f"### Edit Supplier Quote #{supplier_id}")
                with st.form(f"inline_edit_supplier_{supplier_id}"):
                    c1, c2, c3, c4, c5 = st.columns(5)
                    new_name = c1.text_input(
                        "Supplier",
                        value=str(row["supplier"]),
                        key=f"supplier_name_{supplier_id}",
                    )
                    new_base = c2.number_input(
                        "Quoted Base",
                        value=float(row["quoted_base"]),
                        step=0.5,
                        key=f"supplier_base_{supplier_id}",
                    )
                    new_ie07 = c3.number_input(
                        "IE-07",
                        value=float(row["ie07"]),
                        step=0.5,
                        key=f"supplier_ie07_{supplier_id}",
                    )
                    new_freight = c4.number_input(
                        "Freight",
                        value=float(row["freight"]),
                        step=0.1,
                        key=f"supplier_freight_{supplier_id}",
                    )
                    new_other = c5.number_input(
                        "Other Charges",
                        value=float(row["other"]),
                        step=0.1,
                        key=f"supplier_other_{supplier_id}",
                    )

                    save_col, cancel_col = st.columns(2)
                    save_clicked = save_col.form_submit_button(
                        "Save Changes",
                        type="primary",
                    )
                    cancel_clicked = cancel_col.form_submit_button("Cancel")

                    if save_clicked:
                        if not new_name.strip():
                            st.error("Supplier name cannot be blank.")
                        else:
                            conn = get_conn()
                            conn.execute(
                                """
                                UPDATE suppliers SET
                                    supplier=?,quoted_base=?,ie07=?,
                                    freight=?,other=?,updated_at=?
                                WHERE id=?
                                """,
                                (
                                    new_name.strip(),
                                    new_base,
                                    new_ie07,
                                    new_freight,
                                    new_other,
                                    datetime.now().isoformat(timespec="seconds"),
                                    supplier_id,
                                ),
                            )
                            conn.commit()
                            conn.close()
                            st.session_state.pop("edit_supplier_id", None)
                            st.success("Supplier quote updated.")
                            st.rerun()

                    if cancel_clicked:
                        st.session_state.pop("edit_supplier_id", None)
                        st.rerun()

        if st.session_state.get("delete_supplier_id") == supplier_id:
            with st.container(border=True):
                st.error(
                    f"Delete supplier quote #{supplier_id}: "
                    f"{row['supplier']} | "
                    f"Landed incl. GST ₹{row['Landed incl. GST']:.2f}?"
                )
                confirm_col, cancel_col = st.columns(2)

                if confirm_col.button(
                    "Confirm Delete",
                    type="primary",
                    key=f"confirm_supplier_delete_{supplier_id}",
                ):
                    conn = get_conn()
                    conn.execute(
                        "DELETE FROM suppliers WHERE id=?",
                        (supplier_id,),
                    )
                    conn.commit()
                    conn.close()
                    st.session_state.pop("delete_supplier_id", None)
                    st.success("Supplier quote deleted.")
                    st.rerun()

                if cancel_col.button(
                    "Cancel",
                    key=f"cancel_supplier_delete_{supplier_id}",
                ):
                    st.session_state.pop("delete_supplier_id", None)
                    st.rerun()

        st.markdown("<hr style=\"margin:4px 0\">", unsafe_allow_html=True)

with tabs[5]:
    st.subheader("Export Management Data")

    st.download_button(
        "Download Complete Excel Report",
        export_excel(
            settings,
            history,
            forecast,
            suppliers,
        ),
        file_name=(
            f"Electro_Dip_Aluminium_Report_"
            f"{date.today().isoformat()}.xlsx"
        ),
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        type="primary",
    )
