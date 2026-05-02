import os
import webbrowser

import customtkinter as ctk
import pandas as pd
from PIL import Image


class Chart:
    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        self.__master = master
        self.__controller = controller
        self.__config = controller.get_config()
        self.__theme = controller.get_theme()

    def display(self, bank_account_row: pd.Series) -> None:
        """Affiche les années disponibles sous forme de cartes pour accéder au bilan HTML"""

        self.__controller.destroy_widgets()

        # Configuration du chemin
        bilan_dir = os.path.join(self.__config["destination_path"], bank_account_row["name"])

        # Créer le dossier s'il n'existe pas
        if not os.path.exists(bilan_dir):
            os.makedirs(bilan_dir)

        # Header avec bouton retour
        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(10, 60))

        back_btn = ctk.CTkButton(
            header_frame,
            text="←",
            fg_color=self.__theme["blue_03"]["fg_color"],
            hover_color=self.__theme["blue_03"]["hover_color"],
            width=40,
            command=lambda: self.__controller.show_account_menu(bank_account_row),
        )
        back_btn.place(x=0, y=15)

        title_label = ctk.CTkLabel(header_frame, text="Bilans Graphiques", font=("Arial", 60, "bold"))
        title_label.pack(expand=True)

        # Scan des fichiers HTML disponibles
        # On cherche les fichiers qui finissent par .html (ex: Bilan 2026.html, Bilan 2020-2026.html)
        available_years = []
        for file in os.listdir(bilan_dir):
            if file.endswith(".html"):
                # Extraction : "Bilan 2026.html" -> "2026"
                year_name = file.replace("Bilan ", "").replace(".html", "")

                # On construit le chemin relatif vers le fichier
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

        download_icon = ctk.CTkImage(light_image=Image.open("src/static/img/download.png"), size=(24, 24))
        calendar_logo = ctk.CTkImage(light_image=Image.open("src/static/img/chart.png"), size=(48, 48))

        # Génération des cartes d'années
        for i, data in enumerate(available_years):
            # Création de la carte
            card = ctk.CTkFrame(scroll_container, corner_radius=15, border_width=1, height=200)
            card.grid(row=i // 4, column=i % 4, padx=15, pady=15, sticky="nsew")
            card.grid_propagate(False)

            download_btn = ctk.CTkButton(
                card,
                text="",
                image=download_icon,
                width=32,
                height=32,
                fg_color="transparent",
                hover_color=("gray85", "gray25"),
                command=lambda p=data["path"]: self.__handle_download(p),
            )
            download_btn.place(relx=1.0, x=-10, y=10, anchor="ne")

            # Icône Calendrier
            ctk.CTkLabel(card, text="", image=calendar_logo).pack(pady=(20, 5))

            # Année
            ctk.CTkLabel(card, text=data["year"], font=("Arial", 22, "bold")).pack()

            # Bouton Voir
            ctk.CTkButton(
                card,
                text="Voir le bilan",
                fg_color=self.__theme["blue_03"]["fg_color"],
                hover_color=self.__theme["blue_03"]["hover_color"],
                command=lambda p=data["path"]: self.__open_in_browser(p),
                corner_radius=8,
                height=30,
                font=("Arial", 12, "bold"),
            ).pack(side="bottom", pady=15, padx=15, fill="x")

    def __open_in_browser(self, file_path: str) -> None:
        """Ouvre le fichier HTML dans le navigateur par défaut de l'utilisateur"""

        absolute_path = os.path.abspath(file_path)

        if os.path.exists(absolute_path):
            # Utilisation du module webbrowser pour lancer le navigateur par défaut
            # new=2 ouvre dans un nouvel onglet si possible
            webbrowser.open(f"file://{absolute_path}", new=2)
