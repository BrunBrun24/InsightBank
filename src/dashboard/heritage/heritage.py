import os

import customtkinter as ctk
from PIL import Image

from utils.data_utils import handle_download, open_in_browser, open_xlsx_window


class Heritage:
    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        self.__master = master
        self.__controller = controller
        self.__theme = controller.get_theme()
        self.__config = controller.get_config()

    def display(self) -> None:
        """Affiche la vue Patrimoine dynamiquement selon l'existence des fichiers des modules."""

        self.__controller.destroy_widgets()

        card_height = 160
        icon_size = (32, 32)
        download_size = (20, 20)

        dest_path = f"{self.__config['destination_path']}/heritage"
        path_global_chart = f"{dest_path}/heritage_global.html"
        path_global_excel = f"{dest_path}/heritage_global.xlsx"
        path_bank_chart = f"{dest_path}/heritage_bank/heritage_bank.html"
        path_bank_excel = f"{dest_path}/heritage_bank/heritage_bank.xlsx"
        path_stock_chart = f"{dest_path}/heritage_stock/heritage_stock.html"
        path_stock_excel = f"{dest_path}/heritage_stock/heritage_stock.xlsx"

        has_global = os.path.exists(path_global_chart)
        has_bank = os.path.exists(path_bank_chart)
        has_stock = os.path.exists(path_stock_chart)

        img_bank_charts = Image.open("src/static/img/icons/bank_account.png")
        icon_bank_charts = ctk.CTkImage(
            light_image=img_bank_charts,
            dark_image=img_bank_charts,
            size=icon_size,
        )

        img_stock_charts = Image.open("src/static/img/icons/stock.png")
        icon_stock_charts = ctk.CTkImage(
            light_image=img_stock_charts,
            dark_image=img_stock_charts,
            size=icon_size,
        )

        img_report = Image.open("src/static/img/icons/file.png")
        icon_report = ctk.CTkImage(
            light_image=img_report,
            dark_image=img_report,
            size=icon_size,
        )

        img_download_raw = Image.open("src/static/img/icons/download.png")
        img_download = ctk.CTkImage(
            light_image=img_download_raw,
            dark_image=img_download_raw,
            size=download_size,
        )

        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        header_frame.pack(fill="x", padx=40, pady=(20, 40))

        back_btn = ctk.CTkButton(
            header_frame,
            text="←",
            fg_color=self.__theme["blue_01"]["fg_color"],
            hover_color=self.__theme["blue_01"]["hover_color"],
            width=40,
            command=self.__controller.show_home,
        )
        back_btn.place(x=0, y=5)

        title_label = ctk.CTkLabel(header_frame, text="Patrimoine", font=("Arial", 60, "bold"))
        title_label.pack(expand=True)

        # Conteneur principal
        main_container = ctk.CTkFrame(self.__master, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=40, pady=(0, 20))

        if not has_global and not has_bank and not has_stock:
            empty_label = ctk.CTkLabel(
                main_container,
                text="⚠️ Aucun fichier de données patrimoniales n'a été trouvé",
                font=("Arial", 16, "bold"),
                text_color="gray",
            )
            empty_label.pack(expand=True, pady=50)
            return

        if has_global:
            global_actions = [
                {
                    "name": "Analyses Globales",
                    "desc": "Visualiser l'évolution consolidée\n(Banques & Bourse)",
                    "fg_color": self.__theme["blue_03"]["fg_color"],
                    "hover_color": self.__theme["blue_03"]["hover_color"],
                    "icon_path": "src/static/img/icons/chart.png",
                    "cmd": lambda: open_in_browser(path_global_chart),
                    "download_cmd": lambda: handle_download(path_global_chart),
                },
                {
                    "name": "Rapport Excel Global",
                    "desc": "Générer le bilan patrimonial\ncomplet consolidé",
                    "fg_color": self.__theme["magenta"]["fg_color"],
                    "hover_color": self.__theme["magenta"]["hover_color"],
                    "icon_path": "src/static/img/icons/file.png",
                    "cmd": lambda: open_xlsx_window(path_global_excel),
                    "download_cmd": lambda: handle_download(path_global_excel),
                },
            ]

            global_container = ctk.CTkFrame(main_container, fg_color="transparent")
            global_container.pack(fill="x", pady=(0, 15))

            self.__controller.create_card_grid(global_container, global_actions, True)

        grid_container = ctk.CTkFrame(main_container, fg_color="transparent")
        grid_container.pack(fill="x")
        grid_container.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        if has_bank:
            # Carte Graphiques Banques (Gauche)
            card_bank_charts = ctk.CTkFrame(
                grid_container,
                corner_radius=15,
                border_width=2,
                height=card_height,
            )
            card_bank_charts.grid(row=0, column=1, columnspan=2, padx=15, pady=8, sticky="nsew")

            btn_dl_bank_charts = ctk.CTkButton(
                card_bank_charts,
                text="",
                image=img_download,
                width=32,
                height=32,
                corner_radius=8,
                fg_color="transparent",
                hover_color=("gray85", "gray25"),
                command=lambda: handle_download(path_bank_chart),
            )
            btn_dl_bank_charts.place(relx=1.0, x=-8, y=8, anchor="ne")

            ctk.CTkLabel(card_bank_charts, image=icon_bank_charts, text="").pack(pady=(8, 2))
            ctk.CTkLabel(
                card_bank_charts,
                text="Analyses Banques",
                font=("Arial", 15, "bold"),
            ).pack()
            ctk.CTkLabel(
                card_bank_charts,
                text="Graphiques des flux et soldes",
                text_color="gray",
                font=("Arial", 11),
            ).pack(pady=2)
            ctk.CTkButton(
                card_bank_charts,
                text="Voir Graphiques Banques",
                fg_color=self.__theme["blue_03"]["fg_color"],
                hover_color=self.__theme["blue_03"]["hover_color"],
                command=lambda: open_in_browser(path_bank_chart),
                corner_radius=8,
                height=30,
                font=("Arial", 12, "bold"),
            ).pack(pady=(8, 10), padx=20, fill="x")

            # Carte Rapport Excel Banques (Droite)
            card_bank_report = ctk.CTkFrame(
                grid_container,
                corner_radius=15,
                border_width=2,
                height=card_height,
            )
            card_bank_report.grid(row=0, column=3, columnspan=2, padx=15, pady=8, sticky="nsew")

            btn_dl_bank_report = ctk.CTkButton(
                card_bank_report,
                text="",
                image=img_download,
                width=32,
                height=32,
                corner_radius=8,
                fg_color="transparent",
                hover_color=("gray85", "gray25"),
                command=lambda: handle_download(path_bank_excel),
            )
            btn_dl_bank_report.place(relx=1.0, x=-8, y=8, anchor="ne")

            ctk.CTkLabel(card_bank_report, image=icon_report, text="").pack(pady=(8, 2))
            ctk.CTkLabel(
                card_bank_report,
                text="Rapport Excel Banques",
                font=("Arial", 15, "bold"),
            ).pack()
            ctk.CTkLabel(
                card_bank_report,
                text="Générer le rapport bancaire Excel",
                text_color="gray",
                font=("Arial", 11),
            ).pack(pady=2)
            ctk.CTkButton(
                card_bank_report,
                text="Générer Rapport Banques",
                fg_color=self.__theme["magenta"]["fg_color"],
                hover_color=self.__theme["magenta"]["hover_color"],
                command=lambda: open_xlsx_window(path_bank_excel),
                corner_radius=8,
                height=30,
                font=("Arial", 12, "bold"),
            ).pack(pady=(8, 10), padx=20, fill="x")

        if has_stock:
            # Si la section Banque est absente, on place la Bourse sur la ligne 0
            stock_row = 1 if has_bank else 0

            # Carte Graphiques Bourse (Gauche)
            card_stock_charts = ctk.CTkFrame(
                grid_container,
                corner_radius=15,
                border_width=2,
                height=card_height,
            )
            card_stock_charts.grid(row=stock_row, column=1, columnspan=2, padx=15, pady=8, sticky="nsew")

            btn_dl_stock_charts = ctk.CTkButton(
                card_stock_charts,
                text="",
                image=img_download,
                width=32,
                height=32,
                corner_radius=8,
                fg_color="transparent",
                hover_color=("gray85", "gray25"),
                command=lambda: handle_download(path_stock_chart),
            )
            btn_dl_stock_charts.place(relx=1.0, x=-8, y=8, anchor="ne")

            ctk.CTkLabel(card_stock_charts, image=icon_stock_charts, text="").pack(pady=(8, 2))
            ctk.CTkLabel(
                card_stock_charts,
                text="Analyses Bourse",
                font=("Arial", 15, "bold"),
            ).pack()
            ctk.CTkLabel(
                card_stock_charts,
                text="Graphiques de performance titres",
                text_color="gray",
                font=("Arial", 11),
            ).pack(pady=2)
            ctk.CTkButton(
                card_stock_charts,
                text="Voir Graphiques Bourse",
                fg_color=self.__theme["blue_03"]["fg_color"],
                hover_color=self.__theme["blue_03"]["hover_color"],
                command=lambda: open_in_browser(path_stock_chart),
                corner_radius=8,
                height=30,
                font=("Arial", 12, "bold"),
            ).pack(pady=(8, 10), padx=20, fill="x")

            # Carte Rapport Excel Bourse (Droite)
            card_stock_report = ctk.CTkFrame(
                grid_container,
                corner_radius=15,
                border_width=2,
                height=card_height,
            )
            card_stock_report.grid(row=stock_row, column=3, columnspan=2, padx=15, pady=8, sticky="nsew")

            btn_dl_stock_report = ctk.CTkButton(
                card_stock_report,
                text="",
                image=img_download,
                width=32,
                height=32,
                corner_radius=8,
                fg_color="transparent",
                hover_color=("gray85", "gray25"),
                command=lambda: handle_download(path_stock_excel),
            )
            btn_dl_stock_report.place(relx=1.0, x=-8, y=8, anchor="ne")

            ctk.CTkLabel(card_stock_report, image=icon_report, text="").pack(pady=(8, 2))
            ctk.CTkLabel(
                card_stock_report,
                text="Rapport Excel Bourse",
                font=("Arial", 15, "bold"),
            ).pack()
            ctk.CTkLabel(
                card_stock_report,
                text="Générer le rapport boursier Excel",
                text_color="gray",
                font=("Arial", 11),
            ).pack(pady=2)
            ctk.CTkButton(
                card_stock_report,
                text="Générer Rapport Bourse",
                fg_color=self.__theme["magenta"]["fg_color"],
                hover_color=self.__theme["magenta"]["hover_color"],
                command=lambda: open_in_browser(path_stock_excel),
                corner_radius=8,
                height=30,
                font=("Arial", 12, "bold"),
            ).pack(pady=(8, 10), padx=20, fill="x")
