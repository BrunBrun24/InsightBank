from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from accounts.banking.database.banking_db import BankingDB
from config import load_config, save_config


class Configuration:
    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        self.__master = master
        self.__controller = controller
        self.__config = controller.get_config()
        self.__theme = controller.get_theme()
        self.__db_path = self.__config["database"]["database_path"]

    def display(self) -> None:
        self.__controller.destroy_widgets()

        # 1. Header
        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(40, 20))
        ctk.CTkLabel(header_frame, text="Configuration", font=("Arial", 60, "bold")).pack()

        # 2. Conteneurs
        grid_container = ctk.CTkFrame(self.__master, fg_color="transparent")
        grid_container.pack(fill="both", expand=True, anchor="n")

        inner_container = ctk.CTkFrame(grid_container, fg_color="transparent")
        inner_container.pack(anchor="n")
        inner_container.grid_columnconfigure((0, 1, 2), weight=1, uniform="cards")

        CARD_W = 550
        CARD_H = 300

        self.__create_module_card(
            inner_container,
            0,
            0,
            "Source Bancaire",
            "Renseignez ici les établissements bancaires que vous utilisez au quotidien, tels que la BNP Paribas, Boursorama ou le Crédit Agricole. Cette étape est essentielle pour identifier la provenance de vos flux financiers et permettre à l'application d'extraire et de traiter correctement vos données par la suite pour vos analyses.",
            "src/static/img/bank_account.png",
            self.__config["bank"],
            command=self.__update_config_bank,
            widget_type="menu",
            menu_values=["Non défini", "BNP Paribas"],
            width=CARD_W,
            height=CARD_H,
        )

        self.__create_module_card(
            inner_container,
            0,
            1,
            "Architecture",
            "Optimisez la structure de votre budget en créant un système personnalisé de catégories et de sous-catégories. Cette flexibilité vous permet de classer précisément chaque opération, qu'il s'agisse de revenus récurrents ou de dépenses imprévues, pour une analyse financière détaillée.",
            "src/static/img/file.png",
            "Ouvrir",
            command=self.__controller.show_categories_sub_categories,
            width=CARD_W,
            height=CARD_H,
        )

        self.__create_module_card(
            inner_container,
            0,
            2,
            "Automatisation",
            "Simplifiez votre gestion financière grâce à l'attribution automatique de vos nouvelles opérations. En analysant instantanément vos transactions selon vos critères prédéfinis, l'application classe automatiquement vos flux entrants et sortants pour vous offrir un suivi sans aucun effort manuel.",
            "src/static/img/bot.png",
            "Ouvrir",
            command=self.__controller.show_automatisation_cat_sub_cat,
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

    def __update_config_bank(self, bank: str):
        """Met à jour la banque dans le fichier de configuration"""

        try:
            full_config = load_config()
            full_config["bank"] = bank

            save_config(full_config)
            self.__config = load_config()
            self.__controller.set_db(BankingDB(self.__db_path))

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'écriture du fichier : {e}")
            raise
