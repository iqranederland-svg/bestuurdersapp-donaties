#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DEFAULT_OUTPUT_DIR = Path("outputs")
CATEGORY_PERIODIC = "Periodieke donatie"
CATEGORY_BELGIUM = "Belgische donatie"
CATEGORY_ANON = "Overige niet-herleidbare donatie"
CATEGORY_BANK = "Directe bankdonateur"

def eur0(x):
    try:
        n = float(x)
    except Exception:
        return str(x)
    return "€ " + f"{int(round(n)):,}".replace(",", ".")

def pct1(x):
    try:
        return f"{float(x):.1f}%".replace(".", ",")
    except Exception:
        return str(x)

def int0(x):
    try:
        return f"{int(round(float(x))):,}".replace(",", ".")
    except Exception:
        return str(x)

def ensure_output_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def detect_separator(path: Path) -> str:
    candidates = [",", ";", "\t", "|"]
    best_sep = ","
    best_cols = -1
    for sep in candidates:
        try:
            df = pd.read_csv(path, sep=sep, engine="python", nrows=50)
            if len(df.columns) > best_cols:
                best_cols = len(df.columns)
                best_sep = sep
        except Exception:
            continue
    return best_sep

def clean_text_series(x: pd.Series) -> pd.Series:
    x = x.astype(str)
    repl = {
        "\ufeff": "",
        "\u00a0": " ",
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\u200e": "",
        "\u200f": "",
        "\u202a": "",
        "\u202b": "",
        "\u202c": "",
        "\u2060": "",
    }
    for a, b in repl.items():
        x = x.str.replace(a, b, regex=False)
    return x.str.strip()

def parse_date_series(x: pd.Series) -> pd.Series:
    x = clean_text_series(x)
    x = x.str.replace("/", "-", regex=False)
    x = x.str.replace(".", "-", regex=False)
    x = x.replace({"": None, "nan": None, "None": None, "NaT": None})
    d1 = pd.to_datetime(x, errors="coerce", utc=False)
    d2 = pd.to_datetime(x, errors="coerce", dayfirst=True, utc=False)
    out = d1.fillna(d2)
    if out.isna().any():
        extracted = x.str.extract(r"(\d{4}-\d{2}-\d{2})", expand=False)
        d3 = pd.to_datetime(extracted, errors="coerce", utc=False)
        out = out.fillna(d3)
    return out

def parse_amount_eu(x: pd.Series) -> pd.Series:
    s = clean_text_series(x)
    s = s.str.replace("€", "", regex=False)
    s = s.str.replace("EUR", "", regex=False)
    s = s.str.replace(" ", "", regex=False)
    has_comma = s.str.contains(",", na=False)
    has_dot = s.str.contains(r"\.", na=False)
    both = has_comma & has_dot
    only_comma = has_comma & (~has_dot)
    s.loc[both] = s.loc[both].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    s.loc[only_comma] = s.loc[only_comma].str.replace(",", ".", regex=False)
    s = s.str.replace(r"[^0-9.\-]", "", regex=True)
    return pd.to_numeric(s, errors="coerce")

def safe_sheet_name(name: str) -> str:
    bad = '[]:*?/\\'
    out = "".join("_" if c in bad else c for c in name)
    return out[:31]

def ingest_clean(input_csv: Path):
    sep = detect_separator(input_csv)
    df = pd.read_csv(input_csv, sep=sep, engine="python")
    df.columns = [str(c).replace("\ufeff", "").replace("\u00a0", " ").strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]

    required = ["Date", "Interest Date", "Amount", "Counterparty", "Name"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Ontbrekende kolommen: {missing}")

    a = parse_date_series(df["Interest Date"])
    b = parse_date_series(df["Date"])
    df["Datum"] = a.fillna(b)
    df["Bedrag"] = parse_amount_eu(df["Amount"])
    df["Naam"] = clean_text_series(df["Name"])
    df["IBAN"] = clean_text_series(df["Counterparty"])

    df = df[df["Datum"].notna()].copy()
    df = df[df["Bedrag"].notna()].copy()
    df = df[df["Bedrag"] > 0].copy()

    sepay = df["Naam"].str.lower().str.contains("sepay", na=False)

    df["Jaar"] = df["Datum"].dt.year.astype(int)
    df["Maand"] = df["Datum"].dt.to_period("M").astype(str)

    name_lc = df["Naam"].str.lower()
    no_iban = df["IBAN"].isna() | (df["IBAN"].astype(str).str.strip() == "")
    is_mollie = name_lc.str.contains("mollie", na=False)
    is_bancontact = name_lc.str.contains("bancontact", na=False)

    df["Categorie"] = CATEGORY_BANK
    df.loc[is_mollie, "Categorie"] = CATEGORY_PERIODIC
    df.loc[is_bancontact, "Categorie"] = CATEGORY_BELGIUM
    df.loc[sepay, "Categorie"] = CATEGORY_ANON
    df.loc[no_iban & ~is_mollie & ~is_bancontact & ~sepay, "Categorie"] = CATEGORY_ANON
    df["Retentie_geschikt"] = df["Categorie"].eq(CATEGORY_BANK)

    bank = df[df["Categorie"].eq(CATEGORY_BANK) & ~no_iban].copy()
    unique_ibans = sorted(bank["IBAN"].astype(str).str.strip().unique().tolist())
    mapping_rows = []
    for idx, iban in enumerate(unique_ibans, start=1):
        naam = bank.loc[bank["IBAN"].astype(str).str.strip().eq(iban), "Naam"].astype(str).value_counts().index[0]
        mapping_rows.append({"Donateur_ID": f"D-{idx:05d}", "IBAN": iban, "Naam": naam})
    mapping = pd.DataFrame(mapping_rows)
    id_map = dict(zip(mapping["IBAN"], mapping["Donateur_ID"]))
    df["Donateur_ID"] = df["IBAN"].map(id_map)

    public_df = df[["Datum", "Jaar", "Maand", "Bedrag", "Donateur_ID", "Categorie", "Retentie_geschikt"]].copy()
    return public_df, mapping

def income_by_category(df):
    out = (
        df.groupby("Categorie")
        .agg(Transacties=("Bedrag", "size"), Bedrag=("Bedrag", "sum"))
        .reset_index()
        .sort_values("Bedrag", ascending=False)
    )
    total = out["Bedrag"].sum()
    out["Aandeel_totaal_pct"] = out["Bedrag"] / total * 100
    return out

def dashboard_yearly(df):
    total_per_year = (
        df.groupby("Jaar")
        .agg(Totale_inkomsten=("Bedrag", "sum"), Totaal_transacties=("Bedrag", "size"))
        .reset_index()
    )
    bank = df[df["Categorie"] == CATEGORY_BANK]
    periodic = df[df["Categorie"] == CATEGORY_PERIODIC]
    belgium = df[df["Categorie"] == CATEGORY_BELGIUM]
    anon = df[df["Categorie"] == CATEGORY_ANON]

    out = total_per_year.set_index("Jaar")
    out = out.join(bank.groupby("Jaar")["Bedrag"].sum().rename("Directe_bankdonaties"), how="left")
    out = out.join(periodic.groupby("Jaar")["Bedrag"].sum().rename("Periodieke_donaties"), how="left")
    out = out.join(belgium.groupby("Jaar")["Bedrag"].sum().rename("Belgische_donaties"), how="left")
    out = out.join(anon.groupby("Jaar")["Bedrag"].sum().rename("Anonieme_donaties"), how="left")
    out = out.join(bank.groupby("Jaar")["Donateur_ID"].nunique().rename("Unieke_bankdonateurs"), how="left")
    out = out.fillna(0).reset_index()
    out["Periodiek_aandeel_pct"] = out["Periodieke_donaties"] / out["Totale_inkomsten"] * 100
    return out

def donor_base_stats(df):
    bank = df[df["Categorie"] == CATEGORY_BANK].copy()
    total_bank_amount = bank["Bedrag"].sum()
    unique_donateurs = bank["Donateur_ID"].nunique()
    tx = len(bank)
    avg_tx_per = tx / unique_donateurs if unique_donateurs else 0
    return pd.DataFrame([
        ("Unieke bankdonateurs", unique_donateurs),
        ("Retentie-geschikte transacties", tx),
        ("Totale bankdonaties", total_bank_amount),
        ("Gemiddeld aantal transacties per bankdonateur", avg_tx_per),
    ], columns=["KPI", "Waarde"])

def new_donors_per_year(df):
    bank = df[df["Categorie"] == CATEGORY_BANK].copy()
    first_year = bank.groupby("Donateur_ID")["Jaar"].min().reset_index(name="Eerste_jaar")
    return (
        first_year.groupby("Eerste_jaar")
        .size()
        .reset_index(name="Nieuwe donateurs sinds start dataset")
        .rename(columns={"Eerste_jaar": "Jaar"})
        .sort_values("Jaar")
    )

def returning_vs_new_per_year(df):
    bank = df[df["Categorie"] == CATEGORY_BANK].copy()
    first_year = bank.groupby("Donateur_ID")["Jaar"].min().rename("Eerste_jaar")
    bank = bank.join(first_year, on="Donateur_ID")
    bank["Is_nieuw"] = bank["Jaar"] == bank["Eerste_jaar"]
    new_counts = bank.loc[bank["Is_nieuw"]].groupby("Jaar")["Donateur_ID"].nunique().rename("Nieuwe_donateurs")
    ret_counts = bank.loc[~bank["Is_nieuw"]].groupby("Jaar")["Donateur_ID"].nunique().rename("Terugkerende_donateurs")
    out = pd.concat([new_counts, ret_counts], axis=1).fillna(0).reset_index()
    out["Totaal_unieke_donateurs"] = out["Nieuwe_donateurs"] + out["Terugkerende_donateurs"]
    out["Aandeel_nieuw_pct"] = out["Nieuwe_donateurs"] / out["Totaal_unieke_donateurs"] * 100
    return out.sort_values("Jaar")

def cohort_retention(df):
    bank = df[df["Categorie"] == CATEGORY_BANK].copy()
    years = sorted(bank["Jaar"].dropna().unique().tolist())
    donors_by_year = {y: set(bank.loc[bank["Jaar"] == y, "Donateur_ID"].dropna().astype(str).unique()) for y in years}
    rows = []
    for cohort_year in years:
        base = donors_by_year.get(cohort_year, set())
        base_n = len(base)
        if base_n == 0:
            continue
        for target_year in years:
            if target_year < cohort_year:
                continue
            retained = len(base.intersection(donors_by_year.get(target_year, set())))
            pct = retained / base_n * 100 if base_n else 0
            rows.append({"Cohortjaar": int(cohort_year), "Doeljaar": int(target_year), "Aantal_donateurs_in_cohort": base_n, "Teruggekeerd": retained, "Retentie_pct": pct})
    return pd.DataFrame(rows)

def year_on_year_retention(df):
    bank = df[df["Categorie"] == CATEGORY_BANK].copy()
    years = sorted(bank["Jaar"].dropna().unique().tolist())
    donors_by_year = {y: set(bank.loc[bank["Jaar"] == y, "Donateur_ID"].dropna().astype(str).unique()) for y in years}
    rows = []
    for i in range(len(years) - 1):
        y1 = years[i]
        y2 = years[i + 1]
        d1 = donors_by_year.get(y1, set())
        d2 = donors_by_year.get(y2, set())
        retained = len(d1.intersection(d2))
        pct = retained / len(d1) * 100 if len(d1) else 0
        rows.append({"Van_jaar": y1, "Naar_jaar": y2, "Donateurs_startjaar": len(d1), "Ook_actief_volgend_jaar": retained, "Retentie_pct": pct})
    return pd.DataFrame(rows)

def pareto_overall(df):
    bank = df[df["Categorie"] == CATEGORY_BANK].copy()
    donateurs = (
        bank.groupby("Donateur_ID")
        .agg(Totaal_bedrag=("Bedrag", "sum"), Transacties=("Bedrag", "size"))
        .reset_index()
        .sort_values("Totaal_bedrag", ascending=False)
    )
    total = donateurs["Totaal_bedrag"].sum()
    n = len(donateurs)
    rows = []
    for p in [0.01, 0.05, 0.10, 0.25, 0.50]:
        k = max(1, int(round(n * p)))
        amount = donateurs.head(k)["Totaal_bedrag"].sum()
        rows.append({"Segment": f"Top {int(p*100)}%", "Aantal_donateurs": k, "Bedrag": amount, "Aandeel_inkomsten_pct": amount / total * 100 if total else 0})
    return donateurs, pd.DataFrame(rows)

def top_donateurs_all_years(df, top_n=50):
    donateurs, _ = pareto_overall(df)
    return donateurs.head(top_n).copy()

def periodic_per_year(df):
    d = df[df["Categorie"] == CATEGORY_PERIODIC].copy()
    out = (
        d.groupby("Jaar")
        .agg(Payouts=("Bedrag", "size"), Bedrag=("Bedrag", "sum"))
        .reset_index()
        .sort_values("Jaar")
    )
    out["Groei_tov_vorig_jaar_pct"] = out["Bedrag"].pct_change() * 100
    return out

def donor_lifecycle(df):
    bank = df[df["Categorie"] == CATEGORY_BANK].copy()
    donor_span = (
        bank.groupby("Donateur_ID")
        .agg(Eerste_jaar=("Jaar", "min"), Laatste_jaar=("Jaar", "max"), Totaal_bedrag=("Bedrag", "sum"), Transacties=("Bedrag", "size"))
        .reset_index()
    )
    exit_rows = []
    for y in [2023, 2024, 2025]:
        d = donor_span[donor_span["Laatste_jaar"] == y].copy()
        exit_rows.append({
            "Laatste actieve jaar": y,
            "Aantal donateurs": len(d),
            "Totaal bedrag van deze groep": float(d["Totaal_bedrag"].sum()),
            "Gemiddeld bedrag per donateur": float(d["Totaal_bedrag"].mean()) if len(d) else 0.0,
            "Totaal transacties van deze groep": int(d["Transacties"].sum()) if len(d) else 0,
        })
    exit_summary = pd.DataFrame(exit_rows)
    return donor_span, exit_summary

def save_bar_chart(labels, values, title, ylabel, path):
    plt.figure(figsize=(8.5, 4.4))
    bars = plt.bar(range(len(values)), values)
    plt.xticks(range(len(values)), labels, rotation=0)
    plt.title(title)
    plt.ylabel(ylabel)
    for rect, v in zip(bars, values):
        plt.text(rect.get_x() + rect.get_width() / 2, rect.get_height(), int0(v), ha="center", va="bottom", fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()

def save_line_chart(labels, values, title, ylabel, path):
    plt.figure(figsize=(8.5, 4.4))
    xs = list(range(len(values)))
    plt.plot(xs, values, marker="o")
    plt.xticks(xs, labels)
    plt.title(title)
    plt.ylabel(ylabel)
    for x, y in zip(xs, values):
        label = pct1(y) if "pct" in ylabel.lower() else int0(y)
        plt.text(x, y, label, ha="center", va="bottom", fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()

def build_charts(df, output_dir):
    charts = {}
    yearly = dashboard_yearly(df)
    categories = income_by_category(df)
    periodic_year = periodic_per_year(df)
    new_donateurs = new_donors_per_year(df)
    new_vs_returning = returning_vs_new_per_year(df)
    _, pareto_summary = pareto_overall(df)
    yoy = year_on_year_retention(df)
    _, exit_summary = donor_lifecycle(df)

    p = output_dir / "chart_income_year_secure.png"
    save_bar_chart(yearly["Jaar"].astype(str).tolist(), yearly["Totale_inkomsten"].tolist(), "Totale inkomsten per jaar", "Bedrag (€)", p)
    charts["income_year"] = p

    p = output_dir / "chart_bankdonateurs_year_secure.png"
    save_bar_chart(yearly["Jaar"].astype(str).tolist(), yearly["Unieke_bankdonateurs"].tolist(), "Unieke bankdonateurs per jaar", "Aantal donateurs", p)
    charts["bankdonateurs_year"] = p

    p = output_dir / "chart_new_donateurs_year_secure.png"
    save_bar_chart(new_donateurs["Jaar"].astype(str).tolist(), new_donateurs["Nieuwe donateurs sinds start dataset"].tolist(), "Nieuwe donateurs per jaar", "Aantal nieuwe donateurs", p)
    charts["new_donateurs_year"] = p

    p = output_dir / "chart_category_amounts_secure.png"
    save_bar_chart(categories["Categorie"].astype(str).tolist(), categories["Bedrag"].tolist(), "Totale inkomsten per categorie", "Bedrag (€)", p)
    charts["category_amounts"] = p

    p = output_dir / "chart_category_counts_secure.png"
    save_bar_chart(categories["Categorie"].astype(str).tolist(), categories["Transacties"].tolist(), "Aantal transacties per categorie", "Aantal transacties", p)
    charts["category_counts"] = p

    p = output_dir / "chart_periodic_year_secure.png"
    save_bar_chart(periodic_year["Jaar"].astype(str).tolist(), periodic_year["Bedrag"].tolist(), "Periodieke donaties per jaar", "Bedrag (€)", p)
    charts["periodic_year"] = p

    p = output_dir / "chart_periodic_growth_secure.png"
    pg = periodic_year.copy()
    pg["Groei_tov_vorig_jaar_pct"] = pg["Groei_tov_vorig_jaar_pct"].fillna(0)
    save_line_chart(pg["Jaar"].astype(str).tolist(), pg["Groei_tov_vorig_jaar_pct"].tolist(), "Groei periodieke donaties per jaar", "Groei pct", p)
    charts["periodic_growth"] = p

    p = output_dir / "chart_new_vs_returning_secure.png"
    plt.figure(figsize=(8.5, 4.6))
    x = range(len(new_vs_returning))
    width = 0.38
    plt.bar([i - width/2 for i in x], new_vs_returning["Nieuwe_donateurs"], width=width, label="Nieuw")
    plt.bar([i + width/2 for i in x], new_vs_returning["Terugkerende_donateurs"], width=width, label="Terugkerend")
    plt.xticks(list(x), new_vs_returning["Jaar"].astype(str).tolist())
    plt.title("Nieuwe versus terugkerende donateurs")
    plt.ylabel("Aantal donateurs")
    plt.legend()
    plt.tight_layout()
    plt.savefig(p, dpi=200, bbox_inches="tight")
    plt.close()
    charts["new_vs_returning"] = p

    p = output_dir / "chart_pareto_secure.png"
    plt.figure(figsize=(8.5, 4.4))
    plt.plot(range(1, len(pareto_summary)+1), pareto_summary["Aandeel_inkomsten_pct"], marker="o")
    plt.xticks(range(1, len(pareto_summary)+1), pareto_summary["Segment"].tolist())
    plt.ylim(0, 100)
    plt.title("Pareto-concentratie van inkomsten")
    plt.ylabel("Aandeel inkomsten (%)")
    plt.xlabel("Segment")
    for i, y in enumerate(pareto_summary["Aandeel_inkomsten_pct"], start=1):
        plt.text(i, y, pct1(y), ha="center", va="bottom", fontsize=8)
    plt.tight_layout()
    plt.savefig(p, dpi=200, bbox_inches="tight")
    plt.close()
    charts["pareto"] = p

    p = output_dir / "chart_yoy_retention_secure.png"
    save_line_chart(yoy["Van_jaar"].astype(str).tolist(), yoy["Retentie_pct"].tolist(), "Jaar-op-jaar retentie", "Retentie pct", p)
    charts["yoy_retention"] = p

    p = output_dir / "chart_exit_amount_secure.png"
    save_bar_chart(exit_summary["Laatste actieve jaar"].astype(str).tolist(), exit_summary["Totaal bedrag van deze groep"].tolist(), "Historisch bedrag van uitgestroomde groepen", "Bedrag (€)", p)
    charts["exit_amount"] = p

    p = output_dir / "chart_exit_count_secure.png"
    save_bar_chart(exit_summary["Laatste actieve jaar"].astype(str).tolist(), exit_summary["Aantal donateurs"].tolist(), "Aantal uitgestroomde donateurs", "Aantal donateurs", p)
    charts["exit_count"] = p

    return charts

def tbl(data, col_widths, styles, header_bg="#E8EEF7"):
    wrapped = []
    for ridx, row in enumerate(data):
        wrapped_row = []
        for cell in row:
            style = styles["TableHead"] if ridx == 0 else styles["TableText"]
            wrapped_row.append(Paragraph(str(cell), style))
        wrapped.append(wrapped_row)
    t = Table(wrapped, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor(header_bg)),
        ("GRID", (0,0), (-1,-1), 0.45, colors.HexColor("#C7D2E1")),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    return t

def write_excel(df, mapping, output_path, internal_mapping_path):
    yearly = dashboard_yearly(df)
    cat = income_by_category(df)
    donor_stats = donor_base_stats(df)
    new_donateurs = new_donors_per_year(df)
    new_vs_returning = returning_vs_new_per_year(df)
    cohort = cohort_retention(df)
    yoy = year_on_year_retention(df)
    _, pareto_summary = pareto_overall(df)
    top_all = top_donateurs_all_years(df)
    periodic_year = periodic_per_year(df)
    donor_span, exit_summary = donor_lifecycle(df)

    with pd.ExcelWriter(output_path, engine="openpyxl") as w:
        yearly.to_excel(w, sheet_name=safe_sheet_name("01 Dashboard per jaar"), index=False)
        cat.to_excel(w, sheet_name=safe_sheet_name("02 Categorie overzicht"), index=False)
        donor_stats.to_excel(w, sheet_name=safe_sheet_name("03 Donateursbasis"), index=False)
        new_donateurs.to_excel(w, sheet_name=safe_sheet_name("04 Nieuwe donateurs"), index=False)
        new_vs_returning.to_excel(w, sheet_name=safe_sheet_name("05 Nieuw vs terugkerend"), index=False)
        cohort.to_excel(w, sheet_name=safe_sheet_name("06 Cohort lang"), index=False)
        yoy.to_excel(w, sheet_name=safe_sheet_name("07 Jaar-op-jaar retentie"), index=False)
        pareto_summary.to_excel(w, sheet_name=safe_sheet_name("08 Pareto"), index=False)
        top_all.to_excel(w, sheet_name=safe_sheet_name("09 Top alle jaren"), index=False)
        periodic_year.to_excel(w, sheet_name=safe_sheet_name("10 Periodiek per jaar"), index=False)
        donor_span.to_excel(w, sheet_name=safe_sheet_name("11 Donateur lifecycle"), index=False)
        exit_summary.to_excel(w, sheet_name=safe_sheet_name("12 Uitstroom samenvatting"), index=False)
        df.to_excel(w, sheet_name=safe_sheet_name("99 Publieke transacties"), index=False)

    with pd.ExcelWriter(internal_mapping_path, engine="openpyxl") as w:
        mapping.to_excel(w, sheet_name="01 Donateur ID mapping", index=False)


def write_pdf(df, output_path, charts):
    yearly = dashboard_yearly(df)
    cat = income_by_category(df)
    donor_stats = donor_base_stats(df).set_index("KPI")
    new_donateurs = new_donors_per_year(df)
    new_vs_returning = returning_vs_new_per_year(df)
    cohort = cohort_retention(df)
    yoy = year_on_year_retention(df)
    top_all = top_donateurs_all_years(df, top_n=15)
    _, pareto_summary = pareto_overall(df)
    periodic_year = periodic_per_year(df)
    _, exit_summary = donor_lifecycle(df)

    total_income = df["Bedrag"].sum()
    total_tx = len(df)
    unique_bank = int(donor_stats.loc["Unieke bankdonateurs", "Waarde"])
    bank_tx = int(donor_stats.loc["Retentie-geschikte transacties", "Waarde"])

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleBlue", parent=styles["Title"], fontSize=24, leading=28, textColor=colors.HexColor("#0F2747"), alignment=TA_LEFT, spaceAfter=8))
    styles.add(ParagraphStyle(name="Subtle", parent=styles["Normal"], fontSize=10.5, leading=14, textColor=colors.HexColor("#4B5563"), spaceAfter=6))
    styles.add(ParagraphStyle(name="Sec", parent=styles["Heading1"], fontSize=16, leading=20, textColor=colors.HexColor("#0F2747"), spaceAfter=8))
    styles.add(ParagraphStyle(name="BodyPro", parent=styles["BodyText"], fontSize=10.1, leading=14, textColor=colors.HexColor("#1F2937"), spaceAfter=6))
    styles.add(ParagraphStyle(name="TableHead", parent=styles["BodyText"], fontSize=8.7, leading=11, textColor=colors.HexColor("#0F172A")))
    styles.add(ParagraphStyle(name="TableText", parent=styles["BodyText"], fontSize=8.5, leading=11, textColor=colors.HexColor("#1F2937")))

    doc = SimpleDocTemplate(str(output_path), pagesize=A4, leftMargin=1.4*cm, rightMargin=1.4*cm, topMargin=1.2*cm, bottomMargin=1.1*cm)
    story = []

    story.append(Paragraph("Bestuursrapport donaties", styles["TitleBlue"]))
    story.append(Paragraph("Privacy-veilige board edition. IBAN en namen worden niet getoond in rapportage of publieke analyse. Identificatie verloopt uitsluitend via Donateur_ID.", styles["Subtle"]))

    cover = Table([
        [Paragraph("Totale inkomsten", styles["TableText"]), Paragraph(eur0(total_income), styles["TableText"]), Paragraph("Unieke bankdonateurs", styles["TableText"]), Paragraph(int0(unique_bank), styles["TableText"])],
        [Paragraph("Directe bankdonaties", styles["TableText"]), Paragraph(eur0(float(cat.loc[cat["Categorie"] == CATEGORY_BANK, "Bedrag"].sum())), styles["TableText"]), Paragraph("Retentie-geschikte transacties", styles["TableText"]), Paragraph(int0(bank_tx), styles["TableText"])],
        [Paragraph("Periodieke donaties", styles["TableText"]), Paragraph(eur0(float(cat.loc[cat["Categorie"] == CATEGORY_PERIODIC, "Bedrag"].sum())), styles["TableText"]), Paragraph("Totale transacties", styles["TableText"]), Paragraph(int0(total_tx), styles["TableText"])],
        [Paragraph("Top 10% aandeel", styles["TableText"]), Paragraph(pct1(float(pareto_summary.loc[pareto_summary["Segment"] == "Top 10%", "Aandeel_inkomsten_pct"].iloc[0])), styles["TableText"]), Paragraph("Top 5% aandeel", styles["TableText"]), Paragraph(pct1(float(pareto_summary.loc[pareto_summary["Segment"] == "Top 5%", "Aandeel_inkomsten_pct"].iloc[0])), styles["TableText"])],
    ], colWidths=[4.8*cm, 3.5*cm, 4.8*cm, 3.1*cm])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#F7FAFC")),
        ("BOX", (0,0), (-1,-1), 0.8, colors.HexColor("#C7D2E1")),
        ("INNERGRID", (0,0), (-1,-1), 0.45, colors.HexColor("#E5EAF2")),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    story += [Spacer(1, 0.25*cm), cover, Spacer(1, 0.35*cm)]
    story.append(Paragraph("Lezerswijzer - Alle positieve donaties tellen mee in het financiele totaal. Voor donateurretentie worden alleen transacties met IBAN gebruikt, maar deze identificatie wordt in rapportage en app vertaald naar Donateur_ID.", styles["BodyPro"]))
    story.append(PageBreak())

    story.append(Paragraph("1. Executive summary", styles["Sec"]))
    for txt in [
        f"De organisatie ontving in totaal <b>{eur0(total_income)}</b> aan donaties over <b>{int0(total_tx)}</b> transacties. Directe bankdonaties vormen de grootste pijler; periodieke donaties vormen de tweede stabiele pijler.",
        f"De donateuranalyse rust op <b>{int0(unique_bank)}</b> unieke bankdonateurs en <b>{int0(bank_tx)}</b> retentie-geschikte transacties. Daarmee is er een brede basis om zowel instroom als behoud te sturen.",
        "De inkomsten zijn geconcentreerd. De top 10% van de bankdonateurs genereert een groot deel van de bankdonaties. Dat maakt relatiebeheer met de topgroep essentieel en onderstreept het belang van periodieke donaties en middengroepontwikkeling.",
    ]:
        story.append(Paragraph(txt, styles["BodyPro"]))

    story.append(Paragraph("2. Totale donaties en categorieverdeling", styles["Sec"]))
    cat_data = [["Categorie", "Transacties", "Bedrag", "Aandeel van totaal"]]
    for _, r in cat.iterrows():
        cat_data.append([str(r["Categorie"]), int0(r["Transacties"]), eur0(r["Bedrag"]), pct1(r["Aandeel_totaal_pct"])])
    story.append(tbl(cat_data, [5.7*cm, 2.7*cm, 3.8*cm, 3.8*cm], styles))
    if "category_amounts" in charts:
        story += [Spacer(1, 0.2*cm), Image(str(charts["category_amounts"]), width=16.6*cm, height=8.1*cm)]
    if "category_counts" in charts:
        story += [Spacer(1, 0.15*cm), Image(str(charts["category_counts"]), width=16.6*cm, height=8.1*cm)]
    story.append(PageBreak())

    story.append(Paragraph("3. Dashboard per jaar", styles["Sec"]))
    dash_data = [["Jaar", "Totale inkomsten", "Directe bank", "Periodiek", "Belgie", "Overig niet-herleidbaar", "Unieke bankdonateurs"]]
    for _, r in yearly.iterrows():
        dash_data.append([
            str(int(r["Jaar"])),
            eur0(r["Totale_inkomsten"]),
            eur0(r["Directe_bankdonaties"]),
            eur0(r["Periodieke_donaties"]),
            eur0(r["Belgische_donaties"]),
            eur0(r["Anonieme_donaties"]),
            int0(r["Unieke_bankdonateurs"]),
        ])
    story.append(tbl(dash_data, [1.3*cm, 2.5*cm, 2.4*cm, 2.1*cm, 1.8*cm, 3.1*cm, 3.0*cm], styles))
    if "income_year" in charts:
        story += [Spacer(1, 0.2*cm), Image(str(charts["income_year"]), width=16.6*cm, height=8.1*cm)]
    if "bankdonateurs_year" in charts:
        story += [Spacer(1, 0.15*cm), Image(str(charts["bankdonateurs_year"]), width=16.6*cm, height=8.1*cm)]
    story.append(PageBreak())

    story.append(Paragraph("4. Nieuwe donateurs en behoud", styles["Sec"]))
    nd_data = [["Jaar", "Nieuwe donateurs sinds start dataset"]]
    for _, r in new_donateurs.iterrows():
        nd_data.append([str(int(r["Jaar"])), int0(r["Nieuwe donateurs sinds start dataset"])])
    story.append(tbl(nd_data, [5.5*cm, 5.2*cm], styles))
    if "new_donateurs_year" in charts:
        story += [Spacer(1, 0.2*cm), Image(str(charts["new_donateurs_year"]), width=16.6*cm, height=8.1*cm)]
    nvr_data = [["Jaar", "Nieuwe", "Terugkerende", "Totaal unieke", "Aandeel nieuw"]]
    for _, r in new_vs_returning.iterrows():
        nvr_data.append([str(int(r["Jaar"])), int0(r["Nieuwe_donateurs"]), int0(r["Terugkerende_donateurs"]), int0(r["Totaal_unieke_donateurs"]), pct1(r["Aandeel_nieuw_pct"])])
    story += [Spacer(1, 0.2*cm), tbl(nvr_data, [1.6*cm, 2.5*cm, 3.2*cm, 3.2*cm, 3.0*cm], styles)]
    if "new_vs_returning" in charts:
        story += [Spacer(1, 0.2*cm), Image(str(charts["new_vs_returning"]), width=16.6*cm, height=8.1*cm)]
    story.append(PageBreak())

    story.append(Paragraph("5. Retentie en cohort-analyse", styles["Sec"]))
    yoy_data = [["Van jaar", "Naar jaar", "Donateurs startjaar", "Ook actief volgend jaar", "Retentie %"]]
    for _, r in yoy.iterrows():
        yoy_data.append([
            str(int(r["Van_jaar"])),
            str(int(r["Naar_jaar"])),
            int0(r["Donateurs_startjaar"]),
            int0(r["Ook_actief_volgend_jaar"]),
            pct1(r["Retentie_pct"]),
        ])
    story.append(tbl(yoy_data, [1.9*cm, 1.9*cm, 4.1*cm, 4.2*cm, 2.6*cm], styles))
    if "yoy_retention" in charts:
        story += [Spacer(1, 0.2*cm), Image(str(charts["yoy_retention"]), width=16.6*cm, height=8.1*cm)]

    story += [Spacer(1, 0.25*cm)]
    cohort_data = [["Cohortjaar", "Doeljaar", "Aantal in cohort", "Teruggekeerd", "Retentie %"]]
    for _, r in cohort.iterrows():
        cohort_data.append([
            str(int(r["Cohortjaar"])),
            str(int(r["Doeljaar"])),
            int0(r["Aantal_donateurs_in_cohort"]),
            int0(r["Teruggekeerd"]),
            pct1(r["Retentie_pct"]),
        ])
    story.append(tbl(cohort_data, [2.0*cm, 2.0*cm, 3.6*cm, 3.0*cm, 3.0*cm], styles))
    story.append(Paragraph(
        "Cohortanalyse laat zien welk deel van een cohort in latere jaren opnieuw doneert. Daarmee wordt zichtbaar of donateurs slechts eenmalig geven of ook op langere termijn terugkeren.",
        styles["BodyPro"]
    ))
    story.append(PageBreak())

    story.append(Paragraph("6. Pareto-analyse en topdonateurs", styles["Sec"]))
    ps_data = [["Segment", "Aantal donateurs", "Bedrag", "Aandeel inkomsten"]]
    for _, r in pareto_summary.iterrows():
        ps_data.append([r["Segment"], int0(r["Aantal_donateurs"]), eur0(r["Bedrag"]), pct1(r["Aandeel_inkomsten_pct"])])
    story.append(tbl(ps_data, [3.5*cm, 3.6*cm, 4.4*cm, 4.5*cm], styles))
    if "pareto" in charts:
        story += [Spacer(1, 0.2*cm), Image(str(charts["pareto"]), width=16.6*cm, height=8.1*cm)]
    top_data = [["Donateur_ID", "Totaal bedrag", "Transacties"]]
    for _, r in top_all.iterrows():
        top_data.append([str(r["Donateur_ID"]), eur0(r["Totaal_bedrag"]), int0(r["Transacties"])])
    story += [Spacer(1, 0.2*cm), tbl(top_data, [6.0*cm, 4.2*cm, 3.2*cm], styles)]
    story.append(PageBreak())

    story.append(Paragraph("7. Periodieke donaties", styles["Sec"]))
    py_data = [["Jaar", "Payouts", "Bedrag", "Groei t.o.v. vorig jaar"]]
    for _, r in periodic_year.iterrows():
        growth = "" if pd.isna(r["Groei_tov_vorig_jaar_pct"]) else pct1(r["Groei_tov_vorig_jaar_pct"])
        py_data.append([str(int(r["Jaar"])), int0(r["Payouts"]), eur0(r["Bedrag"]), growth])
    story.append(tbl(py_data, [2.0*cm, 3.0*cm, 4.0*cm, 4.8*cm], styles))
    if "periodic_year" in charts:
        story += [Spacer(1, 0.2*cm), Image(str(charts["periodic_year"]), width=16.6*cm, height=8.1*cm)]
    if "periodic_growth" in charts:
        story += [Spacer(1, 0.15*cm), Image(str(charts["periodic_growth"]), width=16.6*cm, height=8.1*cm)]
    story.append(PageBreak())

    story.append(Paragraph("8. Donateur lifecycle en uitstroom", styles["Sec"]))
    exit_data = [["Laatste actieve jaar", "Aantal donateurs", "Totaal bedrag", "Gemiddeld bedrag", "Totaal transacties"]]
    for _, r in exit_summary.iterrows():
        exit_data.append([
            str(int(r["Laatste actieve jaar"])),
            int0(r["Aantal donateurs"]),
            eur0(r["Totaal bedrag van deze groep"]),
            eur0(r["Gemiddeld bedrag per donateur"]),
            int0(r["Totaal transacties van deze groep"]),
        ])
    story.append(tbl(exit_data, [2.4*cm, 2.8*cm, 3.6*cm, 3.4*cm, 3.4*cm], styles))
    if "exit_count" in charts:
        story += [Spacer(1, 0.2*cm), Image(str(charts["exit_count"]), width=16.6*cm, height=8.1*cm)]
    if "exit_amount" in charts:
        story += [Spacer(1, 0.15*cm), Image(str(charts["exit_amount"]), width=16.6*cm, height=8.1*cm)]
    story.append(PageBreak())

    story.append(Paragraph("9. Risicoanalyse en strategische prioriteiten", styles["Sec"]))
    risk_data = [
        ["Thema", "Risico / kans", "Bestuurlijke reactie"],
        ["Concentratierisico", "Een kleine groep donateurs draagt een groot deel van de inkomsten.", "Topdonateurs actief volgen en relatie-opbouw organiseren."],
        ["Periodieke donaties", "Periodieke donaties zijn nu al relevant, maar hebben nog duidelijke groeipotentie.", "Bestaande donateurs gericht converteren naar maandelijkse steun."],
        ["Nieuwe donateurs", "Instroom bepaalt of de basis groeit of langzaam vergrijst.", "Nieuwe donateurs per jaar als vaste KPI opnemen."],
        ["Retentie", "Zonder terugkeer blijft groei duur en fragiel.", "Cohort-retentie en jaar-op-jaar retentie structureel monitoren."],
        ["Middengroep", "De middengroep bevat vaak het grootste verborgen groeipotentieel.", "Segmenteren op totaalbedrag en gericht ontwikkelen."],
    ]
    story.append(tbl(risk_data, [3.4*cm, 6.2*cm, 6.2*cm], styles, header_bg="#F3F4F6"))
    story.append(PageBreak())

    story.append(Paragraph("10. Belangrijkste conclusies", styles["Sec"]))
    conclusions = [
        f"• De organisatie ontving in totaal {eur0(total_income)} aan donaties over {int0(total_tx)} transacties.",
        f"• De kern van het donateurbeeld bestaat uit {int0(unique_bank)} unieke bankdonateurs en {int0(bank_tx)} retentie-geschikte transacties.",
        "• Directe bankdonaties vormen de grootste pijler; periodieke donaties vormen de tweede stabiele pijler.",
        "• Cohortanalyse en jaar-op-jaar retentie moeten samen gelezen worden om de werkelijke stabiliteit van de donateurbasis te beoordelen.",
        "• De strategische prioriteiten zijn helder: topgroep behouden, periodieke donaties vergroten en de middengroep actiever ontwikkelen.",
    ]
    for c in conclusions:
        story.append(Paragraph(c, styles["BodyPro"]))

    doc.build(story)


def main():
    if len(sys.argv) < 2:
        print("Gebruik: python run_donateur_intelligence_secure.py data/raw/bestand.csv")
        sys.exit(1)

    input_csv = Path(sys.argv[1])
    if not input_csv.exists():
        print(f"Bestand niet gevonden: {input_csv}")
        sys.exit(1)

    output_dir = DEFAULT_OUTPUT_DIR
    ensure_output_dir(output_dir)

    public_df, mapping = ingest_clean(input_csv)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    public_excel = output_dir / f"donateur_intelligence_secure_{timestamp}.xlsx"
    internal_mapping = output_dir / f"donateur_id_mapping_internal_{timestamp}.xlsx"
    pdf_path = output_dir / f"bestuursrapport_donaties_secure_{timestamp}.pdf"

    write_excel(public_df, mapping, public_excel, internal_mapping)
    charts = build_charts(public_df, output_dir)
    write_pdf(public_df, pdf_path, charts)

    print("Klaar.")
    print(f"Publieke Excel: {public_excel}")
    print(f"Interne mapping Excel: {internal_mapping}")
    print(f"PDF: {pdf_path}")

if __name__ == "__main__":
    main()
