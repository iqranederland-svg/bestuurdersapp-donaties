from pathlib import Path
import json
import re
import subprocess

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

import streamlit as st

APP_PASSWORD = "IqraDashboard2026"

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("Bestuurdersomgeving")
    password = st.text_input("Voer het wachtwoord in", type="password")

    if password == APP_PASSWORD:
        st.session_state.authenticated = True
        st.rerun()
    elif password != "":
        st.error("Onjuist wachtwoord")

    st.stop()

check_password()


st.set_page_config(page_title="Donateur Intelligence Platform", layout="wide")

OUTPUT_DIR = Path("outputs")
RAW_DIR = Path("data/raw")


def newest(pattern: str):
    files = sorted(OUTPUT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def eur(x) -> str:
    try:
        return "€ " + f"{int(round(float(x))):,}".replace(",", ".")
    except Exception:
        return str(x)


def pct(x) -> str:
    try:
        return f"{float(x):.1f}%".replace(".", ",")
    except Exception:
        return str(x)


def i0(x) -> str:
    try:
        return f"{int(round(float(x))):,}".replace(",", ".")
    except Exception:
        return str(x)


def yearstr(x) -> str:
    try:
        return str(int(round(float(x))))
    except Exception:
        return str(x)


def fmt_money_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].apply(eur)
    return out


def fmt_int_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].apply(i0)
    return out


def fmt_pct_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].apply(lambda x: "" if pd.isna(x) else pct(x))
    return out


def fmt_year_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].apply(yearstr)
    return out



def load_financial_summary():
    fp = OUTPUT_DIR / "financial_summary.json"
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def load_current_period_meta():
    meta_file = OUTPUT_DIR / "current_period.json"
    if meta_file.exists():
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def load_data():
    xlsx = newest("donateur_intelligence_v5_*.xlsx")
    if not xlsx:
        return None

    return {
        "file": xlsx,
        "dashboard": pd.read_excel(xlsx, "01 Dashboard per jaar"),
        "categories": pd.read_excel(xlsx, "02 Categorie overzicht"),
        "donors": pd.read_excel(xlsx, "03 Donateursbasis"),
        "new": pd.read_excel(xlsx, "04 Nieuwe donateurs"),
        "new_returning": pd.read_excel(xlsx, "05 Nieuw vs terugkerend"),
        "cohort": pd.read_excel(xlsx, "06 Cohort lang"),
        "retention": pd.read_excel(xlsx, "07 Jaar-op-jaar retentie"),
        "pareto": pd.read_excel(xlsx, "08 Pareto"),
        "top": pd.read_excel(xlsx, "09 Top alle jaren"),
        "periodic": pd.read_excel(xlsx, "10 Periodiek per jaar"),
        "lifecycle": pd.read_excel(xlsx, "11 Donateur lifecycle"),
        "exit": pd.read_excel(xlsx, "12 Uitstroom samenvatting"),
        "transactions": pd.read_excel(xlsx, "99 Publieke transacties"),
    }


def split_closed_running_years(df: pd.DataFrame):
    years = sorted(df["Jaar"].dropna().astype(int).unique().tolist())
    if not years:
        return df.copy(), df.copy(), None
    running_year = max(years)
    closed = df[df["Jaar"].astype(int) < running_year].copy()
    running = df[df["Jaar"].astype(int) == running_year].copy()
    return closed, running, running_year


def inject_css():
    st.markdown(
        """
<style>
.block-container{max-width:1520px;padding-top:1rem;padding-bottom:2rem;}
.stApp{background:linear-gradient(180deg,#F5F7FB 0%,#EEF3F9 100%);}
.hero{background:linear-gradient(135deg,#0B1F3A 0%,#143D6B 55%,#1F5D8B 100%);padding:30px 34px;border-radius:28px;color:white;margin-bottom:22px;box-shadow:0 18px 42px rgba(11,31,58,0.20);}
.hero-kicker{font-size:13px;opacity:0.82;margin-bottom:8px;letter-spacing:.02em;}
.hero-title{font-size:40px;font-weight:800;margin-bottom:8px;line-height:1.08;}
.hero-sub{font-size:16px;line-height:1.6;max-width:1040px;opacity:0.96;}
.kpi{background:linear-gradient(180deg,#FFFFFF 0%,#FAFBFD 100%);padding:18px 18px 16px 18px;border-radius:22px;border:1px solid #E5EAF2;min-height:156px;height:156px;box-shadow:0 10px 24px rgba(15,39,71,0.06);display:flex;flex-direction:column;justify-content:space-between;overflow:hidden;}
.kpi-title{font-size:13px;color:#6B7280;line-height:1.35;min-height:34px;font-weight:600;}
.kpi-value{font-size:32px;font-weight:800;color:#0F2747;line-height:1.02;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.kpi-sub{font-size:12px;color:#667085;line-height:1.4;min-height:34px;overflow:hidden;}
.section{font-size:28px;font-weight:800;margin-top:28px;margin-bottom:8px;color:#0F2747;line-height:1.12;}
.subsection{font-size:20px;font-weight:700;margin-top:18px;margin-bottom:8px;color:#0F2747;line-height:1.2;}
.section-sub{font-size:14px;color:#667085;margin-bottom:14px;line-height:1.45;}
.summary{background:white;padding:16px 18px;border-radius:18px;border:1px solid #E5EAF2;margin-bottom:12px;line-height:1.65;box-shadow:0 8px 22px rgba(15,39,71,0.05);}
.info-box{background:#FFFFFF;border:1px solid #D8E1EE;border-left:5px solid #1F5D8B;padding:14px 16px;border-radius:14px;line-height:1.65;margin-bottom:12px;}
.nowrap{white-space:nowrap;}
div[data-testid="stMetric"]{background:white;border:1px solid #E5EAF2;padding:14px;border-radius:16px;}
.fact-card{background:linear-gradient(180deg,#FFFFFF 0%,#FBFCFE 100%);border:1px solid #E5EAF2;border-radius:22px;padding:20px 22px;box-shadow:0 10px 24px rgba(15,39,71,0.06);}
.fact-title{font-size:18px;font-weight:800;color:#0F2747;margin-bottom:12px;}
.hero-metric{background:rgba(255,255,255,0.10);border:1px solid rgba(255,255,255,0.14);border-radius:18px;padding:16px 18px;}
.hero-metric-label{font-size:12px;opacity:0.80;margin-bottom:6px;}
.hero-metric-value{font-size:30px;font-weight:800;line-height:1.0;}
.hero-metric-sub{font-size:12px;opacity:0.76;margin-top:8px;line-height:1.4;}
.small-note{font-size:12px;color:#667085;line-height:1.5;}
</style>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = ""):
    st.markdown(f'<div class="section">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-sub">{subtitle}</div>', unsafe_allow_html=True)


def subsection(title: str):
    st.markdown(f'<div class="subsection">{title}</div>', unsafe_allow_html=True)


def info_box(text: str):
    st.markdown(f'<div class="info-box">{text}</div>', unsafe_allow_html=True)


def kpi_card(title: str, value: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="kpi">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def chart_bar(df: pd.DataFrame, x: str, y: str, title: str, kind: str = "count", rotate: int = 0):
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    labels = df[x].astype(str).tolist()
    values = df[y].astype(float).tolist()
    bars = ax.bar(labels, values)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.grid(axis="y", alpha=0.20)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", rotation=rotate, labelsize=10)
    ax.tick_params(axis="y", labelsize=10)
    ymax = max(values) if values else 0
    for rect, val in zip(bars, values):
        label = eur(val) if kind == "eur" else pct(val) if kind == "pct" else i0(val)
        if ymax > 0 and val > ymax * 0.20:
            y_text = rect.get_height() - (0.06 * ymax)
            va = "top"
            color = "white"
        else:
            y_text = rect.get_height() + (0.02 * ymax if ymax > 0 else 0.2)
            va = "bottom"
            color = "black"
        ax.text(rect.get_x() + rect.get_width() / 2, y_text, label, ha="center", va=va, fontsize=10, fontweight="bold", color=color)
    fig.tight_layout()
    return fig


def chart_line(df: pd.DataFrame, x: str, y: str, title: str, kind: str = "count", rotate: int = 0):
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    labels = df[x].astype(str).tolist()
    values = df[y].astype(float).tolist()
    ax.plot(labels, values, marker="o", linewidth=2.2)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.grid(axis="y", alpha=0.20)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", rotation=rotate, labelsize=10)
    ax.tick_params(axis="y", labelsize=10)
    for lx, val in zip(labels, values):
        label = eur(val) if kind == "eur" else pct(val) if kind == "pct" else i0(val)
        ax.text(lx, val, label, ha="center", va="bottom", fontsize=10, fontweight="bold")
    fig.tight_layout()
    return fig




def chart_bar_custom(df: pd.DataFrame, x: str, y: str, title: str, kind: str = "count", rotate: int = 0):
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    labels = df[x].astype(str).tolist()
    values = df[y].astype(float).tolist()
    bars = ax.bar(labels, values, color="#1F5D8B")
    ax.set_title(title, fontsize=14, fontweight="bold", pad=14, color="#0F2747")
    ax.grid(axis="y", alpha=0.18)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", rotation=rotate, labelsize=10)
    ax.tick_params(axis="y", labelsize=10)
    ymax = max(values) if values else 0
    for rect, val in zip(bars, values):
        label = eur(val) if kind == "eur" else pct(val) if kind == "pct" else i0(val)
        inside = ymax > 0 and val > ymax * 0.16
        y_text = rect.get_height() - (0.05 * ymax) if inside else rect.get_height() + (0.02 * ymax if ymax > 0 else 0.2)
        va = "top" if inside else "bottom"
        color = "white" if inside else "#0F2747"
        ax.text(rect.get_x() + rect.get_width() / 2, y_text, label, ha="center", va=va, fontsize=10, fontweight="bold", color=color)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    return fig


def chart_stack_income_mix(yearly_rows):
    df = pd.DataFrame(yearly_rows)
    if len(df) == 0:
        return None
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    years = df["Jaar"].astype(str).tolist()
    eenmalig = pd.to_numeric(df["Eenmalige donaties"], errors="coerce").fillna(0).tolist()
    periodiek = pd.to_numeric(df["Periodieke donaties"], errors="coerce").fillna(0).tolist()
    overig = pd.to_numeric(df["Overige inkomsten"], errors="coerce").fillna(0).tolist()
    ax.bar(years, eenmalig, label="Eenmalig", color="#1F5D8B")
    ax.bar(years, periodiek, bottom=eenmalig, label="Periodiek", color="#34A0A4")
    bottoms = [a + b for a, b in zip(eenmalig, periodiek)]
    ax.bar(years, overig, bottom=bottoms, label="Overig", color="#94A3B8")
    totals = [a + b + c for a, b, c in zip(eenmalig, periodiek, overig)]
    ymax = max(totals) if totals else 0
    for x, total in zip(years, totals):
        ax.text(x, total + (0.02 * ymax if ymax > 0 else 0.2), eur(total), ha="center", va="bottom", fontsize=10, fontweight="bold", color="#0F2747")
    ax.set_title("Inkomstenmix per jaar", fontsize=14, fontweight="bold", pad=14, color="#0F2747")
    ax.grid(axis="y", alpha=0.18)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=3, loc="upper left")
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    return fig

def render_kpis(data):
    dash = data["dashboard"].copy()
    periodic = data["periodic"].copy()
    pareto = data["pareto"].copy()
    donors = data["donors"].copy()
    retention = data["retention"].copy().sort_values("Van_jaar")
    exit_df = data["exit"].copy()

    total_all = float(dash["Totale_inkomsten"].sum())
    total_tx = int(dash["Totaal_transacties"].sum())
    donor_count = int(donors.loc[donors["KPI"] == "Unieke bankdonateurs", "Waarde"].iloc[0]) if (donors["KPI"] == "Unieke bankdonateurs").any() else 0
    dragers_total = float(periodic["Bedrag"].sum()) if len(periodic) else 0.0

    top10 = pareto.loc[pareto["Segment"] == "Top 10%"]
    if len(top10):
        top10_pct = float(top10["Aandeel_inkomsten_pct"].iloc[0])
        top10_amount = float(top10["Bedrag"].iloc[0])
        top10_count = int(top10["Aantal_donateurs"].iloc[0])
    else:
        top10_pct = 0.0
        top10_amount = 0.0
        top10_count = 0

    if len(retention):
        ret_text = pct(float(retention.iloc[-1]["Retentie_pct"]))
        ret_sub = "gedoneerd in 2025 en 2026"
    else:
        ret_text = "-"
        ret_sub = ""

    impact_year = None
    impact_count = 0
    impact_amount = 0.0
    if len(exit_df):
        impact = exit_df.sort_values(["Totaal bedrag van deze groep", "Aantal donateurs"], ascending=False).iloc[0]
        impact_year = int(impact["Laatste actieve jaar"])
        impact_count = int(impact["Aantal donateurs"])
        impact_amount = float(impact["Totaal bedrag van deze groep"])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Totale donaties", eur(total_all), "(2023-heden)")
    with c2:
        kpi_card("Totale transacties", i0(total_tx), "(2023-heden)")
    with c3:
        kpi_card("Aantal donateurs", i0(donor_count), "(2023-heden)")
    with c4:
        kpi_card("Dragers donaties", eur(dragers_total), "(2023-heden)")

    st.markdown("")
    c5, c6, c7 = st.columns(3)
    with c5:
        kpi_card("Top 10% concentratie", pct(top10_pct), f"{i0(top10_count)} donateurs doneerden {eur(top10_amount)}")
    with c6:
        kpi_card("Laatste jaar-op-jaar retentie", ret_text, ret_sub)
    with c7:
        note = ""
        if impact_year is not None:
            note = f"Laatst gedoneerd in {impact_year}<br>({eur(impact_amount)})"
        kpi_card("Uitstroomcohort met grootste impact", f"{i0(impact_count)}*", note)

    st.markdown(
        "<div style='font-size:12px;color:#666;margin-top:6px'>* gebaseerd op laatste donatiejaar 2025. Donateurs kunnen in 2026 nog opnieuw doneren waardoor dit aantal kan wijzigen.</div>",
        unsafe_allow_html=True
    )


def render_donor_health(data):
    lifecycle = data["lifecycle"].copy()
    dash = data["dashboard"].copy()
    if len(dash) == 0 or len(lifecycle) == 0:
        return
    current_year = int(dash["Jaar"].max())
    lifecycle["Eerste_jaar"] = lifecycle["Eerste_jaar"].astype(int)
    lifecycle["Laatste_jaar"] = lifecycle["Laatste_jaar"].astype(int)
    active = lifecycle[lifecycle["Laatste_jaar"] == current_year]
    new = lifecycle[lifecycle["Eerste_jaar"] == current_year]
    churn = lifecycle[lifecycle["Laatste_jaar"] < current_year - 1]

    section_header("Donateurgezondheid", "Gezondheid van de donateurbasis in het meest recente jaar")
    info_box("Actieve donateurs hebben in het meest recente jaar van de dataset gedoneerd. Nieuwe donateurs zijn voor het eerst actief in dat jaar. Structureel uitgestroomde donateurs hebben minimaal één volledig jaar niet meer gedoneerd.")
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Actieve donateurs", i0(len(active)), f"Actief in {current_year}")
    with c2:
        kpi_card("Nieuwe donateurs", i0(len(new)), f"Eerste donatie in {current_year}")
    with c3:
        kpi_card("Structureel uitgestroomd", i0(len(churn)), f"Laatste donatie vóór {current_year - 1}")











def render_dashboard_tab(data):
    meta = load_current_period_meta()
    fin = load_financial_summary()
    period_text = str(meta.get("period_label", "gekozen periode"))

    totals = fin.get("totals", {})
    netto_resultaat = float(totals.get("netto_resultaat", 0) or 0)
    totale_inkomsten = float(totals.get("inkomsten", 0) or 0)
    totale_uitgaven = float(totals.get("uitgaven", 0) or 0)
    contant_kas = float(totals.get("contant_kas", meta.get("contant_kas", 0)) or 0)
    netto_incl_kas = netto_resultaat + contant_kas
    periodieke_donaties = float(totals.get("periodieke_donaties", 0) or 0)
    eenmalige_donaties = float(totals.get("eenmalige_donaties", 0) or 0)
    overige_inkomsten = float(totals.get("overige_inkomsten", 0) or 0)

    donors = data["donors"].copy()
    lifecycle = data["lifecycle"].copy()
    new_df = data["new"].copy().sort_values("Jaar")
    pareto = data["pareto"].copy()
    dash = data["dashboard"].copy().sort_values("Jaar")
    yearly = fin.get("yearly", [])

    donor_count = 0
    hit = donors.loc[donors["KPI"] == "Unieke bankdonateurs", "Waarde"]
    if len(hit):
        donor_count = int(hit.iloc[0])

    current_year = int(dash["Jaar"].max()) if len(dash) else None

    active_count = 0
    new_count = 0
    structural_churn = 0

    if len(lifecycle):
        lc = lifecycle.copy()
        if "Laatste_jaar" in lc.columns and current_year is not None:
            lc["Laatste_jaar"] = pd.to_numeric(lc["Laatste_jaar"], errors="coerce")
            active_count = int((lc["Laatste_jaar"] == current_year).sum())
            structural_churn = int((lc["Laatste_jaar"] < (current_year - 1)).sum())
        if "Eerste_jaar" in lc.columns and current_year is not None:
            lc["Eerste_jaar"] = pd.to_numeric(lc["Eerste_jaar"], errors="coerce")
            new_count = int((lc["Eerste_jaar"] == current_year).sum())

    if len(new_df) and current_year is not None:
        row = new_df.loc[pd.to_numeric(new_df["Jaar"], errors="coerce") == current_year]
        if len(row) and "Nieuwe donateurs sinds start dataset" in row.columns:
            try:
                new_count = int(row.iloc[0]["Nieuwe donateurs sinds start dataset"])
            except Exception:
                pass

    top10_pct = 0.0
    top10_amount = 0.0
    if len(pareto):
        top10 = pareto.loc[pareto["Segment"] == "Top 10%"]
        if len(top10):
            top10_pct = float(top10["Aandeel_inkomsten_pct"].iloc[0])
            top10_amount = float(top10["Bedrag"].iloc[0])

    section_header("Management Dashboard", "Belangrijkste bestuurscijfers • " + period_text)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Netto resultaat", eur(netto_resultaat), "exclusief contant in kas")
    with c2:
        kpi_card("Totale inkomsten", eur(totale_inkomsten), "bankinkomsten binnen rapportageperiode")
    with c3:
        kpi_card("Totale uitgaven", eur(totale_uitgaven), period_text)
    with c4:
        kpi_card("Contant in kas", eur(contant_kas), "stand op rapportmoment")

    st.markdown("")
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        kpi_card("Eenmalige donaties", eur(eenmalige_donaties), period_text)
    with c6:
        kpi_card("Periodieke donaties", eur(periodieke_donaties), period_text)
    with c7:
        kpi_card("Overige inkomsten", eur(overige_inkomsten), period_text)
    with c8:
        kpi_card("Netto incl. kas", eur(netto_incl_kas), "netto resultaat + contant")

    st.markdown("")
    c9, c10, c11, c12 = st.columns(4)
    with c9:
        kpi_card("Aantal donateurs", i0(donor_count), period_text)
    with c10:
        active_sub = f"actief in {current_year}" if current_year is not None else period_text
        kpi_card("Actieve donateurs", i0(active_count), active_sub)
    with c11:
        new_sub = f"nieuw in {current_year}" if current_year is not None else period_text
        kpi_card("Nieuwe donateurs", i0(new_count), new_sub)
    with c12:
        kpi_card("Structureel uitgestroomd", i0(structural_churn), "minstens 1 volledig jaar inactief")

    st.markdown("")
    c13, c14 = st.columns([1, 1])
    with c13:
        kpi_card("Top 10% donateurs", eur(top10_amount), pct(top10_pct) + " van totale donaties")
    with c14:
        income_table = pd.DataFrame([
            {"Categorie": "Eenmalige donaties", "Bedrag": eenmalige_donaties},
            {"Categorie": "Periodieke donaties", "Bedrag": periodieke_donaties},
            {"Categorie": "Overige inkomsten", "Bedrag": overige_inkomsten},
            {"Categorie": "Totale inkomsten", "Bedrag": totale_inkomsten},
        ])
        income_table = fmt_money_cols(income_table, ["Bedrag"])
        st.dataframe(income_table, use_container_width=True, hide_index=True)

    section_header("Progressie", "Ontwikkeling van bankinkomsten en inkomstenmix • contant niet meegenomen")

    g1, g2 = st.columns(2)

    yearly_df = pd.DataFrame(yearly) if yearly else pd.DataFrame()
    if len(yearly_df):
        if "Jaar" in yearly_df.columns and "Inkomsten" in yearly_df.columns:
            with g1:
                st.pyplot(chart_bar_custom(yearly_df, "Jaar", "Inkomsten", "Bankinkomsten per jaar", kind="eur"), use_container_width=True)

        mix_fig = chart_grouped_income_mix(yearly)
        if mix_fig is not None:
            with g2:
                st.pyplot(mix_fig, use_container_width=True)

    section_header("Kernpunten en duiding")

    left, right = st.columns(2)

    with left:
        st.markdown(
            "<div class='summary'>"
            "<strong>Kernpunten</strong><br>"
            f"• Netto resultaat: <strong>{eur(netto_resultaat)}</strong><br>"
            f"• Totale bankinkomsten: <strong>{eur(totale_inkomsten)}</strong><br>"
            f"• De inkomstenbasis wordt hoofdzakelijk gedragen door <strong>eenmalige donaties</strong><br>"
            f"• De top 10% van de donateurs vertegenwoordigt <strong>{pct(top10_pct)}</strong> van de totale donaties"
            "</div>",
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            "<div class='summary'>"
            "<strong>Duiding</strong><br>"
            "• De kostenstructuur oogt beheerst ten opzichte van de inkomsten<br>"
            "• De stichting blijft voor een belangrijk deel afhankelijk van incidentele inkomsten<br>"
            "• Verdere groei van periodieke donaties blijft strategisch belangrijk<br>"
            "• Behoud en heractivatie van donateurs verdienen blijvende aandacht"
            "</div>",
            unsafe_allow_html=True,
        )


def render_donors_tab(data):
    section_header("Donateursbasis", "Instroom, terugkeer, dragers en topdonateurs")
    new_df = data["new"].copy().sort_values("Jaar")
    nr_df = data["new_returning"].copy().sort_values("Jaar")
    periodic = data["periodic"].copy().sort_values("Jaar")
    top_df = data["top"].copy().head(20)

    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.pyplot(chart_bar(new_df, "Jaar", "Nieuwe donateurs sinds start dataset", "Nieuwe donateurs per jaar"), use_container_width=True)
    with r1c2:
        st.pyplot(chart_bar(nr_df, "Jaar", "Terugkerende_donateurs", "Terugkerende donateurs per jaar"), use_container_width=True)

    section_header("Nieuwe versus terugkerende donateurs")
    nr_table = nr_df[["Jaar", "Nieuwe_donateurs", "Terugkerende_donateurs", "Totaal_unieke_donateurs", "Aandeel_nieuw_pct"]].copy()
    nr_table = fmt_year_cols(nr_table, ["Jaar"])
    nr_table = fmt_int_cols(nr_table, ["Nieuwe_donateurs", "Terugkerende_donateurs", "Totaal_unieke_donateurs"])
    nr_table = fmt_pct_cols(nr_table, ["Aandeel_nieuw_pct"])
    st.dataframe(nr_table, use_container_width=True, hide_index=True)

    section_header("Dragers donaties per jaar")
    periodic_table = periodic.copy().rename(columns={"Bedrag": "Dragers donaties"})
    periodic_table = fmt_year_cols(periodic_table, ["Jaar"])
    periodic_table = fmt_int_cols(periodic_table, ["Payouts"])
    periodic_table = fmt_money_cols(periodic_table, ["Dragers donaties"])
    if "Groei_tov_vorig_jaar_pct" in periodic_table.columns:
        periodic_table = fmt_pct_cols(periodic_table, ["Groei_tov_vorig_jaar_pct"])
    st.dataframe(periodic_table, use_container_width=True, hide_index=True)

    section_header("Top donateurs over alle jaren")
    top_table = top_df[["Donateur_ID", "Totaal_bedrag", "Transacties"]].copy()
    top_table = fmt_money_cols(top_table, ["Totaal_bedrag"])
    top_table = fmt_int_cols(top_table, ["Transacties"])
    st.dataframe(top_table, use_container_width=True, hide_index=True)


def render_retention_tab(data):
    section_header("Retentie & uitstroom", "Loyaliteit, terugkeer en verlies van donateurs")
    cohort = data["cohort"].copy()
    retention = data["retention"].copy().sort_values("Van_jaar")
    retention["Label"] = retention["Van_jaar"].astype(int).astype(str) + "→" + retention["Naar_jaar"].astype(int).astype(str)
    exit_df = data["exit"].copy().sort_values("Laatste actieve jaar")
    lifecycle = data["lifecycle"].copy()

    current_year = int(data["dashboard"]["Jaar"].max()) if len(data["dashboard"]) else None
    if current_year is not None and "Laatste_jaar" in lifecycle.columns:
        lifecycle["Actieve donateur"] = lifecycle["Laatste_jaar"].apply(lambda x: "Ja" if pd.notna(x) and int(round(float(x))) == current_year else "Nee")
    else:
        lifecycle["Actieve donateur"] = "Nee"

    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.pyplot(chart_line(retention, "Label", "Retentie_pct", "Jaar-op-jaar retentie", kind="pct"), use_container_width=True)
    with r1c2:
        st.pyplot(chart_bar(exit_df, "Laatste actieve jaar", "Aantal donateurs", "Uitstroom per laatste actieve jaar"), use_container_width=True)

    section_header("Retentie tabel", "Jaar-op-jaar retentie in tabelvorm")
    info_box("Deze tabel laat per overgang van jaar naar jaar zien hoeveel donateurs uit het startjaar ook in het volgende jaar opnieuw actief waren. Dit is de kernmaat voor jaarlijks behoud.")
    retention_table = retention[["Van_jaar", "Naar_jaar", "Donateurs_startjaar", "Ook_actief_volgend_jaar", "Retentie_pct"]].copy()
    retention_table = fmt_year_cols(retention_table, ["Van_jaar", "Naar_jaar"])
    retention_table = fmt_int_cols(retention_table, ["Donateurs_startjaar", "Ook_actief_volgend_jaar"])
    retention_table = fmt_pct_cols(retention_table, ["Retentie_pct"])
    st.dataframe(retention_table, use_container_width=True, hide_index=True)

    section_header("Cohortanalyse", "Per cohortjaar een aparte tabel")
    info_box("Een cohort is de groep donateurs die in een bepaald startjaar actief was. Per cohortjaar zie je hieronder hoeveel van die groep in latere jaren is teruggekeerd. Zo wordt zichtbaar of een cohort duurzaam blijft geven of vooral eenmalig doneert.")
    if len(cohort):
        cohort_years = sorted(cohort["Cohortjaar"].dropna().astype(int).unique().tolist())
        for cy in cohort_years:
            subset = cohort[cohort["Cohortjaar"].astype(int) == cy].copy().sort_values("Doeljaar")
            subset = subset[["Cohortjaar", "Doeljaar", "Aantal_donateurs_in_cohort", "Teruggekeerd", "Retentie_pct"]].copy()
            subset = fmt_year_cols(subset, ["Cohortjaar", "Doeljaar"])
            subset = fmt_int_cols(subset, ["Aantal_donateurs_in_cohort", "Teruggekeerd"])
            subset = fmt_pct_cols(subset, ["Retentie_pct"])
            subsection(f"Cohortjaar {cy}")
            st.dataframe(subset, use_container_width=True, hide_index=True)

    section_header("Uitstroom samenvatting")
    info_box("Deze tabel laat zien in welk laatste actieve jaar donateurs voor het laatst voorkwamen. Voor afgesloten jaren geeft dit een betrouwbaarder beeld van structurele uitstroom. Voor cohorten die worden vergeleken met een lopend opvolgjaar is voorzichtigheid nodig, omdat een deel later nog kan terugkeren.")
    exit_table = exit_df[["Laatste actieve jaar", "Aantal donateurs", "Totaal bedrag van deze groep", "Totaal transacties van deze groep"]].copy()
    exit_table = fmt_year_cols(exit_table, ["Laatste actieve jaar"])
    exit_table = fmt_int_cols(exit_table, ["Aantal donateurs", "Totaal transacties van deze groep"])
    exit_table = fmt_money_cols(exit_table, ["Totaal bedrag van deze groep"])
    st.dataframe(exit_table, use_container_width=True, hide_index=True)

    section_header("Donateur lifecycle")
    info_box("De lifecycle-tabel laat per Donateur_ID zien in welk jaar een donateur voor het eerst en voor het laatst voorkwam, hoeveel transacties hij of zij deed, welk totaalbedrag daarbij hoorde en of deze relatie in het meest recente jaar nog actief was.")
    lifecycle_table = lifecycle.copy()
    lifecycle_table = fmt_year_cols(lifecycle_table, ["Eerste_jaar", "Laatste_jaar"])
    lifecycle_table = fmt_int_cols(lifecycle_table, ["Transacties"])
    lifecycle_table = fmt_money_cols(lifecycle_table, ["Totaal_bedrag"])
    preferred_cols = ["Donateur_ID", "Eerste_jaar", "Laatste_jaar", "Actieve donateur", "Transacties", "Totaal_bedrag"]
    existing_cols = [c for c in preferred_cols if c in lifecycle_table.columns]
    lifecycle_table = lifecycle_table[existing_cols]
    st.dataframe(lifecycle_table, use_container_width=True, hide_index=True)





def render_financial_tab(data):
    meta = load_current_period_meta()
    fin = load_financial_summary()

    subtitle = "Inkomsten, uitgaven, netto resultaat en contant in kas"
    if meta.get("period_label"):
        subtitle = subtitle + " • " + str(meta.get("period_label"))
    section_header("Financieel overzicht", subtitle)

    totals = fin.get("totals", {})
    inkomsten = float(totals.get("inkomsten", 0) or 0)
    uitgaven = float(totals.get("uitgaven", 0) or 0)
    netto_resultaat = float(totals.get("netto_resultaat", 0) or 0)
    contant_kas = float(totals.get("contant_kas", meta.get("contant_kas", 0)) or 0)
    netto_incl_kas = float(totals.get("netto_resultaat_incl_kas", netto_resultaat + contant_kas) or 0)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi_card("Totale inkomsten", eur(inkomsten), "(gekozen periode)")
    with c2:
        kpi_card("Totale uitgaven", eur(uitgaven), "(gekozen periode)")
    with c3:
        kpi_card("Netto resultaat", eur(netto_resultaat), "(gekozen periode)")
    with c4:
        kpi_card("Contant in kas", eur(contant_kas), "(handmatig ingevoerd)")
    with c5:
        kpi_card("Netto resultaat incl. kas", eur(netto_incl_kas), "(gekozen periode)")

    section_header("Inkomstenoverzicht", "Onderverdeling van inkomsten binnen de gekozen periode")
    income_table = pd.DataFrame([
        {"Type": "Periodieke donaties", "Bedrag": totals.get("periodieke_donaties", 0)},
        {"Type": "Eenmalige donaties", "Bedrag": totals.get("eenmalige_donaties", 0)},
        {"Type": "Overige inkomsten", "Bedrag": totals.get("overige_inkomsten", 0)},
        {"Type": "Totale inkomsten", "Bedrag": totals.get("inkomsten", 0)},
    ])
    income_table = fmt_money_cols(income_table, ["Bedrag"])
    st.dataframe(income_table, use_container_width=True, hide_index=True)

    yearly = fin.get("yearly", [])
    if yearly:
        jaar_tabel = pd.DataFrame(yearly)
        jaar_tabel = jaar_tabel.rename(columns={
            "Jaar": "Jaar",
            "Inkomsten": "Totale inkomsten",
            "Uitgaven": "Totale uitgaven",
            "Netto resultaat": "Netto resultaat",
            "Periodieke donaties": "Periodieke donaties",
            "Eenmalige donaties": "Eenmalige donaties",
            "Overige inkomsten": "Overige inkomsten",
        })
        keep = [c for c in ["Jaar", "Periodieke donaties", "Eenmalige donaties", "Overige inkomsten", "Totale inkomsten", "Totale uitgaven", "Netto resultaat"] if c in jaar_tabel.columns]
        jaar_tabel = jaar_tabel[keep]
        jaar_tabel = fmt_year_cols(jaar_tabel, ["Jaar"])
        jaar_tabel = fmt_money_cols(jaar_tabel, [c for c in jaar_tabel.columns if c != "Jaar"])

        section_header("Jaaroverzicht resultaat", "Overzicht van inkomsten, uitgaven en netto resultaat per jaar binnen de gekozen periode")
        st.dataframe(jaar_tabel, use_container_width=True, hide_index=True)

def render_generate_tab():
    section_header("Nieuwe rapportage genereren", "Upload een nieuw CSV bankbestand en laat de rapportage opnieuw opbouwen")
    uploaded_file = st.file_uploader("Upload nieuw CSV bankbestand", type=["csv"])
    if uploaded_file:
        csv_path = RAW_DIR / "upload_temp.csv"
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("CSV geüpload")
        if st.button("Genereer bestuursrapport"):
            result = subprocess.run([sys.executable, "run_donateur_intelligence_v5.py", str(csv_path)], capture_output=True, text=True)
            if result.returncode == 0:
                st.success("Nieuw rapport gegenereerd")
                st.code(result.stdout)
            else:
                st.error("Fout bij genereren rapport")
                st.code(result.stderr)


def render_downloads_tab():
    section_header("Downloads")
    pdf = newest("bestuursrapport_donaties_v5_*.pdf")
    excel = newest("donateur_intelligence_v5_*.xlsx")
    if pdf:
        st.download_button("Download PDF-rapport", pdf.read_bytes(), pdf.name, mime="application/pdf", use_container_width=True)
    if excel:
        st.download_button("Download publieke Excel-analyse", excel.read_bytes(), excel.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    section_header("Privacy")
    st.markdown('<div class="summary">Deze omgeving bevat geen namen, geen IBAN en geen interne mapping. Alleen publieke, geanonimiseerde rapportages worden hier getoond.</div>', unsafe_allow_html=True)


def main():
    inject_css()
    pdf = newest("bestuursrapport_donaties_v5_*.pdf")
    excel = newest("donateur_intelligence_v5_*.xlsx")

    st.markdown(
        """
        <div class="hero">
            <div class="hero-kicker">Bestuursomgeving • Privacy-veilige rapportage</div>
            <div class="hero-title">Donateur Intelligence Platform</div>
            <div class="hero-sub">
                Deze omgeving toont uitsluitend publieke, geanonimiseerde rapportages zonder namen en zonder IBAN.
                Alle identificatie van individuele relaties verloopt intern via Donateur_ID en blijft buiten deze cloudomgeving.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    
    data = load_data()
    if data is None:
        st.warning("Nog geen publieke dataset gevonden.")
        st.stop()

    tabs = st.tabs(["Dashboard", "Donateursbasis", "Retentie & uitstroom", "Financieel overzicht", "Rapport genereren", "Downloads"])

    with tabs[0]:
        render_dashboard_tab(data)

    with tabs[1]:
        render_donors_tab(data)

    with tabs[2]:
        render_retention_tab(data)

    with tabs[3]:
        render_financial_tab(data)

    with tabs[4]:
        render_generate_tab()

    with tabs[5]:
        render_downloads_tab()


# OVERRIDE_RENDER_FINANCIAL_TAB_V2
def render_financial_tab(data):
    meta = load_current_period_meta()
    fin = load_financial_summary()

    period_text = str(meta.get("period_label", "gekozen periode"))
    subtitle = "Inkomsten, uitgaven, netto resultaat en contant in kas"
    if meta.get("period_label"):
        subtitle = subtitle + " • " + period_text
    section_header("Financieel overzicht", subtitle)

    totals = fin.get("totals", {})
    inkomsten = float(totals.get("inkomsten", 0) or 0)
    uitgaven = float(totals.get("uitgaven", 0) or 0)
    netto_resultaat = float(totals.get("netto_resultaat", 0) or 0)
    contant_kas = float(totals.get("contant_kas", meta.get("contant_kas", 0)) or 0)
    netto_incl_kas = float(totals.get("netto_resultaat_incl_kas", netto_resultaat + contant_kas) or 0)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi_card("Totale inkomsten", eur(inkomsten), period_text)
    with c2:
        kpi_card("Totale uitgaven", eur(uitgaven), period_text)
    with c3:
        kpi_card("Netto resultaat", eur(netto_resultaat), period_text)
    with c4:
        kpi_card("Contant in kas", eur(contant_kas), "stand op rapportmoment")
    with c5:
        kpi_card("Netto resultaat incl. kas", eur(netto_incl_kas), period_text)

    section_header("Inkomstenoverzicht", "Onderverdeling van inkomsten binnen " + period_text)
    income_table = pd.DataFrame([
        {"Type": "Periodieke donaties", "Bedrag": totals.get("periodieke_donaties", 0)},
        {"Type": "Eenmalige donaties", "Bedrag": totals.get("eenmalige_donaties", 0)},
        {"Type": "Overige inkomsten", "Bedrag": totals.get("overige_inkomsten", 0)},
        {"Type": "Totale inkomsten", "Bedrag": totals.get("inkomsten", 0)},
    ])
    income_table = fmt_money_cols(income_table, ["Bedrag"])
    st.dataframe(income_table, use_container_width=True, hide_index=True)

    yearly = fin.get("yearly", [])
    if yearly:
        jaar_tabel = pd.DataFrame(yearly)
        keep = [c for c in ["Jaar", "Periodieke donaties", "Eenmalige donaties", "Overige inkomsten", "Inkomsten", "Uitgaven", "Netto resultaat"] if c in jaar_tabel.columns]
        jaar_tabel = jaar_tabel[keep]
        jaar_tabel = jaar_tabel.rename(columns={
            "Inkomsten": "Totale inkomsten",
            "Uitgaven": "Totale uitgaven",
        })
        jaar_tabel = fmt_year_cols(jaar_tabel, ["Jaar"])
        jaar_tabel = fmt_money_cols(jaar_tabel, [c for c in jaar_tabel.columns if c != "Jaar"])
        section_header("Jaaroverzicht resultaat", "Overzicht van inkomsten, uitgaven en netto resultaat per jaar binnen " + period_text)
        st.dataframe(jaar_tabel, use_container_width=True, hide_index=True)

    section_header("Uitgaven detail", "Alle uitgaven uit het bankoverzicht binnen " + period_text)

    expense_rows = fin.get("expense_details", [])
    if not expense_rows:
        st.info("Geen uitgaven gevonden in deze periode.")
        return

    with st.expander("Bekijk alle uitgaven", expanded=False):
        expenses = pd.DataFrame(expense_rows)

        years = ["Alle jaren"] + sorted([int(y) for y in expenses["Jaar"].dropna().unique().tolist()]) if "Jaar" in expenses.columns else ["Alle jaren"]
        c_filter1, c_filter2, c_filter3 = st.columns([1, 3, 1])
        with c_filter1:
            selected_year = st.selectbox("Jaar", years, key="financial_expense_year_filter")
        with c_filter2:
            search_term = st.text_input("Zoek in naam / omschrijving", key="financial_expense_search")
        with c_filter3:
            sort_desc = st.checkbox("Hoog naar laag", value=True, key="financial_expense_sort_desc")

        if selected_year != "Alle jaren" and "Jaar" in expenses.columns:
            expenses = expenses[expenses["Jaar"] == selected_year].copy()

        if search_term:
            q = str(search_term).strip().lower()
            mask = pd.Series(False, index=expenses.index)
            for col in ["Naam", "Omschrijving"]:
                if col in expenses.columns:
                    mask = mask | expenses[col].astype(str).str.lower().str.contains(q, na=False)
            expenses = expenses[mask].copy()

        if "Bedrag" in expenses.columns:
            expenses["Bedrag_sort"] = pd.to_numeric(expenses["Bedrag"], errors="coerce")
            expenses = expenses.sort_values("Bedrag_sort", ascending=not sort_desc, na_position="last")

        show_cols = []
        if "Datum" in expenses.columns:
            show_cols.append("Datum")
        if "Naam" in expenses.columns:
            show_cols.append("Naam")
        if "Omschrijving" in expenses.columns:
            show_cols.append("Omschrijving")
        if "Bedrag" in expenses.columns:
            show_cols.append("Bedrag")

        expenses = expenses[show_cols + (["Bedrag_sort"] if "Bedrag_sort" in expenses.columns else [])].copy()
        expenses = fmt_money_cols(expenses, ["Bedrag"])
        expenses = expenses.drop(columns=["Bedrag_sort"], errors="ignore")

        st.dataframe(expenses, use_container_width=True, hide_index=True)



# OVERRIDE_CHART_GROUPED_INCOME_MIX_V1
def chart_grouped_income_mix(yearly_rows):
    df = pd.DataFrame(yearly_rows)
    if len(df) == 0:
        return None

    fig, ax = plt.subplots(figsize=(7.4, 4.4))

    years = df["Jaar"].astype(str).tolist()
    periodiek = pd.to_numeric(df["Periodieke donaties"], errors="coerce").fillna(0).tolist()
    eenmalig = pd.to_numeric(df["Eenmalige donaties"], errors="coerce").fillna(0).tolist()

    x = list(range(len(years)))
    width = 0.34

    bars1 = ax.bar([i - width / 2 for i in x], eenmalig, width=width, label="Eenmalig", color="#2D7FF9")
    bars2 = ax.bar([i + width / 2 for i in x], periodiek, width=width, label="Periodiek", color="#34A0A4")

    ymax = max(eenmalig + periodiek) if (eenmalig + periodiek) else 0
    for rect, val in zip(bars1, eenmalig):
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            rect.get_height() + (0.02 * ymax if ymax > 0 else 0.2),
            eur(val),
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="#0F2747",
        )
    for rect, val in zip(bars2, periodiek):
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            rect.get_height() + (0.02 * ymax if ymax > 0 else 0.2),
            eur(val),
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="#0F2747",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.grid(axis="y", alpha=0.16)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=2, loc="upper left")
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    return fig


if __name__ == "__main__":
    main()