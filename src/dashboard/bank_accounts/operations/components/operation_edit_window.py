from datetime import datetime

import customtkinter as ctk

from accounts.banking.database.banking_db import BankingDB
from config import load_config
from dashboard.bank_accounts.operations.components.ctk_date_entry import CtkDateEntry


class OperationEditWindow(ctk.CTkToplevel):
    """Fenêtre contextuelle permettant la création ou la modification d'une opération."""

    def __init__(
        self,
        parent,
        db: BankingDB,
        bank_account_id: int,
        operation: dict,
        on_save_callback: callable,
    ) -> None:
        print(operation)
        super().__init__(parent)
        self.title("Modifier l'opération")
        self.transient(parent)
        self.attributes("-topmost", False)

        self.geometry("450x600")
        width, height = 450, 600
        self.__center_window(width, height)

        self.__config = load_config()
        self.__theme = self.__config["theme"]
        self.__bank_account_id = bank_account_id
        self.__op = operation
        self._on_save = on_save_callback
        self.__entries = {}

        # Sources de données issues du JSON (Labels et Types)
        self.__inc__json = self.__config["database"]["incomes"]
        self.__exp__json = self.__config["database"]["expenses"]

        # Sources de données issues de la BDD (Catégories et Sous-catégories)
        self.__inc__db, self.__exp__db = db.get_categories_hierarchy()

        # On stocke les références des widgets de menus pour les rafraîchir plus tard
        self.__menus_refs = []

        self.__setup_widgets()
        self.grab_set()

    def __setup_widgets(self) -> None:
        """Affiche l'interface"""

        title_text = "Modifier l'opération" if self.__op.get("id") else "Nouvelle opération"
        ctk.CTkLabel(self, text=title_text, font=("Arial", 18, "bold")).pack(pady=15)

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=25)

        # Date et Montant
        date_amount_row = ctk.CTkFrame(container, fg_color="transparent")
        date_amount_row.pack(fill="x", pady=(10, 0))
        date_amount_row.grid_columnconfigure((0, 1), weight=1)

        date_frame = ctk.CTkFrame(date_amount_row, fg_color="transparent")
        date_frame.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkLabel(date_frame, text="Date", anchor="w").pack(fill="x")
        self.__date_picker = CtkDateEntry(date_frame, initial_date=self.__op["operation_date"])
        self.__date_picker.pack(fill="x", pady=5)

        amount_frame = ctk.CTkFrame(date_amount_row, fg_color="transparent")
        amount_frame.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        ctk.CTkLabel(amount_frame, text="Montant", anchor="w").pack(fill="x")

        # Logique dynamique du Montant
        self.__amount_var = ctk.StringVar(value=str(self.__op["amount"]))
        self.__amount_var.trace_add("write", self.__on_amount_changed)
        amount_entry = ctk.CTkEntry(amount_frame, textvariable=self.__amount_var)
        amount_entry.pack(fill="x", pady=5)
        self.__entries["amount"] = amount_entry

        # Libellé
        self.__create_field(container, "Libellé", "label")

        # Libellé Court / Type Opération (Dépendant du montant)
        self.__create_linked_menus(
            container,
            "Libellé Court",
            "Type d'opération",
            "short_label_and_operation_type",
            "short_label",
            "operation_type",
            use_db=False,
        )

        # Catégorie / Sous-Catégorie (Dépendant du montant)
        self.__create_linked_menus(
            container,
            "Catégorie",
            "Sous-Catégorie",
            "categories_subcategories",
            "category",
            "sub_category",
            use_db=True,
        )

        self.__error_label = ctk.CTkLabel(self, text="", text_color=self.__theme["red"]["fg_color"], font=("Arial", 12))
        self.__error_label.pack(pady=(0, 5))

        ctk.CTkButton(
            self,
            text="Enregistrer",
            fg_color=self.__theme["green"]["fg_color"],
            hover_color=self.__theme["green"]["hover_color"],
            command=self.__handle_save,
        ).pack(pady=25, padx=25, fill="x")

    def __on_amount_changed(self, *args) -> None:
        """Déclenché à chaque modification du montant pour rafraîchir les listes."""

        try:
            val = float(self.__amount_var.get().replace(",", "."))
            is_income = val >= 0
        except ValueError:
            is_income = False

        # On rafraîchit tous les menus enregistrés dans self.__menus_refs
        for menu_data in self.__menus_refs:
            parent_menu = menu_data["parent_menu"]
            child_menu = menu_data["child_menu"]
            json_key = menu_data["json_key"]
            use_db = menu_data["use_db"]

            # Sélection de la source (DB pour catégories, JSON pour labels/types)
            if use_db:
                source = self.__inc__db if is_income else self.__exp__db
            else:
                source = self.__inc__json[json_key] if is_income else self.__exp__json[json_key]

            # Mettre à jour le menu parent
            new_parents = list(source.keys())
            parent_menu.configure(values=new_parents)

            # Si la valeur actuelle n'est plus dans la liste, on reset
            if parent_menu.get() not in new_parents:
                parent_menu.set(new_parents[0] if new_parents else "")

            # Forcer la synchronisation de l'enfant
            self.__sync_menus(parent_menu.get(), child_menu, source)

    def __create_linked_menus(
        self, parent, label_parent, label_child, json_key, op_key_parent, op_key_child, use_db=False
    ) -> None:
        """Crée un bloc de deux menus déroulants liés hiérarchiquement."""

        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", pady=(10, 0))
        container.grid_columnconfigure((0, 1), weight=1)

        # Déterminer source initiale selon le montant actuel
        try:
            is_inc = float(str(self.__op["amount"]).replace(",", ".")) >= 0
        except Exception:
            is_inc = True

        if use_db:
            source = self.__inc__db if is_inc else self.__exp__db
        else:
            source = self.__inc__json[json_key] if is_inc else self.__exp__json[json_key]

        # Menu Parent
        parent_frame = ctk.CTkFrame(container, fg_color="transparent")
        parent_frame.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        ctk.CTkLabel(parent_frame, text=label_parent, anchor="w").pack(fill="x")

        parent_values = list(source.keys())
        current_parent = self.__op.get(op_key_parent) or (parent_values[0] if parent_values else "")

        # Menu Enfant
        child_frame = ctk.CTkFrame(container, fg_color="transparent")
        child_frame.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        ctk.CTkLabel(child_frame, text=label_child, anchor="w").pack(fill="x")
        child_menu = ctk.CTkOptionMenu(
            child_frame,
            values=[],
            fg_color=self.__theme["blue_01"]["fg_color"],
            button_color=self.__theme["blue_01"]["hover_color"],
        )
        child_menu.pack(fill="x", pady=5)

        parent_menu = ctk.CTkOptionMenu(
            parent_frame,
            values=parent_values,
            fg_color=self.__theme["blue_01"]["fg_color"],
            button_color=self.__theme["blue_01"]["hover_color"],
            command=lambda val: self.__sync_menus(
                val,
                child_menu,
                (self.__inc__db if float(self.__amount_var.get().replace(",", ".")) >= 0 else self.__exp__db)
                if use_db
                else (
                    self.__inc__json[json_key]
                    if float(self.__amount_var.get().replace(",", ".")) >= 0
                    else self.__exp__json[json_key]
                ),
            ),
        )
        parent_menu.set(current_parent)
        parent_menu.pack(fill="x", pady=5)

        self.__sync_menus(current_parent, child_menu, source)
        if self.__op.get(op_key_child):
            child_menu.set(self.__op[op_key_child])

        # Enregistrement pour la sauvegarde
        self.__entries[op_key_parent] = parent_menu
        self.__entries[op_key_child] = child_menu

        # Enregistrement pour le rafraîchissement dynamique
        self.__menus_refs.append(
            {"parent_menu": parent_menu, "child_menu": child_menu, "json_key": json_key, "use_db": use_db}
        )

    def __create_field(self, parent, label, key) -> None:
        """Crée un champ de saisie textuelle (Entry) précédé d'un libellé (Label)."""

        ctk.CTkLabel(parent, text=label, anchor="w").pack(fill="x", pady=(10, 0))
        entry = ctk.CTkEntry(parent)
        entry.insert(0, str(self.__op[key]))
        entry.pack(fill="x", pady=5)
        self.__entries[key] = entry

    def __sync_menus(self, selected_value, child_menu_widget, source_dict) -> None:
        """Synchronise les options d'un menu enfant en fonction de la sélection du parent."""

        new_values = source_dict.get(selected_value, [])
        child_menu_widget.configure(values=new_values)
        if new_values and child_menu_widget.get() not in new_values:
            child_menu_widget.set(new_values[0])
        elif not new_values:
            child_menu_widget.set("")

    def __handle_save(self) -> None:
        """Récupère, valide et transmet les données de l'opération."""

        # 1. Extraction des données brutes
        data = {key: entry.get() for key, entry in self.__entries.items()}

        # On récupère la date via notre widget personnalisé
        raw_date = self.__date_picker.get()

        data["id"] = self.__op["id"]
        data["bank_account_id"] = self.__bank_account_id

        # 2. Validation de la DATE
        # On vérifie si la date est présente et suit le format attendu (YYYY-MM-DD)
        try:
            # datetime.strptime lève une erreur si le format est incorrect
            datetime.strptime(raw_date, "%Y-%m-%d")
            data["operation_date"] = raw_date
        except (ValueError, TypeError):
            self.__error_label.configure(text="Erreur : Format de date invalide (AAAA-MM-JJ).")
            return

        # 3. Validation du MONTANT
        amount_str = data["amount"].replace(",", ".")
        try:
            data["amount"] = float(amount_str)
        except ValueError:
            self.__error_label.configure(text="Erreur : Le montant doit être un nombre valide.")
            return

        # 4. Validation du LIBELLÉ
        if not data["label"].strip():
            self.__error_label.configure(text="Erreur : Le libellé ne peut pas être vide.")
            return

        # 5. Finalisation
        self.__error_label.configure(text="")
        self._on_save(data)
        self.destroy()

    def __center_window(self, width: int, height: int) -> None:
        """Centre une fenêtre au milieu de l'écran"""

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
