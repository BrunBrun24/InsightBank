from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk
import pandas as pd

from utils.ctk_date_entry import CtkDateEntry
from utils.ctk_scrollable_dropdown import CTkScrollableDropdown
from utils.window_utils import center_window_on_parent


class TransactionEditWindow(ctk.CTkToplevel):
    """Fenêtre de saisie et de modification de transaction avec formulaire dynamique selon l'opération."""

    OPERATIONS_MAP = {
        "Achat": "buy",
        "Vente": "sell",
        "Dividende": "dividend",
        "Dépôt": "deposit",
        "Retrait": "withdrawal",
        "Intérêts": "interest",
    }

    REVERSE_OPERATIONS_MAP = {v: k for k, v in OPERATIONS_MAP.items()}

    def __init__(
        self,
        parent: ctk.CTkFrame | ctk.CTk | ctk.CTkToplevel,
        db,
        portfolio_id: int,
        transaction: dict | None = None,
        on_save_callback: dict | None = None,
    ) -> None:
        super().__init__(parent)

        self.__db = db
        self.__portfolio_id = portfolio_id
        self.__tr = transaction or {}
        self._on_save = on_save_callback

        self.__display_to_ticker_map = {}
        self.__ticker_to_display_map = {}

        self.__is_edit_mode = bool(self.__tr and (self.__tr.get("transaction_id") or self.__tr.get("id")))

        self.title("Modifier la transaction" if self.__is_edit_mode else "Nouvelle transaction")
        self.geometry("520x720")
        self.transient(parent)
        self.grab_set()

        self.__portfolio_currency = self.__db.get_portfolio_currency(portfolio_id)
        self.__is_recalculating = False

        self._validate_numeric_cmd = self.register(self.__validate_numeric_input)

        # Variables réactives
        self.__amount_orig_var = ctk.StringVar(value="0.00")
        self.__price_orig_var = ctk.StringVar(value="0.00")
        self.__fee_orig_var = ctk.StringVar(value="0.00")

        self.__rate_var = ctk.StringVar(value="1.0000")

        self.__amount_port_var = ctk.StringVar(value="0.00")
        self.__price_port_var = ctk.StringVar(value="0.00")
        self.__fee_port_var = ctk.StringVar(value="0.00")

        # Liste pour conserver les identifiants de trace actifs
        self.__trace_ids = []
        self.__bind_variable_traces()

        self.__setup_ui()
        center_window_on_parent(self, parent)

        if self.__is_edit_mode:
            self.__populate_fields()

        center_window_on_parent(self, parent)

    def __validate_numeric_input(self, proposed_value: str) -> bool:
        """Valide la saisie numérique dans les champs texte."""

        if proposed_value == "":
            return True
        normalized = proposed_value.replace(",", ".")
        if normalized in [".", "0."]:
            return True
        try:
            float(normalized)
            return True
        except ValueError:
            return False

    def __setup_ui(self) -> None:
        """Construit l'interface graphique de base avec tous les composants pré-instanciés."""

        title_text = "Modifier la transaction" if self.__is_edit_mode else "Nouvelle transaction"
        ctk.CTkLabel(self, text=title_text, font=("Arial", 18, "bold")).pack(pady=15)

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=25)

        # Sélection du Type d'opération
        ctk.CTkLabel(container, text="Type d'opération *", anchor="w").pack(fill="x")
        self.__operation_var = ctk.StringVar(value="Achat")
        self.__operation_selector = ctk.CTkOptionMenu(
            container,
            values=list(self.OPERATIONS_MAP.keys()),
            variable=self.__operation_var,
            command=self.__on_operation_changed,
        )
        self.__operation_selector.pack(fill="x", pady=(0, 10))

        # Zone Titre
        self.__stock_container_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.__stock_container_frame.pack(fill="x", pady=(0, 10))

        self.__stock_label = ctk.CTkLabel(self.__stock_container_frame, text="Titre *", anchor="w")
        self.__stock_frame = ctk.CTkFrame(self.__stock_container_frame, fg_color="transparent")

        self.__stock_selector = ctk.CTkOptionMenu(self.__stock_frame, values=[], command=self.__on_stock_changed)
        self.__stock_selector.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.__scrollable_dropdown = CTkScrollableDropdown(
            attach=self.__stock_selector, values=[], height=200, autocomplete=True, command=self.__on_stock_changed
        )

        # Conteneur horizontal pour Date et Taux de change
        self.__row_date_rate = ctk.CTkFrame(container, fg_color="transparent")
        self.__row_date_rate.pack(fill="x", pady=(0, 10))
        self.__row_date_rate.grid_columnconfigure((0, 1), weight=1)

        # Champ Date
        self.__f_date = ctk.CTkFrame(self.__row_date_rate, fg_color="transparent")
        self.__f_date.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        initial_date = self.__tr.get("date") or datetime.now().strftime("%Y-%m-%d")
        ctk.CTkLabel(self.__f_date, text="Date *", anchor="w").pack(fill="x")
        self.__date_picker = CtkDateEntry(
            self.__f_date,
            initial_date=str(initial_date),
            command=self.__on_date_changed,
            block_future_dates=True,
        )
        self.__date_picker.pack(fill="x")

        # Champ Taux de change
        self.__f_rate = ctk.CTkFrame(self.__row_date_rate, fg_color="transparent")
        self.__f_rate.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        self.__lbl_rate = ctk.CTkLabel(self.__f_rate, text="Taux de change", anchor="w")
        self.__lbl_rate.pack(fill="x")
        entry_rate = ctk.CTkEntry(self.__f_rate, textvariable=self.__rate_var)
        entry_rate.configure(validate="key", validatecommand=(self._validate_numeric_cmd, "%P"))
        entry_rate.pack(fill="x")

        # Conteneur principal des champs dynamiques
        self.__fields_container = ctk.CTkFrame(container, fg_color="transparent")
        self.__fields_container.pack(fill="x", pady=5)

        # Ligne 1 : Champs dans la devise d'origine (Montant, Prix unitaire, Frais)
        self.__row_orig = ctk.CTkFrame(self.__fields_container, fg_color="transparent")
        self.__row_orig.grid_columnconfigure((0, 1, 2), weight=1)

        self.__f_amount_orig = ctk.CTkFrame(self.__row_orig, fg_color="transparent")
        self.__f_amount_orig.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self.__lbl_amount_orig = ctk.CTkLabel(self.__f_amount_orig, text="Montant *", anchor="w")
        self.__lbl_amount_orig.pack(fill="x")
        entry_amount_orig = ctk.CTkEntry(self.__f_amount_orig, textvariable=self.__amount_orig_var)
        entry_amount_orig.configure(validate="key", validatecommand=(self._validate_numeric_cmd, "%P"))
        entry_amount_orig.pack(fill="x")

        self.__f_price_orig = ctk.CTkFrame(self.__row_orig, fg_color="transparent")
        self.__f_price_orig.grid(row=0, column=1, padx=5, sticky="ew")
        self.__lbl_price_orig = ctk.CTkLabel(self.__f_price_orig, text="Prix unitaire *", anchor="w")
        self.__lbl_price_orig.pack(fill="x")
        entry_price_orig = ctk.CTkEntry(self.__f_price_orig, textvariable=self.__price_orig_var)
        entry_price_orig.configure(validate="key", validatecommand=(self._validate_numeric_cmd, "%P"))
        entry_price_orig.pack(fill="x")

        self.__f_fee_orig = ctk.CTkFrame(self.__row_orig, fg_color="transparent")
        self.__f_fee_orig.grid(row=0, column=2, padx=(5, 0), sticky="ew")
        self.__lbl_fee_orig = ctk.CTkLabel(self.__f_fee_orig, text="Frais", anchor="w")
        self.__lbl_fee_orig.pack(fill="x")
        entry_fee_orig = ctk.CTkEntry(self.__f_fee_orig, textvariable=self.__fee_orig_var)
        entry_fee_orig.configure(validate="key", validatecommand=(self._validate_numeric_cmd, "%P"))
        entry_fee_orig.pack(fill="x")

        # Ligne 2 : Champs convertis dans la devise du portefeuille
        self.__row_port = ctk.CTkFrame(self.__fields_container, fg_color="transparent")
        self.__row_port.grid_columnconfigure((0, 1, 2), weight=1)

        self.__f_amount_port = ctk.CTkFrame(self.__row_port, fg_color="transparent")
        self.__f_amount_port.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self.__lbl_amount_port = ctk.CTkLabel(self.__f_amount_port, text="Montant", anchor="w")
        self.__lbl_amount_port.pack(fill="x")
        entry_amount_port = ctk.CTkEntry(self.__f_amount_port, textvariable=self.__amount_port_var)
        entry_amount_port.configure(validate="key", validatecommand=(self._validate_numeric_cmd, "%P"))
        entry_amount_port.pack(fill="x")

        self.__f_price_port = ctk.CTkFrame(self.__row_port, fg_color="transparent")
        self.__f_price_port.grid(row=0, column=1, padx=5, sticky="ew")
        self.__lbl_price_port = ctk.CTkLabel(self.__f_price_port, text="Prix unitaire", anchor="w")
        self.__lbl_price_port.pack(fill="x")
        entry_price_port = ctk.CTkEntry(self.__f_price_port, textvariable=self.__price_port_var)
        entry_price_port.configure(validate="key", validatecommand=(self._validate_numeric_cmd, "%P"))
        entry_price_port.pack(fill="x")

        self.__f_fee_port = ctk.CTkFrame(self.__row_port, fg_color="transparent")
        self.__f_fee_port.grid(row=0, column=2, padx=(5, 0), sticky="ew")
        self.__lbl_fee_port = ctk.CTkLabel(self.__f_fee_port, text="Frais", anchor="w")
        self.__lbl_fee_port.pack(fill="x")
        entry_fee_port = ctk.CTkEntry(self.__f_fee_port, textvariable=self.__fee_port_var)
        entry_fee_port.configure(validate="key", validatecommand=(self._validate_numeric_cmd, "%P"))
        entry_fee_port.pack(fill="x")

        self._refresh_stocks_list()
        self.__render_dynamic_fields()

        btn_label = "Enregistrer" if self.__is_edit_mode else "Ajouter"
        ctk.CTkButton(
            self,
            text=btn_label,
            fg_color="#1a73e8",
            hover_color="#1557b0",
            command=self.__handle_save,
        ).pack(pady=20, padx=25, fill="x")

    def __on_operation_changed(self, choice: str) -> None:
        """Gère le changement de type d'opération."""
        self._refresh_stocks_list()
        self.__render_dynamic_fields()

    def __on_date_changed(self, new_date: str) -> None:
        """Gère le changement de date."""
        self.__update_exchange_rate()
        if not self.__is_edit_mode:
            self.__update_stock_price()
            self.__recalculate_from_orig()

    def __bind_variable_traces(self) -> None:
        """Attache les callbacks aux StringVar et conserve leurs identifiants."""
        self.__unbind_variable_traces()

        t1 = self.__amount_orig_var.trace_add("write", lambda *args: self.__recalculate_from_orig())
        t2 = self.__price_orig_var.trace_add("write", lambda *args: self.__recalculate_from_orig())
        t3 = self.__fee_orig_var.trace_add("write", lambda *args: self.__recalculate_from_orig())
        t4 = self.__rate_var.trace_add("write", lambda *args: self.__recalculate_from_orig())

        t5 = self.__amount_port_var.trace_add("write", lambda *args: self.__recalculate_from_port())
        t6 = self.__price_port_var.trace_add("write", lambda *args: self.__recalculate_from_port())
        t7 = self.__fee_port_var.trace_add("write", lambda *args: self.__recalculate_from_port())

        self.__trace_ids = [
            (self.__amount_orig_var, t1),
            (self.__price_orig_var, t2),
            (self.__fee_orig_var, t3),
            (self.__rate_var, t4),
            (self.__amount_port_var, t5),
            (self.__price_port_var, t6),
            (self.__fee_port_var, t7),
        ]

    def __unbind_variable_traces(self) -> None:
        """Détache proprement les callbacks de trace pour éviter les erreurs de widgets détruits."""
        for var, trace_id in self.__trace_ids:
            try:
                var.trace_remove("write", trace_id)
            except Exception:
                pass
        self.__trace_ids.clear()

    def __render_dynamic_fields(self) -> None:
        """Affiche ou masque les conteneurs pré-existants en fonction du contexte."""

        self.__f_rate.grid_remove()
        self.__row_orig.pack_forget()
        self.__row_port.pack_forget()

        self.__f_price_orig.grid_remove()
        self.__f_price_port.grid_remove()
        self.__f_fee_orig.grid_remove()
        self.__f_fee_port.grid_remove()

        op_display = self.__operation_var.get()
        type_op = self.OPERATIONS_MAP.get(op_display, "buy")

        if type_op in ["buy", "sell", "dividend"]:
            self.__stock_label.pack(fill="x")
            self.__stock_frame.pack(fill="x")
        else:
            self.__stock_label.pack_forget()
            self.__stock_frame.pack_forget()

        if type_op in ["buy", "sell", "dividend"]:
            selected_ticker = self.__tr.get("ticker") if self.__is_edit_mode else self.__get_selected_ticker()
            stock_currency = self.__db.get_currency(selected_ticker) if selected_ticker else self.__portfolio_currency
            is_same_currency = stock_currency == self.__portfolio_currency

            amt_text = (
                f"Montant reçu * ({stock_currency})" if type_op == "dividend" else f"Montant * ({stock_currency})"
            )
            self.__lbl_amount_orig.configure(text=amt_text)
            self.__lbl_fee_orig.configure(text=f"Frais ({stock_currency})")

            self.__row_orig.pack(fill="x", pady=5)
            self.__f_fee_orig.grid()

            if type_op in ["buy", "sell"]:
                self.__lbl_price_orig.configure(text=f"Prix unitaire * ({stock_currency})")
                self.__f_price_orig.grid()

            if not is_same_currency:
                p_amt_text = (
                    f"Montant reçu ({self.__portfolio_currency})"
                    if type_op == "dividend"
                    else f"Montant ({self.__portfolio_currency})"
                )
                self.__lbl_amount_port.configure(text=p_amt_text)
                self.__lbl_fee_port.configure(text=f"Frais ({self.__portfolio_currency})")

                if type_op in ["buy", "sell"]:
                    self.__lbl_price_port.configure(text=f"Prix unitaire ({self.__portfolio_currency})")
                    self.__f_price_port.grid()

                self.__f_fee_port.grid()
                self.__f_rate.grid()
                self.__row_port.pack(fill="x", pady=5)

        elif type_op in ["deposit", "withdrawal", "interest"]:
            self.__lbl_amount_orig.configure(text=f"Montant * ({self.__portfolio_currency})")
            self.__lbl_fee_orig.configure(text=f"Frais ({self.__portfolio_currency})")

            self.__row_orig.pack(fill="x", pady=5)
            self.__f_fee_orig.grid()

    def __populate_fields(self) -> None:
        """Rempli les champs lors d'une modification."""

        self.__is_recalculating = True
        try:
            type_op = self.__tr.get("type", "buy")
            op_display = self.REVERSE_OPERATIONS_MAP.get(type_op, "Achat")
            self.__operation_var.set(op_display)

            ticker = self.__tr.get("ticker")
            if ticker and type_op in ["buy", "sell", "dividend"]:
                display_name = self.__ticker_to_display_map.get(str(ticker), str(ticker))
                self.__stock_selector.set(display_name)

            self.__render_dynamic_fields()

            tr_date = self.__tr.get("date")
            if tr_date and pd.notna(tr_date):
                self.__date_picker.set(str(tr_date))

            rate = float(self.__tr.get("fx_rate", 1.0) or 1.0)
            original_amount = float(self.__tr.get("original_amount", 0.0) or 0.0)
            price_orig = float(self.__tr.get("original_price", 0.0) or 0.0)
            original_fee = float(self.__tr.get("original_fee", 0.0) or 0.0)

            amount_port = float(self.__tr.get("amount", 0.0) or 0.0)
            price_port = float(self.__tr.get("price", 0.0) or 0.0)
            fee_port = float(self.__tr.get("fee", 0.0) or 0.0)

            self.__rate_var.set(f"{rate:.4f}")
            self.__amount_orig_var.set(f"{original_amount:.2f}")
            self.__price_orig_var.set(f"{price_orig:.2f}")
            self.__fee_orig_var.set(f"{original_fee:.2f}")

            self.__amount_port_var.set(f"{amount_port:.2f}")
            self.__price_port_var.set(f"{price_port:.2f}")
            self.__fee_port_var.set(f"{fee_port:.2f}")

        except (ValueError, TypeError):
            pass
        finally:
            self.__is_recalculating = False

    def _refresh_stocks_list(self) -> None:
        """Actualise la liste des titres disponibles dans le menu déroulant."""

        ticker_id_map = self.__db.get_portfolio_ticker_ids(self.__portfolio_id)
        portfolio_tickers = list(ticker_id_map.keys())

        self.__display_to_ticker_map.clear()
        self.__ticker_to_display_map.clear()
        display_options = []

        for ticker in portfolio_tickers:
            company_name = self.__db.get_company_name(ticker)
            if company_name and company_name.strip().upper() != ticker.strip().upper():
                display_label = f"{company_name.strip()} ({ticker})"
            else:
                display_label = ticker

            self.__display_to_ticker_map[display_label] = ticker
            self.__ticker_to_display_map[ticker] = display_label
            display_options.append(display_label)

        sorted_options = sorted(display_options)

        if self.__operation_var.get() == "Achat":
            options = ["+ Ajouter un titre"] + sorted_options
        else:
            options = sorted_options

        self.__stock_selector.configure(values=options)

        if hasattr(self, "_TransactionEditWindow__scrollable_dropdown"):
            self.__scrollable_dropdown.configure(values=options)

        if options and not self.__is_edit_mode:
            default_selection = options[1] if (options[0] == "+ Ajouter un titre" and len(options) > 1) else options[0]
            self.__stock_selector.set(default_selection)
            self.__on_stock_changed(default_selection)
        elif not options:
            self.__stock_selector.set("+ Ajouter un titre" if self.__operation_var.get() == "Achat" else "")

    def __get_selected_ticker(self) -> str | None:
        """Récupère le ticker sélectionné."""
        selected_display = self.__stock_selector.get()
        if not selected_display or selected_display == "+ Ajouter un titre":
            return None
        return self.__display_to_ticker_map.get(selected_display, selected_display)

    def __on_stock_changed(self, choice: str) -> None:
        """Gère la sélection ou l'ajout d'un nouveau titre."""

        self.__stock_selector.set(choice)

        if choice == "+ Ajouter un titre":
            from dashboard.portfolio.transactions.components.add_stock_window import AddStockWindow

            AddStockWindow(self, self.__db, self.__portfolio_id, self._on_stock_added_callback)
        else:
            if not self.__is_edit_mode:
                self.__update_exchange_rate()
                self.__update_stock_price()
            self.__render_dynamic_fields()

    def _on_stock_added_callback(self, new_ticker: str) -> None:
        """Callback suite à l'ajout réussi d'un nouveau titre."""

        self._refresh_stocks_list()
        display_label = self.__ticker_to_display_map.get(new_ticker, new_ticker)
        self.__stock_selector.set(display_label)
        self.__update_exchange_rate()
        self.__update_stock_price()
        self.__render_dynamic_fields()

    def __update_exchange_rate(self) -> None:
        """Recalcule le taux de change pour l'action sélectionnée."""

        if self.__is_edit_mode and (self.__tr["type"] not in ["buy", "sell", "dividend"]):
            return

        selected_ticker = self.__get_selected_ticker()
        if not selected_ticker:
            return

        stock_currency = self.__db.get_currency(selected_ticker)
        if stock_currency == self.__portfolio_currency:
            self.__rate_var.set("1.0000")
            return

        try:
            raw_date = self.__date_picker.get()
            formatted_date = pd.to_datetime(raw_date).strftime("%Y-%m-%d")

            rate_ticker = f"{self.__portfolio_currency}{stock_currency}=X"
            rate = self.__db.get_rate(formatted_date, rate_ticker)

            if rate is None:
                rate_ticker_alt = f"{stock_currency}{self.__portfolio_currency}=X"
                rate_alt = self.__db.get_rate(formatted_date, rate_ticker_alt)
                if rate_alt and float(rate_alt) > 0:
                    rate = 1.0 / float(rate_alt)

            if rate is not None:
                self.__rate_var.set(f"{float(rate):.4f}")
            else:
                self.__rate_var.set("1.0000")
        except Exception:
            self.__rate_var.set("1.0000")

    def __update_stock_price(self) -> None:
        """Récupère automatiquement le prix unitaire de l'action à la date sélectionnée."""

        selected_ticker = self.__get_selected_ticker()
        type_op = self.OPERATIONS_MAP.get(self.__operation_var.get(), "buy")

        if not selected_ticker or type_op not in ["buy", "sell"]:
            return

        try:
            raw_date = self.__date_picker.get()
            formatted_date = pd.to_datetime(raw_date).strftime("%Y-%m-%d")

            price = self.__db.get_rate(formatted_date, selected_ticker)

            if price is not None and float(price) > 0:
                self.__price_orig_var.set(f"{float(price):.2f}")
        except Exception:
            pass

    def __parse_float(self, val_str: str) -> float | None:
        """Parse une chaîne en float de manière tolérante aux saisies partielles."""
        if not val_str:
            return 0.0
        cleaned = val_str.replace(",", ".").strip()
        if cleaned in [".", ",", ""]:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    def __recalculate_from_orig(self) -> None:
        """Mise à jour automatique des devises depuis la monnaie de transaction."""

        if self.__is_recalculating:
            return

        rate = self.__parse_float(self.__rate_var.get())
        original_amount = self.__parse_float(self.__amount_orig_var.get())
        price_orig = self.__parse_float(self.__price_orig_var.get())
        fee_orig = self.__parse_float(self.__fee_orig_var.get())

        if rate is None or original_amount is None or rate <= 0:
            return

        try:
            self.__is_recalculating = True

            amount_converted = round(original_amount / rate, 2)
            price_converted = round(price_orig / rate, 4) if price_orig is not None else 0.0
            fee_converted = round(fee_orig / rate, 2) if fee_orig is not None else 0.0

            def update_vars():
                self.__unbind_variable_traces()
                self.__amount_port_var.set(f"{amount_converted:.2f}")
                self.__price_port_var.set(f"{price_converted:.2f}")
                self.__fee_port_var.set(f"{fee_converted:.2f}")
                self.__bind_variable_traces()
                self.__is_recalculating = False

            self.after_idle(update_vars)

        except Exception:
            self.__is_recalculating = False

    def __recalculate_from_port(self) -> None:
        """Mise à jour automatique des devises depuis la monnaie du portefeuille."""

        if self.__is_recalculating:
            return

        rate = self.__parse_float(self.__rate_var.get())
        amount_port = self.__parse_float(self.__amount_port_var.get())
        price_port = self.__parse_float(self.__price_port_var.get())
        fee_port = self.__parse_float(self.__fee_port_var.get())

        if rate is None or amount_port is None:
            return

        try:
            self.__is_recalculating = True

            original_amount = round(amount_port * rate, 2)
            price_orig = round(price_port * rate, 4) if price_port is not None else 0.0
            fee_orig = round(fee_port * rate, 2) if fee_port is not None else 0.0

            def update_vars():
                self.__unbind_variable_traces()
                self.__amount_orig_var.set(f"{original_amount:.2f}")
                self.__price_orig_var.set(f"{price_orig:.2f}")
                self.__fee_orig_var.set(f"{fee_orig:.2f}")
                self.__bind_variable_traces()
                self.__is_recalculating = False

            self.after_idle(update_vars)

        except Exception:
            self.__is_recalculating = False

    def __handle_save(self) -> None:
        """Valide et enregistre la transaction en base de données."""

        op_display = self.__operation_var.get()
        type_op = self.OPERATIONS_MAP.get(op_display, "buy")

        ticker = None
        portfolio_ticker_id = None

        if type_op in ["buy", "sell", "dividend"]:
            ticker = self.__get_selected_ticker()
            if not ticker:
                messagebox.showerror("Erreur", "Veuillez choisir un titre valide.")
                return

            ticker_id_map = self.__db.get_portfolio_ticker_ids(self.__portfolio_id)
            portfolio_ticker_id = ticker_id_map.get(ticker)

        try:
            original_amount = round(float(self.__amount_orig_var.get().replace(",", ".")), 2)
            original_fee = round(float(self.__fee_orig_var.get().replace(",", ".")), 2)

            if original_amount <= 0:
                messagebox.showerror("Erreur", "Le montant doit être supérieur à zéro.")
                return

            price_orig = (
                round(float(self.__price_orig_var.get().replace(",", ".")), 2) if type_op in ["buy", "sell"] else None
            )
            rate = float(self.__rate_var.get().replace(",", "."))
            amount_converted = original_amount
            price_converted = price_orig
            fee_converted = original_fee
            qty = None

            selected_ticker = self.__get_selected_ticker()
            stock_currency = (
                self.__db.get_currency(selected_ticker)
                if selected_ticker and type_op in ["buy", "sell", "dividend"]
                else self.__portfolio_currency
            )

            is_different_currency = (
                type_op in ["buy", "sell", "dividend"] and stock_currency != self.__portfolio_currency
            )

            if type_op in ["buy", "sell"]:
                if price_orig <= 0:
                    messagebox.showerror("Erreur", "Le prix unitaire doit être supérieur à zéro.")
                    return

                qty = round(original_amount / price_orig, 6)

            if is_different_currency:
                amount_converted = round(float(self.__amount_port_var.get().replace(",", ".")), 2)
                if type_op in ["buy", "sell"]:
                    price_converted = round(float(self.__price_port_var.get().replace(",", ".")), 2)
                else:
                    price_converted = None
                fee_converted = round(float(self.__fee_port_var.get().replace(",", ".")), 2)

            data = {
                "portfolio_id": self.__portfolio_id,
                "portfolio_ticker_id": portfolio_ticker_id,
                "type": type_op,
                "date": self.__date_picker.get(),
                "original_amount": original_amount,
                "original_price": price_orig,
                "original_fee": original_fee,
                "fx_rate": rate,
                "amount": amount_converted,
                "price": price_converted,
                "fee": fee_converted,
            }

            transaction_id = self.__tr.get("id") or self.__tr.get("transaction_id")
            if transaction_id is not None:
                data["transaction_id"] = transaction_id
                data["shares"] = qty

            if callable(self._on_save):
                self._on_save(data)

            self.destroy()

        except ValueError:
            messagebox.showerror("Erreur de saisie", "Veuillez saisir des valeurs numériques valides.")
