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
        """Affiche la page de configuration"""

        self.__controller.destroy_widgets()

        # 1. Header
        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        # On met un pady en bas pour créer l'espace avec les cartes
        header_frame.pack(fill="x", padx=20, pady=(40, 20))

        title_label = ctk.CTkLabel(header_frame, text="Configuration", font=("Arial", 60, "bold"))
        title_label.pack()

        # 2. Conteneur principal (prend toute la largeur)
        grid_container = ctk.CTkFrame(self.__master, fg_color="transparent")
        grid_container.pack(fill="x", pady=40)

        # 3. Conteneur interne (centré horizontalement par défaut avec pack)
        # Ce frame contiendra les colonnes de cartes
        inner_container = ctk.CTkFrame(grid_container, fg_color="transparent")
        inner_container.pack()

        # Banque
        self.__create_module_card(
            inner_container,
            0,
            0,
            "Source Bancaire",
            "Renseignez ici les établissements bancaires que vous utilisez au quotidien, tels que la BNP Paribas, Boursorama ou le Crédit Agricole. Cette étape est essentielle pour identifier la provenance de vos flux financiers et permettre à l'application d'extraire et de traiter correctement vos données par la suite pour vos analyses.",
            "src/static/img/account.png",
            self.__config["bank"],
            command=self.__update_config_bank,
            widget_type="menu",
            menu_values=["Non défini", "BNP Paribas"],
            width=550,
            height=300,
        )

        # Exemple avec une carte standard
        self.__create_module_card(
            inner_container,
            0,
            1,
            "Architecture",
            "Optimisez la structure de votre budget en créant un système personnalisé de catégories et de sous-catégories. Cette flexibilité vous permet de classer précisément chaque transaction, qu'il s'agisse de revenus récurrents ou de dépenses imprévues, pour une analyse financière détaillée.",
            "src/static/img/file.png",
            "Gérer",
            command=self.__manage_config_categorization,
            width=550,
            height=300,
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
            self.temp_var = ctk.StringVar(value=action_text)
            widget = ctk.CTkOptionMenu(
                action_container,
                values=menu_values if menu_values else ["Options"],
                variable=self.temp_var,
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

    def __manage_config_categorization(self) -> None:
        """Affiche la page de gestion des catégories et sous-catégories."""

        self.__controller.destroy_widgets()

        # On stocke une copie de travail pour ne pas modifier le fichier instantanément
        self.temp_config = load_config()
        self.entry_widgets = {"incomes": {}, "expenses": {}}

        # Header
        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(header_frame, text="Configuration des Catégories", font=("Arial", 30, "bold")).pack(pady=(5, 10))

        # Zone d'onglets
        tabview = ctk.CTkTabview(
            self.__master,
            corner_radius=15,
            segmented_button_selected_color=self.__theme["blue_01"]["fg_color"],
        )
        tabview.pack(fill="both", expand=True, padx=20, pady=10)

        self.tab_inc = tabview.add("Revenus")
        self.tab_exp = tabview.add("Dépenses")

        # Remplissage initial
        self.__draw_config_form("incomes")
        self.__draw_config_form("expenses")

        # Bouton Enregistrer Global
        save_all_btn = ctk.CTkButton(
            self.__master,
            text="ENREGISTRER TOUTES LES MODIFICATIONS",
            font=("Arial", 14, "bold"),
            height=45,
            fg_color=self.__theme["green"]["fg_color"],
            hover_color=self.__theme["green"]["hover_color"],
            command=self.__validate_and_save_all,
        )
        save_all_btn.pack(fill="x", padx=20, pady=15)

    def __draw_config_form(self, section_key: str) -> None:
        """Dessine les catégories avec un système d'accordéon (caché par défaut)."""

        tab = self.tab_inc if section_key == "incomes" else self.tab_exp
        for widget in tab.winfo_children():
            widget.destroy()

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # On récupère les catégories et on les transforme en liste pour gérer par index
        categories_dict = self.temp_config["database"][section_key]["categories_subcategories"]
        cat_names_list = list(categories_dict.keys())

        self.entry_widgets[section_key]["categories_subcategories"] = {}

        for cat_id, cat_name in enumerate(cat_names_list):
            sub_cats = categories_dict[cat_name]

            # Frame principale de la ligne catégorie
            cat_row_frame = ctk.CTkFrame(scroll, fg_color=("gray95", "gray20"), corner_radius=10)
            cat_row_frame.pack(fill="x", pady=8, padx=5)

            # Header : Flèche | Nom | Poubelle
            header_line = ctk.CTkFrame(cat_row_frame, fg_color="transparent")
            header_line.pack(fill="x", padx=10, pady=5)

            # Zone grid pour les sous catégories (Cachée par défaut)
            sub_container = ctk.CTkFrame(cat_row_frame, fg_color="transparent")

            # Fonction pour basculer l'affichage
            def toggle_subcats(c=sub_container, b=None):
                if c.winfo_viewable():
                    c.pack_forget()
                    b.configure(text="▶")
                else:
                    c.pack(fill="x", padx=10, pady=(0, 10))
                    b.configure(text="▼")

            # Bouton Flèche pour ouvrir/fermer
            toggle_btn = ctk.CTkButton(
                header_line,
                text="▶",
                width=30,
                height=30,
                fg_color="transparent",
                text_color=("black", "white"),
                font=("Arial", 16, "bold"),
                hover_color=("gray80", "gray40"),
            )
            toggle_btn.configure(command=lambda c=sub_container, b=toggle_btn: toggle_subcats(c, b))
            toggle_btn.pack(side="left", padx=(0, 5))

            # Entrée pour le nom de la catégorie
            name_entry = ctk.CTkEntry(header_line, width=250, placeholder_text="Catégorie", font=("Arial", 13, "bold"))

            # On n'insère le texte que si ce n'est pas une "Nouvelle_cat_"
            if not cat_name.startswith("Nouvelle_cat_"):
                name_entry.insert(0, cat_name)

            name_entry.pack(side="left", pady=5)

            # Bouton Supprimer
            ctk.CTkButton(
                header_line,
                text="Supprimer",
                width=30,
                height=30,
                fg_color=self.__theme["red"]["fg_color"],
                hover_color=self.__theme["red"]["hover_color"],
                command=lambda s=section_key, i=cat_id: self.__remove_temp_row_by_index(s, i),
            ).pack(side="right", padx=5)

            # Logique interne des sous-catégories
            sub_container.badge_frames = []
            current_sub_entries = []

            def refresh_sub_layout(container=sub_container):
                max_cols = 5
                for col in range(max_cols):
                    container.grid_columnconfigure(col, weight=1, uniform="sub_cat_col")

                for child in container.winfo_children():
                    child.grid_forget()

                for i, badge_frame in enumerate(container.badge_frames):
                    r, c = divmod(i, max_cols)
                    badge_frame.grid(row=r, column=c, padx=5, pady=3, sticky="ew")

                idx_next = len(container.badge_frames)
                r_btn, c_btn = divmod(idx_next, max_cols)
                container.add_btn_widget.grid(row=r_btn, column=c_btn, padx=5, pady=5, sticky="w")

            def add_sub_logic(val="", container=sub_container, entries_list=current_sub_entries, rf=refresh_sub_layout):
                badge_fr, entry_widget = self.__create_sub_badge(container, val, entries_list, rf)
                container.badge_frames.append(badge_fr)
                entries_list.append(entry_widget)
                rf()

            sub_container.add_btn_widget = ctk.CTkButton(
                sub_container, text="+", width=28, height=28, corner_radius=14, command=add_sub_logic
            )

            for s_name in sub_cats:
                add_sub_logic(s_name)

            # Stockage des widgets pour la sauvegarde
            self.entry_widgets[section_key]["categories_subcategories"][cat_id] = (name_entry, current_sub_entries)

        # Bouton d'Ajout
        add_cat_container = ctk.CTkFrame(scroll, fg_color="transparent")
        add_cat_container.pack(fill="x", pady=10)

        ctk.CTkButton(
            add_cat_container,
            text="+ Ajouter une catégorie",
            width=200,
            height=35,
            fg_color=("gray80", "gray30"),
            text_color=("black", "white"),
            hover_color=("gray75", "gray35"),
            command=lambda s=section_key: self.__add_temp_row(s),
        ).pack(side="left", padx=20)

    def __add_temp_row(self, section: str) -> None:
        """Ajoute une ligne vide seulement si toutes les catégories actuelles sont remplies."""

        # 1. On synchronise d'abord pour vérifier l'état réel des Entry
        self.__update_temp_config_from_ui()

        # 2. Vérification : y a-t-il une catégorie sans nom (clé commençant par "Nouvelle_cat_")
        # ou dont l'utilisateur n'a pas changé le texte ?
        for cat_name in self.temp_config["database"][section]["categories_subcategories"].keys():
            if cat_name.startswith("Nouvelle_cat_"):
                messagebox.showwarning(
                    "Champs vides", "Veuillez nommer la catégorie précédente avant d'en ajouter une nouvelle."
                )
                return

        # 3. Si tout est rempli, on crée la nouvelle clé unique
        unique_key = f"Nouvelle_cat_{len(self.temp_config['database'][section]) + 1}"
        self.temp_config["database"][section]["categories_subcategories"][unique_key] = [""]

        self.__draw_config_form(section)

    def __create_sub_badge(
        self, container: ctk.CTkFrame, value: str, entries_list: list, refresh_callback: callable
    ) -> tuple[ctk.CTkFrame, ctk.CTkEntry]:
        """Crée et configure un widget "badge" éditable pour une sous-catégorie."""

        badge_frame = ctk.CTkFrame(container, fg_color=("gray85", "gray30"), corner_radius=15)

        entry = ctk.CTkEntry(
            badge_frame,
            width=120,
            height=28,
            border_width=0,
            placeholder_text="Sous-catégorie",
            fg_color="transparent",
            font=("Arial", 12),
        )
        if value:
            entry.insert(0, value)

        entry.pack(side="left", padx=(10, 0), fill="x", expand=True)

        def delete_this():
            badge_frame.destroy()
            if badge_frame in container.badge_frames:
                container.badge_frames.remove(badge_frame)
            if entry in entries_list:
                entries_list.remove(entry)
            refresh_callback()

        del_btn = ctk.CTkButton(
            badge_frame,
            text="x",
            width=20,
            height=20,
            fg_color="transparent",
            text_color=self.__theme["red"]["fg_color"],
            font=("Arial", 14, "bold"),
            command=delete_this,
        )
        del_btn.pack(side="right", padx=(2, 5))

        return badge_frame, entry

    def __remove_temp_row_by_index(self, section: str, index: int) -> None:
        """Supprime une catégorie en utilisant son index dans le dictionnaire."""

        # 1. On synchronise les dernières saisies
        self.__update_temp_config_from_ui()

        # 2. On récupère la liste des clés actuelles
        keys = list(self.temp_config["database"][section]["categories_subcategories"].keys())

        # S'il n'y a qu'une seule catégorie, on interdit la suppression
        if len(keys) <= 1:
            section_name = "revenus" if section == "incomes" else "dépenses"
            messagebox.showerror(
                "Suppression impossible", f"Vous devez garder au moins une catégorie dans la section {section_name}."
            )
            return

        if index >= len(keys):
            return  # Sécurité si l'index n'existe plus

        cat_to_delete = keys[index]

        # 3. Confirmation avec le nom réel (ou 'cette catégorie' si vide)
        display_name = cat_to_delete if not cat_to_delete.startswith("Nouvelle_cat_") else "cette nouvelle catégorie"

        if not messagebox.askyesno("Confirmation", f"Supprimer {display_name} et ses sous-catégories ?"):
            return

        # 4. Suppression réelle
        del self.temp_config["database"][section]["categories_subcategories"][cat_to_delete]

        # 5. On redessine tout
        self.__draw_config_form(section)

    def __update_temp_config_from_ui(self) -> None:
        """Synchronise sans polluer l'interface avec des noms génériques."""

        for section in ["incomes", "expenses"]:
            updated_section = {}
            for cat_id, (name_widget, sub_widgets) in self.entry_widgets[section]["categories_subcategories"].items():
                raw_name = name_widget.get().strip()

                # On garde "Nouvelle_cat_X" uniquement comme clé INTERNE si le champ est vide
                # Cela permet au bouton supprimer de trouver la bonne clé
                if not raw_name:
                    name = f"Nouvelle_cat_{cat_id}"
                else:
                    name = raw_name

                # Pour les sous-catégories, on ne garde que celles qui ont du texte
                subs = [w.get().strip() for w in sub_widgets if w.get().strip()]

                # Si vraiment vide, on laisse une liste avec un string vide pour l'UI
                updated_section[name] = subs if subs else [""]

            self.temp_config["database"][section]["categories_subcategories"] = updated_section

    def __validate_and_save_all(self) -> None:
        """Récupère toutes les données des Entry, valide et sauvegarde."""

        new_db_config = {"incomes": {}, "expenses": {}}
        errors = []

        for section in ["incomes", "expenses"]:
            for cat_id, (name_widget, sub_widgets_list) in self.entry_widgets[section][
                "categories_subcategories"
            ].items():
                name = name_widget.get().strip()

                if not name:
                    errors.append(f"[{section.upper()}] Une catégorie n'a pas de nom.")
                    continue

                # On récupère les valeurs de tous les petits widgets Entry
                subs = [w.get().strip() for w in sub_widgets_list if w.get().strip()]

                if not subs:
                    errors.append(
                        f"[{section.upper()}] La catégorie '{name}' doit avoir au moins une sous-catégorie valide."
                    )
                    continue

                new_db_config[section][name] = subs

        # Vérification finale des erreurs
        if errors:
            error_msg = "\n".join(errors)
            messagebox.showerror("Erreurs de validation", f"Veuillez corriger les points suivants :\n\n{error_msg}")
            return

        # Si tout est OK, on met à jour la config globale et on sauvegarde
        try:
            full_config = load_config()
            full_config["database"]["incomes"]["categories_subcategories"] = new_db_config["incomes"]
            full_config["database"]["expenses"]["categories_subcategories"] = new_db_config["expenses"]

            save_config(full_config)
            self.__config = load_config()
            self.__controller.set_db(BankingDB(self.__db_path))

            messagebox.showinfo("Succès", "Toutes les catégories ont été mises à jour avec succès !")
            self.__controller.show_home()

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'écriture du fichier : {e}")
            raise
