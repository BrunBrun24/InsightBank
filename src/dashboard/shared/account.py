import os
import random
import shutil
from tkinter import messagebox
from typing import Literal

import customtkinter as ctk
import pandas as pd

from utils.window_utils import center_window_on_parent


class Account:
    """Vue générique permettant d'afficher des comptes bancaires ou des portefeuilles boursiers."""

    def __init__(self, master: ctk.CTkFrame, controller, mode: Literal["banking", "stock"] = "banking") -> None:
        self.__master = master
        self.__controller = controller
        self.__theme = controller.get_theme()
        self.__config = controller.get_config()
        self.__mode = mode
        self.__db = controller.get_db_banking() if mode == "banking" else controller.get_db_stock()

    def display(self) -> None:
        """Affiche le tableau de bord avec les cartes de comptes ou de portefeuilles."""

        self.__controller.destroy_widgets()

        # En-tête
        title_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=10)

        page_title = "Tableau de Bord - Comptes" if self.__mode == "banking" else "Portefeuilles Boursiers"
        btn_text = "+ Ajouter un compte" if self.__mode == "banking" else "+ Ajouter un portefeuille"

        ctk.CTkLabel(title_frame, text=page_title, font=("Arial", 32, "bold")).pack(side="left")

        ctk.CTkButton(
            title_frame,
            text=btn_text,
            fg_color=self.__theme["green"]["fg_color"],
            hover_color=self.__theme["green"]["hover_color"],
            command=self.__handle_add_item,
        ).pack(side="right")

        # Conteneur défilant
        scroll_container = ctk.CTkScrollableFrame(self.__master, fg_color="transparent")
        scroll_container.pack(fill="both", expand=True, padx=20, pady=10)
        scroll_container.grid_columnconfigure((0, 1, 2), weight=1, pad=20)

        items_df = self.__db.get_all_bank_accounts() if self.__mode == "banking" else self.__db.get_all_portfolios()

        if not items_df.empty:
            for index, row in items_df.iterrows():
                self.__create_card(scroll_container, row, index)
        else:
            empty_msg = (
                "Aucun compte bancaire enregistré."
                if self.__mode == "banking"
                else "Aucun portefeuille boursier enregistré."
            )
            ctk.CTkLabel(scroll_container, text=empty_msg).grid(row=0, column=0, columnspan=3, pady=50)

    def show_account_menu(self, bank_account_row: pd.Series) -> None:
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
            command=self.__controller.show_bank_accounts
            if self.__mode == "banking"
            else self.__controller.show_stock_portfolios,
        )
        back_btn.place(x=0, y=15)

        title_label = ctk.CTkLabel(header_frame, text=f"{bank_account_row['name']}", font=("Arial", 60, "bold"))
        title_label.pack(expand=True)

        # Conteneur principal
        container = ctk.CTkFrame(self.__master, fg_color="transparent")
        container.pack(fill="x", pady=200)
        container.grid_columnconfigure((0, 1, 2), weight=1)

        # Configuration des actions
        if self.__mode == "banking":
            actions = [
                {
                    "name": "Données",
                    "desc": "Importer ou modifier\nvos opérations.",
                    "fg_color": self.__theme["blue_02"]["fg_color"],
                    "hover_color": self.__theme["blue_02"]["hover_color"],
                    "icon_path": "src/static/img/icons/directory.png",
                    "cmd": lambda: self.__controller.show_bank_operations(bank_account_row),
                },
                {
                    "name": "Analyses",
                    "desc": "Visualiser la santé\nde vos finances.",
                    "fg_color": self.__theme["blue_03"]["fg_color"],
                    "hover_color": self.__theme["blue_03"]["fg_color"],
                    "icon_path": "src/static/img/icons/chart.png",
                    "cmd": lambda: self.__controller.show_charts(bank_account_row),
                },
                {
                    "name": "Rapports",
                    "desc": "Générer un fichier\nExcel complet.",
                    "fg_color": self.__theme["magenta"]["fg_color"],
                    "hover_color": self.__theme["magenta"]["hover_color"],
                    "icon_path": "src/static/img/icons/file.png",
                    "cmd": lambda: self.__controller.show_excel_report(bank_account_row),
                },
            ]
        else:
            actions = [
                {
                    "name": "Données",
                    "desc": "Importer ou modifier\nvos transactions.",
                    "fg_color": self.__theme["blue_02"]["fg_color"],
                    "hover_color": self.__theme["blue_02"]["hover_color"],
                    "icon_path": "src/static/img/icons/directory.png",
                    "cmd": lambda: self.__controller.show_stock_transactions(bank_account_row),
                },
                {
                    "name": "Analyses",
                    "desc": "Visualiser la santé\nde vos finances.",
                    "fg_color": self.__theme["blue_03"]["fg_color"],
                    "hover_color": self.__theme["blue_03"]["fg_color"],
                    "icon_path": "src/static/img/icons/chart.png",
                    "cmd": lambda: self.__controller.show_charts(bank_account_row),
                },
                {
                    "name": "Rapports",
                    "desc": "Générer un fichier\nExcel complet.",
                    "fg_color": self.__theme["magenta"]["fg_color"],
                    "hover_color": self.__theme["magenta"]["hover_color"],
                    "icon_path": "src/static/img/icons/file.png",
                    "cmd": lambda: self.__controller.show_excel_report(bank_account_row),
                },
            ]

        self.__controller.create_card_grid(container, actions)

    def __create_card(self, master: ctk.CTkScrollableFrame, row: pd.Series, index: int) -> None:
        """Génère la carte selon le type de module (Banque ou Bourse)."""

        r, c = divmod(index, 3)
        card = ctk.CTkFrame(master, corner_radius=15, height=240, width=280, border_width=2)
        card.grid(row=r, column=c, padx=15, pady=15, sticky="nsew")
        card.grid_propagate(False)

        # Nom du compte / portefeuille
        lbl_name = ctk.CTkLabel(card, text=row["name"], font=("Arial", 20, "bold"))
        lbl_name.pack(pady=(15, 2))

        if self.__mode == "banking":
            stats = self.__db.get_bank_account_statistics(row["id"])
            total_amount = stats.get("bank_account_amount", 0.0)
            formatted_balance = f"{total_amount:,.2f}".replace(",", " ").replace(".", ",") + " €"
            balance_color = self.__theme["green"]["fg_color"] if total_amount >= 0 else self.__theme["red"]["fg_color"]

            ctk.CTkLabel(card, text=formatted_balance, font=("Arial", 24, "bold"), text_color=balance_color).pack(
                pady=10
            )

            ctk.CTkLabel(
                card,
                text=f"{stats.get('total', 0)} opérations enregistrées",
                text_color="gray",
                font=("Arial", 12, "italic"),
            ).pack(pady=(0, 5))

        else:
            gain_loss = round(random.uniform(-1500.0, 3500.0), 2)
            pct_change = round(random.uniform(-15.0, 45.0), 2)

            sign = "+" if gain_loss >= 0 else ""
            formatted_gain = f"{sign}{gain_loss:,.2f}".replace(",", " ").replace(".", ",") + " €"
            formatted_pct = f"({sign}{pct_change:.2f} %)"

            gain_color = self.__theme["green"]["fg_color"] if gain_loss >= 0 else self.__theme["red"]["fg_color"]

            ctk.CTkLabel(
                card,
                text=formatted_gain,
                font=("Arial", 24, "bold"),
                text_color=gain_color,
            ).pack(pady=(8, 0))

            ctk.CTkLabel(
                card,
                text=formatted_pct,
                font=("Arial", 14, "bold"),
                text_color=gain_color,
            ).pack(pady=(0, 8))

        # Conteneur des actions
        button_container = ctk.CTkFrame(card, fg_color="transparent")
        button_container.pack(side="bottom", padx=10, pady=15)
        button_container.columnconfigure((0, 1, 2), weight=1)

        btn_configs = [
            {
                "text": "Ouvrir",
                "fg_color": self.__theme["green"]["fg_color"],
                "hover_color": self.__theme["green"]["hover_color"],
                "cmd": lambda: self.__handle_open(row),
            },
            {
                "text": "Éditer",
                "fg_color": self.__theme["blue_01"]["fg_color"],
                "hover_color": self.__theme["blue_01"]["hover_color"],
                "cmd": lambda: self.__handle_edit(row["id"], row["name"]),
            },
            {
                "text": "Supprimer",
                "fg_color": self.__theme["red"]["fg_color"],
                "hover_color": self.__theme["red"]["hover_color"],
                "cmd": lambda: self.__handle_delete(row["id"], row["name"]),
            },
        ]

        for i, config in enumerate(btn_configs):
            ctk.CTkButton(
                button_container,
                text=config["text"],
                width=75,
                height=28,
                fg_color=config["fg_color"],
                hover_color=config["hover_color"],
                command=config["cmd"],
            ).grid(row=0, column=i, padx=5)

    def __handle_open(self, row: pd.Series) -> None:
        if self.__mode == "banking":
            self.__controller.show_bank_account_menu(row)
        else:
            self.__controller.show_stock_account_menu(row)

    def __handle_add_item(self) -> None:
        """Gère l'ajout d'un compte bancaire ou d'un portefeuille boursier."""

        if self.__mode == "banking":
            dialog = ctk.CTkInputDialog(text="Entrez le nom du compte :", title="Nouveau compte")
            center_window_on_parent(dialog, self.__master, 300, 150)
            dialog.transient(self.__master.winfo_toplevel())

            name = dialog.get_input()
            if name:
                try:
                    self.__db.add_bank_account(name)
                    self.display()
                except ValueError as e:
                    messagebox.showwarning("Doublon", str(e))
                except Exception as e:
                    messagebox.showerror("Erreur", f"Impossible de créer la ressource : {e}")

        else:
            # Stockage local des données saisies
            result = {"name": None, "currency": None}

            # Fenêtre modale rattachée directement au toplevel parent
            root = self.__master.winfo_toplevel()
            dialog = ctk.CTkToplevel(root)
            dialog.title("Nouveau portefeuille")
            dialog.geometry("360x220")
            dialog.resizable(False, False)

            center_window_on_parent(dialog, self.__master, width=360, height=220)
            dialog.transient(root)

            # Champ Nom
            ctk.CTkLabel(dialog, text="Nom du portefeuille :").pack(pady=(15, 5))
            name_entry = ctk.CTkEntry(dialog, width=240)
            name_entry.pack(pady=5)

            # Choix Devise (EUR / USD)
            ctk.CTkLabel(dialog, text="Devise du portefeuille :").pack(pady=(10, 5))
            currency_menu = ctk.CTkOptionMenu(dialog, values=["EUR", "USD"], width=240)
            currency_menu.pack(pady=5)
            currency_menu.set("EUR")

            def on_confirm(event=None) -> None:
                input_name = name_entry.get().strip()
                if input_name:
                    result["name"] = input_name
                    result["currency"] = currency_menu.get()
                    dialog.destroy()

            # Validation à la touche Entrée
            name_entry.bind("<Return>", on_confirm)

            ctk.CTkButton(dialog, text="Créer", command=on_confirm, width=120).pack(pady=(15, 10))

            dialog.update_idletasks()
            dialog.grab_set()

            # Forcer le focus en vérifiant que le widget existe toujours
            def apply_focus() -> None:
                if name_entry.winfo_exists():
                    name_entry.focus_set()
                    name_entry.focus_force()

            dialog.after(50, apply_focus)
            dialog.wait_window()

            # Traitement du résultat après fermeture
            if result["name"] and result["currency"]:
                try:
                    self.__db.add_portfolio(result["name"], result["currency"])
                    self.display()
                except ValueError as e:
                    messagebox.showwarning("Doublon", str(e))
                except Exception as e:
                    messagebox.showerror("Erreur", f"Impossible de créer le portefeuille : {e}")

    def __handle_delete(self, item_id: int, item_name: str) -> None:
        if messagebox.askyesno("Confirmation", f"Supprimer '{item_name}' ?\nCette action est irréversible."):
            try:
                if self.__mode == "banking":
                    path = os.path.join(self.__config["destination_path"], item_name)
                    if os.path.exists(path):
                        shutil.rmtree(path)
                    self.__db.delete_bank_account(item_id)
                else:
                    self.__db.delete_portfolio(item_id)
                self.display()
            except Exception as e:
                messagebox.showerror("Erreur de suppression", str(e))

    def __handle_edit(self, item_id: int, old_name: str) -> None:
        dialog = ctk.CTkInputDialog(text=f"Nouveau nom pour '{old_name}' :", title="Renommer")
        center_window_on_parent(dialog, self.__master, 300, 150)
        dialog.transient(self.__master.winfo_toplevel())

        new_name = dialog.get_input()
        if new_name and new_name != old_name:
            try:
                if self.__mode == "banking":
                    self.__db.update_bank_account_name(item_id, new_name)
                else:
                    self.__db.update_portfolio_name(item_id, new_name)
                self.display()
            except Exception as e:
                messagebox.showerror("Erreur", str(e))
