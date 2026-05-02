import os
from typing import Any

import pandas as pd
import xlsxwriter

from config import load_config
from accounts.banking.database.banking_db import BankingDB


class ExcelGenerator:
    """Générateur de rapports financiers au format Excel."""

    def __init__(self, db: BankingDB, bank_account_name: str) -> None:
        self.__db = db
        self.__root_path = os.path.join(load_config()["destination_path"], bank_account_name)
        self.__months = [
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
            "ANNÉE",
            "RÉPARTITION",
        ]

        os.makedirs(self.__root_path, exist_ok=True)

    def generate_all_reports(self, bank_account_id: int) -> None:
        """Génère les rapports pour chaque année présente en base."""

        df = self.__db.get_categorized_operations_df(bank_account_id)

        if df.empty:
            return

        df["operation_date"] = pd.to_datetime(df["operation_date"])
        years = sorted(df["operation_date"].dt.year.unique())

        for year in years:
            self.__generate_annual_report(bank_account_id, year)

    def __generate_annual_report(self, bank_account_id: int, year: int) -> None:
        """Génère le rapport Excel avec colonnes décalées et tri décroissant."""

        data_summary = self.__get_monthly_amounts(bank_account_id, year)
        structure = self.__get_filtered_structure(data_summary)

        if not structure:
            return

        file_path = os.path.join(self.__root_path, f"Budget pour {year}.xlsx")

        wb = xlsxwriter.Workbook(file_path)
        ws = wb.add_worksheet("BUDGET PERSONNEL")
        fmt = self.__get_excel_formats(wb)

        # Configuration des colonnes (N est vide pour le décalage)
        ws.set_column("A:A", 35)
        ws.set_column("B:M", 12)
        ws.set_column("N:N", 3)  # Colonne de séparation
        ws.set_column("O:O", 15)  # ANNÉE
        ws.set_column("P:P", 15)  # RÉPARTITION

        # Fusionne de la colonne A à D (0 à 3) et centre le texte
        ws.merge_range("A1:C1", "BUDGET PERSONNEL", fmt["title"])
        ws.merge_range("O1:P1", str(year), fmt["year_tag"])

        for col, month in enumerate(self.__months):
            ws.write(3, col + 1, month, fmt["header_month"])

        row = 4
        sections_totals = {"REVENUS": [], "DÉPENSES": []}
        current_main = ""

        # Remplissage du corps du tableau
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
                    # Mois (B à M)
                    for month_idx in range(1, 13):
                        val = data_summary[
                            (data_summary["sub_category"] == item) & (data_summary["month_idx"] == month_idx)
                        ]["amount"].sum()
                        cell_fmt = fmt["currency_blue"] if month_idx % 2 == 0 else fmt["currency"]
                        ws.write(row, month_idx, val, cell_fmt)

                    # Total Annuel décalé en colonne O (indice 14)
                    row_idx = row + 1
                    ws.write_formula(row, 14, f"=SUM(B{row_idx}:M{row_idx})", fmt["total_column"])
                    row += 1

                # Ligne Total de sous-catégorie
                ws.write(row, 0, "Total", fmt["total_label"])
                for col in range(1, 15):
                    if col == 13:
                        continue  # On saute la colonne N vide

                    col_let = xlsxwriter.utility.xl_col_to_name(col)
                    ws.write_formula(row, col, f"=SUM({col_let}{start_items_row + 1}:{col_let}{row})", fmt["total_val"])

                sections_totals[current_main].append(row + 1)
                row += 2

        # Footer
        # On ajoute une ligne vide pour aérer le tableau avant le footer
        row += 1
        row_total_recettes = row
        row_total_depenses = row + 1
        row_tresorerie = row + 2

        # Libellés à gauche
        ws.write(row_total_recettes, 0, "Total des recettes", fmt["item_label"])
        ws.write(row_total_depenses, 0, "Total des dépenses", fmt["item_label"])
        ws.write(row_tresorerie, 0, "Déficit/excédent de trésorerie", fmt["total_label"])

        for col in range(1, 15):
            if col == 13:
                continue  # On saute la colonne N vide

            col_let = xlsxwriter.utility.xl_col_to_name(col)
            rec_f = (
                "+".join([f"{col_let}{r}" for r in sections_totals["REVENUS"]]) if sections_totals["REVENUS"] else "0"
            )
            dep_f = (
                "+".join([f"{col_let}{r}" for r in sections_totals["DÉPENSES"]]) if sections_totals["DÉPENSES"] else "0"
            )

            # Détermination de l'alternance de bleu (uniquement pour les mois pairs B, D, F...)
            is_blue_col = col % 2 == 0 and col <= 12

            # 1. Ligne Recettes (avec bordure basse)
            f_rec = fmt["footer_rec_blue"] if is_blue_col else fmt["footer_rec"]
            ws.write_formula(row_total_recettes, col, f"={rec_f}", f_rec)

            # 2. Ligne Dépenses (format standard)
            f_dep = fmt["footer_dep_blue"] if is_blue_col else fmt["footer_dep"]
            ws.write_formula(row_total_depenses, col, f"={dep_f}", f_dep)

            # 3. Ligne Trésorerie (Gras, Fond Gris, Bordure épaisse bas)
            ws.write_formula(
                row_tresorerie,
                col,
                f"=({col_let}{row_total_recettes + 1})-({col_let}{row_total_depenses + 1})",
                fmt["total_val"],
            )

        # Nettoyage visuel de la colonne N (13) pour les lignes du footer
        ws.write(row_total_recettes, 13, "", None)
        ws.write(row_total_depenses, 13, "", None)
        ws.write(row_tresorerie, 13, "", None)

        # Post-process : Pourcentages en colonne P (15)
        current_main = ""
        row_cursor = 4
        for section in structure:
            if section["type"] == "main":
                current_main = section["name"]
                row_cursor += 1
            else:
                row_cursor += 1
                target_total = (
                    f"O{row_total_recettes + 1}" if current_main == "REVENUS" else f"O{row_total_depenses + 1}"
                )

                for _ in section["items"]:
                    ws.write_formula(
                        row_cursor,
                        15,
                        f"=IF({target_total}<>0, O{row_cursor + 1}/{target_total}, 0)",
                        fmt["percent_style"],
                    )
                    row_cursor += 1

                # Total de section en Gras
                ws.write_formula(
                    row_cursor, 15, f"=IF({target_total}<>0, O{row_cursor + 1}/{target_total}, 0)", fmt["percent_bold"]
                )
                row_cursor += 2

        wb.close()

    def __get_excel_formats(self, wb) -> dict[str | Any]:
        """Définit les formats visuels du document."""

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
            "currency": wb.add_format({"num_format": "#,##0.00 €", "font_size": 10, **border_thin}),
            "currency_blue": wb.add_format(
                {"num_format": "#,##0.00 €", "bg_color": "#cceeff", "font_size": 10, **border_thin}
            ),
            # Style pour la colonne ANNÉE
            "total_column": wb.add_format(
                {"num_format": "#,##0.00 €", "font_size": 10, "bg_color": "#F9F9F9", **border_thin}
            ),
            # Styles Pourcentages
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
                {"num_format": "#,##0.00 €", "bold": True, "bg_color": "#f2f2f2", "top": 1, "bottom": 2}
            ),
            # Footer
            "footer_label": wb.add_format({"bg_color": "#f2f2f2", "font_color": "black", "bold": True}),
            "footer_val": wb.add_format(
                {"bg_color": "#cceeff", "font_color": "black", "num_format": "#,##0.00 €", "border": 1}
            ),
            # Format spécifique pour la ligne "Total des recettes" (avec le trait en dessous)
            "footer_rec": wb.add_format(
                {"num_format": "#,##0.00 €", "font_size": 10, "bottom": 1, "border_color": "#D3D3D3"}
            ),
            "footer_rec_blue": wb.add_format(
                {
                    "num_format": "#,##0.00 €",
                    "bg_color": "#cceeff",
                    "font_size": 10,
                    "bottom": 1,
                    "border_color": "#D3D3D3",
                }
            ),
            # Format pour la ligne "Total des dépenses" (sans bordure basse particulière)
            "footer_dep": wb.add_format(
                {"num_format": "#,##0.00 €", "font_size": 10, "border": 1, "border_color": "#D3D3D3"}
            ),
            "footer_dep_blue": wb.add_format(
                {
                    "num_format": "#,##0.00 €",
                    "bg_color": "#cceeff",
                    "font_size": 10,
                    "border": 1,
                    "border_color": "#D3D3D3",
                }
            ),
        }

    def __get_monthly_amounts(self, bank_account_id: int, year: int) -> pd.DataFrame:
        """Récupère les sommes des opérations groupées par mois et par sous-catégorie."""

        df = self.__db.get_categorized_operations_df(bank_account_id)
        if df.empty:
            return pd.DataFrame(columns=["sub_category", "month_idx", "amount"])

        df["operation_date"] = pd.to_datetime(df["operation_date"])
        df = df[df["operation_date"].dt.year == year].copy()
        df["month_idx"] = df["operation_date"].dt.month

        summary = df.groupby(["sub_category", "month_idx"])["amount"].sum().reset_index()
        summary["amount"] = summary["amount"].abs()

        return summary

    def __get_filtered_structure(self, data_summary: pd.DataFrame) -> list:
        """Filtre et trie la structure par montant annuel décroissant."""

        df_sub = self.__db.get_all_operations("sub_categories")
        if df_sub.empty:
            return []

        # Dictionnaire des totaux pour le tri
        annual_totals = data_summary.groupby("sub_category")["amount"].sum().to_dict()

        full_structure = []
        categories = df_sub["parent_category"].unique()
        recettes_names = self.__db.get_categories_hierarchy()[0].keys()

        for main_group_name, target_cats in [("REVENUS", recettes_names), ("DÉPENSES", None)]:
            group_content = []
            current_cats = (
                [c for c in categories if c in target_cats]
                if target_cats
                else [c for c in categories if c not in recettes_names]
            )

            for cat in current_cats:
                cat_items = df_sub[df_sub["parent_category"] == cat]["sub_category_name"].tolist()
                active_items = [i for i in cat_items if annual_totals.get(i, 0) > 0]

                # Tri décroissant des items
                active_items.sort(key=lambda x: annual_totals.get(x, 0), reverse=True)

                if active_items:
                    group_content.append({"type": "sub", "name": cat.upper(), "items": active_items})

            # Tri décroissant des sous-catégories par poids total
            group_content.sort(key=lambda x: sum(annual_totals.get(i, 0) for i in x["items"]), reverse=True)

            if group_content:
                full_structure.append({"type": "main", "name": main_group_name})
                full_structure.extend(group_content)

        return full_structure
