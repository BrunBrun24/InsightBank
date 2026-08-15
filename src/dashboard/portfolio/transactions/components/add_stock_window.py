from tkinter import messagebox

import customtkinter as ctk
import yfinance as yf

from utils.window_utils import center_window_on_parent


class AddStockWindow(ctk.CTkToplevel):
    """Fenêtre modale de recherche et d'ajout d'une nouvelle action avec résultats multiples."""

    def __init__(self, parent, db_stock, portfolio_id: int, on_stock_added_callback: callable) -> None:
        super().__init__(parent)
        self.title("Ajouter un titre")
        self.geometry("420x320")
        self.transient(parent)
        self.grab_set()

        self.__db_stock = db_stock
        self.__portfolio_id = portfolio_id
        self.__on_stock_added = on_stock_added_callback
        self.__selected_stock = None
        self.__search_results_map = {}

        self.__setup_ui()
        center_window_on_parent(self, parent)

    def __setup_ui(self) -> None:
        ctk.CTkLabel(self, text="Ajouter un titre", font=("Arial", 16, "bold")).pack(pady=15)

        # Champ de recherche
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(search_frame, text="Rechercher par nom, ticker ou ISIN", anchor="w").pack(fill="x")
        self.__search_entry = ctk.CTkEntry(search_frame, placeholder_text="Ex: Apple, AAPL, US0378331005, ...")
        self.__search_entry.pack(fill="x", pady=5)
        self.__search_entry.bind("<KeyRelease>", self.__on_search_change)

        # Liste des résultats trouvés
        self.__results_box = ctk.CTkOptionMenu(
            self, values=["Saisissez un terme de recherche..."], command=self.__on_select_stock
        )
        self.__results_box.pack(fill="x", padx=20, pady=10)

        # Zone d'information sur l'action sélectionnée
        self.__info_label = ctk.CTkLabel(self, text="Rechercher et sélectionner un titre.", text_color="gray")
        self.__info_label.pack(pady=10)

        # Boutons d'action
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=15)

        ctk.CTkButton(btn_frame, text="Annuler", fg_color="transparent", text_color="black", command=self.destroy).pack(
            side="left", expand=True
        )

        self.__add_btn = ctk.CTkButton(btn_frame, text="Ajouter", state="disabled", command=self.__handle_add)
        self.__add_btn.pack(side="right", expand=True)

    def __on_search_change(self, event) -> None:
        query = self.__search_entry.get().strip()
        if len(query) < 2:
            return

        try:
            search_engine = yf.Search(query, max_results=10)
            quotes = search_engine.quotes

            if not quotes:
                self.__results_box.configure(values=["Aucun résultat trouvé"])
                self.__results_box.set("Aucun résultat trouvé")
                self.__info_label.configure(text="Aucun résultat correspondant.", text_color="red")
                self.__add_btn.configure(state="disabled")
                self.__selected_stock = None
                return

            self.__search_results_map.clear()
            options = []

            for quote in quotes:
                symbol = quote.get("symbol")
                name = quote.get("longname") or quote.get("shortname") or symbol
                quote_type = quote.get("quoteType", "")
                exchange = quote.get("exchDisp", quote.get("exchange", ""))

                if symbol:
                    display_str = f"{symbol} - {name} ({exchange})"
                    options.append(display_str)

                    self.__search_results_map[display_str] = {
                        "ticker": symbol,
                        "company_name": name,
                        "quote_type": quote_type,
                        "exchange": exchange,
                    }

            if options:
                self.__results_box.configure(values=options)
                self.__results_box.set(options[0])
                self.__on_select_stock(options[0])
            else:
                self.__results_box.configure(values=["Aucun résultat valide"])
                self.__results_box.set("Aucun résultat valide")
                self.__add_btn.configure(state="disabled")

        except Exception:
            self.__info_label.configure(text="Erreur lors de la recherche Yahoo Finance.", text_color="red")
            self.__add_btn.configure(state="disabled")

    def __on_select_stock(self, choice: str) -> None:
        stock_data = self.__search_results_map.get(choice)
        if not stock_data:
            return

        try:
            ticker_obj = yf.Ticker(stock_data["ticker"])
            info = ticker_obj.info
            currency = info.get("currency", "USD")

            self.__selected_stock = {
                "ticker": stock_data["ticker"],
                "company_name": stock_data["company_name"],
                "currency": currency,
                "isin": info.get("isin", None),
                "country": info.get("country", None),
            }

            self.__info_label.configure(
                text=f"Sélectionné : {self.__selected_stock['company_name']} [{currency}]", text_color="green"
            )
            self.__add_btn.configure(state="normal")
        except Exception:
            self.__selected_stock = {
                "ticker": stock_data["ticker"],
                "company_name": stock_data["company_name"],
                "currency": "USD",
                "isin": None,
                "country": None,
            }
            self.__info_label.configure(
                text=f"Sélectionné : {self.__selected_stock['company_name']}", text_color="green"
            )
            self.__add_btn.configure(state="normal")

    def __handle_add(self) -> None:
        if not self.__selected_stock:
            return

        try:
            tickers_list = [self.__selected_stock["ticker"]]
            self.__db_stock.add_data_tickers(tickers_list)
            self.__db_stock.add_tickers_in_portfolio_ticker(self.__portfolio_id, tickers_list)
            self.__on_stock_added(self.__selected_stock["ticker"])
            self.destroy()
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'ajouter le titre : {e}")
