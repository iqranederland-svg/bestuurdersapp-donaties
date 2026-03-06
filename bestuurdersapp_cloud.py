from pathlib import Path
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
            out[c] = out[c].apply(pct)
    return out


def fmt_year_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].apply(yearstr)
    return out


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
.block-container{max-width:1500px;padding-top:1rem;padding-bottom:2rem;}
.stApp{background:#F4F7FB;}
.hero{background:linear-gradient(135deg,#0F2747 0%,#1E3A5F 100%);padding:28px 32px;border-radius:24px;color:white;margin-bottom:20px;box-shadow:0 10px 26px rgba(15,39,71,0.16);}
.hero-kicker{font-size:13px;opacity:0.86;margin-bottom:8px;}
.hero-title{font-size:38px;font-weight:800;margin-bottom:8px;line-height:1.12;}
.hero-sub{font-size:16px;line-height:1.55;max-width:980px;}
.kpi{background:white;padding:18px 18px 16px 18px;border-radius:18px;border:1px solid #E5E7EB;min-height:150px;height:150px;box-shadow:0 4px 16px rgba(15,39,71,0.05);display:flex;flex-direction:column;justify-content:space-between;overflow:hidden;}
.kpi-title{font-size:13px;color:#6B7280;line-height:1.35;min-height:34px;}
.kpi-value{font-size:30px;font-weight:800;color:#0F2747;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.kpi-sub{font-size:12px;color:#6B7280;line-height:1.4;min-height:34px;overflow:hidden;}
.section{font-size:26px;font-weight:800;margin-top:26px;margin-bottom:8px;color:#0F2747;line-height:1.15;}
.subsection{font-size:20px;font-weight:700;margin-top:18px;margin-bottom:8px;color:#0F2747;line-height:1.2;}
.section-sub{font-size:14px;color:#6B7280;margin-bottom:14px;line-height:1.4;}
.summary{background:white;padding:15px;border-radius:14px;border:1px solid #E5E7EB;margin-bottom:10px;line-height:1.6;box-shadow:0 4px 16px rgba(15,39,71,0.05);}
.info-box{background:#FFFFFF;border:1px solid #D8E1EE;border-left:5px solid #0F2747;padding:14px 16px;border-radius:12px;line-height:1.6;margin-bottom:12px;}
.nowrap{white-space:nowrap;}
div[data-testid="stMetric"]{background:white;border:1px solid #E5E7EB;padding:14px;border-radius:14px;}
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
    section_header("Management Dashboard", "Kernoverzicht met bedragen, donateursbasis, dragers en uitstroom")
    render_kpis(data)
    render_donor_health(data)

    dash = data["dashboard"].copy().sort_values("Jaar")
    closed_dash, running_dash, running_year = split_closed_running_years(dash)
    periodic = data["periodic"].copy().sort_values("Jaar")
    closed_periodic = periodic[periodic["Jaar"].astype(int) < running_year].copy() if running_year is not None else periodic.copy()
    exit_df = data["exit"].copy().sort_values("Laatste actieve jaar")
    new_df = data["new"].copy().sort_values("Jaar")

    if running_year is not None:
        info_box(f"Het jaar {running_year} is nog niet afgerond. Grafieken vergelijken daarom primair afgesloten jaren. De stand van {running_year} wordt afzonderlijk weergegeven om vertekening te voorkomen.")

    section_header("Kernvisualisaties")
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.pyplot(chart_bar(closed_dash if len(closed_dash) else dash, "Jaar", "Totale_inkomsten", "Totale donaties per afgesloten jaar", kind="eur"), use_container_width=True)
    with r1c2:
        st.pyplot(chart_bar(closed_dash if len(closed_dash) else dash, "Jaar", "Unieke_bankdonateurs", "Aantal donateurs per afgesloten jaar"), use_container_width=True)

    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.pyplot(chart_bar(closed_periodic if len(closed_periodic) else periodic, "Jaar", "Bedrag", "Dragers donaties per afgesloten jaar", kind="eur"), use_container_width=True)
    with r2c2:
        st.pyplot(chart_bar(exit_df, "Laatste actieve jaar", "Aantal donateurs", "Uitstroom per laatste actieve jaar"), use_container_width=True)

    section_header("Jaaroverzicht", "Totale donaties en hoofdgroepen per jaar")
    year_table = dash[["Jaar", "Totale_inkomsten", "Directe_bankdonaties", "Periodieke_donaties", "Belgische_donaties", "Anonieme_donaties", "Unieke_bankdonateurs", "Totaal_transacties"]].copy()
    year_table["Overige donaties"] = year_table["Belgische_donaties"] + year_table["Anonieme_donaties"]
    year_table = year_table.rename(columns={
        "Totale_inkomsten": "Totale inkomsten",
        "Directe_bankdonaties": "Eenmalige donaties",
        "Periodieke_donaties": "Dragers donaties",
        "Unieke_bankdonateurs": "Unieke donateurs",
        "Totaal_transacties": "Totaal transacties",
    })
    year_table = year_table[["Jaar", "Totale inkomsten", "Eenmalige donaties", "Dragers donaties", "Overige donaties", "Unieke donateurs", "Totaal transacties"]]
    year_table = fmt_money_cols(year_table, ["Totale inkomsten", "Eenmalige donaties", "Dragers donaties", "Overige donaties"])
    year_table = fmt_year_cols(year_table, ["Jaar"])
    year_table = fmt_int_cols(year_table, ["Unieke donateurs", "Totaal transacties"])
    st.dataframe(year_table, use_container_width=True, hide_index=True)
    info_box("Overige donaties bestaan uit niet individueel herleidbare stromen, waaronder Sepay, Belgische donateurs en anonieme donateurs.")

    if running_year is not None and len(running_dash):
        section_header(f"Lopend jaar {running_year}", "Voorlopige stand van het nog niet afgesloten kalenderjaar")
        running_table = running_dash[["Jaar", "Totale_inkomsten", "Directe_bankdonaties", "Periodieke_donaties", "Belgische_donaties", "Anonieme_donaties", "Unieke_bankdonateurs", "Totaal_transacties"]].copy()
        running_table["Overige donaties"] = running_table["Belgische_donaties"] + running_table["Anonieme_donaties"]
        running_table = running_table.rename(columns={
            "Totale_inkomsten": "Totale inkomsten",
            "Directe_bankdonaties": "Eenmalige donaties",
            "Periodieke_donaties": "Dragers donaties",
            "Unieke_bankdonateurs": "Unieke donateurs",
            "Totaal_transacties": "Totaal transacties",
        })
        running_table = running_table[["Jaar", "Totale inkomsten", "Eenmalige donaties", "Dragers donaties", "Overige donaties", "Unieke donateurs", "Totaal transacties"]]
        running_table = fmt_money_cols(running_table, ["Totale inkomsten", "Eenmalige donaties", "Dragers donaties", "Overige donaties"])
        running_table = fmt_year_cols(running_table, ["Jaar"])
        running_table = fmt_int_cols(running_table, ["Unieke donateurs", "Totaal transacties"])
        st.dataframe(running_table, use_container_width=True, hide_index=True)

    section_header("Managementsamenvatting")
    points = []
    pareto = data["pareto"].copy()
    if len(pareto):
        r = pareto.loc[pareto["Segment"] == "Top 10%"].iloc[0]
        points.append(f'De top 10% van de bankdonateurs vertegenwoordigt <strong class="nowrap">{pct(r["Aandeel_inkomsten_pct"])}</strong> van de directe bankdonaties, goed voor <strong class="nowrap">{eur(r["Bedrag"])}</strong>.')
    if len(periodic):
        r = periodic.iloc[-1]
        points.append(f'In <strong class="nowrap">{int(r["Jaar"])}</strong> bedroegen de dragers donaties <strong class="nowrap">{eur(r["Bedrag"])}</strong>.')
    if len(new_df):
        r = new_df.iloc[-1]
        points.append(f'In <strong class="nowrap">{int(r["Jaar"])}</strong> kwamen er <strong class="nowrap">{i0(r["Nieuwe donateurs sinds start dataset"])}</strong> nieuwe donateurs bij sinds start van de dataset.')
    retention = data["retention"].copy().sort_values("Van_jaar")
    if len(retention):
        r = retention.iloc[-1]
        points.append(f'De laatste gemeten jaar-op-jaar retentie bedraagt <strong class="nowrap">{pct(r["Retentie_pct"])}</strong> over de overgang <strong class="nowrap">{int(r["Van_jaar"])} → {int(r["Naar_jaar"])}</strong>.')
    if len(exit_df):
        r = exit_df.sort_values("Totaal bedrag van deze groep", ascending=False).iloc[0]
        points.append(f'Het uitstroomcohort met grootste impact heeft laatste actieve jaar <strong class="nowrap">{int(r["Laatste actieve jaar"])}</strong> en vertegenwoordigt een historische donatiewaarde van <strong class="nowrap">{eur(r["Totaal bedrag van deze groep"])}</strong>. Door het lopende opvolgjaar moet dit voorzichtig worden geïnterpreteerd.')
    for p in points:
        st.markdown(f'<div class="summary">{p}</div>', unsafe_allow_html=True)


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

    tabs = st.tabs(["Dashboard", "Donateursbasis", "Retentie & uitstroom", "Rapport genereren", "Downloads"])
    with tabs[0]:
        render_dashboard_tab(data)
    with tabs[1]:
        render_donors_tab(data)
    with tabs[2]:
        render_retention_tab(data)
    with tabs[3]:
        render_generate_tab()
    with tabs[4]:
        render_downloads_tab()


if __name__ == "__main__":
    main()