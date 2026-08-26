import os
import shutil
import threading
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk
import pandas as pd
import yfinance as yf

from accounts.stock.importers.data_extractor import DataExtractor
from accounts.stock.importers.fetch_stock import fetch_stock_data, get_ticker_from_isin
from accounts.stock.processing.portfolio_tracker import PortfolioTracker
from accounts.stock.reporting.stock_excel_generator import StockExcelGenerator
from accounts.stock.visualization.portfolio_exporter import generate_rapport
from dashboard.portfolio.transactions.components.transaction_edit_window import TransactionEditWindow
from utils.data_utils import remove_accents
from utils.loading_popup import LoadingPopup


class Transactions:
    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        self.__master = master
        self.__controller = controller
        self.__theme = controller.get_theme()
        self.__stock_db = controller.get_db_stock()
        self.__config = controller.get_config()
        self.__sort_column = "date"
        self.__sort_ascending = False

    def display(self, stock_portfolio_row: pd.Series, page: int = 1) -> None:
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
            command=lambda: self.__controller.show_stock_account_menu(stock_portfolio_row),
        )
        back_btn.place(x=0, y=15)

        ctk.CTkLabel(
            nav_header,
            text="Gestion du Portefeuille",
            font=("Arial", 40, "bold"),
        ).pack(pady=(5, 30))

        # Barre d'actions
        account_actions_bar = ctk.CTkFrame(self.__master, fg_color="transparent")
        account_actions_bar.pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(
            account_actions_bar,
            text="Importer des transactions",
            fg_color=self.__theme["green"]["fg_color"],
            hover_color=self.__theme["green"]["hover_color"],
            command=lambda: self.__handle_import_process(stock_portfolio_row),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            account_actions_bar,
            text="Ajouter une transaction",
            fg_color=self.__theme["green"]["fg_color"],
            hover_color=self.__theme["green"]["hover_color"],
            command=lambda: self.__handle_add_transaction(stock_portfolio_row),
        ).pack(side="left", padx=5)

        # Zone d'affichage
        self.__table_container_wrapper = ctk.CTkFrame(self.__master, fg_color="transparent")
        self.__table_container_wrapper.pack(fill="both", expand=True, padx=20, pady=10)

        # Premier chargement du tableau
        self.__update_table_content(stock_portfolio_row, page)

    def __update_table_content(self, stock_portfolio_row: pd.Series, page: int) -> None:
        """Rafraîchit uniquement le tableau avec une zone de lignes à hauteur fixe."""

        # Nettoyage du conteneur dynamique
        for widget in self.__table_container_wrapper.winfo_children():
            widget.destroy()

        portfolio_id = stock_portfolio_row["id"]
        items_per_page = 21

        currency_symbols = {
            "EUR": "€",
            "USD": "$",
        }

        type_op = {
            "buy": "Achat",
            "sell": "Vente",
            "dividend": "Dividende",
            "deposit": "Dépôt",
            "withdrawal": "Retrait",
            "interest": "Intérêts",
        }

        try:
            df = self.__stock_db.get_transactions_by_stock_account(portfolio_id)

            if not df.empty:
                df = df.sort_values(by="date", ascending=True)
                df["id_view"] = range(1, len(df) + 1)

                df = df.sort_values(
                    by=[self.__sort_column, "id_view"],
                    ascending=[self.__sort_ascending, False],
                    key=lambda col: col.map(lambda x: remove_accents(str(x).lower()) if isinstance(x, str) else x),
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
                header_table.grid_columnconfigure((1, 2, 3, 4, 5, 6, 7, 8, 9), weight=1, uniform="group_trans")
                header_table.grid_columnconfigure((10, 11), weight=0, minsize=85)

                columns = [
                    "#",
                    "Date",
                    "Devise du compte",
                    "Opération",
                    "Nom",
                    "Ticker",
                    "Quantité",
                    "Prix",
                    "Montant",
                    "Frais",
                ]

                col_map = {
                    "#": "id_view",
                    "Date": "date",
                    "Devise du compte": "account_currency",
                    "Opération": "type",
                    "Nom": "name",
                    "Ticker": "ticker",
                    "Quantité": "shares",
                    "Prix": "price",
                    "Montant": "amount",
                    "Frais": "fee",
                }

                for i, col_name in enumerate(columns):
                    padx_val = (25, 60) if i == 0 else 5
                    anchor_val = "w" if i in [1, 3, 4] else "center"

                    display_text = col_name
                    if col_name in col_map and self.__sort_column == col_map[col_name]:
                        display_text += " ▲" if self.__sort_ascending else " ▼"

                    lbl = ctk.CTkLabel(
                        header_table,
                        text=display_text,
                        font=("Arial", 14, "bold"),
                        text_color="black",
                        anchor=anchor_val,
                    )
                    lbl.grid(
                        row=0,
                        column=i,
                        padx=padx_val,
                        pady=5,
                        sticky="nsew",
                    )

                    if col_name in col_map:
                        lbl.configure(cursor="hand2")
                        lbl.bind(
                            "<Button-1>",
                            lambda event, c=col_map[col_name]: self.__sort_handler(stock_portfolio_row, c),
                        )

                    if col_name == "#":
                        lbl.configure(width=50, anchor="center")

                # Zone dédiée aux lignes
                rows_container = ctk.CTkFrame(self.__table_container_wrapper, fg_color="transparent", height=680)
                rows_container.pack(fill="x")
                rows_container.pack_propagate(False)

                for i, (_, transaction) in enumerate(page_data.iterrows(), 1):
                    row_bg = "gray95" if i % 2 == 0 else "gray90"
                    row_f = ctk.CTkFrame(rows_container, fg_color=row_bg, height=30)
                    row_f.pack(fill="x", pady=1)

                    row_f.grid_columnconfigure(0, weight=0)
                    row_f.grid_columnconfigure((1, 2, 3, 4, 5, 6, 7, 8, 9), weight=1, uniform="group_trans")
                    row_f.grid_columnconfigure((10, 11), weight=0, minsize=85)

                    # Conversion de la devise en symbole
                    curr_symbol = currency_symbols.get(
                        str(transaction["account_currency"]).upper(), str(transaction["account_currency"])
                    )

                    # 0. # (Numéro d'affichage)
                    ctk.CTkLabel(
                        row_f, text=str(transaction["id_view"]), font=("Arial", 11, "italic"), width=50, anchor="center"
                    ).grid(row=0, column=0, padx=(25, 60), sticky="nsew")

                    # 1. Date
                    ctk.CTkLabel(row_f, text=str(transaction["date"]), anchor="w").grid(
                        row=0, column=1, padx=5, sticky="nsew"
                    )

                    # 2. Devise du compte
                    ctk.CTkLabel(row_f, text=str(transaction["account_currency"]), anchor="center").grid(
                        row=0, column=2, padx=5, sticky="nsew"
                    )

                    # 3. Type
                    type_key = str(transaction["type"]).lower()
                    type_text = type_op.get(type_key, type_key.capitalize())

                    ctk.CTkLabel(row_f, text=type_text, anchor="w").grid(row=0, column=3, padx=5, sticky="nsew")

                    # 4. Nom
                    name_val = str(transaction["name"]) if pd.notna(transaction["name"]) else "-"
                    ctk.CTkLabel(row_f, text=name_val, anchor="w").grid(row=0, column=4, padx=5, sticky="nsew")

                    # 5. Ticker
                    ticker_val = str(transaction["ticker"]) if pd.notna(transaction["ticker"]) else "-"
                    ctk.CTkLabel(row_f, text=ticker_val, anchor="center").grid(row=0, column=5, padx=5, sticky="nsew")

                    # 6. Quantité
                    qty_val = transaction["shares"]
                    qty_str = f"{qty_val:g}" if pd.notna(qty_val) else "-"
                    ctk.CTkLabel(row_f, text=qty_str, anchor="center").grid(row=0, column=6, padx=5, sticky="nsew")

                    # 7. Prix (price)
                    price_val = transaction["price"]
                    price_str = (
                        f"{price_val:,.2f}".replace(",", " ") + f" {curr_symbol}" if pd.notna(price_val) else "-"
                    )
                    ctk.CTkLabel(row_f, text=price_str, anchor="center").grid(row=0, column=7, padx=5, sticky="nsew")

                    # 8. Montant
                    amt = transaction["amount"]
                    formatted_amt = f"{amt:,.2f}".replace(",", " ") + f" {curr_symbol}"
                    op_type = str(transaction["type"]).lower()
                    is_incoming = op_type in ["sell", "dividend", "interest", "deposit"]
                    color = self.__theme["green"]["fg_color"] if is_incoming else self.__theme["red"]["fg_color"]

                    ctk.CTkLabel(
                        row_f, text=formatted_amt, text_color=color, font=("Arial", 12, "bold"), anchor="center"
                    ).grid(row=0, column=8, padx=5, sticky="nsew")

                    # 9. Frais
                    fee_val = transaction["fee"]
                    fee_str = f"{fee_val:,.2f}".replace(",", " ") + f" {curr_symbol}" if fee_val > 0 else "-"
                    ctk.CTkLabel(row_f, text=fee_str, anchor="center").grid(row=0, column=9, padx=5, sticky="nsew")

                    # 10. Bouton Modifier
                    ctk.CTkButton(
                        row_f,
                        text="Modifier",
                        width=75,
                        height=22,
                        fg_color=self.__theme["blue_01"]["fg_color"],
                        hover_color=self.__theme["blue_01"]["hover_color"],
                        command=lambda o=transaction: self.__handle_edit_transaction(o, stock_portfolio_row),
                    ).grid(row=0, column=10, padx=5, pady=5)

                    # 11. Bouton Supprimer
                    ctk.CTkButton(
                        row_f,
                        text="Supprimer",
                        width=75,
                        height=22,
                        fg_color=self.__theme["red"]["fg_color"],
                        hover_color=self.__theme["red"]["hover_color"],
                        command=lambda o_id=transaction["id"]: self.__handle_delete_transaction(
                            stock_portfolio_row, o_id
                        ),
                    ).grid(row=0, column=11, padx=5, pady=5)

                # Barre de Pagination
                pagination_container = ctk.CTkFrame(self.__table_container_wrapper, fg_color="transparent")
                pagination_container.pack(fill="x", pady=20)

                center_frame = ctk.CTkFrame(pagination_container, fg_color="transparent")
                center_frame.pack(expand=True)

                # Saut -10 pages
                ctk.CTkButton(
                    center_frame,
                    text=" << ",
                    width=40,
                    state="normal" if page > 1 else "disabled",
                    fg_color=self.__theme["blue_01"]["fg_color"],
                    hover_color=self.__theme["blue_01"]["hover_color"],
                    command=lambda: self.__update_table_content(stock_portfolio_row, max(1, page - 10)),
                ).pack(side="left", padx=5)

                # Précédent
                ctk.CTkButton(
                    center_frame,
                    text=" < ",
                    width=40,
                    state="normal" if page > 1 else "disabled",
                    fg_color=self.__theme["blue_01"]["fg_color"],
                    hover_color=self.__theme["blue_01"]["hover_color"],
                    command=lambda: self.__update_table_content(stock_portfolio_row, page - 1),
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
                    command=lambda: self.__update_table_content(stock_portfolio_row, page + 1),
                ).pack(side="left", padx=5)

                # Saut +10 pages
                ctk.CTkButton(
                    center_frame,
                    text=" >> ",
                    width=40,
                    state="normal" if page < total_pages else "disabled",
                    fg_color=self.__theme["blue_01"]["fg_color"],
                    hover_color=self.__theme["blue_01"]["hover_color"],
                    command=lambda: self.__update_table_content(stock_portfolio_row, min(total_pages, page + 10)),
                ).pack(side="left", padx=5)

            else:
                ctk.CTkLabel(self.__table_container_wrapper, text="Aucune transaction enregistrée.").pack(pady=40)

        except Exception as e:
            ctk.CTkLabel(self.__table_container_wrapper, text=f"Erreur de chargement : {e}", text_color="red").pack(
                pady=20
            )

    def __sort_handler(self, stock_portfolio_row: pd.Series, column_name: str) -> None:
        """Tri une colonne en particulier dans l'ordre croissant"""

        if self.__sort_column == column_name:
            self.__sort_ascending = not self.__sort_ascending
        else:
            self.__sort_column = column_name
            self.__sort_ascending = True

        self.__update_table_content(stock_portfolio_row, page=1)

    def __handle_add_transaction(self, stock_portfolio_row: pd.Series) -> None:
        """Ouvre la fenêtre pour ajouter une nouvelle transaction."""

        # On définit les valeurs par défaut pour une nouvelle ligne
        default_tr = {
            "id": None,  # None indique à la BDD qu'il s'agit d'une insertion
            "date": datetime.now().strftime("%Y-%m-%d"),
            "type": "",
            "amount": "0.00",
            "fee": "0.00",
            "price": "0.00",
            "currency": "0.00",
        }

        win = TransactionEditWindow(
            parent=self.__master,
            db=self.__stock_db,
            portfolio_id=stock_portfolio_row["id"],
            on_save_callback=lambda data: self.__process_add(data, stock_portfolio_row),
            transaction=default_tr,
        )
        win.title("Ajouter une transaction")

    def __handle_delete_transaction(self, stock_portfolio_row: pd.Series, transaction_id: int) -> None:
        """Gère la suppression d'une transaction et rafraîchit l'affichage."""
        loading_win = LoadingPopup(self.__master, "Suppression en cours...")

        def task():
            try:
                self.__stock_db.delete_transaction(transaction_id)
                self.update_bilan(stock_portfolio_row["id"], stock_portfolio_row["name"])
            except Exception:
                self.__master.after(
                    0, lambda: messagebox.showerror("Erreur", "Erreur lors de la suppression d'une transaction")
                )
            finally:
                self.__master.after(0, lambda: self.__on_process_complete(loading_win, stock_portfolio_row))

        threading.Thread(target=task, daemon=True).start()

    def __handle_edit_transaction(self, transaction: pd.Series, stock_portfolio_row: pd.Series) -> None:
        """Ouvre la fenêtre de modification en récupérant au préalable les données complètes en BDD."""

        full_transaction_data = self.__stock_db.get_transaction_by_id(int(transaction["id"]))
        win = TransactionEditWindow(
            self.__master,
            self.__stock_db,
            stock_portfolio_row["id"],
            lambda data: self.__process_update(data, stock_portfolio_row),
            full_transaction_data,
        )
        win.title("Modifier une transaction")

    def __handle_import_process(self, stock_portfolio_row: pd.Series) -> None:
        """Lance l'extraction et injecte les données avec un écran de chargement bloquant."""

        extractor = DataExtractor(stock_portfolio_row["id"], self.__master)
        df, source = extractor.run_extraction()

        if df is None or df.empty:
            return

        loading_win = LoadingPopup(self.__master, "Traitement et vérification des données...")

        def task():
            nonlocal df
            try:
                portfolio_id = int(df["portfolio_id"].iloc[0])

                if source == "Trade Republic":
                    allowed_types = [
                        "CUSTOMER_INPAYMENT",
                        "BUY",
                        "INTEREST_PAYMENT",
                        "DIVIDEND",
                        "UNBUNDLING",
                        "SELL",
                        "CARD_ORDERING_FEE",
                        "MERGER",
                        "CARD_TRANSACTION",
                        "SPLIT",
                    ]
                    df = df[df["type"].isin(allowed_types)].reset_index(drop=True)
                    df["fee"] = df["fee"].fillna(0) - df["tax"].fillna(0).abs()
                    df = self.__aggregate_similar_trades(df)
                    df = self.__apply_split_trade_republic(df)
                    df = self.__apply_merge_trade_repulic(df)
                    extracted_data, isin_ticker_add = fetch_stock_data(self.__stock_db, df)
                elif (
                    self.__sanitize_and_validate(df)
                    and self.__validate_opearations(df)
                    and self.__validate_tickers(df)
                    and self.__validate_currencies(df)
                ):
                    extracted_data, isin_ticker_add = fetch_stock_data(self.__stock_db, df)
                else:
                    loading_win.close()
                    return

                tickers_to_add = [isin_ticker["ticker"] for isin_ticker in isin_ticker_add]
                self.__stock_db.add_data_tickers(tickers_to_add, extracted_data)
                self.__stock_db.add_tickers_in_portfolio_ticker(portfolio_id, tickers_to_add)

                if source == "Trade Republic":
                    df = self.__apply_unbundling_trade_republic(df)

                    type_mapping = {
                        "customer_inpayment": "deposit",
                        "customer_outpayment": "withdrawal",
                        "card_transaction": "withdrawal",
                        "card_ordering_fee": "withdrawal",
                        "interest_payment": "interest",
                        "dividend": "dividend",
                    }
                    df["type"] = df["type"].str.lower().map(type_mapping).fillna(df["type"].str.lower())

                    isin_ticker = []
                    for i_t in isin_ticker_add:
                        temp = {}
                        temp["currency"] = self.__stock_db.get_currency(i_t["ticker"])
                        temp["ticker"] = i_t["ticker"]
                        temp["isin"] = i_t["isin"]
                        isin_ticker.append(temp)

                    # Construction des mappings
                    isin_to_ticker = {item["isin"]: item["ticker"] for item in isin_ticker_add}
                    isin_to_currency = {
                        item["isin"]: self.__stock_db.get_currency(item["ticker"]) for item in isin_ticker_add
                    }
                    df["currency"] = df["symbol"].map(isin_to_currency).fillna(df["currency"])
                    df["symbol"] = df["symbol"].map(isin_to_ticker).fillna(df["symbol"])

                    df["original_amount"] = abs(df["amount"])
                    df["original_fee"] = df["fee"].fillna(0).abs()
                    df["type"] = df["type"].str.lower()

                    df = self.__apply_currency_conversion_trade_republic(df, portfolio_id)
                    mask = (df["type"] == "buy") & (df["fee"] > 0)
                    df.loc[mask, "amount"] = (
                        df.loc[mask, "amount"].fillna(0).abs() + df.loc[mask, "fee"].fillna(0).abs()
                    )

                else:
                    df = self.__apply_currency_conversion(df, portfolio_id)

                ticker_to_id = self.__stock_db.get_portfolio_ticker_ids(portfolio_id)
                df["portfolio_ticker_id"] = df["symbol"].map(ticker_to_id)

                db_columns = [
                    "portfolio_ticker_id",
                    "portfolio_id",
                    "date",
                    "type",
                    "original_amount",
                    "amount",
                    "price",
                    "original_price",
                    "original_fee",
                    "fee",
                    "fx_rate",
                ]
                operations_to_insert = df[db_columns]
                self.__stock_db.add_transactions(operations_to_insert)
                self.update_bilan(stock_portfolio_row["id"], stock_portfolio_row["name"])

                if source == "Trade Republic":
                    messagebox.showinfo(
                        "Information",
                        "Pour que votre portefeuille soit exact, veuillez vérifier et éventuellement modifier les transactions suivantes :\n\n"
                        "• Pour toute transaction exécutée manuellement (hors plan d'investissement), ajoutez 1 € dans la colonne 'Montant'.\n\n"
                        "• Pour les cadeaux reçus, ajoutez les dépôts nets (le montant investi directement, sans frais).",
                    )

                self.__master.after(0, lambda: self.__on_import_success(stock_portfolio_row, loading_win))

            except Exception as e:
                self.__master.after(0, lambda err=e: self.__on_import_error(err, loading_win))

        # Lancement du thread secondaire
        threading.Thread(target=task, daemon=True).start()

    def __on_import_success(self, stock_portfolio_row: pd.Series, loading_win: LoadingPopup) -> None:
        """Rappel exécuté sur le thread principal en cas de succès."""
        loading_win.close()
        messagebox.showinfo(
            "Succès",
            f"Données importées avec succès pour le compte : {stock_portfolio_row['name']}",
        )
        self.__controller.show_stock_transactions(stock_portfolio_row)

    def __on_import_error(self, error: Exception, loading_win: LoadingPopup) -> None:
        """Rappel exécuté sur le thread principal en cas d'erreur."""
        loading_win.close()
        messagebox.showerror("Erreur", f"Erreur lors de l'insertion : {error}")

    def __validate_opearations(self, df: pd.DataFrame) -> bool:
        """Vérifie que les types d'opérations sont valides."""

        valid_ops = {
            "buy",
            "sell",
            "dividend",
            "interest",
            "deposit",
            "withdrawal",
        }
        type_ops = df["type"].dropna().unique()

        for type_op in type_ops:
            if type_op not in valid_ops:
                messagebox.showerror(
                    "Erreur Opération",
                    f"Dans la colonne 'type', le type '{type_op}' n'est pas reconnue.\n"
                    f"Choix autorisés : {', '.join(sorted(valid_ops))}",
                )
                return False
        return True

    def __validate_currencies(self, df: pd.DataFrame) -> bool:
        valid_ops = {"EUR", "USD"}
        currencies = df["currency"].dropna().unique()

        for currency in currencies:
            if currency not in valid_ops:
                messagebox.showerror(
                    "Erreur Opération",
                    f"Dans la colonne 'devise': '{currency}' n'est pas valide.\n"
                    f"Choix autorisés : {', '.join(sorted(valid_ops))}",
                )
                return False
        return True

    def __sanitize_and_validate(self, df: pd.DataFrame) -> bool:
        """Convertit les colonnes numériques et valide les champs requis ou interdits par opération."""

        # Validation de la date
        if "date" in df.columns:
            parsed_dates = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")
            invalid_dates = df[parsed_dates.isna()]
            if not invalid_dates.empty:
                invalid_rows = [i + 2 for i in invalid_dates.index.tolist()]
                messagebox.showerror(
                    "Erreur Date",
                    f"La colonne 'date' doit être au format valide AAAA-MM-JJ (lignes : {invalid_rows}).",
                )
                return False
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

        # Conversion numérique sécurisée
        numeric_cols = ["amount", "price", "fee"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Validation des frais
        if "fee" in df.columns:
            numeric_fees = pd.to_numeric(df["fee"], errors="coerce")
            invalid_fee_orig = df[numeric_fees.isna()]

            if not invalid_fee_orig.empty:
                invalid_rows = [i + 2 for i in invalid_fee_orig.index.tolist()]
                messagebox.showerror(
                    "Erreur de saisie",
                    f"Les frais doivent être renseignés avec des chiffres valides (lignes : {invalid_rows}).",
                )
                return False

        # Validation de 'amount'
        invalid_amount_orig = df[df["amount"].isna() | (df["amount"] <= 0)]
        if not invalid_amount_orig.empty:
            invalid_rows = [i + 2 for i in invalid_amount_orig.index.tolist()]
            messagebox.showerror(
                "Erreur de saisie",
                f"La colonne 'montant' doit contenir un nombre strictement supérieur à 0 (lignes : {invalid_rows}).",
            )
            return False

        # Symbol requis pour buy, sell, dividend
        symbol_required_mask = df["type"].isin(["buy", "sell", "dividend"])
        invalid_symbol_missing = df[
            symbol_required_mask & (df["symbol"].isna() | (df["symbol"].astype(str).str.strip() == ""))
        ]
        if not invalid_symbol_missing.empty:
            invalid_rows = [i + 2 for i in invalid_symbol_missing.index.tolist()]
            messagebox.showerror(
                "Erreur Symbol",
                f"Le champ 'symbol' est obligatoire pour 'buy', 'sell' et 'dividend' (lignes : {invalid_rows}).",
            )
            return False

        # Symbol interdis pour interest, deposit, withdrawal
        symbol_forbidden_mask = df["type"].isin(["interest", "deposit", "withdrawal"])
        invalid_symbol_present = df[
            symbol_forbidden_mask & df["symbol"].notna() & (df["symbol"].astype(str).str.strip() != "")
        ]
        if not invalid_symbol_present.empty:
            invalid_rows = [i + 2 for i in invalid_symbol_present.index.tolist()]
            messagebox.showerror(
                "Erreur Ticker",
                "La colonne 'ticker' doit être vide pour les opérations 'interest', 'deposit' et 'withdrawal' "
                f"(lignes : {invalid_rows}).",
            )
            return False

        # Prix requis pour buy, sell (> 0)
        price_required_mask = df["type"].isin(["buy", "sell"])
        invalid_price_missing = df[price_required_mask & (df["price"].isna() | (df["price"] <= 0))]
        if not invalid_price_missing.empty:
            invalid_rows = [i + 2 for i in invalid_price_missing.index.tolist()]
            messagebox.showerror(
                "Erreur Prix",
                f"La colonne 'prix d'achat' doit être un nombre > 0 pour les achats/ventes (lignes : {invalid_rows}).",
            )
            return False

        # Prix interdis pour dividend, interest, deposit, withdrawal
        price_forbidden_mask = df["type"].isin(["dividend", "interest", "deposit", "withdrawal"])
        invalid_price_present = df[price_forbidden_mask & df["price"].notna()]
        if not invalid_price_present.empty:
            invalid_rows = [i + 2 for i in invalid_price_present.index.tolist()]
            messagebox.showerror(
                "Erreur Prix",
                "La colonne 'prix d'achat' doit être vide pour 'dividend', 'interest', 'deposit' et 'withdrawal' "
                f"(lignes : {invalid_rows}).",
            )
            return False

        return True

    def __validate_tickers(self, df: pd.DataFrame) -> bool:
        """Vérifie l'existence des tickers uniques (ignore les valeurs vides/NaN)."""

        # Ne vérifie que les tickers renseignés (non vides)
        valid_tickers = df["symbol"].dropna()
        valid_tickers = valid_tickers[valid_tickers.astype(str).str.strip() != ""]
        tickers = valid_tickers.unique()

        for ticker in tickers:
            try:
                ticker_data = yf.Ticker(ticker).history(period="1d")
                if ticker_data.empty:
                    messagebox.showerror(
                        "Erreur Ticker",
                        f"Le ticker '{ticker}' n'a pas été trouvé sur Yahoo Finance.",
                    )
                    return False
            except Exception:
                messagebox.showerror(
                    "Erreur",
                    f"Impossible de vérifier le ticker '{ticker}'.\n\nVérifiez le nom du ticker ex: (Apple => AAPL)",
                )
                return False

        return True

    def __process_add(self, new_transaction: dict, stock_portfolio_row: pd.Series) -> None:
        loading_win = LoadingPopup(self.__master, "Ajout en cours...")

        def task():
            try:
                df = pd.DataFrame([new_transaction])
                self.__stock_db.add_transactions(df)
                self.update_bilan(stock_portfolio_row["id"], stock_portfolio_row["name"])
            except Exception:
                self.__master.after(0, lambda: messagebox.showerror("Erreur", "Erreur lors de l'ajout"))
            finally:
                self.__master.after(0, lambda: self.__on_process_complete(loading_win, stock_portfolio_row))

        threading.Thread(target=task, daemon=True).start()

    def __process_update(self, updated_data: dict, stock_portfolio_row: pd.Series) -> None:
        loading_win = LoadingPopup(self.__master, "Modification en cours...")

        def task():
            try:
                self.__stock_db.update_transaction(updated_data)
                self.update_bilan(stock_portfolio_row["id"], stock_portfolio_row["name"])
            except Exception:
                self.__master.after(0, lambda: messagebox.showerror("Erreur", "Erreur lors de la mise à jour"))
            finally:
                self.__master.after(0, lambda: self.__on_process_complete(loading_win, stock_portfolio_row))

        threading.Thread(target=task, daemon=True).start()

    def __on_process_complete(self, loading_win: LoadingPopup, stock_portfolio_row: pd.Series) -> None:
        loading_win.close()
        self.__controller.show_stock_transactions(stock_portfolio_row)

    def __apply_currency_conversion(self, df: pd.DataFrame, portfolio_id: int) -> pd.DataFrame:
        """Calcule et uniformise les prix, montants et taux de change pour un portefeuille."""
        portfolio_currency = self.__stock_db.get_portfolio_currency(portfolio_id)
        df = df.copy()

        # Cast explicite des colonnes en float pour éviter la perte de précision (LossySetitemError)
        df["original_amount"] = df["amount"].astype(float)
        df["original_fee"] = df["fee"].astype(float)
        df["original_price"] = df["price"].astype(float)
        df["amount"] = df["amount"].astype(float)
        df["fee"] = df["fee"].astype(float)
        df["price"] = df["price"].astype(float)
        df["fx_rate"] = 1.0

        for index, row in df.iterrows():
            tx_currency = str(row["currency"]).upper() if pd.notna(row["currency"]) else portfolio_currency
            symbol = row["symbol"]
            tx_type = row["type"]
            date_str = str(row["date"])

            stock_currency = (
                self.__stock_db.get_currency(symbol).upper()
                if pd.notna(symbol) and self.__stock_db.get_currency(symbol)
                else tx_currency
            )

            # Normalisation vers la devise native de l'actif (original_*)
            if tx_currency != stock_currency:
                rate_tx_to_stock = self.__get_exchange_rate(date_str, tx_currency, stock_currency)
                if rate_tx_to_stock and rate_tx_to_stock > 0:
                    df.at[index, "original_amount"] = round(float(row["amount"]) * rate_tx_to_stock, 2)
                    df.at[index, "original_fee"] = round(float(row["fee"]) * rate_tx_to_stock, 2)
                    if tx_type in ("buy", "sell") and pd.notna(row["price"]):
                        df.at[index, "original_price"] = round(float(row["price"]) * rate_tx_to_stock, 2)

            # Conversion vers la devise du portefeuille
            if tx_currency != portfolio_currency:
                rate_tx_to_port = self.__get_exchange_rate(date_str, tx_currency, portfolio_currency)
                if rate_tx_to_port and rate_tx_to_port > 0:
                    df.at[index, "fx_rate"] = rate_tx_to_port
                    df.at[index, "amount"] = round(float(row["amount"]) * rate_tx_to_port, 2)
                    df.at[index, "fee"] = round(float(row["fee"]) * rate_tx_to_port, 2)
                    if tx_type in ("buy", "sell") and pd.notna(row["price"]):
                        df.at[index, "price"] = round(float(row["price"]) * rate_tx_to_port, 2)

        return df

    def __apply_currency_conversion_trade_republic(self, df: pd.DataFrame, portfolio_id: int) -> pd.DataFrame:
        """Convertit les montants, prix et frais selon la devise du portefeuille."""
        df = df.copy()

        df["fx_rate"] = 1.0
        df["original_price"] = df["price"]
        df["amount"] = df["original_amount"]
        df["fee"] = df["original_fee"]

        portfolio_currency = self.__stock_db.get_portfolio_currency(portfolio_id)

        if portfolio_currency == "EUR":
            usd_mask = df["currency"] == "USD"
            for index, row in df[usd_mask].iterrows():
                rate = self.__stock_db.get_rate(str(row["date"]), "EURUSD=X")

                if rate is not None and rate > 0:
                    df.at[index, "fx_rate"] = rate
                    df.at[index, "original_price"] = round(row["price"] * rate, 2)
                    df.at[index, "original_amount"] = round(row["amount"] * rate, 2)
                    df.at[index, "original_fee"] = round(row["fee"] * rate, 2)

            mask = df["type"].isin(["buy"])
            df.loc[mask, "amount"] = df.loc[mask, "amount"].round()

        else:
            for index, row in df.iterrows():
                rate = self.__stock_db.get_rate(str(row["date"]), "EURUSD=X")
                if rate is not None and rate > 0:
                    df.at[index, "fx_rate"] = 1 / rate

                    converted_price = round(row["original_price"] * rate, 2)
                    converted_amount = round(row["original_amount"] * rate, 2)
                    converted_fee = round(row["original_fee"] * rate, 2)

                    df.at[index, "amount"] = converted_amount
                    df.at[index, "fee"] = converted_fee

                    if row["type"] in ("buy", "sell", "dividend"):
                        df.at[index, "price"] = converted_price

                        symbol_currency = self.__stock_db.get_currency(row["symbol"])
                        if symbol_currency == "USD":
                            df.at[index, "original_amount"] = converted_amount
                            df.at[index, "original_fee"] = converted_fee

                            if row["type"] in ("buy", "sell"):
                                df.at[index, "original_price"] = converted_price

                    else:
                        df.at[index, "original_amount"] = converted_amount
                        df.at[index, "original_fee"] = converted_fee

        return df

    def __apply_unbundling_trade_republic(self, df: pd.DataFrame) -> pd.DataFrame:
        """Traite les opérations de scission (UNBUNDLING) en les convertissant en achats (BUY)."""
        df = df.copy()

        # Suppression des lignes d'unbundling avec 0 action (lignes techniques)
        df = df[~((df["type"] == "UNBUNDLING") & (df["shares"] <= 0))].copy()

        # Masque pour les lignes UNBUNDLING restantes (shares > 0)
        unbundling_mask = df["type"] == "UNBUNDLING"

        deposits = []

        # Complétion des informations pour chaque opération d'attribution
        for idx, row in df[unbundling_mask].iterrows():
            ticker = get_ticker_from_isin(row["symbol"])
            date_str = str(row["date"])
            shares = float(row["shares"])

            # Récupération du prix de clôture à la date donnée et de la devise
            close_price = self.__stock_db.get_rate(date_str, ticker) or 0.0
            stock_currency = self.__stock_db.get_currency(ticker)

            total_amount = round(shares * close_price, 2)

            # Mise à jour de la ligne courante en BUY
            df.at[idx, "price"] = close_price
            df.at[idx, "original_price"] = close_price
            df.at[idx, "amount"] = total_amount
            df.at[idx, "original_amount"] = total_amount
            df.at[idx, "currency"] = stock_currency
            df.at[idx, "fee"] = 0.0
            df.at[idx, "original_fee"] = 0.0
            df.at[idx, "type"] = "BUY"

            # Création de la ligne DEPOSIT correspondante
            deposit_row = row.copy()
            deposit_row["type"] = "DEPOSIT"
            deposit_row["amount"] = total_amount
            deposit_row["original_amount"] = total_amount
            deposit_row["currency"] = stock_currency
            deposit_row["price"] = 0.0
            deposit_row["original_price"] = 0.0
            deposit_row["shares"] = 0.0
            deposit_row["fee"] = 0.0
            deposit_row["original_fee"] = 0.0

            deposits.append(deposit_row)

        if deposits:
            df = pd.concat([df, pd.DataFrame(deposits)], ignore_index=True)

        return df.reset_index(drop=True)

    def __get_exchange_rate(self, date_str: str, from_curr: str, to_curr: str) -> float:
        """Récupère le taux de change entre deux devises avec fallback inversé."""
        if from_curr == to_curr:
            return 1.0

        # Tentative 1: Taux direct (ex: USDEUR=X)
        ticker_direct = f"{from_curr}{to_curr}=X"
        rate = self.__stock_db.get_rate(date_str, ticker_direct)
        if rate and float(rate) > 0:
            return float(rate)

        # Tentative 2: Inverse du taux (ex: 1 / EURUSD=X)
        ticker_inverse = f"{to_curr}{from_curr}=X"
        rate_inv = self.__stock_db.get_rate(date_str, ticker_inverse)
        if rate_inv and float(rate_inv) > 0:
            return 1.0 / float(rate_inv)

        return 1.0

    def update_bilan(self, portfolio_id: int, portfolio_name: str) -> None:
        """Coordonne la mise à jour complète des fichiers bilan pour un portefeuille."""

        # Supprime le dossier bilan du compte pour que les données soient à jour
        path = os.path.join(f"{self.__config['destination_path']}/stock", portfolio_name)
        if os.path.exists(path):
            shutil.rmtree(path)

        portfolio_tracker = PortfolioTracker(self.__stock_db, portfolio_id)
        if not portfolio_tracker.run():
            return

        file_name = f"{self.__config['destination_path']}/stock/{portfolio_name}/Bilan {portfolio_name}"
        
        generate_rapport(
            self.__stock_db,
            portfolio_id,
            portfolio_tracker,
            f"{file_name}.html",
        )

        currency = self.__stock_db.get_portfolio_currency(portfolio_id)
        currency_symbol = None
        if currency == "EUR":
            currency_symbol = "€"
        elif currency == "USD":
            currency_symbol = "$"

        excel_generator = StockExcelGenerator(portfolio_tracker, portfolio_name, f"{file_name}.xlsx", currency_symbol)
        excel_generator.generate_report()

    @staticmethod
    def __apply_merge_trade_repulic(df: pd.DataFrame) -> pd.DataFrame:
        # Identifier les lignes d'absorption (anciennes actions retirées) et d'attribution (nouvelles actions)
        merger_out = df[(df["type"] == "MERGER") & (df["shares"] < 0)].copy()
        merger_in = df[(df["type"] == "MERGER") & (df["shares"] > 0)].copy()

        # Clé de correspondance basée sur la valeur absolue du nombre d'actions
        merger_out["abs_shares"] = merger_out["shares"].abs()
        merger_in["abs_shares"] = merger_in["shares"].abs()

        # Association des paires (ancien symbole -> nouveau symbole)
        merger_pairs = pd.merge(
            merger_out,
            merger_in,
            on=["date", "name", "abs_shares", "portfolio_id"],
            suffixes=("_old", "_new"),
        )

        # Dictionnaire de remplacement : {ancien_symbole: nouveau_symbole}
        symbol_replacement = dict(zip(merger_pairs["symbol_old"], merger_pairs["symbol_new"]))

        # Remplacement de l'ancien symbole partout dans le DataFrame
        if symbol_replacement:
            df["symbol"] = df["symbol"].replace(symbol_replacement)

        # Suppression des lignes MERGER devenues inutiles
        df = df[df["type"] != "MERGER"].reset_index(drop=True)

        return df

    @staticmethod
    def __apply_split_trade_republic(df: pd.DataFrame) -> pd.DataFrame:
        """Met à jour l'ancien symbole par le nouveau dans les transactions précédentes lors d'un SPLIT/changement d'ISIN."""
        df = df.copy()

        split_mask = df["type"] == "SPLIT"

        # Traitement des couples de lignes de split
        for idx, row in df[split_mask & (df["shares"] > 0)].iterrows():
            date = row["date"]
            new_isin = row["symbol"]
            new_ticker = get_ticker_from_isin(new_isin)

            # Recherche de la ligne négative associée à la même date pour trouver l'ancien symbole/ISIN
            old_split_row = df[split_mask & (df["shares"] < 0) & (df["date"] == date)]

            if not old_split_row.empty:
                old_isin = old_split_row.iloc[0]["symbol"]
                old_ticker = get_ticker_from_isin(old_isin)

                # Si le symbole a effectivement changé, on met à jour l'historique précédent
                if old_ticker != new_ticker:
                    # Filtre pour ne garder que les identifiants non nuls
                    targets_to_replace = [
                        item for item in [old_isin, old_ticker] if pd.notna(item) and item is not None
                    ]

                    if targets_to_replace:
                        df.loc[df["symbol"].isin(targets_to_replace), "symbol"] = new_ticker

        # Suppression des lignes techniques de SPLIT (positives et négatives)
        df = df[~split_mask].copy()

        return df.reset_index(drop=True)

    @staticmethod
    def __aggregate_similar_trades(df: pd.DataFrame) -> pd.DataFrame:
        """Combine les lignes d'achats ou de ventes identiques (même date, symbol, type et price)."""
        df = df.copy()

        # Masque pour isoler uniquement les opérations TRADING (BUY/SELL)
        trade_mask = df["type"].isin(["BUY", "SELL"]) & (df["category"] == "TRADING")

        # Séparation du DataFrame en deux parties : à agréger et à conserver telle quelle
        trades_df = df[trade_mask].copy()
        other_df = df[~trade_mask].copy()

        if trades_df.empty:
            return df

        # Groupement par clés uniques d'exécution
        group_cols = ["date", "category", "type", "symbol", "price", "currency", "portfolio_id"]

        # Dictionnaire d'agrégation dynamique selon les colonnes présentes
        agg_dict = {
            "shares": "sum",
            "amount": "sum",
        }

        # Ajout optionnel des frais/taxes/montants originaux s'ils existent
        optional_sum_cols = ["fee", "tax", "original_amount", "original_fee"]
        for col in optional_sum_cols:
            if col in trades_df.columns:
                agg_dict[col] = "sum"

        # Pour les colonnes texte/métadonnées (ex: name, original_currency, fx_rate), on garde la 1ère valeur
        first_cols = ["name", "original_currency", "fx_rate"]
        for col in first_cols:
            if col in trades_df.columns:
                agg_dict[col] = "first"

        # Application du regroupement
        aggregated_trades = trades_df.groupby(group_cols, dropna=False, as_index=False).agg(agg_dict)

        # Reconstitution du DataFrame global et tri par date
        final_df = pd.concat([other_df, aggregated_trades], ignore_index=True)
        final_df = final_df.sort_values(by="date").reset_index(drop=True)

        return final_df
