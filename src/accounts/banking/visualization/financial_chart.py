import json
import uuid
from pathlib import Path

import pandas as pd
from jinja2 import Template

from accounts.banking.database.banking_db import BankingDB
from config import load_config


def generate_all_reports(banking_db: BankingDB, bank_account_id: int, bank_account_name: str) -> None:
    """Génère les rapports financiers annuels et le bilan global pour un compte bancaire donné."""
    destination_path = Path(load_config()["destination_path"])
    root_path = destination_path / "bank_account" / bank_account_name
    root_path.mkdir(parents=True, exist_ok=True)

    years_data = banking_db.get_categorized_operations_by_year(bank_account_id)

    all_years_incomes = []
    all_years_expenses = []
    all_years_combined = []

    for year, data in years_data.items():
        output_file = root_path / f"Bilan {year}.html"
        generate_bank_report(
            banking_db=banking_db,
            incomes_df=data["incomes"],
            expenses_df=data["expenses"],
            incomes_expenses_df=data["all"],
            output_path=output_file,
        )

        all_years_incomes.append(data["incomes"])
        all_years_expenses.append(data["expenses"])
        all_years_combined.append(data["all"])

    # Bilan Global sur l'ensemble des années disponibles
    if years_data:
        sorted_years = sorted(years_data.keys())
        output_file = root_path / f"Bilan {sorted_years[0]}-{sorted_years[-1]}.html"
        generate_bank_report(
            banking_db=banking_db,
            incomes_df=pd.concat(all_years_incomes),
            expenses_df=pd.concat(all_years_expenses),
            incomes_expenses_df=pd.concat(all_years_combined),
            output_path=output_file,
        )


def generate_bank_report(
    banking_db: BankingDB,
    incomes_df: pd.DataFrame,
    expenses_df: pd.DataFrame,
    incomes_expenses_df: pd.DataFrame,
    output_path: str | Path,
    embed_js: bool = True,
) -> None:
    """Génère et sauvegarde un rapport financier HTML complet pour un ensemble de données."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    incomes_empty = incomes_df.empty
    expenses_empty = expenses_df.empty
    incomes_or_expenses_empty = incomes_empty or expenses_empty

    # Traitement des données JS / Highcharts
    incomes_categories, expenses_categories = banking_db.get_category_lists()

    json_data_bar = prepare_bar_chart_json(incomes_expenses_df)
    json_data_evolution = _prepare_evolution_chart_json(incomes_expenses_df, incomes_categories, expenses_categories)
    json_data_sankey = prepare_sankey_json(incomes_expenses_df)
    json_data_sunburst = prepare_sunburst_json(incomes_df, expenses_df)

    years = sorted(incomes_expenses_df["year"].unique().tolist(), reverse=True) if not incomes_expenses_df.empty else []

    # Inlining du code JS si demandé
    highcharts_js_content = ""
    if embed_js:
        js_dir = Path("src/static/js")
        js_files = ["highcharts.js", "sunburst.js", "sankey.js", "exporting.js"]
        for js_file in js_files:
            file_path = js_dir / js_file
            if file_path.exists():
                highcharts_js_content += f"\n/* --- {js_file} --- */\n" + file_path.read_text(encoding="utf-8")

    # Compilation Jinja2
    template_path = Path("src/static/template/bank.html")
    template = Template(template_path.read_text(encoding="utf-8"))

    rendered_html = template.render(
        report_title="Bilan Financier",
        graph_id=uuid.uuid4().hex[:8],
        has_only_incomes_or_expenses=incomes_or_expenses_empty,
        data_global_json=json_data_bar,
        data_evolution_json=json_data_evolution,
        sankey_data_json=json_data_sankey,
        sunburst_data_json=json_data_sunburst,
        incomes_list_json=json.dumps(incomes_categories, ensure_ascii=False),
        years_json=json.dumps(years),
        sankey_years=years,
        multiple_years=len(years) > 1,
        embed_js=embed_js,
        highcharts_js=highcharts_js_content,
    )

    output_file.write_text(rendered_html, encoding="utf-8")


def prepare_bar_chart_json(incomes_expenses_df: pd.DataFrame) -> str:
    """Prépare la structure JSON pour le graphique en barres comparatif."""
    df = incomes_expenses_df.copy()
    df["operation_date"] = pd.to_datetime(df["operation_date"])
    df["year"] = df["operation_date"].dt.year

    data_dict = {}
    for cat, cat_df in df.groupby("category"):
        data_dict[cat] = {}
        for sub_cat, sub_df in cat_df.groupby("sub_category"):
            data_dict[cat][sub_cat] = {}
            for year, year_df in sub_df.groupby("year"):
                monthly = (
                    year_df.groupby(year_df["operation_date"].dt.month)["amount"]
                    .sum()
                    .abs()
                    .reindex(range(1, 13), fill_value=0)
                    .tolist()
                )
                data_dict[cat][sub_cat][int(year)] = [round(m, 2) for m in monthly]

    return json.dumps(data_dict, ensure_ascii=False)


def _prepare_evolution_chart_json(
    incomes_expenses_df: pd.DataFrame, incomes_list: list[str], expenses_list: list[str]
) -> str:
    """Prépare la structure JSON pour le graphique d'évolution des flux."""
    df = incomes_expenses_df.copy()
    df["operation_date"] = pd.to_datetime(df["operation_date"])
    df["year"] = df["operation_date"].dt.year
    df["month"] = df["operation_date"].dt.month

    years = sorted(df["year"].unique().tolist())

    incomes_df = df[df["category"].isin(incomes_list)]
    expenses_df = df[df["category"].isin(expenses_list)]

    def build_nested_structure(target_df: pd.DataFrame) -> dict:
        result = {}
        for cat, cat_df in target_df.groupby("category"):
            result[cat] = {}
            for sub, sub_df in cat_df.groupby("sub_category"):
                result[cat][sub] = {}
                for y in years:
                    monthly = (
                        sub_df[sub_df["year"] == y]
                        .groupby("month")["amount"]
                        .sum()
                        .abs()
                        .reindex(range(1, 13), fill_value=0)
                        .tolist()
                    )
                    result[cat][sub][y] = [round(v, 2) for v in monthly]
        return result

    datasets = {
        "Revenus": build_nested_structure(incomes_df),
        "Depenses": build_nested_structure(expenses_df),
    }
    return json.dumps(datasets, ensure_ascii=False)


def prepare_sankey_json(incomes_expenses_df: pd.DataFrame) -> str:
    """Prépare les opérations au format JSON pour le diagramme de Sankey."""
    df_copy = incomes_expenses_df.copy()
    df_copy["operation_date"] = df_copy["operation_date"].astype(str)
    df_copy["amount"] = df_copy["amount"].astype(float)
    df_copy["year"] = df_copy["year"].astype(int)
    return json.dumps(df_copy.to_dict(orient="records"), ensure_ascii=False)


def prepare_sunburst_json(incomes_df: pd.DataFrame, expenses_df: pd.DataFrame) -> str:
    """Prépare la structure de données hiérarchique au format attendu par Highcharts Sunburst."""
    sunburst_data = []

    def process_dataframe(df: pd.DataFrame, root_name: str) -> None:
        if df.empty:
            return

        sunburst_data.append({"id": root_name, "name": root_name, "parent": ""})

        # Trier les catégories par montant total décroissant
        cat_totals = df.groupby("category")["amount"].apply(lambda x: x.abs().sum()).sort_values(ascending=False)

        for cat in cat_totals.index:
            cat_df = df[df["category"] == cat]
            cat_id = f"{root_name}_{cat}"
            sunburst_data.append({"id": cat_id, "name": cat, "parent": root_name})

            # Trier les sous-catégories par montant total décroissant
            sub_totals = (
                cat_df.groupby("sub_category")["amount"].apply(lambda x: x.abs().sum()).sort_values(ascending=False)
            )

            for sub_cat in sub_totals.index:
                sub_df = cat_df[cat_df["sub_category"] == sub_cat]
                sub_cat_id = f"{cat_id}_{sub_cat}"
                total_val = round(float(sub_df["amount"].abs().sum()), 2)
                sunburst_data.append(
                    {
                        "id": sub_cat_id,
                        "name": sub_cat,
                        "parent": cat_id,
                        "value": total_val,
                    }
                )

    process_dataframe(incomes_df, "Revenus")
    process_dataframe(expenses_df, "Dépenses")

    return json.dumps(sunburst_data, ensure_ascii=False)
