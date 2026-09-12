import os
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import numpy as np
import pandas as pd
import yfinance as yf

from accounts.heritage.processing.processing import calculate_heritage
from accounts.stock.importers.data_extractor import DataExtractor
from accounts.stock.importers.fetch_stock import fetch_stock_data, get_ticker_from_isin
from accounts.stock.processing.compute_metrics import (
    calculate_stocks_correlation_matrix,
    calculate_volatility_portfolio,
    compute_deposit_evolution,
    compute_portfolio_repartition,
    monthly_simple_returns,
    portfolio_percentage_per_day,
    sharpe_ratio,
    sortino_ratio,
    weighted_average_correlation,
)
from accounts.stock.processing.portfolio_tracker import PortfolioTracker
from accounts.stock.reporting.stock_excel_generator import StockExcelGenerator
from accounts.stock.visualization.portfolio_exporter import chart_generate_rapport
from config import load_config
from dashboard.portfolio.transactions.components.transaction_edit_window import TransactionEditWindow
from utils.data_utils import remove_accents
from utils.loading_popup import LoadingPopup
from utils.window_utils import center_window_on_screen


class Transactions:
    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        """Initialise le composant Transactions et ses filtres/sélections."""
        self.__master = master
        self.__controller = controller
        self.__theme = controller.get_theme()
        self.__bank_db = controller.get_bank_db()
        self.__stock_db = controller.get_stock_db()
        self.__config = controller.get_config()
        self._sort_column = "date"
        self._sort_ascending = False
        self.__selected_transaction_ids = set()
        self.__column_filters = {}

    def display(self, stock_portfolio_row: pd.Series, page: int = 1) -> None:
        """Initialise la structure fixe (Header, Actions) et lance le chargement du tableau."""

        self.__controller.destroy_widgets()
        self.__selected_transaction_ids.clear()

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
        self.__account_actions_bar = ctk.CTkFrame(self.__master, fg_color="transparent")
        self.__account_actions_bar.pack(fill="x", padx=20, pady=10)

        self.__build_actions_bar(stock_portfolio_row)

        # Zone d'affichage
        self.__table_container_wrapper = ctk.CTkFrame(self.__master, fg_color="transparent")
        self.__table_container_wrapper.pack(fill="both", expand=True, padx=20, pady=10)

        # Premier chargement du tableau
        self.__update_table_content(stock_portfolio_row, page)

    def __build_actions_bar(self, stock_portfolio_row: pd.Series) -> None:
        """Construit la barre d'actions dynamiquement selon la sélection."""
        for widget in self.__account_actions_bar.winfo_children():
            widget.destroy()

        ctk.CTkButton(
            self.__account_actions_bar,
            text="Importer des transactions",
            fg_color=self.__theme["green"]["fg_color"],
            hover_color=self.__theme["green"]["hover_color"],
            command=lambda: self.__handle_import_process(stock_portfolio_row),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            self.__account_actions_bar,
            text="Ajouter une transaction",
            fg_color=self.__theme["green"]["fg_color"],
            hover_color=self.__theme["green"]["hover_color"],
            command=lambda: self.__handle_add_transaction(stock_portfolio_row),
        ).pack(side="left", padx=5)

        # Bouton de réinitialisation des filtres
        is_custom_sorted = hasattr(self, "_sort_column") and self._sort_column != "date"
        has_active_filters = len(self.__column_filters) > 0 or is_custom_sorted

        if has_active_filters:
            ctk.CTkButton(
                self.__account_actions_bar,
                text="Réinitialiser les filtres",
                width=150,
                height=28,
                fg_color="gray60",
                hover_color="gray50",
                font=("Arial", 12),
                command=lambda: (
                    self.__column_filters.clear(),
                    setattr(self, "_sort_column", "date"),
                    setattr(self, "_sort_ascending", False),
                    self.__update_table_content(stock_portfolio_row, 1),
                ),
            ).pack(side="right", padx=5)

        # Bouton de suppression groupée si des transactions sont sélectionnées
        if self.__selected_transaction_ids:
            ctk.CTkButton(
                self.__account_actions_bar,
                text=f"Supprimer la sélection ({len(self.__selected_transaction_ids)})",
                fg_color=self.__theme["red"]["fg_color"],
                hover_color=self.__theme["red"]["hover_color"],
                command=lambda: self.__handle_delete_selected_transactions(stock_portfolio_row),
            ).pack(side="right", padx=5)

    def __update_table_content(self, stock_portfolio_row: pd.Series, page: int) -> None:
        """Rafraîchit le tableau avec prise en compte des filtres par colonne."""

        self.__build_actions_bar(stock_portfolio_row)

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
                # Application des filtres par colonne
                df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
                df["year_str"] = df["date_dt"].dt.year.astype(str)

                for col_name, selected_vals in self.__column_filters.items():
                    if col_name == "Date":
                        if selected_vals:
                            df = df[df["year_str"].isin(selected_vals)]
                        else:
                            df = df.iloc[0:0]
                    elif col_name == "Devise du compte":
                        if selected_vals:
                            df = df[df["account_currency"].astype(str).isin(selected_vals)]
                        else:
                            df = df.iloc[0:0]
                    elif col_name == "Opération":
                        if selected_vals:
                            df = df[df["type"].astype(str).isin(selected_vals)]
                        else:
                            df = df.iloc[0:0]
                    elif col_name == "Nom":
                        if selected_vals:
                            df = df[df["name"].astype(str).isin(selected_vals)]
                        else:
                            df = df.iloc[0:0]
                    elif col_name == "Ticker":
                        if selected_vals:
                            df = df[df["ticker"].astype(str).isin(selected_vals)]
                        else:
                            df = df.iloc[0:0]
                    elif col_name in ["Quantité", "Prix", "Montant", "Frais"]:
                        col_key_map = {
                            "Quantité": "shares",
                            "Prix": "price",
                            "Montant": "amount",
                            "Frais": "fee",
                        }
                        target_col = col_key_map[col_name]
                        if selected_vals:
                            if isinstance(selected_vals, dict):
                                op = selected_vals.get("operator")
                                target = selected_vals.get("value")
                                if op == "Supérieur ou égal (>=)":
                                    df = df[df[target_col] >= target]
                                elif op == "Inférieur ou égal (<=)":
                                    df = df[df[target_col] <= target]
                                elif op == "Égal (=)":
                                    df = df[df[target_col] == target]
                            elif isinstance(selected_vals, list):
                                df = df[df[target_col].isin(selected_vals)]
                        else:
                            df = df.iloc[0:0]

                df = df.sort_values(by="date", ascending=True)
                df["id_view"] = range(1, len(df) + 1)

                if hasattr(self, "_sort_column") and self._sort_column:
                    df = df.sort_values(
                        by=[self._sort_column, "id_view"],
                        ascending=[self._sort_ascending, False],
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

                header_table.grid_columnconfigure(0, weight=0, minsize=40)
                header_table.grid_columnconfigure(1, weight=0, minsize=50)
                header_table.grid_columnconfigure((2, 3, 4, 5, 6, 7, 8, 9, 10), weight=1, uniform="group_trans")
                header_table.grid_columnconfigure(11, weight=0, minsize=90)

                page_ids = page_data["id"].tolist()
                all_page_selected = (
                    all(tr_id in self.__selected_transaction_ids for tr_id in page_ids) and len(page_ids) > 0
                )

                master_cb = ctk.CTkCheckBox(
                    header_table,
                    text="",
                    width=20,
                    checkbox_width=18,
                    checkbox_height=18,
                    command=lambda: self.__toggle_select_all_page(stock_portfolio_row, page, page_ids, master_cb),
                )
                master_cb.grid(row=0, column=0, padx=(10, 0), pady=5, sticky="w")
                if all_page_selected:
                    master_cb.select()

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
                    "Justificatifs",
                ]

                num_cols = ["Quantité", "Prix", "Montant", "Frais"]

                for i, col_name in enumerate(columns, start=1):
                    padx_val = (10, 20) if i == 1 else 5

                    if col_name in num_cols or col_name == "Justificatifs":
                        anchor_val = "center"
                        cell_sticky = "nsew"
                    elif i in [2, 3, 4, 5, 6]:
                        anchor_val = "w"
                        cell_sticky = "w"
                    else:
                        anchor_val = "center"
                        cell_sticky = "w"

                    cell_header_f = ctk.CTkFrame(header_table, fg_color="transparent")
                    cell_header_f.grid(row=0, column=i, padx=padx_val, pady=5, sticky=cell_sticky)

                    if col_name in num_cols or col_name == "Justificatifs":
                        inner_center_f = ctk.CTkFrame(cell_header_f, fg_color="transparent")
                        inner_center_f.pack(expand=True)

                        lbl = ctk.CTkLabel(
                            inner_center_f,
                            text=col_name,
                            font=("Arial", 14, "bold"),
                            text_color="black",
                            anchor="center",
                        )
                        lbl.pack(side="left")

                        if col_name in num_cols:
                            filter_btn = ctk.CTkButton(
                                inner_center_f,
                                text="▼",
                                width=18,
                                height=18,
                                font=("Arial", 9),
                                fg_color="transparent",
                                hover_color="gray70",
                                text_color="black",
                            )
                            filter_btn.configure(
                                command=lambda btn=filter_btn, c=col_name: self.__show_excel_filter_popup(
                                    btn, c, stock_portfolio_row, page, is_numeric=True
                                )
                            )
                            filter_btn.pack(side="left", padx=(4, 0))
                    else:
                        # Si c'est la colonne Ticker, on centre le contenu
                        if col_name == "Ticker":
                            cell_header_f.pack_configure(expand=True)
                            anchor_val = "center"

                        lbl = ctk.CTkLabel(
                            cell_header_f,
                            text=col_name,
                            font=("Arial", 14, "bold"),
                            text_color="black",
                            anchor=anchor_val,
                        )
                        lbl.pack(side="left")

                        if col_name not in ["#", "Justificatifs"]:
                            filter_btn = ctk.CTkButton(
                                cell_header_f,
                                text="▼",
                                width=18,
                                height=18,
                                font=("Arial", 9),
                                fg_color="transparent",
                                hover_color="gray70",
                                text_color="black",
                            )
                            filter_btn.configure(
                                command=lambda btn=filter_btn, c=col_name: self.__show_excel_filter_popup(
                                    btn, c, stock_portfolio_row, page
                                )
                            )
                            filter_btn.pack(side="left", padx=(4, 0))

                    if col_name == "#":
                        lbl.configure(width=50, anchor="center")

                # Zone dédiée aux lignes
                rows_container = ctk.CTkFrame(self.__table_container_wrapper, fg_color="transparent", height=680)
                rows_container.pack(fill="x")
                rows_container.pack_propagate(False)

                for i, (_, transaction) in enumerate(page_data.iterrows(), 1):
                    tr_id = transaction["id"]
                    is_selected = tr_id in self.__selected_transaction_ids

                    default_bg = "gray95" if i % 2 == 0 else "gray90"
                    hover_bg = "gray82"

                    row_f = ctk.CTkFrame(rows_container, fg_color=default_bg, height=30, cursor="hand2")
                    row_f.pack(fill="x", pady=1)

                    row_f.grid_columnconfigure(0, weight=0, minsize=40)
                    row_f.grid_columnconfigure(1, weight=0, minsize=50)
                    row_f.grid_columnconfigure((2, 3, 4, 5, 6, 7, 8, 9, 10), weight=1, uniform="group_trans")
                    row_f.grid_columnconfigure(11, weight=0, minsize=90)

                    cb_var = ctk.BooleanVar(value=is_selected)

                    row_cb = ctk.CTkCheckBox(
                        row_f,
                        text="",
                        width=20,
                        checkbox_width=18,
                        checkbox_height=18,
                        variable=cb_var,
                        fg_color=default_bg,
                        border_color="black",
                        checkmark_color="black",
                        command=lambda tid=tr_id: self.__toggle_select_transaction(tid, stock_portfolio_row, page),
                    )
                    row_cb.grid(row=0, column=0, padx=(10, 0), sticky="w")
                    if tr_id in self.__selected_transaction_ids:
                        row_cb.select()

                    curr_symbol = currency_symbols.get(
                        str(transaction["account_currency"]).upper(), str(transaction["account_currency"])
                    )

                    lbl_id = ctk.CTkLabel(
                        row_f,
                        text=str(transaction["id_view"]),
                        font=("Arial", 11, "italic"),
                        width=50,
                        anchor="center",
                        fg_color=default_bg,
                    )
                    lbl_id.grid(row=0, column=1, padx=(10, 20), sticky="nsew")

                    lbl_date = ctk.CTkLabel(row_f, text=str(transaction["date"]), anchor="w", fg_color=default_bg)
                    lbl_date.grid(row=0, column=2, padx=5, sticky="nsew")

                    lbl_curr = ctk.CTkLabel(
                        row_f, text=str(transaction["account_currency"]), anchor="center", fg_color=default_bg
                    )
                    lbl_curr.grid(row=0, column=3, padx=5, sticky="nsew")

                    type_key = str(transaction["type"]).lower()
                    type_text = type_op.get(type_key, type_key.capitalize())
                    lbl_type = ctk.CTkLabel(row_f, text=type_text, anchor="w", fg_color=default_bg)
                    lbl_type.grid(row=0, column=4, padx=5, sticky="nsew")

                    name_val = str(transaction["name"]) if pd.notna(transaction["name"]) else "-"
                    lbl_name = ctk.CTkLabel(row_f, text=name_val, anchor="w", fg_color=default_bg)
                    lbl_name.grid(row=0, column=5, padx=5, sticky="nsew")

                    ticker_val = str(transaction["ticker"]) if pd.notna(transaction["ticker"]) else "-"
                    lbl_ticker = ctk.CTkLabel(row_f, text=ticker_val, anchor="center", fg_color=default_bg)
                    lbl_ticker.grid(row=0, column=6, padx=5, sticky="nsew")

                    qty_val = transaction["shares"]
                    qty_str = f"{qty_val:g}" if pd.notna(qty_val) else "-"
                    lbl_qty = ctk.CTkLabel(row_f, text=qty_str, anchor="center", fg_color=default_bg)
                    lbl_qty.grid(row=0, column=7, padx=5, sticky="nsew")

                    price_val = transaction["price"]
                    price_str = (
                        f"{price_val:,.2f}".replace(",", " ") + f" {curr_symbol}" if pd.notna(price_val) else "-"
                    )
                    lbl_price = ctk.CTkLabel(row_f, text=price_str, anchor="center", fg_color=default_bg)
                    lbl_price.grid(row=0, column=8, padx=5, sticky="nsew")

                    amt = transaction["amount"]
                    formatted_amt = f"{amt:,.2f}".replace(",", " ") + f" {curr_symbol}"
                    op_type = str(transaction["type"]).lower()
                    is_incoming = op_type in ["sell", "dividend", "interest", "deposit"]
                    color = self.__theme["green"]["fg_color"] if is_incoming else self.__theme["red"]["fg_color"]

                    lbl_amt = ctk.CTkLabel(
                        row_f,
                        text=formatted_amt,
                        text_color=color,
                        font=("Arial", 12, "bold"),
                        anchor="center",
                        fg_color=default_bg,
                    )
                    lbl_amt.grid(row=0, column=9, padx=5, sticky="nsew")

                    fee_val = transaction["fee"]
                    fee_str = f"{fee_val:,.2f}".replace(",", " ") + f" {curr_symbol}" if fee_val > 0 else "-"
                    lbl_fee = ctk.CTkLabel(row_f, text=fee_str, anchor="center", fg_color=default_bg)
                    lbl_fee.grid(row=0, column=10, padx=5, sticky="nsew")

                    attachments = self.__stock_db.get_transaction_attachments(tr_id)
                    has_attachments = len(attachments) > 0

                    att_text = f"Fichier ({len(attachments)})" if has_attachments else "Fichier"
                    att_color = self.__theme["blue_01"]["fg_color"] if has_attachments else "gray60"
                    att_hover = self.__theme["blue_01"]["hover_color"] if has_attachments else "gray50"

                    att_btn = ctk.CTkButton(
                        row_f,
                        text=att_text,
                        width=95,
                        height=24,
                        corner_radius=6,
                        font=("Arial", 11, "bold"),
                        fg_color=att_color,
                        hover_color=att_hover,
                        command=lambda o=transaction: self.__handle_attachments_modal(o, stock_portfolio_row, page),
                    )
                    att_btn.grid(row=0, column=11, padx=5, pady=4)

                    widgets_in_row = [
                        row_f,
                        lbl_id,
                        lbl_date,
                        lbl_curr,
                        lbl_type,
                        lbl_name,
                        lbl_ticker,
                        lbl_qty,
                        lbl_price,
                        lbl_amt,
                        lbl_fee,
                    ]

                    def on_enter(event, wf=widgets_in_row, cb=row_cb):
                        for w in wf:
                            w.configure(fg_color=hover_bg)
                        cb.configure(fg_color=hover_bg)

                    def on_leave(event, wf=widgets_in_row, cb=row_cb, bg=default_bg):
                        for w in wf:
                            w.configure(fg_color=bg)
                        cb.configure(fg_color=bg)

                    for w in widgets_in_row:
                        w.bind("<Enter>", on_enter)
                        w.bind("<Leave>", on_leave)
                        if w != att_btn:
                            w.bind(
                                "<Button-1>",
                                lambda event, o=transaction: self.__handle_edit_transaction(o, stock_portfolio_row),
                            )

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

    def __show_excel_filter_popup(self, button, col_name, stock_portfolio_row, page, is_numeric=False):
        """Affiche une fenêtre pop-up de filtre dynamique (style Excel) adaptée aux transactions."""

        df_all = self.__stock_db.get_transactions_by_stock_account(stock_portfolio_row["id"])
        if df_all.empty:
            return

        # Filtrage en cascade
        df_filtered = df_all.copy()
        df_filtered["date_dt"] = pd.to_datetime(df_filtered["date"], errors="coerce")
        df_filtered["year_str"] = df_filtered["date_dt"].dt.year.astype(str)

        col_db_map = {
            "Quantité": "shares",
            "Prix": "price",
            "Montant": "amount",
            "Frais": "fee",
        }

        for col_k, selected_vals in self.__column_filters.items():
            if col_k == col_name:
                continue

            if col_k == "Date" and selected_vals:
                df_filtered = df_filtered[df_filtered["year_str"].isin(selected_vals)]
            elif col_k == "Devise du compte" and selected_vals:
                df_filtered = df_filtered[df_filtered["account_currency"].astype(str).isin(selected_vals)]
            elif col_k == "Opération" and selected_vals:
                df_filtered = df_filtered[df_filtered["type"].astype(str).isin(selected_vals)]
            elif col_k == "Nom" and selected_vals:
                df_filtered = df_filtered[df_filtered["name"].astype(str).isin(selected_vals)]
            elif col_k == "Ticker" and selected_vals:
                df_filtered = df_filtered[df_filtered["ticker"].astype(str).isin(selected_vals)]
            elif col_k in col_db_map and selected_vals:
                target_col = col_db_map[col_k]
                if isinstance(selected_vals, dict):
                    op = selected_vals.get("operator")
                    target = selected_vals.get("value")
                    if op == "Supérieur ou égal (>=)":
                        df_filtered = df_filtered[df_filtered[target_col] >= target]
                    elif op == "Inférieur ou égal (<=)":
                        df_filtered = df_filtered[df_filtered[target_col] <= target]
                    elif op == "Égal (=)":
                        df_filtered = df_filtered[df_filtered[target_col] == target]
                elif isinstance(selected_vals, list):
                    df_filtered = df_filtered[df_filtered[target_col].isin(selected_vals)]

        popup_width = 280
        popup_height = 250 if is_numeric else 410

        x = button.winfo_rootx()
        if is_numeric:
            x = button.winfo_rootx() + button.winfo_width() - popup_width

        y = button.winfo_rooty() + button.winfo_height()

        popup = ctk.CTkToplevel(button.winfo_toplevel())
        popup.wm_overrideredirect(True)
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        popup.grab_set()

        main_frame = ctk.CTkFrame(popup, fg_color="gray90", corner_radius=6)
        main_frame.pack(fill="both", expand=True, padx=2, pady=2)

        # Filtre spécifique numérique (Quantité, Prix, Montant, Frais)
        if is_numeric:
            sort_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            sort_frame.pack(fill="x", padx=10, pady=(8, 4))

            target_db_col = col_db_map[col_name]

            ctk.CTkButton(
                sort_frame,
                text="Trier du plus petit au plus grand",
                anchor="w",
                fg_color="transparent",
                text_color="black",
                hover_color="gray80",
                height=22,
                font=("Arial", 11),
                command=lambda: (
                    popup.destroy(),
                    setattr(self, "_sort_column", target_db_col),
                    setattr(self, "_sort_ascending", True),
                    self.__update_table_content(stock_portfolio_row, page),
                ),
            ).pack(fill="x")

            ctk.CTkButton(
                sort_frame,
                text="Trier du plus grand au plus petit",
                anchor="w",
                fg_color="transparent",
                text_color="black",
                hover_color="gray80",
                height=22,
                font=("Arial", 11),
                command=lambda: (
                    popup.destroy(),
                    setattr(self, "_sort_column", target_db_col),
                    setattr(self, "_sort_ascending", False),
                    self.__update_table_content(stock_portfolio_row, page),
                ),
            ).pack(fill="x")

            ctk.CTkFrame(main_frame, height=1, fg_color="gray70").pack(fill="x", padx=10, pady=6)

            current_num_filter = self.__column_filters.get(col_name, {})

            op_var = ctk.StringVar(
                value=current_num_filter.get("operator", "Supérieur ou égal (>=)")
                if isinstance(current_num_filter, dict)
                else "Supérieur ou égal (>=)"
            )
            op_dropdown = ctk.CTkOptionMenu(
                main_frame,
                values=["Supérieur ou égal (>=)", "Inférieur ou égal (<=)", "Égal (=)"],
                variable=op_var,
                height=28,
            )
            op_dropdown.pack(fill="x", padx=10, pady=(5, 5))

            val_var = ctk.StringVar(
                value=str(current_num_filter.get("value", "")) if isinstance(current_num_filter, dict) else ""
            )
            val_entry = ctk.CTkEntry(
                main_frame,
                textvariable=val_var,
                placeholder_text="Valeur (ex: 50.00)",
                height=28,
            )
            val_entry.pack(fill="x", padx=10, pady=(5, 10))

            def apply_numeric_filter():
                raw_val = val_var.get().replace(",", ".").strip()
                if raw_val:
                    try:
                        target_val = float(raw_val)
                        self.__column_filters[col_name] = {
                            "operator": op_var.get(),
                            "value": target_val,
                        }
                    except ValueError:
                        messagebox.showerror("Erreur", "Veuillez saisir un nombre valide.")
                        return
                else:
                    self.__column_filters.pop(col_name, None)

                popup.destroy()
                self.__update_table_content(stock_portfolio_row, page)

            btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent", height=40)
            btn_frame.pack(fill="x", padx=10, pady=10)

            ctk.CTkButton(
                btn_frame,
                text="OK",
                width=115,
                height=28,
                fg_color=self.__theme["blue_01"]["fg_color"],
                command=apply_numeric_filter,
            ).pack(side="left", padx=(0, 5))

            ctk.CTkButton(
                btn_frame,
                text="Annuler",
                width=115,
                height=28,
                fg_color="gray60",
                hover_color="gray50",
                command=popup.destroy,
            ).pack(side="right", padx=(5, 0))

            return

        # Autres colonnes COLONNES (Date, Devise, Opération, Nom, Ticker)
        if col_name == "Date":
            unique_values = sorted([str(x) for x in df_filtered["year_str"].dropna().unique()])
        elif col_name == "Devise du compte":
            unique_values = sorted([str(x) for x in df_filtered["account_currency"].dropna().unique()])
        elif col_name == "Opération":
            unique_values = sorted([str(x) for x in df_filtered["type"].dropna().unique()])
        elif col_name == "Nom":
            unique_values = sorted([str(x) for x in df_filtered["name"].dropna().unique()])
        elif col_name == "Ticker":
            unique_values = sorted([str(x) for x in df_filtered["ticker"].dropna().unique()])
        else:
            unique_values = []

        if col_name == "Date":
            sort_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            sort_frame.pack(fill="x", padx=10, pady=(8, 4))

            ctk.CTkButton(
                sort_frame,
                text="Trier de la plus ancienne à la plus récente",
                anchor="w",
                fg_color="transparent",
                text_color="black",
                hover_color="gray80",
                height=22,
                font=("Arial", 11),
                command=lambda: (
                    popup.destroy(),
                    setattr(self, "_sort_column", "date"),
                    setattr(self, "_sort_ascending", True),
                    self.__update_table_content(stock_portfolio_row, page),
                ),
            ).pack(fill="x")
            ctk.CTkButton(
                sort_frame,
                text="Trier de la plus récente à la plus ancienne",
                anchor="w",
                fg_color="transparent",
                text_color="black",
                hover_color="gray80",
                height=22,
                font=("Arial", 11),
                command=lambda: (
                    popup.destroy(),
                    setattr(self, "_sort_column", "date"),
                    setattr(self, "_sort_ascending", False),
                    self.__update_table_content(stock_portfolio_row, page),
                ),
            ).pack(fill="x")

            ctk.CTkFrame(main_frame, height=1, fg_color="gray70").pack(fill="x", padx=10, pady=4)

        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(main_frame, textvariable=search_var, placeholder_text="Rechercher", height=28)
        search_entry.pack(fill="x", padx=10, pady=(5, 5))

        scroll_frame = ctk.CTkScrollableFrame(main_frame, fg_color="transparent", height=180)
        scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)

        saved_selected = self.__column_filters.get(col_name, None)
        if saved_selected is not None:
            current_selected = [val for val in saved_selected if val in unique_values]
            if not current_selected:
                current_selected = unique_values
        else:
            current_selected = unique_values

        vars_dict = {}

        select_all_var = ctk.BooleanVar(value=all(val in current_selected for val in unique_values))

        def toggle_select_all():
            state = select_all_var.get()
            for v in vars_dict.values():
                v.set(state)

        select_all_cb = ctk.CTkCheckBox(
            scroll_frame, text="(Sélectionner tout)", variable=select_all_var, command=toggle_select_all
        )
        select_all_cb.pack(anchor="w", padx=5, pady=2)

        checkboxes = []
        for val in unique_values:
            v = ctk.BooleanVar(value=val in current_selected)
            vars_dict[val] = v
            display_text = str(val)
            cb = ctk.CTkCheckBox(scroll_frame, text=display_text, variable=v)
            cb.pack(anchor="w", padx=5, pady=2)
            checkboxes.append((val, cb))

        def filter_checkboxes(*args):
            query = search_var.get().lower()
            for val, cb in checkboxes:
                display_str = str(val)
                if query in display_str.lower():
                    cb.pack(anchor="w", padx=5, pady=2)
                else:
                    cb.pack_forget()

        search_var.trace("w", filter_checkboxes)

        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent", height=40)
        btn_frame.pack(fill="x", padx=10, pady=10)
        btn_frame.pack_propagate(False)

        def apply_filter():
            selected = [val for val, v in vars_dict.items() if v.get()]
            if len(selected) == len(unique_values):
                self.__column_filters.pop(col_name, None)
            else:
                self.__column_filters[col_name] = selected
            popup.destroy()
            self.__update_table_content(stock_portfolio_row, page)

        ok_btn = ctk.CTkButton(
            btn_frame,
            text="OK",
            width=115,
            height=28,
            fg_color=self.__theme["blue_01"]["fg_color"],
            command=apply_filter,
        )
        ok_btn.pack(side="left", padx=(0, 5))

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Annuler",
            width=115,
            height=28,
            fg_color="gray60",
            hover_color="gray50",
            command=popup.destroy,
        )
        cancel_btn.pack(side="right", padx=(5, 0))

    def __toggle_select_transaction(self, transaction_id: int, stock_portfolio_row: pd.Series, page: int) -> None:
        """Ajoute ou retire une transaction de la sélection multiple."""
        if transaction_id in self.__selected_transaction_ids:
            self.__selected_transaction_ids.remove(transaction_id)
        else:
            self.__selected_transaction_ids.add(transaction_id)
        self.__build_actions_bar(stock_portfolio_row)

    def __toggle_select_all_page(
        self, stock_portfolio_row: pd.Series, page: int, page_ids: list, master_cb: ctk.CTkCheckBox
    ) -> None:
        """Sélectionne ou désélectionne toutes les transactions de la page courante."""
        all_selected = all(tr_id in self.__selected_transaction_ids for tr_id in page_ids)
        if all_selected:
            for tr_id in page_ids:
                self.__selected_transaction_ids.discard(tr_id)
        else:
            for tr_id in page_ids:
                self.__selected_transaction_ids.add(tr_id)
        self.__build_actions_bar(stock_portfolio_row)
        self.__update_table_content(stock_portfolio_row, page)

    def __handle_delete_selected_transactions(self, stock_portfolio_row: pd.Series) -> None:
        """Gère la suppression groupée des transactions sélectionnées."""
        if not self.__selected_transaction_ids:
            return

        if not messagebox.askyesno(
            "Confirmation",
            f"Souhaitez-vous vraiment supprimer les {len(self.__selected_transaction_ids)} transaction(s) sélectionnée(s) ?",
        ):
            return

        loading_win = LoadingPopup(self.__master, "Suppression en cours...")

        def task():
            try:
                for tr_id in list(self.__selected_transaction_ids):
                    self.__stock_db.delete_transaction(tr_id)
                self.__selected_transaction_ids.clear()
                self.update_bilan(stock_portfolio_row["id"], stock_portfolio_row["name"])
            except Exception:
                self.__master.after(0, lambda: messagebox.showerror("Erreur", "Erreur lors de la suppression groupée"))
            finally:
                self.__master.after(0, lambda: self.__on_process_complete(loading_win, stock_portfolio_row))

        threading.Thread(target=task, daemon=True).start()

    def __handle_attachments_modal(self, transaction: pd.Series, stock_portfolio_row: pd.Series, page: int) -> None:
        """Ouvre une fenêtre modale pour gérer les pièces justificatives d'une transaction."""
        currency_symbols = {"EUR": "€", "USD": "$"}
        curr_symbol = currency_symbols.get(
            str(transaction["account_currency"]).upper(), str(transaction["account_currency"])
        )

        att_win = ctk.CTkToplevel(self.__master)
        att_win.title("Gestion des pièces justificatives")

        width, height = 940, 530
        att_win.geometry(f"{width}x{height}")
        att_win.minsize(width, height)
        center_window_on_screen(att_win, width, height, 2)

        att_win.grab_set()

        header_card = ctk.CTkFrame(att_win, fg_color="gray85", corner_radius=10)
        header_card.pack(fill="x", padx=25, pady=20)

        ctk.CTkLabel(header_card, text="Pièces justificatives de la transaction", font=("Arial", 16, "bold")).pack(
            anchor="w", padx=15, pady=(12, 5)
        )

        amt = transaction["amount"]
        formatted_amt = f"{amt:,.2f}".replace(",", " ") + f" {curr_symbol}"
        op_type = str(transaction["type"]).lower()
        is_incoming = op_type in ["sell", "dividend", "interest", "deposit"]
        amt_color = self.__theme["green"]["fg_color"] if is_incoming else self.__theme["red"]["fg_color"]

        # Ligne 1 : Date | Opération | Montant
        info_row_1 = ctk.CTkFrame(header_card, fg_color="transparent")
        info_row_1.pack(fill="x", padx=15, pady=(0, 6))

        ctk.CTkLabel(info_row_1, text="Date :", font=("Arial", 13, "bold")).pack(side="left")
        ctk.CTkLabel(info_row_1, text=f"{transaction['date']}", font=("Arial", 13)).pack(side="left", padx=(4, 15))

        ctk.CTkLabel(info_row_1, text="Opération :", font=("Arial", 13, "bold")).pack(side="left")
        ctk.CTkLabel(info_row_1, text=f"{transaction['type']}", font=("Arial", 13)).pack(side="left", padx=(4, 15))

        ctk.CTkLabel(info_row_1, text="Montant :", font=("Arial", 13, "bold")).pack(side="left")
        ctk.CTkLabel(info_row_1, text=f"{formatted_amt}", font=("Arial", 13, "bold"), text_color=amt_color).pack(
            side="left", padx=(4, 0)
        )

        # Ligne 2 : Ticker | Nom (créée uniquement si le ticker est valide)
        ticker_val = transaction["ticker"]
        if pd.notna(ticker_val) and str(ticker_val).strip() != "":
            info_row_2 = ctk.CTkFrame(header_card, fg_color="transparent")
            info_row_2.pack(fill="x", padx=15, pady=(0, 6))

            ctk.CTkLabel(info_row_2, text="Ticker :", font=("Arial", 13, "bold")).pack(side="left")
            ctk.CTkLabel(info_row_2, text=f"{ticker_val}", font=("Arial", 13)).pack(side="left", padx=(4, 20))

            ctk.CTkLabel(info_row_2, text="Nom :", font=("Arial", 13, "bold")).pack(side="left")
            ctk.CTkLabel(info_row_2, text=f"{transaction['name']}", font=("Arial", 13)).pack(side="left", padx=(4, 0))

        # Ligne 3 : Commentaire
        raw_comment = transaction["comment"]
        comment_display = "" if raw_comment is None or str(raw_comment).lower() == "nan" else str(raw_comment)

        info_row_3 = ctk.CTkFrame(header_card, fg_color="transparent")
        info_row_3.pack(fill="x", padx=15, pady=(0, 12))

        ctk.CTkLabel(info_row_3, text="Commentaire :", font=("Arial", 13, "bold")).pack(side="left", anchor="n")

        comment_textbox = ctk.CTkTextbox(info_row_3, height=55, wrap="word")
        comment_textbox.insert("1.0", comment_display)
        comment_textbox.configure(state="disabled")
        comment_textbox.pack(side="left", fill="x", expand=True, padx=(4, 0))

        list_frame = ctk.CTkScrollableFrame(att_win, width=580, height=220, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=25, pady=(0, 15))

        self.__refresh_attachment_list(transaction["id"], list_frame, stock_portfolio_row, page)

        footer_frame = ctk.CTkFrame(att_win, fg_color="transparent")
        footer_frame.pack(fill="x", padx=25, pady=(0, 20))

        ctk.CTkButton(
            footer_frame,
            text="+ Ajouter un fichier",
            height=35,
            font=("Arial", 13, "bold"),
            fg_color=self.__theme["green"]["fg_color"],
            hover_color=self.__theme["green"]["hover_color"],
            command=lambda: self.__add_attachment_file(transaction["id"], list_frame, stock_portfolio_row, page),
        ).pack(fill="x")

    def __refresh_attachment_list(
        self, tr_id: int, list_frame: ctk.CTkScrollableFrame, stock_portfolio_row: pd.Series, page: int
    ) -> None:
        """Rafraîchit la liste des pièces justificatives dans la modale."""
        for w in list_frame.winfo_children():
            w.destroy()

        attachments = self.__stock_db.get_transaction_attachments(tr_id)
        if not attachments:
            empty_lbl = ctk.CTkLabel(
                list_frame,
                text="Aucun document rattaché pour le moment.",
                font=("Arial", 13, "italic"),
                text_color="gray50",
            )
            empty_lbl.pack(pady=30)
            return

        for att in attachments:
            row = ctk.CTkFrame(list_frame, fg_color="gray90", height=45, corner_radius=6)
            row.pack(fill="x", pady=4)
            row.pack_propagate(False)

            full_name = att["file_name"]
            max_len = 35
            display_name = (full_name[:max_len] + "...") if len(full_name) > max_len else full_name

            ctk.CTkLabel(row, text=display_name, anchor="w", font=("Arial", 13)).pack(side="left", padx=15)

            ctk.CTkButton(
                row,
                text="Supprimer",
                width=80,
                height=26,
                fg_color=self.__theme["red"]["fg_color"],
                hover_color=self.__theme["red"]["hover_color"],
                command=lambda aid=att["id"]: (
                    self.__stock_db.delete_transaction_attachment(aid),
                    self.__refresh_attachment_list(tr_id, list_frame, stock_portfolio_row, page),
                    self.__update_table_content(stock_portfolio_row, page),
                ),
            ).pack(side="right", padx=8)

            ctk.CTkButton(
                row,
                text="Télécharger",
                width=95,
                height=26,
                fg_color=self.__theme["blue_01"]["fg_color"],
                hover_color=self.__theme["blue_01"]["hover_color"],
                command=lambda aid=att["id"]: self.__download_attachment(aid),
            ).pack(side="right", padx=2)

            ctk.CTkButton(
                row,
                text="Aperçu",
                width=70,
                height=26,
                fg_color="gray50",
                hover_color="gray40",
                command=lambda aid=att["id"]: self.__preview_attachment(aid),
            ).pack(side="right", padx=2)

    def __add_attachment_file(
        self, tr_id: int, list_frame: ctk.CTkScrollableFrame, stock_portfolio_row: pd.Series, page: int
    ) -> None:
        """Permet à l'utilisateur de sélectionner et d'ajouter un fichier justificatif."""
        file_path = filedialog.askopenfilename(title="Sélectionner un fichier justificatif")
        if file_path:
            path_obj = Path(file_path)
            with open(path_obj, "rb") as f:
                file_bytes = f.read()
            self.__stock_db.add_transaction_attachment(tr_id, file_bytes, path_obj.name, path_obj.suffix)
            self.__refresh_attachment_list(tr_id, list_frame, stock_portfolio_row, page)
            self.__update_table_content(stock_portfolio_row, page)

    def __download_attachment(self, attachment_id: int) -> None:
        """Télécharge et enregistre la pièce justificative sur le disque."""
        data = self.__stock_db.get_transaction_attachment_data(attachment_id)
        if not data:
            messagebox.showerror("Erreur", "Fichier introuvable.")
            return

        save_path = filedialog.asksaveasfilename(initialfile=data["file_name"])
        if save_path:
            with open(save_path, "wb") as f:
                f.write(data["file_data"])
            messagebox.showinfo("Succès", "Fichier téléchargé avec succès.")

    def __preview_attachment(self, attachment_id: int) -> None:
        """Ouvre un aperçu temporaire de la pièce justificative."""
        data = self.__stock_db.get_transaction_attachment_data(attachment_id)
        if not data:
            messagebox.showerror("Erreur", "Fichier introuvable.")
            return

        suffix = Path(data["file_name"]).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data["file_data"])
            tmp_path = tmp.name

        try:
            if os.name == "nt":
                os.startfile(tmp_path)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir l'aperçu : {e}")

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

    def __on_import_error(self, error: Exception, loading_win: LoadingPopup | None) -> None:
        """Rappel exécuté sur le thread principal en cas d'erreur."""
        if loading_win is not None and loading_win.winfo_exists():
            loading_win.close()

        # Détection des erreurs de connexion Internet (ConnectionError ou mots-clés DNS / HTTPS)
        error_str = str(error)
        if (
            isinstance(error, ConnectionError)
            or "NameResolutionError" in error_str
            or "HTTPSConnectionPool" in error_str
        ):
            messagebox.showerror(
                "Connexion Internet requise",
                "Impossible de contacter le serveur : pas de connexion à Internet.\n"
                "Veuillez vérifier votre connexion Internet et refaire la manipulation.",
            )
        else:
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

    def update_bilan(self, portfolio_id: int | None = None, portfolio_name: str | None = None) -> None:
        """Coordonne la mise à jour complète des fichiers bilan pour un portefeuille."""
        paths = []
        base_dest = Path(self.__config["destination_path"])
        heritage_path = base_dest / "heritage" / "heritage_stock"
        paths.append(heritage_path)
        paths.append(base_dest / "heritage" / "heritage_global.html")
        paths.append(base_dest / "heritage" / "heritage_global.xlsx")

        if portfolio_id is not None:
            stock_path = base_dest / "stock" / portfolio_name
            paths.append(stock_path)

        # Nettoyage des répertoires existants
        for path in paths:
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()

        portfolio_tracker = PortfolioTracker(self.__stock_db, portfolio_id)
        if portfolio_tracker.run():
            if portfolio_id is not None:
                chart_generate_rapport(self.__stock_db, portfolio_name, stock_path, portfolio_tracker, portfolio_id)
                currency_symbol = self.__stock_db.get_portfolio_currency_symbol(portfolio_id)
                excel_generator = StockExcelGenerator(portfolio_tracker, stock_path, currency_symbol, portfolio_name)
                excel_generator.generate_report()

            self.__update_bilan_all_portfolios(heritage_path)

        calculate_heritage(self.__bank_db, self.__stock_db)

    def __update_bilan_all_portfolios(self, heritage_path: str) -> None:
        # Regroupement par devises et consolidation dans la devise cible
        target_currency = load_config()["currency"]
        currency_symbol = "€" if target_currency == "EUR" else "$"
        portfolios = self.__stock_db.get_all_portfolios()

        # Dictionnaires d'accumulation pour l'ensemble du patrimoine
        aggregated_metrics = {
            "currency": target_currency,
            "portfolio_gross_value": None,
            "portfolio_values": None,
            "portfolio_deposit": None,
            "portfolio_cash": 0.0,
            "portfolio_pct": None,
            "portfolio_monthly_returns": None,
            "portfolio_total_gains": None,
            "portfolio_latent_gain": None,
            "portfolio_dividends": None,
            "benchmark_pct": None,
            "weighted_average_correlation": 0.0,
            "benchmark_gains": None,
            "ticker_investments": None,
            "ticker_values": None,
            "ticker_dividends": None,
            "ticker_latent_gains": None,
            "ticker_latent_gains_pct": None,
            "initial_invested_amount": 0.0,
            "portfolio_daily_returns": None,
            "ticker_shares": None,
        }

        if not portfolios.empty:
            grouped = portfolios.groupby("currency")

            for currency, group in grouped:
                # Récupération et combinaison des transactions pour tous les portefeuilles de cette devise
                currency_transactions = []
                for p_id in group["id"]:
                    df = self.__stock_db.get_transactions_by_stock_account(p_id)
                    if not df.empty:
                        currency_transactions.append(df)

                if not currency_transactions:
                    continue

                combined_df = pd.concat(currency_transactions, ignore_index=True).sort_values(by="date", ascending=True)

                # Calcul de performance pour ce groupe de même devise
                group_tracker = PortfolioTracker(self.__stock_db)
                group_tracker.set_transactions(combined_df)
                group_tracker.run(currency)

                # Conversion du résultat dans la devise cible si nécessaire
                rate = 1.0
                if currency != target_currency:
                    rate = self.__stock_db.get_latest_fx_rate(currency, target_currency)

                # Addition des métriques converties dans les totaux globaux
                aggregated_metrics["portfolio_cash"] += group_tracker.portfolio_cash * rate
                aggregated_metrics["initial_invested_amount"] += group_tracker.initial_invested_amount * rate

                # Cumul des séries et DataFrames temporels
                for key in [
                    "portfolio_gross_value",
                    "portfolio_values",
                    "portfolio_dividends",
                    "portfolio_latent_gain",
                    "portfolio_total_gains",
                    "benchmark_gains",
                    "ticker_investments",
                    "ticker_values",
                    "ticker_dividends",
                    "ticker_latent_gains",
                    "ticker_shares",
                ]:
                    metric_val = getattr(group_tracker, key, None)
                    if metric_val is not None:
                        converted_val = metric_val * rate
                        if aggregated_metrics[key] is None:
                            aggregated_metrics[key] = converted_val
                        else:
                            aggregated_metrics[key] = aggregated_metrics[key].add(converted_val, fill_value=0)

            aggregated_metrics["transactions"] = self.__stock_db.get_all_transactions_converted(target_currency)
            aggregated_metrics["portfolio_pct"] = (
                aggregated_metrics["portfolio_total_gains"] * 100 / aggregated_metrics["initial_invested_amount"]
            ).round(2)
            aggregated_metrics["benchmark_pct"] = (
                aggregated_metrics["benchmark_gains"] * 100 / aggregated_metrics["initial_invested_amount"]
            ).round(2)
            aggregated_metrics["monthly_simple_returns"] = monthly_simple_returns(
                aggregated_metrics["portfolio_gross_value"], aggregated_metrics["transactions"]
            ).round(2)
            aggregated_metrics["portfolio_monthly_returns"] = aggregated_metrics["monthly_simple_returns"]
            aggregated_metrics["portfolio_repartition"] = compute_portfolio_repartition(
                aggregated_metrics["portfolio_values"], aggregated_metrics["ticker_values"]
            )
            aggregated_metrics["portfolio_daily_returns"] = portfolio_percentage_per_day(
                aggregated_metrics["portfolio_values"], aggregated_metrics["transactions"]
            ).round(2)
            aggregated_metrics["ticker_prices"] = self.__stock_db.get_tickers_prices(
                None,
                aggregated_metrics["ticker_investments"].columns.to_list(),
                aggregated_metrics["ticker_investments"].index[0].strftime("%Y-%m-%d"),
                target_currency,
            )
            aggregated_metrics["sharpe_ratio"] = sharpe_ratio(aggregated_metrics["portfolio_daily_returns"])
            aggregated_metrics["sortino_ratio"] = sortino_ratio(aggregated_metrics["portfolio_daily_returns"])
            aggregated_metrics["volatility"] = calculate_volatility_portfolio(
                aggregated_metrics["portfolio_daily_returns"]
            )
            aggregated_metrics["weighted_average_correlation"] = weighted_average_correlation(
                aggregated_metrics["ticker_investments"],
                aggregated_metrics["ticker_prices"],
                aggregated_metrics["ticker_shares"],
            )
            aggregated_metrics["correlation"] = calculate_stocks_correlation_matrix(
                aggregated_metrics["ticker_investments"], aggregated_metrics["ticker_prices"]
            )
            aggregated_metrics["portfolio_deposit"] = compute_deposit_evolution(
                aggregated_metrics["transactions"],
                aggregated_metrics["transactions"].index[0],
                aggregated_metrics["ticker_prices"].index[-1],
            ).round(2)
            aggregated_metrics["ticker_latent_gains_pct"] = (
                (
                    (
                        aggregated_metrics["ticker_latent_gains"]
                        / aggregated_metrics["ticker_investments"].replace(0, np.nan)
                    )
                    * 100
                )
                .fillna(0)
                .round(2)
            )
            aggregated_metrics["volatility_portfolio"] = calculate_volatility_portfolio(
                aggregated_metrics["portfolio_daily_returns"]
            )
            aggregated_metrics["portfolio_gross_value"] = aggregated_metrics["portfolio_gross_value"].round(2)
            aggregated_metrics["portfolio_values"] = aggregated_metrics["portfolio_values"].round(2)
            aggregated_metrics["portfolio_cash"] = aggregated_metrics["portfolio_cash"].round(2)
            aggregated_metrics["portfolio_latent_gain"] = aggregated_metrics["portfolio_latent_gain"].round(2)
            aggregated_metrics["portfolio_total_gains"] = aggregated_metrics["portfolio_total_gains"].round(2)
            aggregated_metrics["portfolio_dividends"] = aggregated_metrics["portfolio_dividends"].round(2)
            aggregated_metrics["benchmark_gains"] = aggregated_metrics["benchmark_gains"].round(2)
            aggregated_metrics["ticker_investments"] = aggregated_metrics["ticker_investments"].round(2)
            aggregated_metrics["ticker_values"] = aggregated_metrics["ticker_values"].round(2)
            aggregated_metrics["ticker_dividends"] = aggregated_metrics["ticker_dividends"].round(2)
            aggregated_metrics["ticker_latent_gains"] = aggregated_metrics["ticker_latent_gains"].round(2)
            aggregated_metrics["initial_invested_amount"] = round(aggregated_metrics["initial_invested_amount"], 2)

        chart_generate_rapport(self.__stock_db, "heritage_stock", heritage_path, aggregated_metrics)
        excel_generator = StockExcelGenerator(aggregated_metrics, heritage_path, currency_symbol, "heritage_stock")
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
