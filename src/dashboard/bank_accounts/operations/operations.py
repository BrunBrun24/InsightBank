import os
import shutil
import unicodedata
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk
import pandas as pd

from accounts.banking.database.banking_db import BankingDB
from accounts.banking.importers.data_extractor import DataExtractor
from accounts.banking.processing.categorizer import Categorizer
from accounts.banking.reporting.excel_generator import ExcelGenerator as BnpParibasExcelReportGenerator
from accounts.banking.visualization.financial_chart import FinancialChart
from dashboard.bank_accounts.operations.components.operation_edit_window import OperationEditWindow


class Operations:
    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        self.__master = master
        self.__controller = controller
        self.__config = controller.get_config()
        self.__theme = controller.get_theme()
        self.__db_path = self.__config["database"]["database_path"]
        self.__db = BankingDB(self.__db_path)
        self.__sort_column = "operation_date"
        self.__sort_ascending = False

    def display(self, bank_account_row: pd.Series, page: int = 1) -> None:
        """Initialise la structure fixe (Header, Actions) et lance le chargement du tableau."""

        self.__controller.destroy_widgets()

        # Header de navigation
        nav_header = ctk.CTkFrame(self.__master, fg_color="transparent")
        nav_header.pack(fill="x", padx=20, pady=10)

        back_btn = ctk.CTkButton(
            nav_header,
            text="←",
            fg_color=self.__theme["blue_01"]["fg_color"],
            hover_color=self.__theme["blue_01"]["hover_color"],
            width=40,
            command=lambda: self.__controller.show_account_menu(bank_account_row),
        )
        back_btn.place(x=0, y=15)

        ctk.CTkLabel(
            nav_header,
            text="Gestion du compte",
            font=("Arial", 40, "bold"),
        ).pack(pady=(5, 30))

        # Barre d'actions
        account_actions_bar = ctk.CTkFrame(self.__master, fg_color="transparent")
        account_actions_bar.pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(
            account_actions_bar,
            text="Importer des opérations",
            fg_color=self.__theme["green"]["fg_color"],
            hover_color=self.__theme["green"]["hover_color"],
            command=lambda: self.__handle_import_process(bank_account_row),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            account_actions_bar,
            text="Ajouter une opération",
            fg_color=self.__theme["green"]["fg_color"],
            hover_color=self.__theme["green"]["hover_color"],
            command=lambda: self.__handle_add_operation(bank_account_row),
        ).pack(side="left", padx=5)

        operations = self.__db.get_unprocessed_raw_operations(bank_account_row["id"])
        ctk.CTkButton(
            account_actions_bar,
            text="Catégoriser les opérations",
            fg_color=self.__theme["blue_01"]["fg_color"],
            hover_color=self.__theme["blue_01"]["hover_color"],
            state="normal" if operations else "disabled",
            command=lambda: self.__handle_categorization_process(bank_account_row),
        ).pack(side="left", padx=5)

        # Zone d'affichage
        self.__table_container_wrapper = ctk.CTkFrame(self.__master, fg_color="transparent")
        self.__table_container_wrapper.pack(fill="both", expand=True, padx=20, pady=10)

        # Premier chargement du tableau
        self.__update_table_content(bank_account_row, page)

    def __update_table_content(self, bank_account_row: pd.Series, page: int) -> None:
        """Rafraîchit uniquement le tableau avec une zone de lignes à hauteur fixe."""

        # Nettoyage du conteneur dynamique
        for widget in self.__table_container_wrapper.winfo_children():
            widget.destroy()

        bank_account_id = bank_account_row["id"]
        items_per_page = 21

        try:
            df = self.__db.get_operations_by_bank_account(bank_account_id)

            if not df.empty:
                # Logique de Tri et Pagination
                df = df.sort_values(by="operation_date", ascending=True)
                df["id_view"] = range(1, len(df) + 1)

                # Application du tri dynamique choisi par l'utilisateur
                df = df.sort_values(
                    by=[self.__sort_column, "id_view"],
                    ascending=[self.__sort_ascending, False],
                    key=lambda col: col.map(
                        lambda x: self.__remove_accents(str(x).lower()) if isinstance(x, str) else x
                    ),
                )

                total_ops = len(df)
                total_pages = max(1, (total_ops // items_per_page) + (1 if total_ops % items_per_page > 0 else 0))
                page = max(1, min(page, total_pages))

                start_idx = (page - 1) * items_per_page
                page_data = df.iloc[start_idx : start_idx + items_per_page]

                # Header du Tableau
                header_table = ctk.CTkFrame(self.__table_container_wrapper, fg_color="gray80", height=40)
                header_table.pack(fill="x", pady=(0, 5))
                header_table.pack_propagate(False)

                header_table.grid_columnconfigure(0, weight=0)
                header_table.grid_columnconfigure((1, 3, 4, 5), weight=1, uniform="group_trans")
                header_table.grid_columnconfigure(2, weight=3, uniform="group_trans")
                header_table.grid_columnconfigure((6, 7), weight=0, minsize=85)

                columns = ["#", "Date", "Libellé", "Catégorie", "Sous-Catégorie", "Montant", "Actions"]

                # Mapping des noms de colonnes pour le tri
                col_map = {
                    "#": "id_view",
                    "Date": "operation_date",
                    "Libellé": "label",
                    "Catégorie": "category",
                    "Sous-Catégorie": "sub_category",
                    "Montant": "amount",
                }

                for i, col_name in enumerate(columns):
                    padx_val = (25, 60) if i == 0 else 5
                    anchor_val = "w" if i in [1, 2, 3, 4] else "center"

                    # On crée le texte avec la petite flèche de tri
                    display_text = col_name
                    if col_name in col_map:
                        if self.__sort_column == col_map[col_name]:
                            display_text += " ▲" if self.__sort_ascending else " ▼"

                    # On crée un Label
                    lbl = ctk.CTkLabel(
                        header_table,
                        text=display_text,
                        font=("Arial", 14, "bold"),
                        text_color="black",
                        anchor=anchor_val if col_name != "Actions" else "center",
                    )
                    lbl.grid(
                        row=0,
                        column=i,
                        columnspan=2 if col_name == "Actions" else 1,
                        padx=padx_val,
                        pady=5,
                        sticky="nsew",
                    )

                    # On rend le Label cliquable uniquement s'il est dans col_map
                    if col_name in col_map:
                        lbl.configure(cursor="hand2")
                        lbl.bind(
                            "<Button-1>", lambda event, c=col_map[col_name]: self.__sort_handler(bank_account_row, c)
                        )

                    if col_name == "#":
                        lbl.configure(width=50, anchor="center")

                # Zone dédiée aux lignes
                rows_container = ctk.CTkFrame(self.__table_container_wrapper, fg_color="transparent", height=680)
                rows_container.pack(fill="x")
                rows_container.pack_propagate(False)

                for i, (index, operation) in enumerate(page_data.iterrows(), 1):
                    row_bg = "gray95" if i % 2 == 0 else "gray90"
                    row_f = ctk.CTkFrame(rows_container, fg_color=row_bg, height=30)
                    row_f.pack(fill="x", pady=1)

                    row_f.grid_columnconfigure(0, weight=0)
                    row_f.grid_columnconfigure((1, 3, 4, 5), weight=1, uniform="group_trans")
                    row_f.grid_columnconfigure(2, weight=3, uniform="group_trans")
                    row_f.grid_columnconfigure((6, 7), weight=0, minsize=85)

                    ctk.CTkLabel(
                        row_f, text=str(operation["id_view"]), font=("Arial", 11, "italic"), width=50, anchor="center"
                    ).grid(row=0, column=0, padx=(25, 60), sticky="nsew")

                    ctk.CTkLabel(row_f, text=operation["operation_date"], anchor="w").grid(
                        row=0, column=1, padx=5, sticky="nsew"
                    )
                    ctk.CTkLabel(row_f, text=operation["label"], anchor="w").grid(
                        row=0, column=2, padx=(5, 60), sticky="nsew"
                    )
                    ctk.CTkLabel(row_f, text=operation["category"], anchor="w").grid(
                        row=0, column=3, padx=5, sticky="nsew"
                    )
                    ctk.CTkLabel(row_f, text=operation["sub_category"], anchor="w").grid(
                        row=0, column=4, padx=5, sticky="nsew"
                    )

                    amt = operation["amount"]
                    formatted_amt = f"{amt:,.2f}".replace(",", " ") + " €"
                    color = self.__theme["red"]["fg_color"] if amt < 0 else self.__theme["green"]["fg_color"]
                    ctk.CTkLabel(row_f, text=formatted_amt, text_color=color, font=("Arial", 12, "bold")).grid(
                        row=0, column=5, padx=5, sticky="nsew"
                    )

                    ctk.CTkButton(
                        row_f,
                        text="Modifier",
                        width=75,
                        height=22,
                        fg_color=self.__theme["blue_01"]["fg_color"],
                        hover_color=self.__theme["blue_01"]["hover_color"],
                        command=lambda o=operation: self.__handle_edit_operation(o, bank_account_row),
                    ).grid(row=0, column=6, padx=5, pady=5)

                    ctk.CTkButton(
                        row_f,
                        text="Supprimer",
                        width=75,
                        height=22,
                        fg_color=self.__theme["red"]["fg_color"],
                        hover_color=self.__theme["red"]["hover_color"],
                        command=lambda o_id=operation["id"]: self.__handle_delete_operation(bank_account_row, o_id),
                    ).grid(row=0, column=7, padx=5, pady=5)

                # Barre de Pagination
                pagination_container = ctk.CTkFrame(self.__table_container_wrapper, fg_color="transparent")
                pagination_container.pack(fill="x", pady=20)

                center_frame = ctk.CTkFrame(pagination_container, fg_color="transparent")
                center_frame.pack(expand=True)

                # Saut de -10 pages
                ctk.CTkButton(
                    center_frame,
                    text=" << ",
                    width=40,
                    state="normal" if page > 1 else "disabled",
                    fg_color=self.__theme["blue_01"]["fg_color"],
                    hover_color=self.__theme["blue_01"]["hover_color"],
                    command=lambda: self.__update_table_content(bank_account_row, max(1, page - 10)),
                ).pack(side="left", padx=5)

                # Précédent
                ctk.CTkButton(
                    center_frame,
                    text=" < ",
                    width=40,
                    state="normal" if page > 1 else "disabled",
                    fg_color=self.__theme["blue_01"]["fg_color"],
                    hover_color=self.__theme["blue_01"]["hover_color"],
                    command=lambda: self.__update_table_content(bank_account_row, page - 1),
                ).pack(side="left", padx=5)

                ctk.CTkLabel(
                    center_frame, text=f"Page {page} / {total_pages}", font=("Arial", 13, "bold"), width=120
                ).pack(side="left", padx=15)

                # Suivant
                ctk.CTkButton(
                    center_frame,
                    text=" > ",
                    width=40,
                    state="normal" if page < total_pages else "disabled",
                    fg_color=self.__theme["blue_01"]["fg_color"],
                    hover_color=self.__theme["blue_01"]["hover_color"],
                    command=lambda: self.__update_table_content(bank_account_row, page + 1),
                ).pack(side="left", padx=5)

                # Saut de +10 pages
                ctk.CTkButton(
                    center_frame,
                    text=" >> ",
                    width=40,
                    state="normal" if page < total_pages else "disabled",
                    fg_color=self.__theme["blue_01"]["fg_color"],
                    hover_color=self.__theme["blue_01"]["hover_color"],
                    command=lambda: self.__update_table_content(bank_account_row, min(total_pages, page + 10)),
                ).pack(side="left", padx=5)

            else:
                ctk.CTkLabel(self.__table_container_wrapper, text="Aucune opération enregistrée.").pack(pady=40)

        except Exception as e:
            ctk.CTkLabel(self.__table_container_wrapper, text=f"Erreur de chargement : {e}", text_color="red").pack(
                pady=20
            )

    def __sort_handler(self, bank_account_row: pd.Series, column_name: str) -> None:
        """Tri une colonne en particulier dans l'ordre croissant"""

        if self.__sort_column == column_name:
            self.__sort_ascending = not self.__sort_ascending
        else:
            self.__sort_column = column_name
            self.__sort_ascending = True

        self.__update_table_content(bank_account_row, page=1)

    def __handle_add_operation(self, bank_account_row: pd.Series) -> None:
        """Ouvre la fenêtre pour ajouter une nouvelle opération."""

        # On définit les valeurs par défaut pour une nouvelle ligne
        default_op = {
            "id": None,  # None indique à la BDD qu'il s'agit d'une insertion
            "operation_date": datetime.now().strftime("%Y-%m-%d"),
            "label": "",
            "amount": "0.00",
            "category": "",
            "sub_category": "",
        }

        win = OperationEditWindow(
            parent=self.__master,
            db=self.__db,
            bank_account_id=bank_account_row["id"],
            operation=default_op,
            on_save_callback=lambda data: self.__process_add(data, bank_account_row),
        )
        win.title("Ajouter une opération")

    def __handle_delete_operation(self, bank_account_row: pd.Series, operation_id: int) -> None:
        """Gère la suppression d'une opération et rafraîchit l'affichage."""

        try:
            self.__db.delete_operation(bank_account_row["id"], operation_id)
            self.__update_bilan(bank_account_row["id"], bank_account_row["name"])
            self.__controller.show_operations(bank_account_row)

        except Exception as e:
            messagebox.showerror(f"Erreur lors de la suppression d'une opération' : {str(e)}")
            raise

    def __handle_edit_operation(self, operation: pd.Series, bank_account_row: pd.Series) -> None:
        """Ouvre la fenêtre de modification pour une opération donnée."""

        OperationEditWindow(
            self.__master,
            self.__db,
            bank_account_row["id"],
            operation,
            lambda data: self.__process_update(data, bank_account_row),
        )

    def __handle_import_process(self, bank_account_row: pd.Series) -> None:
        """Lance l'extraction et injecte le nom du compte sélectionné dans les données."""

        try:
            extractor = DataExtractor()
            df = extractor.run_extraction(bank_account_row["id"])

            if df is None:
                return

            df["bank_account_id"] = bank_account_row["id"]
            self.__db.add_operations(df)

            # Catégorise les différentes opérations
            categorizer = Categorizer(self.__master, self.__db, bank_account_row["id"])
            cat_window = categorizer.categorize()

            if cat_window and cat_window.winfo_exists():
                self.__master.wait_window(cat_window)

            self.__update_bilan(bank_account_row["id"], bank_account_row["name"])

            messagebox.showinfo(
                "Succès",
                f"Données importées avec succès pour le compte : {bank_account_row['name']}",
            )
            self.__controller.show_operations(bank_account_row)

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'insertion : {e}")
            raise

    def __handle_categorization_process(self, bank_account_row: pd.Series) -> None:
        """Lance le processus de catégorisation."""

        try:
            categorizer = Categorizer(self.__master, self.__db, bank_account_row["id"])
            cat_window = categorizer.categorize()

            if cat_window and cat_window.winfo_exists():
                self.__master.wait_window(cat_window)

            if categorizer.has_changed:
                self.__update_bilan(bank_account_row["id"], bank_account_row["name"])
                self.__controller.show_operations(bank_account_row)

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de la catégorisation : {e}")
            raise

    def __process_add(self, new_operation: dict, bank_account_row: pd.Series) -> None:
        """Met à jour la base de données et rafraîchit l'affichage."""

        try:
            df = pd.DataFrame([new_operation])
            self.__db.add_operations(df)
            self.__update_bilan(bank_account_row["id"], bank_account_row["name"])
            self.__controller.show_operations(bank_account_row)

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'ajout : {e}")
            raise

    def __process_update(self, updated_data: dict, bank_account_row: pd.Series) -> None:
        """Met à jour la base de données et rafraîchit l'affichage."""

        try:
            self.__db.update_operation(bank_account_row["id"], updated_data)
            self.__update_bilan(bank_account_row["id"], bank_account_row["name"])
            self.__controller.show_operations(bank_account_row)

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de la mise à jour : {e}")
            raise

    def __update_bilan(self, bank_account_id: int, bank_account_name: str) -> None:
        """Coordonne la mise à jour complète des fichiers bilan pour un compte bancaire."""

        # Supprime le dossier bilan du compte pour que les données soient à jour
        path = os.path.join(self.__config["destination_path"], bank_account_name)
        if os.path.exists(path):
            shutil.rmtree(path)

        # Créer les graphiques HTML
        chart_generator = FinancialChart(self.__db, bank_account_name)
        chart_generator.generate_all_reports(bank_account_id)

        # Créer les fichiers Excel
        excel_generator = BnpParibasExcelReportGenerator(self.__db, bank_account_name)
        excel_generator.generate_all_reports(bank_account_id)

    @staticmethod
    def __remove_accents(input_str: str) -> str:
        """Remplace les lettre avec des accents"""

        if not isinstance(input_str, str):
            return input_str

        # Normalise les caractères (ex: 'É' devient 'E')
        nfkd_form = unicodedata.normalize("NFKD", input_str)
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)])
