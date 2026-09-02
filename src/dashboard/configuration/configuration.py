import customtkinter as ctk
from PIL import Image

from config import load_config, update_config_benchmark, update_config_currency


class Configuration:
    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        self.__master = master
        self.__controller = controller
        self.__theme = controller.get_theme()

    def display(self) -> None:
        self.__controller.destroy_widgets()

        # 1. Header
        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(30, 20))
        ctk.CTkLabel(header_frame, text="Configuration", font=("Arial", 50, "bold")).pack()

        # 2. Conteneurs
        grid_container = ctk.CTkFrame(self.__master, fg_color="transparent")
        grid_container.pack(fill="both", expand=True, anchor="n")

        inner_container = ctk.CTkFrame(grid_container, fg_color="transparent")
        inner_container.pack(anchor="n")
        inner_container.grid_columnconfigure((0, 1, 2), weight=1, uniform="cards")

        currency = load_config()["currency"]
        ticker_benchmark = load_config()["benchmark"]
        if ticker_benchmark == "^GSPC":
            benchmark = "S&P 500"
        elif ticker_benchmark == "^IXIC":
            benchmark = "NASDAQ"
        elif ticker_benchmark == "URTH":
            benchmark = "MSCI World"
        elif ticker_benchmark == "^FCHI":
            benchmark = "CAC 40"

        CARD_W = 550
        CARD_H = 300

        self.__create_module_card(
            inner_container,
            0,
            0,
            "Catégories et Sous-Catégories",
            "Optimisez la structure de votre budget en créant un système personnalisé de catégories et de sous-catégories. "
            "Cette flexibilité vous permet de classer précisément chaque opération, qu'il s'agisse de revenus récurrents ou de "
            "dépenses imprévues, pour une analyse financière détaillée",
            "src/static/img/icons/file.png",
            "Ouvrir",
            command=self.__controller.show_categories_sub_categories,
            width=CARD_W,
            height=CARD_H,
        )

        self.__create_module_card(
            inner_container,
            0,
            1,
            "Automatisation",
            "Simplifiez votre gestion financière grâce à l'attribution automatique de vos nouvelles opérations. "
            "En analysant instantanément vos opérations selon vos critères prédéfinis, l'application classe automatiquement "
            "vos flux entrants et sortants pour vous offrir un suivi sans aucun effort manuel",
            "src/static/img/icons/bot.png",
            "Ouvrir",
            command=self.__controller.show_automatisation_cat_sub_cat,
            width=CARD_W,
            height=CARD_H,
        )

        self.__create_module_card(
            inner_container,
            0,
            2,
            "Devise",
            "Sélectionnez la monnaie d'affichage principale appliquée à l'ensemble de votre patrimoine."
            "Vos montants et analyses seront automatiquement convertis pour vous offrir une vision consolidée "
            "et homogène dans la devise de votre choix",
            "src/static/img/icons/heritage.png",
            currency,
            command=update_config_currency,
            widget_type="menu",
            menu_values=["EUR", "USD"],
            width=CARD_W,
            height=CARD_H,
        )

        self.__create_module_card(
            inner_container,
            1,
            0,
            "Titres",
            "Gérez la composition de vos portefeuilles en toute simplicité. "
            "Ajoutez ou supprimez des entreprises et des titres financiers pour chaque portefeuille, "
            "et conservez une vue d'ensemble claire de vos investissements",
            "src/static/img/icons/file.png",
            "Ouvrir",
            command=self.__controller.show_portfolio_tickers,
            width=CARD_W,
            height=CARD_H,
        )

        self.__create_module_card(
            inner_container,
            1,
            1,
            "Benchmark",
            "Comparez la performance globale de votre portefeuille ainsi que chacun de vos titres "
            "face à votre indice de référence. "
            "Identifiez instantanément si vos investissements battent le marché "
            "et repérez les actifs qui génèrent de la surperformance",
            "src/static/img/icons/stock.png",
            benchmark,
            command=update_config_benchmark,
            widget_type="menu",
            menu_values=["S&P 500", "NASDAQ", "MSCI World", "CAC 40"],
            width=CARD_W,
            height=CARD_H,
        )

    def __create_module_card(
        self,
        parent,
        row,
        col,
        title,
        desc,
        icon_path,
        action_text,
        command,
        widget_type="button",
        menu_values=None,
        color="blue_01",
        width=320,
        height=360,
    ) -> None:
        """Créez une carte spécialisée"""

        # Création de la carte avec taille fixe
        card = ctk.CTkFrame(parent, corner_radius=20, border_width=1, width=width, height=height)
        card.grid(row=row, column=col, padx=15, pady=15, sticky="n")

        # Bloque la taille pour qu'elle ne bouge pas
        card.pack_propagate(False)

        # Icône
        img = ctk.CTkImage(light_image=Image.open(icon_path), size=(45, 45))
        ctk.CTkLabel(card, image=img, text="").pack(pady=(25, 10))

        # Titre
        ctk.CTkLabel(card, text=title, font=("Arial", 20, "bold")).pack(pady=5)

        # Description
        ctk.CTkLabel(
            card, text=desc, text_color="gray", font=("Arial", 13), wraplength=width - 40, justify="center"
        ).pack(pady=5, padx=20)

        spacer = ctk.CTkFrame(card, fg_color="transparent", height=0)
        spacer.pack(expand=True, fill="both")

        # On place le widget dans un petit frame en bas pour assurer sa visibilité
        action_container = ctk.CTkFrame(card, fg_color="transparent")
        action_container.pack(side="bottom", pady=(0, 25))

        if widget_type == "menu":
            current_var = ctk.StringVar(value=action_text)
            widget = ctk.CTkOptionMenu(
                action_container,
                values=menu_values if menu_values else ["Options"],
                variable=current_var,
                command=command,
                width=width * 0.25,
                height=30,
                corner_radius=10,
                fg_color=self.__theme[color]["fg_color"],
                button_color=self.__theme[color]["hover_color"],
            )
        else:
            widget = ctk.CTkButton(
                action_container,
                text=action_text,
                command=command,
                width=width * 0.25,
                height=30,
                corner_radius=10,
                fg_color=self.__theme[color]["fg_color"],
                hover_color=self.__theme[color]["hover_color"],
            )

        widget.pack()
