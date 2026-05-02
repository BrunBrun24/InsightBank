import customtkinter as ctk


class Home:
    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        self.__master = master
        self.__controller = controller
        self.__theme = controller.get_theme()

    def display(self) -> None:
        """Affiche la page d'accueil avec un message de bienvenue et des statistiques globales."""

        self.__controller.destroy_widgets()

        # Header
        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=20)

        title_label = ctk.CTkLabel(header_frame, text="Accueil", font=("Arial", 60, "bold"))
        title_label.pack(expand=True)

        # Conteneur principal agrandi
        container = ctk.CTkFrame(self.__master, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=40)

        actions = [
            {
                "name": "Comptes",
                "desc": "Gérer vos différents\ncomptes.",
                "fg_color": self.__theme["green"]["fg_color"],
                "hover_color": self.__theme["green"]["hover_color"],
                "icon_path": "src/static/img/account.png",
                "cmd": lambda: self.__controller.show_accounts(),
            },
            {
                "name": "Bourse",
                "desc": "Suivre vos placements\net investissements.",
                "fg_color": self.__theme["green"]["fg_color"],
                "hover_color": self.__theme["green"]["hover_color"],
                "icon_path": "src/static/img/stock.png",
                "cmd": lambda: self.__controller.show_home(),  # TODO
            },
            {
                "name": "Patrimoine",
                "desc": "Visualisez l'évolution de votre\npatrimoine.",
                "fg_color": self.__theme["green"]["fg_color"],
                "hover_color": self.__theme["green"]["hover_color"],
                "icon_path": "src/static/img/heritage.png",
                "cmd": lambda: self.__controller.show_home(),  # TODO
            },
            {
                "name": "Configuration",
                "desc": "Configurez ici l'ensemble de\nvos préférences et réglages.",
                "fg_color": self.__theme["blue_03"]["fg_color"],
                "hover_color": self.__theme["blue_03"]["hover_color"],
                "icon_path": "src/static/img/edit.png",
                "cmd": lambda: self.__controller.show_configuration(),
            },
            {
                "name": "Informations",
                "desc": "Consulter l'aide et\nles mentions légales.",
                "fg_color": self.__theme["blue_03"]["fg_color"],
                "hover_color": self.__theme["blue_03"]["hover_color"],
                "icon_path": "src/static/img/information.png",
                "cmd": lambda: self.__controller.show_home(),  # TODO
            },
        ]

        self.__controller.create_card_grid(container, actions)
