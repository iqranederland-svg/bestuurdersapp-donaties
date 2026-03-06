from pathlib import Path
import datetime
import shutil
import subprocess
import sys

import pandas as pd

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def eur(x):
    try:
        return "€ " + f"{int(round(float(x))):,}".replace(",", ".")
    except Exception:
        return str(x)


def i0(x):
    try:
        return f"{int(round(float(x))):,}".replace(",", ".")
    except Exception:
        return str(x)


def pct(x):
    try:
        return f"{float(x):.1f}%".replace(".", ",")
    except Exception:
        return str(x)


def yearstr(x):
    try:
        return str(int(round(float(x))))
    except Exception:
        return str(x)


def newest(pattern):
    files = sorted(OUTPUT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def tbl(data, col_widths, header_bg="#EAF0F8"):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F2747")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#C7D2E1")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def run_secure_engine(csv_path):
    result = subprocess.run(
        [sys.executable, "run_donateur_intelligence_secure.py", csv_path],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "Secure engine faalde")
    return result.stdout


def load_secure_book(xlsx_path):
    return {
        "dashboard": pd.read_excel(xlsx_path, "01 Dashboard per jaar"),
        "categories": pd.read_excel(xlsx_path, "02 Categorie overzicht"),
        "donors": pd.read_excel(xlsx_path, "03 Donateursbasis"),
        "new": pd.read_excel(xlsx_path, "04 Nieuwe donateurs"),
        "new_returning": pd.read_excel(xlsx_path, "05 Nieuw vs terugkerend"),
        "cohort": pd.read_excel(xlsx_path, "06 Cohort lang"),
        "retention": pd.read_excel(xlsx_path, "07 Jaar-op-jaar retentie"),
        "pareto": pd.read_excel(xlsx_path, "08 Pareto"),
        "top": pd.read_excel(xlsx_path, "09 Top alle jaren"),
        "periodic": pd.read_excel(xlsx_path, "10 Periodiek per jaar"),
        "lifecycle": pd.read_excel(xlsx_path, "11 Donateur lifecycle"),
        "exit": pd.read_excel(xlsx_path, "12 Uitstroom samenvatting"),
        "transactions": pd.read_excel(xlsx_path, "99 Publieke transacties"),
    }


def split_closed_running_years(df):
    years = sorted(df["Jaar"].dropna().astype(int).unique().tolist())
    if not years:
        return df.copy(), df.copy(), None
    running_year = max(years)
    closed = df[df["Jaar"].astype(int) < running_year].copy()
    running = df[df["Jaar"].astype(int) == running_year].copy()
    return closed, running, running_year


def add_active_flag(lifecycle, current_year):
    out = lifecycle.copy()
    if current_year is None or "Laatste_jaar" not in out.columns:
        out["Actieve donateur"] = "Nee"
        return out

    out["Actieve donateur"] = out["Laatste_jaar"].apply(
        lambda x: "Ja" if pd.notna(x) and int(round(float(x))) == current_year else "Nee"
    )
    return out


def build_management_pdf(book, pdf_path):
    dash = book["dashboard"].copy().sort_values("Jaar")
    cats = book["categories"].copy()
    donor_stats = book["donors"].copy()
    new_df = book["new"].copy().sort_values("Jaar")
    nr_df = book["new_returning"].copy().sort_values("Jaar")
    retention = book["retention"].copy().sort_values("Van_jaar")
    cohort = book["cohort"].copy().sort_values(["Cohortjaar", "Doeljaar"])
    pareto = book["pareto"].copy()
    periodic = book["periodic"].copy().sort_values("Jaar")
    exit_df = book["exit"].copy().sort_values("Laatste actieve jaar")
    lifecycle = book["lifecycle"].copy()

    closed_dash, running_dash, running_year = split_closed_running_years(dash)
    lifecycle = add_active_flag(lifecycle, running_year)

    total_income = float(dash["Totale_inkomsten"].sum()) if len(dash) else 0.0
    total_tx = int(dash["Totaal_transacties"].sum()) if len(dash) else 0

    donor_count = 0
    hit = donor_stats.loc[donor_stats["KPI"] == "Unieke bankdonateurs", "Waarde"]
    if len(hit):
        donor_count = int(hit.iloc[0])

    dragers_total = 0.0
    if len(periodic) and "Bedrag" in periodic.columns:
        dragers_total = float(periodic["Bedrag"].sum())

    top10_pct = 0.0
    top10_amount = 0.0
    top10_count = 0
    top10 = pareto.loc[pareto["Segment"] == "Top 10%"]
    if len(top10):
        top10_pct = float(top10["Aandeel_inkomsten_pct"].iloc[0])
        top10_amount = float(top10["Bedrag"].iloc[0])
        top10_count = int(top10["Aantal_donateurs"].iloc[0])

    impact_year = None
    impact_count = 0
    impact_amount = 0.0
    if len(exit_df):
        impact = exit_df.sort_values(["Totaal bedrag van deze groep", "Aantal donateurs"], ascending=False).iloc[0]
        impact_year = int(impact["Laatste actieve jaar"])
        impact_count = int(impact["Aantal donateurs"])
        impact_amount = float(impact["Totaal bedrag van deze groep"])

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleBlue", parent=styles["Title"], fontSize=24, leading=28, textColor=colors.HexColor("#0F2747"), alignment=TA_LEFT, spaceAfter=8))
    styles.add(ParagraphStyle(name="Subtle", parent=styles["Normal"], fontSize=10.5, leading=14, textColor=colors.HexColor("#4B5563"), spaceAfter=6))
    styles.add(ParagraphStyle(name="Sec", parent=styles["Heading1"], fontSize=16, leading=20, textColor=colors.HexColor("#0F2747"), spaceAfter=8))
    styles.add(ParagraphStyle(name="BodyPro", parent=styles["BodyText"], fontSize=10.2, leading=14, textColor=colors.HexColor("#1F2937"), spaceAfter=6))

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=1.4 * cm,
        rightMargin=1.4 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.1 * cm,
    )

    story = []

    story.append(Paragraph("Bestuursrapport donaties v5", styles["TitleBlue"]))
    story.append(Paragraph("Privacy-veilige managementeditie. Geen namen en geen IBAN. Identificatie verloopt uitsluitend via Donateur_ID in interne processen.", styles["Subtle"]))
    story.append(Spacer(1, 0.2 * cm))

    cover_data = [
        ["KPI", "Waarde", "KPI", "Waarde"],
        ["Totale donaties", eur(total_income), "Totaal transacties", i0(total_tx)],
        ["Aantal donateurs", i0(donor_count), "Dragers donaties", eur(dragers_total)],
        ["Top 10% aandeel", pct(top10_pct), "Top 10% bedrag", eur(top10_amount)],
    ]
    story.append(tbl(cover_data, [5.0 * cm, 3.2 * cm, 5.0 * cm, 3.2 * cm]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(PageBreak())

    story.append(Paragraph("1. Executive summary", styles["Sec"]))
    story.append(Paragraph(
        "De organisatie ontving in totaal " + eur(total_income) + " aan donaties over " + i0(total_tx) + " transacties. "
        "De direct identificeerbare donateurbasis bestaat uit " + i0(donor_count) + " donateurs. "
        "Dragers donaties vertegenwoordigen in totaal " + eur(dragers_total) + " en vormen de structurele inkomstenlaag.",
        styles["BodyPro"],
    ))
    story.append(Paragraph(
        i0(top10_count) + " donateurs doneerden gezamenlijk " + eur(top10_amount) + ". "
        "Dit vertegenwoordigt " + pct(top10_pct) + " van alle directe bankdonaties. "
        "Dit toont het strategische belang van relatiebeheer met deze kerngroep donateurs.",
        styles["BodyPro"],
    ))
    if running_year is not None:
        story.append(Paragraph(
            "Let op: het meest recente jaar " + str(running_year) + " is nog niet volledig afgerond. "
            "Vergelijkingen met eerdere jaren kunnen daarom een vertekend beeld geven. "
            "Uitstroom in relatie tot het lopende jaar moet voorzichtig worden geïnterpreteerd.",
            styles["BodyPro"],
        ))

    story.append(PageBreak())

    story.append(Paragraph("2. Jaaroverzicht", styles["Sec"]))
    y = dash.copy()
    y["Overige donaties"] = y["Belgische_donaties"] + y["Anonieme_donaties"]
    year_data = [["Jaar", "Totale inkomsten", "Eenmalige donaties", "Dragers donaties", "Overige donaties", "Aantal donateurs", "Totaal transacties"]]
    for _, r in y.iterrows():
        year_data.append([
            yearstr(r["Jaar"]),
            eur(r["Totale_inkomsten"]),
            eur(r["Directe_bankdonaties"]),
            eur(r["Periodieke_donaties"]),
            eur(r["Overige donaties"]),
            i0(r["Unieke_bankdonateurs"]),
            i0(r["Totaal_transacties"]),
        ])
    story.append(tbl(year_data, [1.4 * cm, 2.7 * cm, 2.7 * cm, 2.5 * cm, 2.5 * cm, 2.4 * cm, 2.4 * cm]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "Overige donaties bestaan uit niet individueel herleidbare stromen, waaronder Sepay, Belgische donateurs en anonieme donateurs.",
        styles["BodyPro"],
    ))

    if running_year is not None and len(running_dash):
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph("Lopend jaar", styles["Sec"]))
        rr = running_dash.iloc[0]
        story.append(Paragraph(
            "Voorlopige stand " + str(int(rr["Jaar"])) + ": "
            + eur(rr["Totale_inkomsten"]) + ", "
            + i0(rr["Unieke_bankdonateurs"]) + " donateurs en "
            + i0(rr["Totaal_transacties"]) + " transacties. "
            "Dit jaar is nog niet afgesloten en kan later nog oplopen.",
            styles["BodyPro"],
        ))

    story.append(PageBreak())

    story.append(Paragraph("3. Donateursbasis", styles["Sec"]))
    new_data = [["Jaar", "Nieuwe donateurs sinds start dataset"]]
    for _, r in new_df.iterrows():
        new_data.append([yearstr(r["Jaar"]), i0(r["Nieuwe donateurs sinds start dataset"])])
    story.append(tbl(new_data, [2.0 * cm, 6.4 * cm]))

    story.append(Spacer(1, 0.2 * cm))
    nr_data = [["Jaar", "Nieuwe", "Terugkerende", "Totaal unieke", "Aandeel nieuw"]]
    for _, r in nr_df.iterrows():
        nr_data.append([
            yearstr(r["Jaar"]),
            i0(r["Nieuwe_donateurs"]),
            i0(r["Terugkerende_donateurs"]),
            i0(r["Totaal_unieke_donateurs"]),
            pct(r["Aandeel_nieuw_pct"]),
        ])
    story.append(tbl(nr_data, [1.6 * cm, 2.4 * cm, 3.0 * cm, 3.0 * cm, 2.6 * cm]))
    story.append(Paragraph(
        "Deze tabellen laten zien in hoeverre de donateurbasis groeit door nieuwe instroom en in hoeverre groei voortkomt uit terugkerende relaties.",
        styles["BodyPro"],
    ))

    story.append(PageBreak())

    story.append(Paragraph("4. Retentie", styles["Sec"]))
    ret_data = [["Van jaar", "Naar jaar", "Donateurs startjaar", "Ook actief volgend jaar", "Retentie"]]
    for _, r in retention.iterrows():
        ret_data.append([
            yearstr(r["Van_jaar"]),
            yearstr(r["Naar_jaar"]),
            i0(r["Donateurs_startjaar"]),
            i0(r["Ook_actief_volgend_jaar"]),
            pct(r["Retentie_pct"]),
        ])
    story.append(tbl(ret_data, [1.8 * cm, 1.8 * cm, 3.8 * cm, 4.0 * cm, 2.2 * cm]))
    story.append(Paragraph(
        "Jaar-op-jaar retentie laat zien welk deel van de donateurs uit een startjaar ook in het volgende jaar opnieuw actief is. Dit is de kernmaat voor jaarlijks behoud.",
        styles["BodyPro"],
    ))

    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph("Cohortanalyse", styles["Sec"]))
    story.append(Paragraph(
        "Een cohort is de groep donateurs die in een bepaald startjaar actief was. Per cohortjaar wordt hieronder zichtbaar welk deel in latere jaren terugkeert.",
        styles["BodyPro"],
    ))
    cohort_years = sorted(cohort["Cohortjaar"].dropna().astype(int).unique().tolist()) if len(cohort) else []
    for cy in cohort_years:
        subset = cohort[cohort["Cohortjaar"].astype(int) == cy].copy().sort_values("Doeljaar")
        c_data = [["Cohortjaar", "Doeljaar", "Aantal in cohort", "Teruggekeerd", "Retentie"]]
        for _, r in subset.iterrows():
            c_data.append([
                yearstr(r["Cohortjaar"]),
                yearstr(r["Doeljaar"]),
                i0(r["Aantal_donateurs_in_cohort"]),
                i0(r["Teruggekeerd"]),
                pct(r["Retentie_pct"]),
            ])
        story.append(Paragraph("Cohortjaar " + str(cy), styles["BodyPro"]))
        story.append(tbl(c_data, [2.0 * cm, 2.0 * cm, 3.4 * cm, 3.0 * cm, 2.6 * cm]))
        story.append(Spacer(1, 0.15 * cm))

    story.append(PageBreak())

    story.append(Paragraph("5. Dragers donaties", styles["Sec"]))
    p_data = [["Jaar", "Payouts", "Dragers donaties", "Groei t.o.v. vorig jaar"]]
    for _, r in periodic.iterrows():
        growth = "" if pd.isna(r.get("Groei_tov_vorig_jaar_pct")) else pct(r["Groei_tov_vorig_jaar_pct"])
        p_data.append([
            yearstr(r["Jaar"]),
            i0(r["Payouts"]),
            eur(r["Bedrag"]),
            growth,
        ])
    story.append(tbl(p_data, [1.8 * cm, 2.4 * cm, 3.6 * cm, 4.2 * cm]))
    story.append(Paragraph(
        "Dragers donaties vormen de stabiele inkomstenlaag. Groei in deze groep vergroot de voorspelbaarheid en stabiliteit van inkomsten.",
        styles["BodyPro"],
    ))

    story.append(PageBreak())

    story.append(Paragraph("6. Inkomstenstructuur en concentratie", styles["Sec"]))
    cat_data = [["Categorie", "Transacties", "Bedrag", "Aandeel van totaal"]]
    for _, r in cats.iterrows():
        cat_data.append([
            str(r["Categorie"]),
            i0(r["Transacties"]),
            eur(r["Bedrag"]),
            pct(r["Aandeel_totaal_pct"]),
        ])
    story.append(tbl(cat_data, [5.0 * cm, 2.5 * cm, 3.6 * cm, 3.2 * cm]))

    story.append(Spacer(1, 0.2 * cm))
    pareto_data = [["Segment", "Aantal donateurs", "Bedrag", "Aandeel inkomsten"]]
    for _, r in pareto.iterrows():
        pareto_data.append([
            str(r["Segment"]),
            i0(r["Aantal_donateurs"]),
            eur(r["Bedrag"]),
            pct(r["Aandeel_inkomsten_pct"]),
        ])
    story.append(tbl(pareto_data, [3.0 * cm, 3.0 * cm, 4.0 * cm, 3.5 * cm]))
    story.append(Paragraph(
        "De inkomstenstructuur is geconcentreerd: een relatief kleine groep donateurs vertegenwoordigt een groot deel van de donatiewaarde. Dit vraagt om relatiebeheer met de topgroep én ontwikkeling van de bredere basis.",
        styles["BodyPro"],
    ))

    story.append(PageBreak())

    story.append(Paragraph("7. Uitstroom en lifecycle", styles["Sec"]))
    story.append(Paragraph(
        "Uitstroom wordt hieronder gescheiden naar laatste actieve jaar. Voor afgesloten jaren geeft dit een betrouwbaarder beeld van structurele uitstroom. Voor het meest recente niet-afgesloten opvolgjaar moet voorzichtigheid worden betracht.",
        styles["BodyPro"],
    ))

    exit_data = [["Laatste actieve jaar", "Aantal donateurs", "Historische donatiewaarde", "Totaal transacties"]]
    for _, r in exit_df.iterrows():
        exit_data.append([
            yearstr(r["Laatste actieve jaar"]),
            i0(r["Aantal donateurs"]),
            eur(r["Totaal bedrag van deze groep"]),
            i0(r["Totaal transacties van deze groep"]),
        ])
    story.append(tbl(exit_data, [2.5 * cm, 3.0 * cm, 4.2 * cm, 3.4 * cm]))

    lc = lifecycle.copy()
    lc = add_active_flag(lc, running_year)
    lc_short = lc[["Donateur_ID", "Eerste_jaar", "Laatste_jaar", "Actieve donateur", "Transacties", "Totaal_bedrag"]].copy().head(20)
    lc_data = [["Donateur_ID", "Eerste jaar", "Laatste jaar", "Actief", "Transacties", "Totaal bedrag"]]
    for _, r in lc_short.iterrows():
        lc_data.append([
            str(r["Donateur_ID"]),
            yearstr(r["Eerste_jaar"]),
            yearstr(r["Laatste_jaar"]),
            str(r["Actieve donateur"]),
            i0(r["Transacties"]),
            eur(r["Totaal_bedrag"]),
        ])
    story.append(Spacer(1, 0.2 * cm))
    story.append(tbl(lc_data, [3.0 * cm, 2.0 * cm, 2.0 * cm, 2.1 * cm, 2.4 * cm, 3.1 * cm]))

    story.append(PageBreak())

    story.append(Paragraph("8. Bestuurlijke duiding en prioriteiten", styles["Sec"]))
    priorities = [
        "1. Bescherm de topgroep: een beperkt aantal donateurs vertegenwoordigt een groot deel van de waarde.",
        "2. Vergroot dragers donaties: dit vergroot de voorspelbaarheid en stabiliteit van inkomsten.",
        "3. Verbeter retentie na de eerste donatie: groei wordt duurder als donateurs niet terugkomen.",
        "4. Activeer slapende donateurs opnieuw: heractivatie is vaak goedkoper dan nieuwe werving.",
        "5. Laat de middengroep doorgroeien: hier zit vaak het grootste verborgen groeipotentieel.",
    ]
    for line in priorities:
        story.append(Paragraph(line, styles["BodyPro"]))

    doc.build(story)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Gebruik: python run_donateur_intelligence_v5.py <csv-bestand>")

    csv_path = sys.argv[1]

    stdout = run_secure_engine(csv_path)

    secure_xlsx = newest("donateur_intelligence_secure_*.xlsx")
    secure_pdf = newest("bestuursrapport_donaties_secure_*.pdf")

    if secure_xlsx is None:
        raise RuntimeError("Geen secure Excel gevonden na draaien van secure engine")

    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    v5_xlsx = OUTPUT_DIR / f"donateur_intelligence_v5_{now}.xlsx"
    shutil.copy2(secure_xlsx, v5_xlsx)

    v5_pdf = OUTPUT_DIR / f"bestuursrapport_donaties_v5_{now}.pdf"
    book = load_secure_book(secure_xlsx)
    build_management_pdf(book, v5_pdf)

    print(stdout.strip())
    print("Klaar V5.")
    print("Publieke Excel:", v5_xlsx)
    print("PDF:", v5_pdf)
    if secure_pdf is not None:
        print("Bron secure PDF:", secure_pdf)


if __name__ == "__main__":
    main()
