import json
import threading
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from utils.loading_popup import LoadingPopup


class DataManagement:
    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        self.__master = master
        self.__controller = controller
        self.__theme = controller.get_theme()

    def display(self) -> None:
        """Affiche la page de gestion des données sans scroll et centrée."""
        self.__controller.destroy_widgets()

        # Configuration de la grille principale pour centrer le contenu
        self.__master.grid_rowconfigure(1, weight=1)
        self.__master.grid_columnconfigure(0, weight=1)

        # Header supérieur
        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=10)

        # Bouton de retour placé en absolu pour ne pas gêner le centrage du label
        back_btn = ctk.CTkButton(
            header_frame,
            text="←",
            fg_color=self.__theme["blue_01"]["fg_color"],
            hover_color=self.__theme["blue_01"]["hover_color"],
            width=40,
            command=self.__controller.show_configuration,
        )
        back_btn.place(x=0, y=15)

        # Titre centré
        ctk.CTkLabel(
            header_frame,
            text="Importation & Exportation des Données",
            font=("Arial", 30, "bold"),
        ).pack(pady=(5, 10))

        # Conteneur fixe occupant tout l'espace disponible
        main_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        main_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Conteneur de grille pour les cartes, centré dans main_frame
        grid_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        grid_container.grid(row=0, column=0, sticky="n", pady=(150, 0))

        items = [
            {
                "name": "Importation",
                "desc": "                   Restaurez vos données à partir d'un fichier de sauvegarde JSON préalablement exporté.                   \nAttention, cette action remplacera les données actuelles",
                "icon_path": "src/static/img/icons/file.png",
                "fg_color": self.__theme["green"]["fg_color"],
                "hover_color": self.__theme["green"]["hover_color"],
                "cmd": self.__import_data,
            },
            {
                "name": "Exportation",
                "desc": "                       Sauvegardez l'intégralité de vos bases de données sous forme de fichiers JSON                       \npour les archiver ou les transférer en toute sécurité",
                "icon_path": "src/static/img/icons/file.png",
                "fg_color": self.__theme["blue_01"]["fg_color"],
                "hover_color": self.__theme["blue_01"]["hover_color"],
                "cmd": self.__export_data,
            },
        ]

        self.__controller.create_card_grid(grid_container, items)

    def __export_data(self) -> None:
        """Gère l'exportation globale des bases de données vers un fichier JSON."""
        default_filename = f"insightbank_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.json"

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=default_filename,
            filetypes=[("Fichiers JSON", "*.json"), ("Tous les fichiers", "*.*")],
            title="Exporter les données",
        )
        if not file_path:
            return

        # Affichage du popup de chargement
        loading_win = LoadingPopup(self.__controller, "Exportation des données en cours...")

        def task():
            try:
                combined_data = {}

                # Récupération et ajout des données de BankDB
                bank_db = self.__controller.get_bank_db()
                if bank_db:
                    combined_data["bank_database"] = bank_db.export_database_to_dict()

                # Récupération et ajout des données de StockDB
                stock_db = self.__controller.get_stock_db()
                if stock_db:
                    combined_data["stock_database"] = stock_db.export_database_to_dict()

                # Écriture de l'ensemble dans le fichier JSON unique
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(combined_data, f, ensure_ascii=False, indent=4)

                self.__controller.after(0, lambda: self.__on_export_success(loading_win))
            except Exception as e:
                self.__controller.after(0, lambda err=e: self.__on_export_error(loading_win, err))

        threading.Thread(target=task, daemon=True).start()

    def __on_export_success(self, loading_win) -> None:
        if loading_win and loading_win.winfo_exists():
            loading_win.close()
        messagebox.showinfo("Succès", "L'exportation des données a été réalisée avec succès !")

    def __on_export_error(self, loading_win, error) -> None:
        if loading_win and loading_win.winfo_exists():
            loading_win.close()
        messagebox.showerror("Erreur", f"Une erreur est survenue lors de l'exportation :\n{error}")

    def __import_data(self) -> None:
        """Gère l'importation globale des données depuis un fichier JSON."""
        file_path = filedialog.askopenfilename(
            filetypes=[("Fichiers JSON", "*.json")],
            title="Sélectionner le fichier à importer",
        )
        if not file_path:
            return

        loading_win = LoadingPopup(self.__controller, "Importation des données en cours...")

        def task():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    combined_data = json.load(f)

                # Restauration de la base bancaire
                bank_db = self.__controller.get_bank_db()
                if bank_db and "bank_database" in combined_data:
                    bank_db.import_database_from_dict(combined_data["bank_database"])

                # Restauration de la base boursière (si présente)
                stock_db = self.__controller.get_stock_db()
                if stock_db and "stock_database" in combined_data:
                    stock_db.import_database_from_dict(combined_data["stock_database"])

                self.__controller.after(0, lambda: self.__on_import_success(loading_win))
            except Exception as e:
                self.__controller.after(0, lambda err=e: self.__on_import_error(loading_win, err))

        threading.Thread(target=task, daemon=True).start()

    def __on_import_success(self, loading_win) -> None:
        if loading_win and loading_win.winfo_exists():
            loading_win.close()
        self.__controller.update_all_bank_stock_bilan()
        self.__controller.show_home()

    def __on_import_error(self, loading_win, error) -> None:
        if loading_win and loading_win.winfo_exists():
            loading_win.close()
        messagebox.showerror("Erreur", f"Une erreur est survenue lors de l'importation :\n{error}")
