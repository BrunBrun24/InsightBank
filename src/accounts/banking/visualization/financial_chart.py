import json
import uuid
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from accounts.banking.database.banking_db import BankingDB
from accounts.stock.database.stock_db import StockDB
from config import load_config


def chart_generate_all_reports(
    banking_db: BankingDB, stock_db: StockDB, root_path: str | Path, bank_account_id: int | None = None
) -> None:
    root_path.mkdir(parents=True, exist_ok=True)
    is_heritage = not bank_account_id is not None

    if not is_heritage:
        currency_symbol = banking_db.get_bank_account_currency_symbol(bank_account_id)
        years_data = banking_db.get_categorized_operations_by_year(bank_account_id, stock_db, is_heritage)
    else:
        currency_symbol = "€" if load_config()["currency"] == "EUR" else "$"
        bank_accounts = banking_db.get_all_bank_account_currencies()
        years_data = banking_db.get_categorized_operations_by_year(bank_accounts, stock_db, is_heritage)

    all_years_incomes = []
    all_years_expenses = []
    all_years_combined = []

    for year, data in years_data.items():
        output_file = root_path / f"{year}.html"
        generate_bank_report(
            banking_db=banking_db,
            incomes_df=data["incomes"],
            expenses_df=data["expenses"],
            incomes_expenses_df=data["all"],
            output_path=output_file,
            currency_symbol=currency_symbol,
        )

        all_years_incomes.append(data["incomes"])
        all_years_expenses.append(data["expenses"])
        all_years_combined.append(data["all"])

    # Bilan Global sur l'ensemble des années disponibles
    if years_data:
        sorted_years = sorted(years_data.keys())
        if not is_heritage:
            output_file = root_path / f"{sorted_years[0]} - {sorted_years[-1]}.html"
        else:
            output_file = root_path / "heritage_bank.html"
        generate_bank_report(
            banking_db=banking_db,
            incomes_df=pd.concat(all_years_incomes),
            expenses_df=pd.concat(all_years_expenses),
            incomes_expenses_df=pd.concat(all_years_combined),
            output_path=output_file,
            currency_symbol=currency_symbol,
        )


def generate_bank_report(
    banking_db: BankingDB,
    incomes_df: pd.DataFrame,
    expenses_df: pd.DataFrame,
    incomes_expenses_df: pd.DataFrame,
    output_path: str | Path,
    currency_symbol: str,
) -> None:
    """Génère et sauvegarde un rapport financier HTML complet pour un ensemble de données."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    incomes_or_expenses_empty = incomes_df.empty or expenses_df.empty

    # Traitement des données JS / Highcharts
    incomes_categories, expenses_categories = banking_db.get_category_lists()
    years = sorted(incomes_expenses_df["year"].unique().tolist(), reverse=True) if not incomes_expenses_df.empty else []

    data = {
        "graph_id": uuid.uuid4().hex[:8],
        "currency_symbol": currency_symbol,
        "json_data_bar": prepare_bar_chart_json(incomes_expenses_df),
        "json_data_evolution": prepare_evolution_chart_json(
            incomes_expenses_df, incomes_categories, expenses_categories
        ),
        "json_data_sankey": prepare_sankey_json(incomes_expenses_df),
        "json_data_sunburst": prepare_sunburst_json(incomes_df, expenses_df),
        "incomes_list_json": json.dumps(incomes_categories, ensure_ascii=False),
        "years_json": json.dumps(years),
        "sankey_years": years,
        "multiple_years": len(years) > 1,
    }

    # Fichiers JavaScript vendor
    static_dir = Path("src/static")
    vendor_dir = static_dir / "vendor"
    bank_dir = static_dir / "bank"

    # Chargement des scripts vendor
    vendor_files = [
        "highcharts.js",
        "sunburst.js",
        "sankey.js",
        "exporting.js",
    ]
    vendor_scripts = "\n".join(
        [(vendor_dir / file).read_text(encoding="utf-8") for file in vendor_files if (vendor_dir / file).exists()]
    )

    # Lecture du CSS et du JS
    bank_css = (bank_dir / "bank.css").read_text(encoding="utf-8")
    bank_js = (bank_dir / "bank.js").read_text(encoding="utf-8")

    # Configuration de Jinja2
    env = Environment(loader=FileSystemLoader(bank_dir))
    template = env.get_template("bank.html")

    # Rendu avec injection inline de toutes les ressources
    html_rendu = template.render(
        vendor_scripts=vendor_scripts,
        bank_css=bank_css,
        bank_js=bank_js,
        has_only_incomes_or_expenses=incomes_or_expenses_empty,
        data=data,
    )

    output_file.write_text(html_rendu, encoding="utf-8")


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


def prepare_evolution_chart_json(
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
