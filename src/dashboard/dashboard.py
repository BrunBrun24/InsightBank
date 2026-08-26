import threading

import customtkinter as ctk
import pandas as pd
from PIL import Image

from accounts.banking.database.banking_db import BankingDB
from accounts.stock.database.stock_db import StockDB
from config import load_config
from dashboard.bank_accounts.operations.operations import Operations
from dashboard.configuration.automatisation_cat_sub_cat.automatisation_cat_sub_cat import AutomatisationCatSubCat
from dashboard.configuration.categories_sub_categories.categories_sub_categories import CategoriesSubCategories
from dashboard.configuration.configuration import Configuration
from dashboard.configuration.portfolio_tickers.portfolio_tickers import PortfolioTickers
from dashboard.home.home import Home
from dashboard.information.information import Information
from dashboard.portfolio.transactions.transactions import Transactions
from dashboard.shared.account import Account
from dashboard.shared.chart import Chart
from dashboard.shared.excel_report import ExcelReport
from utils.loading_popup import LoadingPopup


class Dashboard(ctk.CTk):
    """Interface principale de l'application."""

    def __init__(self) -> None:
        super().__init__()

        # Configuration de base de la fenêtre
        self.title("InsightBank - Dashboard")
        self.minsize(1000, 800)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # Mise en place du layout de base
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.__main_view = ctk.CTkFrame(self, corner_radius=15, fg_color="transparent")
        self.__main_view.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        # Centrage et affichage maximisé
        self.after(20, lambda: self.wm_state("zoomed"))

        # Affichage immédiat du popup de chargement par-dessus
        self.update()  # Force Tkinter à initialiser la fenêtre principale
        self.__loading_win = LoadingPopup(self, "Lancement d'InsightBank et chargement des données...")

        # Lancement du chargement lourd en arrière-plan
        threading.Thread(target=self.__async_init, daemon=True).start()

    def __async_init(self) -> None:
        """Effectue les chargements lourds en arrière-plan."""
        try:
            self.__config = load_config()
            self.__theme = self.__config["theme"]
            self.__banking_db_path = self.__config["database"]["db_banking_path"]
            self.__db_stock_path = self.__config["database"]["db_stock_path"]
            self.__banking_db = BankingDB(self.__banking_db_path)
            self.__stock_db = StockDB(self.__db_stock_path)

            # Demande au thread principal de construire la suite des modules
            self.after(0, self.__finish_init)
        except Exception as e:
            self.after(0, lambda err=e: self.__on_init_error(err))

    def __finish_init(self) -> None:
        """Construit le reste des modules une fois les bases de données chargées."""
        self.__bank_account_module = Account(self.__main_view, self, mode="banking")
        self.__stock_account_module = Account(self.__main_view, self, mode="stock")
        self.__home_module = Home(self.__main_view, self)
        self.__configuration_module = Configuration(self.__main_view, self)
        self.__banking_operations_module = Operations(self.__main_view, self)
        self.__stock_operations_module = Transactions(self.__main_view, self)
        self.__bank_chart = Chart(self.__main_view, self, mode="banking")
        self.__stock_chart = Chart(self.__main_view, self, mode="stock")
        self.__bank_excel_report = ExcelReport(self.__main_view, self, "banking")
        self.__stock_excel_report = ExcelReport(self.__main_view, self, "stock")
        self.__information = Information(self.__main_view, self)
        self.__categories_sub_categories = CategoriesSubCategories(self.__main_view, self)
        self.__automatisation_cat_sub_cat = AutomatisationCatSubCat(self.__main_view, self)
        self.__portfolio_tickers = PortfolioTickers(self.__main_view, self)

        self.__setup_navigation_frame()
        self.show_home()

        # Fermeture de la fenêtre de chargement
        if self.__loading_win and self.__loading_win.winfo_exists():
            self.__loading_win.close()

    def __on_init_error(self, error: Exception) -> None:
        if self.__loading_win and self.__loading_win.winfo_exists():
            self.__loading_win.close()
        raise error

    def get_db_banking(self) -> BankingDB:
        return self.__banking_db

    def set_db_banking(self, db: BankingDB) -> None:
        self.__banking_db = db

    def get_db_stock(self) -> StockDB:
        return self.__stock_db

    def get_config(self) -> dict:
        return self.__config

    def get_theme(self) -> dict:
        return self.__theme

    def show_home(self) -> None:
        self.__home_module.display()

    def show_configuration(self) -> None:
        self.__configuration_module.display()

    def show_manage_config_categorization(self) -> None:
        self.__configuration_module.display()

    def show_bank_accounts(self) -> None:
        self.__bank_account_module.display()

    def show_stock_portfolios(self) -> None:
        self.__stock_account_module.display()

    def show_bank_account_menu(self, bank_account_row: pd.Series) -> None:
        self.__bank_account_module.show_account_menu(bank_account_row)

    def show_stock_account_menu(self, portfolio_row: pd.Series) -> None:
        self.__stock_account_module.show_account_menu(portfolio_row)

    def show_bank_operations(self, bank_account_row: pd.Series) -> None:
        self.__banking_operations_module.display(bank_account_row)

    def show_stock_transactions(self, portfolio_row: pd.Series) -> None:
        self.__stock_operations_module.display(portfolio_row)

    def show_bank_charts(self, bank_account_row: pd.Series) -> None:
        self.__bank_chart.display(bank_account_row)

    def show_stock_charts(self, stock_account_row: pd.Series) -> None:
        self.__stock_chart.display(stock_account_row)

    def show_bank_excel_report(self, bank_account_row: pd.Series) -> None:
        self.__bank_excel_report.display(bank_account_row)

    def show_stock_excel_report(self, stock_account_row: pd.Series) -> None:
        self.__stock_excel_report.display(stock_account_row)

    def show_information(self) -> None:
        self.__information.display()

    def show_categories_sub_categories(self) -> None:
        self.__categories_sub_categories.display()

    def show_automatisation_cat_sub_cat(self) -> None:
        self.__automatisation_cat_sub_cat.display()

    def show_portfolio_tickers(self) -> None:
        self.__portfolio_tickers.display()

    def update_bank_bilan(self, bank_account_id: int, bank_account_name: str, callback=None) -> None:
        loading_win = LoadingPopup(self, "Renommage du compte et génération des bilans...")

        def task():
            try:
                self.__banking_operations_module.update_bilan(bank_account_id, bank_account_name)
            finally:
                self.after(0, lambda: self.__on_update_bilan_complete(loading_win, callback))

        threading.Thread(target=task, daemon=True).start()

    def update_stock_bilan(self, portfolio_id: int, portfolio_name: str, callback=None) -> None:
        loading_win = LoadingPopup(self, "Renommage du compte et génération des bilans...")

        def task():
            try:
                self.__stock_operations_module.update_bilan(portfolio_id, portfolio_name)
            finally:
                self.after(0, lambda: self.__on_update_bilan_complete(loading_win, callback))

        threading.Thread(target=task, daemon=True).start()

    def __on_update_bilan_complete(self, loading_win: LoadingPopup, callback=None) -> None:
        if loading_win and loading_win.winfo_exists():
            loading_win.close()
        if callback:
            callback()

    def create_card_grid(self, container: ctk.CTkFrame, items: list) -> None:
        """Crée une grille de cartes (3 max par ligne) parfaitement centrées."""

        # On vide le container
        for child in container.winfo_children():
            child.destroy()

        # On utilise 6 colonnes pour permettre de centrer 1, 2 ou 3 cartes proprement
        container.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        total = len(items)

        for i, item in enumerate(items):
            row = i // 3
            col_in_row = i % 3

            # On calcule combien d'items il y a sur la ligne actuelle
            remaining = total - (row * 3)
            items_on_this_row = min(3, remaining)

            card = ctk.CTkFrame(container, corner_radius=20, border_width=1)

            # Logique de placement
            if items_on_this_row == 3:
                # On prend 2 colonnes par carte (Total 6)
                card.grid(row=row, column=col_in_row * 2, columnspan=2, padx=15, pady=15, sticky="nsew")

            elif items_on_this_row == 2:
                # On place les cartes sur les colonnes 1-2 et 3-4 (On laisse 0 et 5 vides)
                start_col = 1 if col_in_row == 0 else 3
                card.grid(row=row, column=start_col, columnspan=2, padx=15, pady=15, sticky="nsew")

            elif items_on_this_row == 1:
                # On place la carte sur les colonnes 2-3 (Milieu parfait)
                card.grid(row=row, column=2, columnspan=2, padx=15, pady=15, sticky="nsew")

            img_data = Image.open(item["icon_path"])
            ctk_icon = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(40, 40))

            # Icône
            icon_circle = ctk.CTkLabel(
                card,
                image=ctk_icon,
                text="",
                font=("Arial", 40),
                fg_color=item["fg_color"],
                width=80,
                height=80,
                corner_radius=40,
            )
            icon_circle.pack(pady=(30, 10))

            ctk.CTkLabel(card, text=item["name"], font=("Arial", 20, "bold")).pack()
            ctk.CTkLabel(card, text=item["desc"], text_color="gray").pack(pady=10, padx=20)

            # Spacer invisible pour pousser le bouton en bas et garder la hauteur uniforme
            ctk.CTkLabel(card, text="", height=1).pack(expand=True)

            # Bouton
            ctk.CTkButton(
                card,
                text="Accéder",
                fg_color=item["fg_color"],
                hover_color=item["hover_color"],
                command=item["cmd"],
                corner_radius=10,
                height=35,
                font=("Arial", 15, "bold"),
            ).pack(side="bottom", pady=20, padx=20, fill="x")

    def __setup_navigation_frame(self) -> None:
        """Crée une barre latérale étroite avec des icônes."""

        # Configuration de la largeur de la barre
        self.__nav_frame = ctk.CTkFrame(self, corner_radius=0, width=70)
        self.__nav_frame.grid(row=0, column=0, sticky="nsew")
        self.__nav_frame.grid_rowconfigure(4, weight=1)

        icon_size = (28, 28)
        home_icon = ctk.CTkImage(light_image=Image.open("src/static/img/icons/home.png"), size=icon_size)
        bank_account_icon = ctk.CTkImage(
            light_image=Image.open("src/static/img/icons/bank_account.png"), size=icon_size
        )
        stock_icon = ctk.CTkImage(light_image=Image.open("src/static/img/icons/stock.png"), size=icon_size)
        heritage_icon = ctk.CTkImage(light_image=Image.open("src/static/img/icons/heritage.png"), size=icon_size)
        edit_icon = ctk.CTkImage(light_image=Image.open("src/static/img/icons/edit.png"), size=icon_size)
        information_icon = ctk.CTkImage(light_image=Image.open("src/static/img/icons/information.png"), size=icon_size)

        # Bouton home
        ctk.CTkButton(
            self.__nav_frame,
            text="",
            image=home_icon,
            width=40,
            height=40,
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            command=self.show_home,
        ).grid(row=0, column=0, padx=10, pady=(20, 10))

        # Bouton bank_account
        ctk.CTkButton(
            self.__nav_frame,
            text="",
            image=bank_account_icon,
            width=40,
            height=40,
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            command=self.show_bank_accounts,
        ).grid(row=1, column=0, padx=10, pady=(10, 20))

        # Bouton stock
        ctk.CTkButton(
            self.__nav_frame,
            text="",
            image=stock_icon,
            width=40,
            height=40,
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            command=self.show_stock_portfolios,
        ).grid(row=2, column=0, padx=10, pady=(10, 20))

        # Bouton heritage
        ctk.CTkButton(
            self.__nav_frame,
            text="",
            image=heritage_icon,
            width=40,
            height=40,
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            command=self.show_home,  # TODO
        ).grid(row=3, column=0, padx=10, pady=(10, 20))

        # Bouton edit
        ctk.CTkButton(
            self.__nav_frame,
            text="",
            image=edit_icon,
            width=40,
            height=40,
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            command=self.show_configuration,
        ).grid(row=5, column=0, padx=10, pady=10)

        # Bouton information
        ctk.CTkButton(
            self.__nav_frame,
            text="",
            image=information_icon,
            width=40,
            height=40,
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            command=self.show_information,
        ).grid(row=6, column=0, padx=10, pady=10)

    def destroy_widgets(self) -> None:
        for widget in self.__main_view.winfo_children():
            widget.destroy()

        self.__main_view.update_idletasks()
