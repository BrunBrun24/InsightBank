import unicodedata
from typing import Dict, List

import customtkinter as ctk

from accounts.banking.database.banking_db import BankingDB
from config import load_config


class Categorizer:
    """
    Fournit une interface graphique pour la catégorisation des opérations financières.

    - Charger les opérations brutes et les catégories/sous-catégories depuis la base.
    - Afficher chaque opération à catégoriser dans une fenêtre.
    - Catégoriser automatiquement certaines opérations selon des règles prédéfinies.
    - Permettre la catégorisation manuelle via des boutons représentant les catégories et sous-catégories.
    - Passer à l’opération suivante sans catégorisation si nécessaire.
    - Enregistrer les opérations catégorisées dans la base et les marquer comme traitées.
    """

    def __init__(self, parent: ctk.CTk, db: BankingDB, account_id: int, buttons_per_row=5) -> None:
        """
        Initialise l'interface de catégorisation et charge les données nécessaires.

        Prépare l'état initial de l'application en récupérant la hiérarchie des
        catégories, les identifiants techniques et la liste des opérations à traiter.
        """

        config = load_config()

        # Permet de savoir s'il y a eu de nouvelles opérations qui ont été catégorisées
        self.has_changed = False

        self.__db = db
        self.__account_id = account_id
        self.__buttons_per_row = buttons_per_row
        self.__theme = config["theme"]
        self.__operations = self.__db.get_unprocessed_raw_operations(self.__account_id)
        self.__incomes_categories_and_sub_categories = config["database"]["incomes"]["categories_subcategories"]
        self.__expenses_categories_and_sub_categories = config["database"]["expenses"]["categories_subcategories"]
        self.__history = []  # Pile pour stocker les opérations précédemment traitées

        # On crée une fenêtre secondaire liée au parent
        self.__root = ctk.CTkToplevel(parent)
        self.__root.title("Classification des opérations")
        self.__root.grab_set()  # Rend la fenêtre "modale" (bloque celle du dessous)
        self.__window_width = 1200
        self.__window_height = 600
        self.__display_label = ctk.CTkLabel(self.__root, text="", wraplength=self.__window_width - 50)
        self.__display_label.grid(
            row=(len(self.__expenses_categories_and_sub_categories) // self.__buttons_per_row) + 1,
            column=0,
            columnspan=self.__buttons_per_row,
            pady=20,
        )

    def categorize(self) -> ctk.CTkToplevel:
        """
        Lance l'interface graphique pour la catégorisation des opérations.

        Actions :
        - Configure la fenêtre principale
        - Centre la fenêtre à l'écran
        - Affiche la première opération à catégoriser
        - Démarre la boucle principale Tkinter pour gérer les interactions utilisateur
        """

        self.__root.title("Catégorisation d'opérations")

        self.__center_window()
        self.__update_display()

        return self.__root

    def __center_window(self) -> None:
        """
        Centre la fenêtre Tkinter sur l'écran en ajustant sa position
        en fonction de la largeur et hauteur de l'écran et de la fenêtre.
        """

        screen_width = self.__root.winfo_screenwidth()
        screen_height = self.__root.winfo_screenheight()

        x = (screen_width // 2) - (self.__window_width // 2)
        y = (screen_height // 2) - (self.__window_height // 2)

        self.__root.geometry(f"{self.__window_width}x{self.__window_height}+{x}+{y}")

    def __update_display(self) -> None:
        """
        Met à jour l'affichage de l'interface Tkinter avec l'opération courante.

        - Si aucune opération n'est disponible, ferme la fenêtre.
        - Traite les cas spéciaux automatiquement si applicable.
        - Affiche le texte descriptif de l'opération.
        - Détermine et affiche les boutons des catégories pertinentes selon le montant.
        """

        if not self.__operations:
            self.__root.after(0, self.__root.destroy)
            return

        # On marque qu'une catégorisation à eu lieu
        self.has_changed = True

        # Récupère la première opération
        row = self.__operations[0]
        self.current_row = row

        # Affichage du texte
        self.__display_label.configure(text=row[4] + "\n\n" + f"{row[1]}   =>   {row[5]}€")

        if row[5] >= 0:
            # On récupère le dictionnaire des revenus
            source_dict = self.__incomes_categories_and_sub_categories
        else:
            # On récupère le dictionnaire des dépenses
            source_dict = self.__expenses_categories_and_sub_categories

        # Tri alphabétique des catégories (clés du dictionnaire choisi)
        sorted_keys = sorted(source_dict.keys(), key=self.__normalize_text)

        # On reconstruit un dictionnaire trié pour l'affichage
        filtered_buttons = {key: source_dict[key] for key in sorted_keys}

        self.__create_buttons(filtered_buttons)

    def __create_buttons(self, filtered_buttons: Dict[str, List[str]]) -> None:
        """Crée dynamiquement des boutons Tkinter pour les catégories et sous-catégories."""

        # Supprimer tous les widgets sauf le label d'affichage
        for widget in self.__root.winfo_children():
            if widget != self.__display_label:
                widget.destroy()

        # Création des boutons
        for i, (label, sub_labels) in enumerate(filtered_buttons.items()):
            row = i // self.__buttons_per_row
            column = i % self.__buttons_per_row

            button = ctk.CTkButton(
                self.__root,
                text=label,
                fg_color=self.__theme["blue_01"]["fg_color"],
                hover_color=self.__theme["blue_01"]["hover_color"],
                command=lambda l=label: self.__button_clicked(l),
            )
            button.grid(row=row, column=column, padx=10, pady=10, sticky="ew")

        # Calcul de la ligne pour les boutons de navigation (après les catégories)
        navigation_row = (len(filtered_buttons) // self.__buttons_per_row) + 10

        # Bouton "Annuler" (Affiché uniquement si un historique existe)
        if self.__history:
            undo_button = ctk.CTkButton(
                self.__root,
                text="Annuler",
                fg_color=self.__theme["red"]["fg_color"],
                hover_color=self.__theme["red"]["hover_color"],
                command=self.__undo_last_action,
            )
            undo_button.grid(row=navigation_row, column=0, pady=10, sticky="ew")

        # Bouton "Suivant"
        skip_button = ctk.CTkButton(
            self.__root,
            text="Suivant",
            fg_color=self.__theme["blue_01"]["fg_color"],
            hover_color=self.__theme["blue_01"]["hover_color"],
            command=self.__skip_entry,
        )
        skip_button.grid(row=navigation_row, column=self.__buttons_per_row - 1, pady=10, sticky="e")

        # Ajustement automatique des colonnes
        for i in range(self.__buttons_per_row):
            self.__root.grid_columnconfigure(i, weight=1)

    def __button_clicked(self, category_name: str) -> None:
        """
        Gère le clic sur une catégorie principale et affiche ses sous-catégories.

        Si la catégorie possède des éléments enfants, l'interface est nettoyée
        pour afficher les boutons des sous-catégories triés par ordre alphabétique.
        Sinon, l'opération est directement traitée.
        """

        if self.current_row[5] >= 0:
            sub_categories = self.__incomes_categories_and_sub_categories[category_name]
        else:
            sub_categories = self.__expenses_categories_and_sub_categories[category_name]

        # Cas où la catégorie contient des sous-catégories
        if isinstance(sub_categories, list) and sub_categories:
            # Nettoyage des anciens boutons (on conserve uniquement le label d'affichage)
            for widget in self.__root.winfo_children():
                if widget != self.__display_label:
                    widget.destroy()

            # Tri alphabétique insensible aux accents grâce à la méthode de normalisation
            sorted_sub_categories = sorted(sub_categories, key=self.__normalize_text)

            # Création dynamique de la grille de boutons pour les sous-catégories
            for i, sub_label in enumerate(sorted_sub_categories):
                row = i // self.__buttons_per_row
                column = i % self.__buttons_per_row

                btn = ctk.CTkButton(
                    self.__root,
                    text=sub_label,
                    fg_color=self.__theme["blue_01"]["fg_color"],
                    hover_color=self.__theme["blue_01"]["hover_color"],
                    command=lambda s=sub_label, c=category_name: self.__sub_button_clicked(s, c),
                )
                btn.grid(row=row, column=column, padx=10, pady=10, sticky="ew")

            # Calcul de la position de la ligne de navigation (placée après les boutons)
            row_index = (len(sorted_sub_categories) // self.__buttons_per_row) + 10

            # Ajout des boutons de navigation : Retour et Suivant
            back_button = ctk.CTkButton(
                self.__root,
                text="Retour",
                fg_color=self.__theme["blue_01"]["fg_color"],
                hover_color=self.__theme["blue_01"]["hover_color"],
                command=self.__update_display,
            )
            back_button.grid(
                row=row_index,
                column=0,
                columnspan=self.__buttons_per_row - 2,
                pady=10,
                sticky="w",
            )

            next_button = ctk.CTkButton(
                self.__root,
                text="Suivant",
                command=self.__skip_entry,
                fg_color=self.__theme["blue_01"]["fg_color"],
                hover_color=self.__theme["blue_01"]["hover_color"],
            )
            next_button.grid(row=row_index, column=self.__buttons_per_row - 1, pady=10, sticky="e")

        else:
            # Si aucune sous-catégorie n'existe, on traite directement l'opération
            raise ValueError(f"Erreur : Il n'y a pas de sous-catégories pour la catégorie '{category_name}'.")

    def __skip_entry(self) -> None:
        """
        Passe à l'opération suivante sans effectuer de catégorisation.

        Actions :
        - Supprime l'opération actuellement affichée de la liste
        - Met à jour l'affichage pour montrer l'opération suivante
        """

        if self.__operations:
            # On enlève la première (celle affichée actuellement)
            self.__operations.pop(0)

        # Mise à jour de l'affichage
        self.__update_display()

    def __undo_last_action(self) -> None:
        """
        Annule la dernière catégorisation effectuée et recharge l'opération.

        Actions :
        - Récupère l'opération de la pile d'historique.
        - Supprime l'entrée correspondante dans la base de données.
        - Réinsère l'opération en début de file d'attente.
        - Rafraîchit l'affichage.
        """

        if not self.__history:
            # Aucun historique disponible, on ne fait rien
            return

        # Récupère la dernière opération traitée (LIFO)
        last_operation = self.__history.pop()

        # Suppression en base de données via l'ID de la transaction
        self.__db.delete_operation(self.__account_id, last_operation[0])

        # Réinsertion en première position de la liste de travail
        self.__operations.insert(0, last_operation)

        # Mise à jour de l'interface graphique
        self.__update_display()

    def __sub_button_clicked(self, sub_categorie: str, main_categorie: str) -> None:
        """
        Gère le clic sur une sous-catégorie et archive l'opération.

        Actions :
        - Enregistre l'opération courante avec la catégorie et sous-catégorie sélectionnées
        - Passe à l'opération suivante dans la liste
        """

        # Archivage de l'opération courante avant traitement
        self.__history.append(self.current_row)

        # Conversion des noms des boutons en IDs techniques
        self.__db.update_operation_according_classification(
            self.__operations[0][0],
            main_categorie,
            sub_categorie,
        )

        # Passage à l'élément suivant
        self.__operations.pop(0)
        self.__update_display()

    def __normalize_text(self, text: str) -> str:
        """Normalise une chaîne de caractères en supprimant les accents et en passant en minuscules"""

        normalized = unicodedata.normalize("NFD", text)
        return "".join(c for c in normalized if unicodedata.category(c) != "Mn").lower()
