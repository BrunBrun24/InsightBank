from tkinter import messagebox

import customtkinter as ctk

from config import save_config


class AutomatisationCatSubCat:
    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        self.__master = master
        self.__controller = controller
        self.__config = controller.get_config()
        self.__theme = controller.get_theme()

        # Contiendra les critères de la règle en cours de création
        self.current_building_conditions = []

    def display(self) -> None:
        """Affiche la page d'automatisation des catégories et sous-catégories."""

        self.__controller.destroy_widgets()
        self.__custom_rules = self.__config.get("custom_rules", [])

        # Extraction extensive depuis le json (incomes + expenses)
        short_labels_set = set()
        operation_types_set = set()

        for flow in ["incomes", "expenses"]:
            flow_data = self.__config.get("database", {}).get(flow, {})
            mapping = flow_data.get("short_label_and_operation_type", {})

            for short_label, op_list in mapping.items():
                short_labels_set.add(short_label)
                for op_type in op_list:
                    operation_types_set.add(op_type)

        self.__short_labels_values = sorted(short_labels_set)
        self.__operation_types_values = sorted(operation_types_set)

        # Fusion des structures catégories / sous-catégories revenus et dépenses
        self.all_categories_map = {}
        for flow in ["incomes", "expenses"]:
            flow_cats = self.__config.get("database", {}).get(flow, {}).get("categories_subcategories", {})
            for cat, subcats in flow_cats.items():
                if cat not in self.all_categories_map:
                    self.all_categories_map[cat] = []
                self.all_categories_map[cat].extend(subcats)
                self.all_categories_map[cat] = list(set(self.all_categories_map[cat]))

        # Header supérieur
        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=10)

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
            text="Gestionnaire de Règles d'Automatisation Complexes",
            font=("Arial", 30, "bold"),
        ).pack(pady=(5, 10))

        # Conteneur principal défilable
        self.main_frame = ctk.CTkScrollableFrame(self.__master, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=(5, 20))

        # Section option / Configuration
        self.__render_settings_section()

        # Section 1 : Formulaire de création
        self.form_frame = ctk.CTkFrame(self.main_frame, corner_radius=10)
        self.form_frame.pack(fill="x", pady=(0, 20), padx=5)

        form_title = ctk.CTkLabel(
            self.form_frame, text="Étape 1 : Ajouter des critères", font=ctk.CTkFont(weight="bold")
        )
        form_title.grid(row=0, column=0, columnspan=4, sticky="w", padx=15, pady=10)

        # 1. Choix du champ
        ctk.CTkLabel(self.form_frame, text="Champ :").grid(row=1, column=0, padx=15, pady=2, sticky="w")
        self.field_var = ctk.StringVar(value="Libellé")
        field_menu = ctk.CTkOptionMenu(
            self.form_frame,
            values=["Libellé", "Libellé court", "Type d'opération", "Montant"],
            variable=self.field_var,
            command=self.__on_field_changed,
            fg_color=self.__theme["blue_01"]["fg_color"],
            button_hover_color=self.__theme["blue_01"]["hover_color"],
        )
        field_menu.grid(row=2, column=0, padx=15, pady=(0, 15), sticky="w")

        # 2. Choix de la condition
        ctk.CTkLabel(self.form_frame, text="Condition :").grid(row=1, column=1, padx=15, pady=2, sticky="w")
        self.condition_var = ctk.StringVar()
        self.condition_menu = ctk.CTkOptionMenu(
            self.form_frame,
            values=[],
            variable=self.condition_var,
            fg_color=self.__theme["blue_01"]["fg_color"],
            button_hover_color=self.__theme["blue_01"]["hover_color"],
        )
        self.condition_menu.grid(row=2, column=1, padx=15, pady=(0, 15), sticky="w")

        # 3. Saisie ou Sélection de la valeur
        self.value_label = ctk.CTkLabel(self.form_frame, text="Valeur(s) (virgule pour le 'OU') :")
        self.value_label.grid(row=1, column=2, padx=15, pady=2, sticky="w")

        # Mode A : Saisie libre (Par défaut)
        self.value_entry = ctk.CTkEntry(self.form_frame, placeholder_text="Ex: NETFLIX, SPOTIFY", width=200)
        self.value_entry.grid(row=2, column=2, padx=15, pady=(0, 15), sticky="w")

        # Mode B : Menu déroulant (Masqué initialement)
        self.value_dropdown_var = ctk.StringVar()
        self.value_dropdown_menu = ctk.CTkOptionMenu(
            self.form_frame,
            values=[],
            variable=self.value_dropdown_var,
            fg_color=self.__theme["blue_01"]["fg_color"],
            button_hover_color=self.__theme["blue_01"]["hover_color"],
            width=200,
        )

        # Config initiale de l'état "Libellé"
        self.__on_field_changed("Libellé")

        # Bouton d'ajout de critère
        add_criterion_btn = ctk.CTkButton(
            self.form_frame,
            text="+ Ajouter ce critère",
            fg_color=self.__theme["blue_02"]["fg_color"],
            hover_color=self.__theme["blue_02"]["hover_color"],
            command=self.__add_criterion_to_current_list,
        )
        add_criterion_btn.grid(row=2, column=3, padx=15, pady=(0, 15), sticky="w")

        # Zone d'affichage dynamique du panier de critères temporaires
        self.criteria_container = ctk.CTkFrame(self.form_frame, fg_color="transparent")
        self.criteria_container.grid(row=3, column=0, columnspan=4, padx=15, pady=5, sticky="w")

        self.__render_current_criteria_bucket()

        # Étape 2 : Assignation catégories / sous-catégories
        separator = ctk.CTkFrame(self.form_frame, height=2, fg_color="gray")
        separator.grid(row=4, column=0, columnspan=4, sticky="ew", padx=15, pady=10)

        form_title2 = ctk.CTkLabel(
            self.form_frame,
            text="Étape 2 : Action à mener si tous les critères sont respectés",
            font=ctk.CTkFont(weight="bold"),
        )
        form_title2.grid(row=5, column=0, columnspan=4, sticky="w", padx=15, pady=5)

        # Menu Catégorie principale
        ctk.CTkLabel(self.form_frame, text="Catégorie :").grid(row=6, column=0, padx=15, pady=2, sticky="w")
        self.category_var = ctk.StringVar()
        self.category_menu = ctk.CTkOptionMenu(
            self.form_frame,
            values=[],
            variable=self.category_var,
            command=self.__update_subcategories_menu,
            fg_color=self.__theme["blue_01"]["fg_color"],
            button_hover_color=self.__theme["blue_01"]["hover_color"],
        )
        self.category_menu.grid(row=7, column=0, padx=15, pady=(0, 15), sticky="w")

        # Menu Sous-Catégorie
        ctk.CTkLabel(self.form_frame, text="Sous-Catégorie :").grid(row=6, column=1, padx=15, pady=2, sticky="w")
        self.subcategory_var = ctk.StringVar()
        self.subcategory_menu = ctk.CTkOptionMenu(
            self.form_frame,
            values=[],
            variable=self.subcategory_var,
            fg_color=self.__theme["blue_01"]["fg_color"],
            button_hover_color=self.__theme["blue_01"]["hover_color"],
        )
        self.subcategory_menu.grid(row=7, column=1, padx=15, pady=(0, 15), sticky="w")

        self.__load_all_categories(force_init=True)

        # Bouton final de sauvegarde de la règle complète
        save_rule_btn = ctk.CTkButton(
            self.form_frame,
            text="Enregistrer la règle finale",
            fg_color=self.__theme["green"]["fg_color"],
            hover_color=self.__theme["green"]["hover_color"],
            command=self.__save_final_rule,
        )
        save_rule_btn.grid(row=7, column=2, columnspan=2, padx=15, pady=(0, 15), sticky="e")

        # Section 2 : Liste des règles
        list_title = ctk.CTkLabel(
            self.main_frame, text="Règles actives enregistrées", font=ctk.CTkFont(size=14, weight="bold")
        )
        list_title.pack(anchor="w", pady=(10, 5))

        self.rules_list_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.rules_list_frame.pack(fill="x", expand=True)

        self.__render_rules_list()

    def __render_settings_section(self) -> None:
        """Affiche le panneau de configuration globale (Switch de catégorisation)."""

        settings_frame = ctk.CTkFrame(self.main_frame, corner_radius=10)
        settings_frame.pack(fill="x", pady=(0, 20), padx=5)

        settings_title = ctk.CTkLabel(settings_frame, text="Configuration globale", font=ctk.CTkFont(weight="bold"))
        settings_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 5))

        # Variables d'état récupérées depuis config.json
        is_smart_enabled = self.__config.get("smart_categorization_enabled", True)
        self.smart_cat_var = ctk.BooleanVar(value=is_smart_enabled)

        # Interrupteur / Switch
        smart_cat_switch = ctk.CTkSwitch(
            settings_frame,
            text="Activer la catégorisation intelligente",
            variable=self.smart_cat_var,
            command=self.__on_smart_cat_toggled,
            progress_color=self.__theme["green"]["fg_color"],
        )
        smart_cat_switch.grid(row=1, column=0, padx=15, pady=(5, 15), sticky="w")

        desc_lbl = ctk.CTkLabel(
            settings_frame,
            text="Applique automatiquement la catégorisation en se basant sur les opérations passées.",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color="gray",
        )
        desc_lbl.grid(row=1, column=1, padx=10, pady=(5, 15), sticky="w")

    def __on_smart_cat_toggled(self) -> None:
        """Sauvegarde l'état du switch dans la configuration JSON."""

        state = self.smart_cat_var.get()
        self.__config["smart_categorization_enabled"] = state
        save_config(self.__config)

    def __on_field_changed(self, selected_field: str) -> None:
        """Gère la bascule de l'interface et des conditions selon le champ sélectionné."""

        if selected_field == "Montant":
            conditions = ["égal", "plus petit que", "plus grand que"]
            self.condition_menu.configure(state="normal", values=conditions)
            self.condition_var.set(conditions[0])
        elif selected_field in ["Libellé court", "Type d'opération"]:
            conditions = ["est exactement"]
            self.condition_menu.configure(values=conditions)
            self.condition_var.set("est exactement")
            self.condition_menu.configure(state="disabled")
        else:
            conditions = ["contient", "commence par", "termine par", "est exactement"]
            self.condition_menu.configure(state="normal", values=conditions)
            self.condition_var.set(conditions[0])

        if selected_field in ["Libellé court", "Type d'opération"]:
            self.value_entry.grid_remove()
            self.value_dropdown_menu.grid(row=2, column=2, padx=15, pady=(0, 15), sticky="w")
            self.value_label.configure(text="Sélectionnez la valeur :")

            target_values = (
                self.__short_labels_values if selected_field == "Libellé court" else self.__operation_types_values
            )

            if target_values:
                self.value_dropdown_menu.configure(values=target_values)
                self.value_dropdown_var.set(target_values[0])
            else:
                self.value_dropdown_menu.configure(values=["[Aucune valeur trouvée]"])
                self.value_dropdown_var.set("[Aucune valeur trouvée]")
        else:
            self.value_dropdown_menu.grid_remove()
            self.value_entry.grid(row=2, column=2, padx=15, pady=(0, 15), sticky="w")
            self.value_label.configure(text="Valeur(s) (virgule pour le 'OU') :")

    def __add_criterion_to_current_list(self) -> None:
        """Ajoute un critère unique au panier temporaire de la règle."""

        field = self.field_var.get()
        operator = self.condition_var.get()

        if field in ["Libellé court", "Type d'opération"]:
            val_raw = self.value_dropdown_var.get()
            if val_raw == "[Aucune valeur trouvée]":
                messagebox.showwarning("Erreur", "Aucune valeur valide sélectionnée.")
                return
        else:
            val_raw = self.value_entry.get().strip()

        if not val_raw:
            messagebox.showwarning("Erreur", "Veuillez renseigner une valeur pour le critère.")
            return

        if field == "Montant":
            try:
                float(val_raw.replace(",", "."))
            except ValueError:
                messagebox.showerror("Erreur", "Le montant saisi doit être un nombre valide.")
                return

        values_list = (
            [val_raw]
            if field in ["Libellé court", "Type d'opération"]
            else [v.strip() for v in val_raw.split(",") if v.strip()]
        )

        criterion = {"field": field, "operator": operator, "values": values_list}
        self.current_building_conditions.append(criterion)

        self.__render_current_criteria_bucket()
        self.value_entry.delete(0, "end")

    def __render_current_criteria_bucket(self) -> None:
        """Génère la liste de badges interactifs pour les critères en cours de création."""

        for widget in self.criteria_container.winfo_children():
            widget.destroy()

        if not self.current_building_conditions:
            no_criteria_lbl = ctk.CTkLabel(
                self.criteria_container,
                text="Critères de la règle : (Aucun critère ajouté)",
                font=ctk.CTkFont(slant="italic"),
                text_color="gray",
            )
            no_criteria_lbl.pack(anchor="w")
            return

        head_lbl = ctk.CTkLabel(
            self.criteria_container,
            text="Critères actifs pour cette règle (cliquez sur X pour retirer) :",
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        head_lbl.pack(anchor="w", pady=(0, 5))

        for idx, c in enumerate(self.current_building_conditions):
            badge_frame = ctk.CTkFrame(self.criteria_container, fg_color=("#D1D1D1", "#3A3A3A"), corner_radius=4)
            badge_frame.pack(fill="x", pady=2)

            readable_text = f" 📍 [{c['field']}] {c['operator']} ({' OU '.join(c['values'])})"
            lbl = ctk.CTkLabel(badge_frame, text=readable_text, font=ctk.CTkFont(size=12))
            lbl.pack(side="left", padx=10, pady=4)

            remove_btn = ctk.CTkButton(
                badge_frame,
                text="X",
                width=20,
                height=18,
                fg_color=self.__theme["red"]["fg_color"],
                hover_color=self.__theme["red"]["hover_color"],
                command=lambda index=idx: self.__remove_single_criterion(index),
            )
            remove_btn.pack(side="right", padx=5, pady=4)

    def __remove_single_criterion(self, index: int) -> None:
        """Retire un critère spécifique de la liste temporaire avant la sauvegarde finale."""

        if 0 <= index < len(self.current_building_conditions):
            self.current_building_conditions.pop(index)
            self.__render_current_criteria_bucket()

    def __load_all_categories(self, force_init: bool = False) -> None:
        """Charge l'intégralité des catégories (Revenus + Dépenses) triées par ordre alphabétique."""

        cat_names = sorted(self.all_categories_map.keys())

        if not hasattr(self, "category_menu") and not force_init:
            return

        self.category_menu.configure(values=cat_names)
        if cat_names:
            self.category_var.set(cat_names[0])
            self.__update_subcategories_menu(cat_names[0])

    def __update_subcategories_menu(self, selected_category: str) -> None:
        """Met à jour le menu des sous-catégories à la sélection d'une catégorie mère."""

        subcats = self.all_categories_map.get(selected_category, [])
        self.subcategory_menu.configure(values=subcats)
        if subcats:
            self.subcategory_var.set(subcats[0])
        else:
            self.subcategory_var.set("")

    def __save_final_rule(self) -> None:
        """Valide l'ensemble des critères accumulés et enregistre la règle."""

        if not self.current_building_conditions:
            messagebox.showwarning(
                "Erreur",
                "Impossible d'enregistrer : vous devez ajouter au moins un critère via le bouton '+ Ajouter ce critère'.",
            )
            return

        new_id = max([r["id"] for r in self.__custom_rules], default=0) + 1

        complete_rule = {
            "id": new_id,
            "target_category": self.category_var.get(),
            "target_subcategory": self.subcategory_var.get(),
            "conditions": self.current_building_conditions,
        }

        self.__custom_rules.append(complete_rule)
        self.__config["custom_rules"] = self.__custom_rules
        save_config(self.__config)

        # Réinitialisation complète du formulaire après sauvegarde réussie
        self.current_building_conditions = []
        self.__render_current_criteria_bucket()
        self.__load_all_categories()
        self.field_var.set("Libellé")
        self.__on_field_changed("Libellé")
        self.__render_rules_list()

        messagebox.showinfo("Succès", "Règle d'automatisation enregistrée avec succès !")

    def __render_rules_list(self) -> None:
        """Affiche toutes les règles existantes en supportant l'ancien et le nouveau format."""

        for widget in self.rules_list_frame.winfo_children():
            widget.destroy()

        if not self.__custom_rules:
            no_rule_lbl = ctk.CTkLabel(
                self.rules_list_frame, text="Aucune règle configurée.", font=ctk.CTkFont(slant="italic")
            )
            no_rule_lbl.pack(anchor="w", padx=10, pady=10)
            return

        for rule in self.__custom_rules:
            rule_card = ctk.CTkFrame(self.rules_list_frame, corner_radius=6, fg_color=("#EAEAEA", "#2B2B2B"))
            rule_card.pack(fill="x", pady=6, padx=5)

            if "conditions" in rule:
                cond_strings = []
                for c in rule["conditions"]:
                    cond_strings.append(f"[{c['field']}] {c['operator']} ('{' ou '.join(c['values'])}')")
                text_critere = " ET ".join(cond_strings)
                text_cible = f"➡️  [{rule.get('target_category', '')} > {rule.get('target_subcategory', '')}]"
            else:
                values_str = " ou ".join([f"'{v}'" for v in rule.get("values", [])])
                text_critere = f"[{rule.get('field', 'Champ')}] {rule.get('condition', 'égal')} ({values_str})"
                text_cible = f"➡️  [{rule.get('target_category', 'Catégorie')}]"

            full_description = f" SI : {text_critere} {text_cible}"

            lbl = ctk.CTkLabel(rule_card, text=full_description, font=ctk.CTkFont(size=12), justify="left")
            lbl.pack(side="left", padx=15, pady=10)

            del_btn = ctk.CTkButton(
                rule_card,
                text="Supprimer",
                width=80,
                height=24,
                fg_color=self.__theme["red"]["fg_color"],
                hover_color=self.__theme["red"]["hover_color"],
                command=lambda r_id=rule["id"]: self.__delete_rule(r_id),
            )
            del_btn.pack(side="right", padx=15, pady=10)

    def __delete_rule(self, rule_id: int) -> None:
        """Supprime définitivement une règle enregistrée via son identifiant unique."""

        self.__custom_rules = [r for r in self.__custom_rules if r["id"] != rule_id]
        self.__config["custom_rules"] = self.__custom_rules
        save_config(self.__config)
        self.__render_rules_list()
