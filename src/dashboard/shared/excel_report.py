import os
from typing import Literal

import customtkinter as ctk
import pandas as pd
from PIL import Image

from utils.data_utils import handle_download, open_xlsx_window


class ExcelReport:
    def __init__(self, master: ctk.CTkFrame, controller, mode: Literal["bank", "stock"] = "bank") -> None:
        self.__master = master
        self.__controller = controller
        self.__config = controller.get_config()
        self.__theme = controller.get_theme()
        self.__mode = mode

    def display(self, account_row: pd.Series) -> None:
        """Affiche les années disponibles sous forme de cartes pour accéder au bilan Excel"""

        self.__controller.destroy_widgets()

        # Configuration du chemin selon le mode
        subfolder = "bank_account" if self.__mode == "bank" else "stock"
        bilan_dir = os.path.join(self.__config["destination_path"], subfolder, account_row["name"])

        # Créer le dossier s'il n'existe pas
        if not os.path.exists(bilan_dir):
            os.makedirs(bilan_dir)

        # Action du bouton retour adaptée au mode
        back_command = (
            (lambda: self.__controller.show_bank_account_menu(account_row))
            if self.__mode == "bank"
            else (lambda: self.__controller.show_stock_account_menu(account_row))
        )

        # Header avec bouton retour
        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(10, 60))

        back_btn = ctk.CTkButton(
            header_frame,
            text="←",
            fg_color=self.__theme["magenta"]["fg_color"],
            hover_color=self.__theme["magenta"]["hover_color"],
            width=40,
            command=back_command,
        )
        back_btn.place(x=0, y=15)

        title_label = ctk.CTkLabel(header_frame, text="Bilans Excel", font=("Arial", 60, "bold"))
        title_label.pack(expand=True)

        # On cherche les fichiers qui finissent par .xlsx
        available_years = []
        for file in os.listdir(bilan_dir):
            if file.endswith(".xlsx"):
                year_name = file.replace(".xlsx", "")
                file_path = os.path.join(bilan_dir, file)
                available_years.append({"year": year_name, "path": file_path})

        # Trier les années par ordre décroissant
        available_years.sort(key=lambda x: (1 if "-" in x["year"] else 0, x["year"]), reverse=True)

        # Conteneur pour les cartes
        scroll_container = ctk.CTkScrollableFrame(self.__master, fg_color="transparent")
        scroll_container.pack(fill="both", expand=True, pady=40, padx=40)

        # On définit une grille de 4 colonnes
        scroll_container.grid_columnconfigure((0, 1, 2, 3), weight=1)

        if not available_years:
            ctk.CTkLabel(scroll_container, text="Aucun bilan généré pour le moment.", font=("Arial", 16)).pack(pady=100)
            return

        download_logo = ctk.CTkImage(light_image=Image.open("src/static/img/icons/download.png"), size=(24, 24))
        excel_logo = ctk.CTkImage(light_image=Image.open("src/static/img/icons/file.png"), size=(48, 48))

        # Génération des cartes d'années
        for i, data in enumerate(available_years):
            # Création de la carte
            card = ctk.CTkFrame(scroll_container, corner_radius=15, border_width=1, height=200)
            card.grid(row=i // 4, column=i % 4, padx=15, pady=15, sticky="nsew")
            card.grid_propagate(False)

            download_btn = ctk.CTkButton(
                card,
                text="",
                image=download_logo,
                width=32,
                height=32,
                fg_color="transparent",
                hover_color=("gray85", "gray25"),
                command=lambda p=data["path"]: handle_download(p),
            )
            download_btn.place(relx=1.0, x=-10, y=10, anchor="ne")

            # Icône file
            ctk.CTkLabel(card, text="", image=excel_logo).pack(pady=(20, 5))

            # Année
            ctk.CTkLabel(card, text=data["year"], font=("Arial", 22, "bold")).pack()

            # Bouton Voir
            ctk.CTkButton(
                card,
                text="Ouvrir dans Excel",
                fg_color=self.__theme["magenta"]["fg_color"],
                hover_color=self.__theme["magenta"]["hover_color"],
                command=lambda p=data["path"]: open_xlsx_window(p),
                corner_radius=8,
                height=30,
                font=("Arial", 12, "bold"),
            ).pack(side="bottom", pady=15, padx=15, fill="x")
