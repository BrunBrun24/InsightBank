import customtkinter as ctk
from PIL import Image


class Information:
    """Page d'aide utilisant des icônes PIL à la place des emojis."""

    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        self.__master = master
        self.__controller = controller
        self.__theme = controller.get_theme()

    def display(self) -> None:
        """Affiche les sections d'aide avec icônes graphiques."""

        self.__controller.destroy_widgets()

        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(40, 20))
        ctk.CTkLabel(header_frame, text="Informations", font=("Arial", 60, "bold")).pack()

        scroll_container = ctk.CTkScrollableFrame(self.__master, fg_color="transparent")
        scroll_container.pack(fill="both", expand=True, padx=40, pady=20)

        # Section Fonctionnement
        self.__add_info_section(
            scroll_container,
            "Fonctionnement des Comptes",
            "Pour analyser vos comptes bancaires efficacement, suivez ces étapes :\n\n"
            "1. Création : Allez dans le menu 'Comptes' pour créer votre premier compte bancaire.\n"
            "2. Importation : Ajoutez ou importez vos données financières (Excel ou manuel).\n"
            "3. Catégorisation : Classez vos transactions selon vos catégories personnalisées.\n"
            "4. Analyse : Visualisez vos graphiques dans 'Analyses' ou vos rapports dans 'Rapports'.",
            "src/static/img/bank_account.png",
        )

        # Section Formats
        self.__add_info_section(
            scroll_container,
            "Sources de données & Formats",
            "L'application traite vos données selon la source configurée :\n\n"
            "• Source BNP Paribas : Connectez-vous à votre espace client, téléchargez vos opérations au format .xls ou .csv et importez-les directement.\n\n"
            "• Source 'Non défini' (Standard) : Si aucune banque n'est choisie, votre fichier Excel doit impérativement comporter les colonnes suivantes :\n"
            "   - 'Date operation'       au format Date (DD-MM-YYYY ou YYYY-MM-DD)\n"
            "   - 'Libelle operation'\n"
            "   - 'Montant operation en euro'",
            "src/static/img/file.png",
        )

        # Section Configuration
        self.__add_info_section(
            scroll_container,
            "Configuration du profil",
            "Le menu 'Configuration' permet de personnaliser votre expérience :\n\n"
            "• Banque : Choisissez votre établissement (ex: BNP Paribas).\n"
            "• Architecture : Gérez vos noms de catégories et de sous-catégories.",
            "src/static/img/edit.png",
        )

    def __add_info_section(self, container: ctk.CTkFrame, title: str, text: str, icon_path: str) -> None:
        """Ajoute un bloc d'information avec une icône PIL alignée à gauche du titre."""

        section_frame = ctk.CTkFrame(container, corner_radius=15, border_width=1)
        section_frame.pack(fill="x", pady=15, padx=10)

        # Titre avec icône
        title_container = ctk.CTkFrame(section_frame, fg_color="transparent")
        title_container.pack(fill="x", padx=20, pady=(15, 5))

        img_data = Image.open(icon_path)
        ctk_icon = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(20, 20))

        icon_label = ctk.CTkLabel(title_container, image=ctk_icon, text="")
        icon_label.pack(side="left", padx=(0, 12))

        # Titre
        ctk.CTkLabel(
            title_container, text=title, font=("Arial", 22, "bold"), text_color=self.__theme["blue_03"]["fg_color"]
        ).pack(side="left")

        # Texte explicatif
        ctk.CTkLabel(section_frame, text=text, font=("Arial", 14), justify="left", wraplength=1100).pack(
            anchor="w", padx=20, pady=(0, 20)
        )
