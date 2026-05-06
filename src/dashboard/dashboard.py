import customtkinter as ctk
import pandas as pd
from PIL import Image

from accounts.banking.database.banking_db import BankingDB
from config import load_config
from dashboard.bank_accounts.bank_accounts import BankAccounts
from dashboard.bank_accounts.chart.chart import Chart
from dashboard.bank_accounts.excel_report.excel_report import ExcelReport
from dashboard.bank_accounts.operations.operations import Operations
from dashboard.configuration.configuration import Configuration
from dashboard.home.home import Home
from dashboard.information.information import Information


class Dashboard(ctk.CTk):
    """Interface principale de l'application Financial Data Visualizer."""

    def __init__(self) -> None:
        super().__init__()

        self.__config = load_config()
        self.__theme = self.__config["theme"]
        self.__db_path = self.__config["database"]["database_path"]
        self.__db = BankingDB(self.__db_path)

        self.__setup_interface()

        self.__configuration_module = Configuration(self.__main_view, self)
        self.__home_module = Home(self.__main_view, self)
        self.__account_module = BankAccounts(self.__main_view, self)
        self.__operation_module = Operations(self.__main_view, self)
        self.__chart = Chart(self.__main_view, self)
        self.__excel_report = ExcelReport(self.__main_view, self)
        self.__information = Information(self.__main_view, self)

        self.__setup_navigation_frame()
        self.show_home()

    def get_db(self) -> BankingDB:
        return self.__db

    def set_db(self, db: BankingDB) -> None:
        self.__db = db

    def get_config(self) -> dict:
        return self.__config

    def get_theme(self) -> dict:
        return self.__theme

    def show_home(self) -> None:
        self.__home_module.display()

    def show_configuration(self) -> None:
        self.__configuration_module.display()

    def show_bank_accounts(self) -> None:
        self.__account_module.show_bank_accounts()

    def show_account_menu(self, bank_account_row: pd.Series) -> None:
        self.__account_module.show_account_menu(bank_account_row)

    def show_operations(self, bank_account_row: pd.Series) -> None:
        self.__operation_module.display(bank_account_row)

    def show_charts(self, bank_account_row: pd.Series) -> None:
        self.__chart.display(bank_account_row)

    def show_excel_report(self, bank_account_row: pd.Series) -> None:
        self.__excel_report.display(bank_account_row)

    def show_information(self) -> None:
        self.__information.display()

    def create_card_grid(self, container: ctk.CTkFrame, items: list) -> None:
        """Crée une grille de cartes (3 max par ligne) parfaitement centrées."""

        # On vide le container au cas où
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

    def __setup_interface(self) -> None:
        """Création de l'interface graphique et centrage"""

        self.title("Financial Data Visualizer - Dashboard")
        self.minsize(1000, 800)

        # Lancement immédiat en mode maximisé
        self.after(10, lambda: self.wm_state("zoomed"))

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Zone principale de contenu
        self.__main_view = ctk.CTkFrame(self, corner_radius=15, fg_color="transparent")
        self.__main_view.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

    def __setup_navigation_frame(self) -> None:
        """Crée une barre latérale étroite avec des icônes."""

        # Configuration de la largeur de la barre
        self.__nav_frame = ctk.CTkFrame(self, corner_radius=0, width=70)
        self.__nav_frame.grid(row=0, column=0, sticky="nsew")
        self.__nav_frame.grid_rowconfigure(4, weight=1)

        icon_size = (28, 28)
        home_icon = ctk.CTkImage(light_image=Image.open("src/static/img/home.png"), size=icon_size)
        bank_account_icon = ctk.CTkImage(light_image=Image.open("src/static/img/bank_account.png"), size=icon_size)
        stock_icon = ctk.CTkImage(light_image=Image.open("src/static/img/stock.png"), size=icon_size)
        heritage_icon = ctk.CTkImage(light_image=Image.open("src/static/img/heritage.png"), size=icon_size)
        edit_icon = ctk.CTkImage(light_image=Image.open("src/static/img/edit.png"), size=icon_size)
        information_icon = ctk.CTkImage(light_image=Image.open("src/static/img/information.png"), size=icon_size)

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
            command=self.show_home,  # TODO
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

    def center_window(self, window: ctk.CTkInputDialog) -> None:
        """Centre une fenêtre au milieu de l'écran"""

        # Calcul des coordonnées pour centrer par rapport à l'application (self)
        x = self.winfo_x() + (self.winfo_width() // 2) - (window.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (window.winfo_height() // 2)

        window.geometry(f"+{x}+{y}")

    def destroy_widgets(self) -> None:
        """
        Supprime tous les widgets de la vue principale et force le rafraîchissement
        de l'affichage avant de continuer.
        """

        # Récupération de tous les enfants de la vue principale
        for widget in self.__main_view.winfo_children():
            widget.destroy()

        # Force Tkinter à traiter tous les événements de destruction en attente
        # Cela garantit que les widgets sont réellement enlevés de l'écran
        self.__main_view.update_idletasks()
