import customtkinter as ctk
from PIL import Image


class Information:
    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        self.__master = master
        self.__controller = controller
        self.__theme = controller.get_theme()

    def display(self) -> None:
        """Affiche les sections d'aide avec icônes graphiques et captures d'exemples."""

        self.__controller.destroy_widgets()

        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(30, 10))
        ctk.CTkLabel(header_frame, text="Informations", font=("Arial", 50, "bold")).pack()

        scroll_container = ctk.CTkScrollableFrame(self.__master, fg_color="transparent")
        scroll_container.pack(fill="both", expand=True, padx=40, pady=10)
        scroll_factor = 50

        def _on_mousewheel(event):
            scroll_container._parent_canvas.yview_scroll(int(-1 * (event.delta / 120) * scroll_factor), "units")

        # Application du binding sur le canvas du scrollable frame
        scroll_container._parent_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.__add_info_section(
            scroll_container,
            title="Compte - Gestion des Comptes Bancaires",
            text=(
                "Pour gérer vos comptes bancaires et suivre vos dépenses :\n\n"
                "1. Création : Allez dans le menu 'Comptes' pour ajouter votre compte bancaire.\n\n"
                "2. Importation : Vous pouvez importer vos opérations via un fichier Excel ou CSV :\n"
                "   • Source BNP Paribas : Import direct du fichier brut (.xls, .xlsx, .csv).\n"
                "   • Source 'Non précisé' : Si votre banque n'est pas répertoriée, le fichier doit "
                "comporter exactement les colonnes suivantes :"
            ),
            icon_path="src/static/img/icons/bank_account.png",
            single_preview_path="src/static/img/help_previews/compte_import.png",
            target_width=450,
        )

        trade_republic_steps = [
            "src/static/img/help_previews/stock_import_trade_republic_1.png",
            "src/static/img/help_previews/stock_import_trade_republic_2.png",
            "src/static/img/help_previews/stock_import_trade_republic_3.png",
        ]

        text_bourse = (
            "Pour suivre vos investissements et vos transactions boursières :\n\n"
            "1. Importation Trade Republic : Dans l'application mobile, allez dans Profil > Relevés > "
            "Exportation de transactions, sélectionnez votre période puis cliquez sur 'Créer' :\n"
        )

        text_bourse_custom = (
            "\n2. Source 'Non précisé' : Pour un fichier personnalisé, respectez impérativement "
            "la structure et les colonnes ci-dessous :\n\n"
            "   • 'date' : Format YYYY-MM-DD ou DD/MM/YYYY\n"
            "   • 'devise' : Devise autorisée (EUR ou USD)\n"
            "   • 'type' : buy, sell, dividend, interest, deposit, withdrawal\n"
            "   • 'montant' : Montant global de la transaction\n"
            "   • 'frais' : Frais appliqués à l'ordre\n"
            "   • 'symbol' : Ticker boursier (ex: AAPL, MC.PA)\n"
            "   • 'prix d'achat' : Prix unitaire à l'exécution"
        )

        self.__add_stock_section(
            scroll_container,
            title="Bourse - Gestion du Portefeuille",
            icon_path="src/static/img/icons/stock.png",
            text_tr=text_bourse,
            tr_paths=trade_republic_steps,
            text_custom=text_bourse_custom,
            custom_preview_path="src/static/img/help_previews/stock_transactions.png",
        )

        self.__add_info_section(
            scroll_container,
            title="Configuration",
            text=(
                "Personnalisez le traitement de vos flux financiers dans le menu 'Configuration' :\n\n"
                "• Architecture : Modifiez, ajoutez ou supprimez vos catégories et sous-catégories de dépenses/revenus.\n\n"
                "• Automatisation : Créez des règles d'attribution automatique basées sur le libellé des transactions "
                "afin de catégoriser automatiquement vos nouveaux imports sans effort manuel."
            ),
            icon_path="src/static/img/icons/edit.png",
        )

    def __add_info_section(
        self,
        container: ctk.CTkFrame,
        title: str,
        text: str,
        icon_path: str,
        single_preview_path: str | None = None,
        target_width: int = 500,
    ) -> None:
        """Ajoute un bloc d'information standard."""

        section_frame = ctk.CTkFrame(container, corner_radius=15, border_width=1)
        section_frame.pack(fill="x", pady=15, padx=10)

        title_container = ctk.CTkFrame(section_frame, fg_color="transparent")
        title_container.pack(fill="x", padx=20, pady=(18, 8))

        img_data = Image.open(icon_path)
        ctk_icon = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(24, 24))

        ctk.CTkLabel(title_container, image=ctk_icon, text="").pack(side="left", padx=(0, 12))
        ctk.CTkLabel(
            title_container,
            text=title,
            font=("Arial", 22, "bold"),
            text_color=self.__theme["blue_03"]["fg_color"],
        ).pack(side="left")

        # 🔧 FIX : fill="x" + Suppression de wraplength=1050
        ctk.CTkLabel(
            section_frame,
            text=text,
            font=("Arial", 14),
            justify="left",
            anchor="w",
        ).pack(fill="x", anchor="w", padx=25, pady=(5, 12))

        # Image unique
        if single_preview_path:
            preview_img = Image.open(single_preview_path)
            orig_w, orig_h = preview_img.size
            target_height = int(target_width * (orig_h / orig_w))

            ctk_preview = ctk.CTkImage(
                light_image=preview_img,
                dark_image=preview_img,
                size=(target_width, target_height),
            )
            image_label = ctk.CTkLabel(section_frame, image=ctk_preview, text="")
            image_label.pack(anchor="w", padx=35, pady=(10, 20))

    def __add_stock_section(
        self,
        container: ctk.CTkFrame,
        title: str,
        icon_path: str,
        text_tr: str,
        tr_paths: list[str],
        text_custom: str,
        custom_preview_path: str,
    ) -> None:
        """Crée la section Bourse complète dans une seule carte avec images agrandies."""

        section_frame = ctk.CTkFrame(container, corner_radius=15, border_width=1)
        section_frame.pack(fill="x", pady=15, padx=10)

        title_container = ctk.CTkFrame(section_frame, fg_color="transparent")
        title_container.pack(fill="x", padx=20, pady=(18, 8))

        img_data = Image.open(icon_path)
        ctk_icon = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(24, 24))

        ctk.CTkLabel(title_container, image=ctk_icon, text="").pack(side="left", padx=(0, 12))
        ctk.CTkLabel(
            title_container,
            text=title,
            font=("Arial", 22, "bold"),
            text_color=self.__theme["blue_03"]["fg_color"],
        ).pack(side="left")

        # 🔧 FIX : Partie Trade Republic (fill="x" + suppression wraplength)
        ctk.CTkLabel(
            section_frame,
            text=text_tr,
            font=("Arial", 14),
            justify="left",
            anchor="w",
        ).pack(fill="x", anchor="w", padx=25, pady=(5, 10))

        # Conteneur des 3 photos Trade Republic agrandies
        tr_row_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        tr_row_frame.pack(anchor="w", padx=35, pady=(5, 15))

        target_h = 420
        for path in tr_paths:
            img = Image.open(path)
            orig_w, orig_h = img.size
            calc_w = int(target_h * (orig_w / orig_h))

            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(calc_w, target_h))
            img_lbl = ctk.CTkLabel(tr_row_frame, image=ctk_img, text="")
            img_lbl.pack(side="left", padx=(0, 20))

        # 🔧 FIX : Partie Format Personnalisé (fill="x" + suppression wraplength)
        ctk.CTkLabel(
            section_frame,
            text=text_custom,
            font=("Arial", 14),
            justify="left",
            anchor="w",
        ).pack(fill="x", anchor="w", padx=25, pady=(10, 10))

        # Capture Excel
        excel_img = Image.open(custom_preview_path)
        orig_w, orig_h = excel_img.size
        target_w = 680
        calc_h = int(target_w * (orig_h / orig_w))

        ctk_preview = ctk.CTkImage(
            light_image=excel_img,
            dark_image=excel_img,
            size=(target_w, calc_h),
        )
        image_label = ctk.CTkLabel(section_frame, image=ctk_preview, text="")
        image_label.pack(anchor="w", padx=35, pady=(5, 20))
