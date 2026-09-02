import os
from pathlib import Path

import pandas as pd
import xlsxwriter

from accounts.bank.database.bank_db import BankDB
from accounts.stock.database.stock_db import StockDB
from config import load_config


def excel_generate_all_reports(
    bank_db: BankDB, stock_db: StockDB, root_path: str | Path, bank_account_id: int | None = None
) -> None:
    is_heritage = not bank_account_id is not None

    if not is_heritage:
        currency_symbol = bank_db.get_bank_account_currency_symbol(bank_account_id)
        df = bank_db.get_categorized_operations_df(bank_account_id)
        if df.empty:
            return
    else:
        target_currency = "€" if load_config()["currency"] == "EUR" else "$"
        bank_accounts = bank_db.get_all_bank_account_currencies()
        all_operations_dfs = []

        for account in bank_accounts:
            acc_id = account["id"]
            acc_currency = account["currency"]

            df = bank_db.get_categorized_operations_df(acc_id)

            if acc_currency != target_currency:
                rates = stock_db.get_currency_conversion_rates(acc_currency, target_currency)

                if not rates.empty:
                    rates_df = rates.reset_index()
                    rates_df.columns = ["operation_date", "rate"]
                    rates_df = rates_df.sort_values("operation_date")

                    # Alignement avec la date la plus proche
                    df = df.sort_values("operation_date")
                    df = pd.merge_asof(df, rates_df, on="operation_date", direction="nearest")

                    df["rate"] = df["rate"].fillna(1.0)
                    df["amount"] = (df["amount"] * df["rate"]).round(2)
                    df = df.drop(columns=["rate"])

            all_operations_dfs.append(df)

        if not all_operations_dfs:
            return {}

        df = pd.concat(all_operations_dfs, ignore_index=True)
        currency_symbol = target_currency

    os.makedirs(root_path, exist_ok=True)
    df["operation_date"] = pd.to_datetime(df["operation_date"])
    years = sorted(df["operation_date"].dt.year.unique())

    if not is_heritage:
        for year in years:
            generate_annual_report(bank_db, df, root_path, [year], currency_symbol, is_heritage, year)

    generate_annual_report(bank_db, df, root_path, years, currency_symbol, is_heritage, None)


def generate_annual_report(
    bank_db: BankDB,
    df: pd.DataFrame,
    root_path: str | Path,
    years_list: list[int],
    currency_symbol: str,
    is_heritage: bool,
    year: int | None = None,
) -> None:
    data_summary = get_monthly_amounts(df, year)
    structure = get_filtered_structure(bank_db, data_summary)

    if not structure:
        return

    if years_list:
        if len(years_list) == 1:
            header_year = str(years_list[0])
        else:
            header_year = f"{min(years_list)} - {max(years_list)}"
    else:
        header_year = str(year) if year is not None else ""

    if not is_heritage:
        if year == None:
            year = header_year
        file_path = os.path.join(root_path, f"{year}.xlsx")
    else:
        file_path = os.path.join(root_path, "heritage_bank.xlsx")

    wb = xlsxwriter.Workbook(file_path)
    ws = wb.add_worksheet("BUDGET PERSONNEL")
    fmt = get_excel_formats(wb, currency_symbol)

    ws.set_column("A:A", 35)
    ws.set_column("B:M", 12)
    ws.set_column("N:N", 3)
    ws.set_column("O:O", 15)
    ws.set_column("P:P", 15)

    ws.merge_range("A1:C1", "BUDGET PERSONNEL", fmt["title"])
    ws.merge_range("O1:P1", header_year, fmt["year_tag"])

    months = [
        "JAN",
        "FÉV",
        "MAR",
        "AVR",
        "MAI",
        "JUIN",
        "JUIL",
        "AOÛ",
        "SEPT",
        "OCT",
        "NOV",
        "DÉC",
        "",
        "TOTAL",
        "RÉPARTITION",
    ]
    for col, month in enumerate(months):
        ws.write(3, col + 1, month, fmt["header_month"])

    row = 4
    sections_totals = {"REVENUS": [], "DÉPENSES": []}
    current_main = ""

    for section in structure:
        if section["type"] == "main":
            current_main = section["name"]
            ws.write(row, 0, section["name"], fmt["main_cat"])
            for col in range(1, 16):
                ws.write(row, col, "", fmt["main_cat"])
            row += 1
        else:
            ws.write(row, 0, section["name"], fmt["sub_cat"])
            for col in range(1, 16):
                ws.write(row, col, "", fmt["sub_cat"])
            row += 1
            start_items_row = row

            for item in section["items"]:
                ws.write(row, 0, item, fmt["item_label"])
                for month_idx in range(1, 13):
                    val = data_summary[
                        (data_summary["sub_category"] == item) & (data_summary["month_idx"] == month_idx)
                    ]["amount"].sum()
                    cell_fmt = fmt["currency_blue"] if month_idx % 2 == 0 else fmt["currency"]
                    ws.write(row, month_idx, val, cell_fmt)

                row_idx = row + 1
                ws.write_formula(row, 14, f"=SUM(B{row_idx}:M{row_idx})", fmt["total_column"])
                row += 1

            ws.write(row, 0, "Total", fmt["total_label"])
            for col in range(1, 15):
                if col == 13:
                    continue

                col_let = xlsxwriter.utility.xl_col_to_name(col)
                ws.write_formula(row, col, f"=SUM({col_let}{start_items_row + 1}:{col_let}{row})", fmt["total_val"])

            if current_main in sections_totals:
                sections_totals[current_main].append(row + 1)
            row += 2

    row += 1
    row_total_recettes = row
    row_total_depenses = row + 1
    row_tresorerie = row + 2

    ws.write(row_total_recettes, 0, "Total des recettes", fmt["item_label"])
    ws.write(row_total_depenses, 0, "Total des dépenses", fmt["item_label"])
    ws.write(row_tresorerie, 0, "Déficit/excédent de trésorerie", fmt["total_label"])

    for col in range(1, 15):
        if col == 13:
            continue

        col_let = xlsxwriter.utility.xl_col_to_name(col)
        rec_f = "+".join([f"{col_let}{r}" for r in sections_totals["REVENUS"]]) if sections_totals["REVENUS"] else "0"
        dep_f = "+".join([f"{col_let}{r}" for r in sections_totals["DÉPENSES"]]) if sections_totals["DÉPENSES"] else "0"

        is_blue_col = col % 2 == 0 and col <= 12

        f_rec = fmt["footer_rec_blue"] if is_blue_col else fmt["footer_rec"]
        ws.write_formula(row_total_recettes, col, f"={rec_f}", f_rec)

        f_dep = fmt["footer_dep_blue"] if is_blue_col else fmt["footer_dep"]
        ws.write_formula(row_total_depenses, col, f"={dep_f}", f_dep)

        ws.write_formula(
            row_tresorerie,
            col,
            f"=({col_let}{row_total_recettes + 1})-({col_let}{row_total_depenses + 1})",
            fmt["total_val"],
        )

    ws.write(row_total_recettes, 13, "", None)
    ws.write(row_total_depenses, 13, "", None)
    ws.write(row_tresorerie, 13, "", None)

    current_main = ""
    row_cursor = 4
    for section in structure:
        if section["type"] == "main":
            current_main = section["name"]
            row_cursor += 1
        else:
            row_cursor += 1
            target_total = f"O{row_total_recettes + 1}" if current_main == "REVENUS" else f"O{row_total_depenses + 1}"

            for _ in section["items"]:
                ws.write_formula(
                    row_cursor,
                    15,
                    f"=IF({target_total}<>0, O{row_cursor + 1}/{target_total}, 0)",
                    fmt["percent_style"],
                )
                row_cursor += 1

            ws.write_formula(
                row_cursor, 15, f"=IF({target_total}<>0, O{row_cursor + 1}/{target_total}, 0)", fmt["percent_bold"]
            )
            row_cursor += 2

    wb.close()


def get_excel_formats(wb: xlsxwriter.Workbook, currency_symbol: str) -> dict:
    """Définit les formats visuels du document Excel."""
    border_thin = {"border": 1, "border_color": "#D3D3D3"}
    return {
        "title": wb.add_format(
            {"font_name": "Arial", "font_size": 24, "bold": True, "align": "center", "valign": "vcenter"}
        ),
        "year_tag": wb.add_format(
            {"bg_color": "#1f77b4", "font_color": "white", "bold": True, "align": "center", "border": 2}
        ),
        "header_month": wb.add_format({"font_color": "#7f7f7f", "align": "right", "font_size": 10, "bottom": 2}),
        "main_cat": wb.add_format(
            {
                "font_color": "#1f77b4",
                "bold": True,
                "font_size": 12,
                "top": 2,
                "top_color": "#1f77b4",
                "bottom": 1,
                "bottom_color": "#1f77b4",
            }
        ),
        "sub_cat": wb.add_format({"font_color": "#1f77b4", "bold": True, "font_size": 10, "bottom": 1}),
        "item_label": wb.add_format({"font_color": "#333333", "font_size": 10, **border_thin}),
        "currency": wb.add_format({"num_format": f"#,##0.00 {currency_symbol}", "font_size": 10, **border_thin}),
        "currency_blue": wb.add_format(
            {"num_format": f"#,##0.00 {currency_symbol}", "bg_color": "#cceeff", "font_size": 10, **border_thin}
        ),
        "total_column": wb.add_format(
            {"num_format": f"#,##0.00 {currency_symbol}", "font_size": 10, "bg_color": "#F9F9F9", **border_thin}
        ),
        "percent_style": wb.add_format(
            {
                "num_format": "0.00%",
                "font_size": 10,
                "align": "center",
                "font_color": "#1f77b4",
                "bg_color": "#F9F9F9",
                "italic": True,
                **border_thin,
            }
        ),
        "percent_bold": wb.add_format(
            {
                "num_format": "0.00%",
                "font_size": 10,
                "align": "center",
                "font_color": "#1f77b4",
                "bg_color": "#F9F9F9",
                "bold": True,
                "italic": True,
                "top": 1,
                "bottom": 2,
            }
        ),
        "total_label": wb.add_format(
            {"font_color": "#1f77b4", "bold": True, "bg_color": "#f2f2f2", "top": 1, "bottom": 2}
        ),
        "total_val": wb.add_format(
            {"num_format": f"#,##0.00 {currency_symbol}", "bold": True, "bg_color": "#f2f2f2", "top": 1, "bottom": 2}
        ),
        "footer_label": wb.add_format({"bg_color": "#f2f2f2", "font_color": "black", "bold": True}),
        "footer_val": wb.add_format(
            {"bg_color": "#cceeff", "font_color": "black", "num_format": f"#,##0.00 {currency_symbol}", "border": 1}
        ),
        "footer_rec": wb.add_format(
            {"num_format": f"#,##0.00 {currency_symbol}", "font_size": 10, "bottom": 1, "border_color": "#D3D3D3"}
        ),
        "footer_rec_blue": wb.add_format(
            {
                "num_format": f"#,##0.00 {currency_symbol}",
                "bg_color": "#cceeff",
                "font_size": 10,
                "bottom": 1,
                "border_color": "#D3D3D3",
            }
        ),
        "footer_dep": wb.add_format(
            {"num_format": f"#,##0.00 {currency_symbol}", "font_size": 10, "border": 1, "border_color": "#D3D3D3"}
        ),
        "footer_dep_blue": wb.add_format(
            {
                "num_format": f"#,##0.00 {currency_symbol}",
                "bg_color": "#cceeff",
                "font_size": 10,
                "border": 1,
                "border_color": "#D3D3D3",
            }
        ),
    }


def get_monthly_amounts(df: pd.DataFrame, year: int | None = None) -> pd.DataFrame:
    """Récupère les sommes des opérations groupées par mois et par sous-catégorie"""
    if df.empty:
        return pd.DataFrame(columns=["sub_category", "month_idx", "amount"])

    # Filtrer par année uniquement si year est renseigné
    if year is not None:
        df = df[df["operation_date"].dt.year == year].copy()
    else:
        df = df.copy()

    df["month_idx"] = df["operation_date"].dt.month

    summary = df.groupby(["sub_category", "month_idx"])["amount"].sum().reset_index()
    summary["amount"] = summary["amount"].abs()

    return summary


def get_filtered_structure(bank_db: BankDB, data_summary: pd.DataFrame) -> list[dict]:
    """Filtre et trie la structure des catégories par montant total décroissant."""
    df_sub = bank_db.get_categories_structure()
    annual_totals = data_summary.groupby("sub_category")["amount"].sum().to_dict()

    full_structure = []
    categories = df_sub["main_category"].unique() if not df_sub.empty else []
    recettes_names = list(bank_db.get_categories_hierarchy()[0].keys())

    for main_group_name, target_cats in [("REVENUS", recettes_names), ("DÉPENSES", None)]:
        group_content = []
        current_cats = (
            [c for c in categories if c in target_cats]
            if target_cats
            else [c for c in categories if c not in recettes_names]
        )

        for cat in current_cats:
            cat_items = df_sub[df_sub["main_category"] == cat]["sub_category"].tolist()
            active_items = [i for i in cat_items if annual_totals.get(i, 0) > 0]
            active_items.sort(key=lambda x: annual_totals.get(x, 0), reverse=True)

            if active_items:
                group_content.append({"type": "sub", "name": cat.upper(), "items": active_items})

        group_content.sort(key=lambda x: sum(annual_totals.get(i, 0) for i in x["items"]), reverse=True)

        if group_content:
            full_structure.append({"type": "main", "name": main_group_name})
            full_structure.extend(group_content)

    # Récupération des sous-catégories absentes de df_sub (non catégorisées)
    known_items = {item for sec in full_structure if sec.get("type") == "sub" for item in sec["items"]}
    orphan_items = [item for item in annual_totals.keys() if item not in known_items and annual_totals[item] > 0]

    if orphan_items:
        orphan_items.sort(key=lambda x: annual_totals.get(x, 0), reverse=True)
        full_structure.append({"type": "main", "name": "AUTRES"})
        full_structure.append({"type": "sub", "name": "NON CATÉGORISÉ", "items": orphan_items})

    return full_structure
