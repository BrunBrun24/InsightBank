import os
import shutil
import subprocess
from tkinter import filedialog, messagebox

import customtkinter as ctk
import pandas as pd
from PIL import Image


class ExcelReport:
    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        self.__master = master
        self.__controller = controller
        self.__config = controller.get_config()
        self.__theme = controller.get_theme()

    def display(self, account_row: pd.Series) -> None:
        """Affiche les années disponibles sous forme de cartes pour accéder au bilan Excel"""

        self.__controller.destroy_widgets()

        bilan_dir = os.path.join(self.__config["destination_path"], account_row["name"])

        # Créer le dossier s'il n'existe pas
        if not os.path.exists(bilan_dir):
            os.makedirs(bilan_dir)

        # Header avec bouton retour
        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(10, 60))

        back_btn = ctk.CTkButton(
            header_frame,
            text="←",
            fg_color=self.__theme["magenta"]["fg_color"],
            hover_color=self.__theme["magenta"]["hover_color"],
            width=40,
            command=lambda: self.__controller.show_account_menu(account_row),
        )
        back_btn.place(x=0, y=15)

        title_label = ctk.CTkLabel(header_frame, text="Bilans Excel", font=("Arial", 60, "bold"))
        title_label.pack(expand=True)

        # Scan des fichiers HTML disponibles
        # On cherche les fichiers qui finissent par .xlsx (ex: Bilan 2026.xlsx, Bilan 2020-2026.xlsx)
        available_years = []
        for file in os.listdir(bilan_dir):
            if file.endswith(".xlsx"):
                # Extraction : "Bilan 2026.xlsx" -> "2026"
                year_name = file.replace("Bilan ", "").replace(".xlsx", "")

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

        download_logo = ctk.CTkImage(light_image=Image.open("src/static/img/download.png"), size=(24, 24))
        excel_logo = ctk.CTkImage(light_image=Image.open("src/static/img/file.png"), size=(48, 48))

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
                command=lambda p=data["path"]: self.__handle_download(p),
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
                command=lambda p=data["path"]: self.__open_xlsx_window(p),
                corner_radius=8,
                height=30,
                font=("Arial", 12, "bold"),
            ).pack(side="bottom", pady=15, padx=15, fill="x")

    def __open_xlsx_window(self, file_path: str) -> None:
        """Ouvre le fichier Excel."""

        if not os.path.exists(file_path):
            messagebox.showerror("Erreur", "Le fichier Excel est introuvable.")
            return

        try:
            subprocess.Popen(["start", "excel", "/r", os.path.abspath(file_path)], shell=True)

        except (OSError, subprocess.SubprocessError):
            try:
                os.startfile(file_path)
            except OSError:
                messagebox.showerror(
                    "Erreur critique", f"Aucun logiciel n'est associé aux fichiers {os.path.splitext(file_path)[1]}"
                )

    def __handle_download(self, file_path: str) -> None:
        """Permet à l'utilisateur de copier le bilan HTML vers un emplacement local."""

        try:
            # Vérifier si le fichier source existe
            if not os.path.exists(file_path):
                messagebox.showerror("Erreur", "Le fichier source est introuvable.")
                return

            # Extraire le nom du fichier par défaut
            default_filename = os.path.basename(file_path)

            # Ouvrir la boîte de dialogue pour choisir la destination
            destination_path = filedialog.asksaveasfilename(
                defaultextension=".html",
                initialfile=default_filename,
                filetypes=[("Fichier HTML", "*.html"), ("Tous les fichiers", "*.*")],
                title="Télécharger le bilan",
            )

            # Si l'utilisateur n'a pas annulé, on copie le fichier
            if destination_path:
                shutil.copy2(file_path, destination_path)
                messagebox.showinfo(
                    "Succès", f"Le bilan a été téléchargé avec succès :\n{os.path.basename(destination_path)}"
                )

        except Exception as e:
            messagebox.showerror("Erreur", f"Échec du téléchargement : {str(e)}")
            raise
