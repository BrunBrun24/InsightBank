import os
import shutil
from tkinter import messagebox

import customtkinter as ctk
import pandas as pd

from accounts.banking.reporting.excel_generator import ExcelGenerator
from accounts.banking.visualization.financial_chart import FinancialChart


class Account:
    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        self.__master = master
        self.__controller = controller
        self.__theme = controller.get_theme()
        self.__db = controller.get_db()
        self.__config = controller.get_config()

    def show_accounts(self) -> None:
        """Affiche le Dashboard global avec les comptes sous forme de cartes."""

        self.__controller.destroy_widgets()

        # Titre et Résumé Global
        title_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(title_frame, text="Tableau de Bord", font=("Arial", 32, "bold")).pack(side="left")

        ctk.CTkButton(
            title_frame,
            text="+ Ajouter un compte",
            fg_color=self.__theme["green"]["fg_color"],
            hover_color=self.__theme["green"]["hover_color"],
            command=self.__handle_add_account,
        ).pack(side="right")

        # Grille des comptes
        # On utilise une Frame scrollable pour la grille
        scroll_container = ctk.CTkScrollableFrame(self.__master, fg_color="transparent")
        scroll_container.pack(fill="both", expand=True, padx=20, pady=10)

        # Configuration de la grille (3 colonnes pour que ce soit aéré)
        scroll_container.grid_columnconfigure((0, 1, 2), weight=1, pad=20)

        try:
            account_df = self.__db.get_all_accounts()
            if not account_df.empty:
                for index, row in account_df.iterrows():
                    self.__create_account_card(scroll_container, row, index)
            else:
                ctk.CTkLabel(scroll_container, text="Aucun compte. Cliquez sur 'Ajouter' pour commencer.").grid(
                    row=0, column=0, columnspan=3, pady=50
                )
        except Exception as e:
            raise e

    def show_account_menu(self, account_row: pd.Series) -> None:
        """Affiche les différentes actions que l'on peut effectuer sur un compte"""

        self.__controller.destroy_widgets()

        # On crée un frame qui prend toute la largeur
        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=10)

        # Bouton de retour placé en absolu pour ne pas gêner le centrage du label
        back_btn = ctk.CTkButton(
            header_frame,
            text="←",
            fg_color=self.__theme["blue_01"]["fg_color"],
            hover_color=self.__theme["blue_01"]["hover_color"],
            width=40,
            command=self.__controller.show_accounts,
        )
        back_btn.place(x=0, y=15)

        title_label = ctk.CTkLabel(header_frame, text=f"{account_row['name']}", font=("Arial", 60, "bold"))
        title_label.pack(expand=True)

        # Conteneur principal
        container = ctk.CTkFrame(self.__master, fg_color="transparent")
        container.pack(fill="x", pady=200)
        container.grid_columnconfigure((0, 1, 2), weight=1)

        # Configuration des actions
        actions = [
            {
                "name": "Données",
                "desc": "Importer ou modifier\nvos transactions.",
                "fg_color": self.__theme["blue_02"]["fg_color"],
                "hover_color": self.__theme["blue_02"]["hover_color"],
                "icon_path": "src/static/img/directory.png",
                "cmd": lambda: self.__controller.show_operations(account_row),
            },
            {
                "name": "Analyses",
                "desc": "Visualiser la santé\nde vos finances.",
                "fg_color": self.__theme["blue_03"]["fg_color"],
                "hover_color": self.__theme["blue_03"]["fg_color"],
                "icon_path": "src/static/img/chart.png",
                "cmd": lambda: self.__controller.show_charts(account_row),
            },
            {
                "name": "Rapports",
                "desc": "Générer un fichier\nExcel complet.",
                "fg_color": self.__theme["magenta"]["fg_color"],
                "hover_color": self.__theme["magenta"]["hover_color"],
                "icon_path": "src/static/img/file.png",
                "cmd": lambda: self.__controller.show_excel_report(account_row),
            },
        ]

        self.__controller.create_card_grid(container, actions)

    def __create_account_card(self, master: ctk.CTkScrollableFrame, row: pd.Series, index: int) -> None:
        """Crée une carte stylisée pour un compte bancaire incluant le solde total."""

        # Positionnement de la carte dans la grille principale
        r, c = divmod(index, 3)
        card = ctk.CTkFrame(master, corner_radius=15, height=240, width=280, border_width=2)
        card.grid(row=r, column=c, padx=15, pady=15, sticky="nsew")
        card.grid_propagate(False)

        # Nom du compte
        lbl_name = ctk.CTkLabel(card, text=row["name"], font=("Arial", 20, "bold"))
        lbl_name.pack(pady=(15, 2))

        # Récupération des statistiques
        stats = self.__db.get_account_statistics(row["id"])

        total_amount = stats.get("account_amount", 0.0)

        # Formatage du texte
        formatted_balance = f"{total_amount:,.2f}".replace(",", " ").replace(".", ",") + " €"
        balance_color = self.__theme["green"]["fg_color"] if total_amount >= 0 else self.__theme["red"]["fg_color"]

        lbl_balance = ctk.CTkLabel(card, text=formatted_balance, font=("Arial", 24, "bold"), text_color=balance_color)
        lbl_balance.pack(pady=10)

        # Nombre d'opérations
        lbl_ops = ctk.CTkLabel(
            card,
            text=f"{stats.get('total', 0)} opérations enregistrées",
            text_color="gray",
            font=("Arial", 12, "italic"),
        )
        lbl_ops.pack(pady=(0, 5))

        # Conteneur pour les boutons
        button_container = ctk.CTkFrame(card, fg_color="transparent")
        button_container.pack(side="bottom", padx=10, pady=15)
        button_container.columnconfigure((0, 1, 2), weight=1)

        # Configuration des boutons
        btn_configs = [
            {
                "text": "Ouvrir",
                "fg_color": self.__theme["green"]["fg_color"],
                "hover_color": self.__theme["green"]["hover_color"],
                "cmd": lambda: self.__controller.show_account_menu(row),
            },
            {
                "text": "Éditer",
                "fg_color": self.__theme["blue_01"]["fg_color"],
                "hover_color": self.__theme["blue_01"]["hover_color"],
                "cmd": lambda: self.__handle_edit_account(row["id"], row["name"]),
            },
            {
                "text": "Supprimer",
                "fg_color": self.__theme["red"]["fg_color"],
                "hover_color": self.__theme["red"]["hover_color"],
                "cmd": lambda: self.__handle_delete_account(row["id"], row["name"]),
            },
        ]

        for i, config in enumerate(btn_configs):
            btn = ctk.CTkButton(
                button_container,
                text=config["text"],
                width=75,
                height=28,
                fg_color=config["fg_color"],
                hover_color=config["hover_color"],
                command=config["cmd"],
            )
            btn.grid(row=0, column=i, padx=5)

    def __handle_add_account(self) -> None:
        """Ouvre une boîte de dialogue pour créer un nouveau compte bancaire."""

        dialog = ctk.CTkInputDialog(text="Entrez le nom du nouveau compte :", title="Nouveau Compte")
        self.__controller.center_window(dialog)
        dialog.transient(self.__master)
        dialog.attributes("-topmost", False)

        account_name = dialog.get_input()

        if account_name:
            try:
                self.__db.add_account(account_name)
                self.__controller.show_accounts()

            except ValueError as e:
                messagebox.showwarning("Doublon", str(e))
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de créer le compte : {e}")
                raise

    def __handle_delete_account(self, account_id: int, account_name: str) -> None:
        """Demande confirmation avant de supprimer un compte et ses données."""

        if messagebox.askyesno(
            "Confirmation",
            f"Supprimer le compte '{account_name}' ?\nCette action est irréversible.",
        ):
            try:
                # Supprime le dossier bilan du compte
                path = os.path.join(self.__config["destination_path"], account_name)
                if os.path.exists(path):
                    shutil.rmtree(path)

                self.__db.delete_account(account_id)
                self.__controller.show_accounts()
            except Exception as e:
                messagebox.showerror(
                    "Erreur de suppression", f"Impossible de supprimer le compte ou ses fichiers :\n{str(e)}"
                )
                raise

    def __handle_edit_account(self, account_id: int, old_name: str) -> None:
        """Ouvre un dialogue centré et immobile pour renommer le compte."""

        dialog = ctk.CTkInputDialog(
            text=f"Nouveau nom pour '{old_name}' :",
            title="Renommer",
            button_fg_color=self.__theme["blue_01"]["fg_color"],
            button_hover_color=self.__theme["blue_01"]["hover_color"],
        )
        self.__controller.center_window(dialog)
        dialog.transient(self.__master)
        dialog.attributes("-topmost", False)

        new_name = dialog.get_input()

        if new_name and new_name != old_name:
            try:
                self.__db.update_account_name(account_id, new_name)
                self.__update_bilan(account_id, new_name)
                self.__controller.show_accounts()

            except Exception as e:
                messagebox.showerror(f"Erreur lors de la modification du nom du compte : {str(e)}")
                raise

    def __update_bilan(self, account_id: int, account_name: str) -> None:
        """Coordonne la mise à jour complète des fichiers bilan pour un compte bancaire."""

        # Supprime le dossier bilan du compte pour que les données soient à jour
        path = os.path.join(self.__config["destination_path"], account_name)
        if os.path.exists(path):
            shutil.rmtree(path)

        # Créer les graphiques HTML
        chart_generator = FinancialChart(self.__db, account_name)
        chart_generator.generate_all_reports(account_id)

        # Créer les fichiers Excel
        excel_generator = ExcelGenerator(self.__db, account_name)
        excel_generator.generate_all_reports(account_id)
