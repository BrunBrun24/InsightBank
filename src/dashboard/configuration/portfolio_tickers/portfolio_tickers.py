from tkinter import messagebox

import customtkinter as ctk

from accounts.stock.database.stock_db import StockDB

from ...portfolio.transactions.components.add_stock_window import AddStockWindow


class PortfolioTickers:
    def __init__(self, master: ctk.CTkFrame, controller) -> None:
        self.__master = master
        self.__controller = controller
        self.__config = controller.get_config()
        self.__theme = controller.get_theme()
        self.__stock_db_path = self.__config["database"]["db_stock_path"]
        self.__stock_db = StockDB(self.__stock_db_path)

    def display(self) -> None:
        """Affiche la page de gestion des tickers par portefeuille en grille responsive."""

        self.__controller.destroy_widgets()

        # En-tête de la page
        header_frame = ctk.CTkFrame(self.__master, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=10)

        back_btn = ctk.CTkButton(
            header_frame,
            text="←",
            fg_color=self.__theme["blue_01"]["fg_color"],
            hover_color=self.__theme["blue_01"]["hover_color"],
            width=40,
            command=self.__controller.show_configuration,
        )
        back_btn.place(x=0, y=15)

        ctk.CTkLabel(header_frame, text="Configuration des Titres par Portefeuille", font=("Arial", 30, "bold")).pack(
            pady=(5, 10)
        )

        # Zone déroulante principale
        scroll = ctk.CTkScrollableFrame(self.__master, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        portfolios = self.__stock_db.get_portfolios()

        if not portfolios:
            ctk.CTkLabel(scroll, text="Aucun portefeuille trouvé.", font=("Arial", 14)).pack(pady=20)
            return

        # Construction de l'accordéon par Portefeuille
        for port_id, port_name in portfolios:
            tickers = self.__stock_db.get_tickers_by_portfolio(port_id)

            # Frame principale du portefeuille
            port_row_frame = ctk.CTkFrame(scroll, fg_color=("gray95", "gray20"), corner_radius=10)
            port_row_frame.pack(fill="x", pady=8, padx=5)

            # Ligne d'en-tête (Flèche | Nom du portefeuille)
            header_line = ctk.CTkFrame(port_row_frame, fg_color="transparent")
            header_line.pack(fill="x", padx=10, pady=8)

            # Zone d'affichage des badges
            tickers_container = ctk.CTkFrame(port_row_frame, fg_color="transparent")

            # Ouverture/Fermeture de l'accordéon
            def toggle_tickers(c=tickers_container, b=None):
                if c.winfo_viewable():
                    c.pack_forget()
                    b.configure(text="▶")
                else:
                    c.pack(fill="x", padx=15, pady=(0, 10))
                    b.configure(text="▼")

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
            toggle_btn.configure(command=lambda c=tickers_container, b=toggle_btn: toggle_tickers(c, b))
            toggle_btn.pack(side="left", padx=(0, 5))

            ctk.CTkLabel(
                header_line,
                text=f"{port_name} ({len(tickers)} titre{'s' if len(tickers) > 1 else ''})",
                font=("Arial", 14, "bold"),
                anchor="w",
            ).pack(side="left", padx=5)

            # Configuration des colonnes pour le retour à la ligne automatique (4 colonnes)
            max_cols = 4
            for col in range(max_cols):
                tickers_container.grid_columnconfigure(col, weight=1)

            # Placement des badges en grille
            for idx, (ticker_symbol, company_name) in enumerate(tickers):
                r, c = divmod(idx, max_cols)
                badge = self.__create_ticker_badge(tickers_container, port_id, ticker_symbol, company_name)
                badge.grid(row=r, column=c, padx=5, pady=4, sticky="ew")

            # Bouton d'ajout "+" positionné à la suite des badges
            next_idx = len(tickers)
            r_btn, c_btn = divmod(next_idx, max_cols)

            add_badge_btn = ctk.CTkButton(
                tickers_container,
                text="+ Ajouter un titre",
                height=32,
                corner_radius=15,
                fg_color=self.__theme["green"]["fg_color"],
                hover_color=self.__theme["green"]["hover_color"],
                font=("Arial", 12, "bold"),
                command=lambda p_id=port_id: self.__open_add_stock_window(p_id),
            )
            add_badge_btn.grid(row=r_btn, column=c_btn, padx=5, pady=4, sticky="w")

    def __create_ticker_badge(
        self, container: ctk.CTkFrame, portfolio_id: int, ticker: str, company_name: str
    ) -> ctk.CTkFrame:
        """Crée un badge avec largeur minimale, alignement propre et tronquage si nécessaire."""

        display_text = f"{company_name} ({ticker})" if company_name and company_name != "-" else ticker

        # Badge avec hauteur minimale et largeur flexible
        badge_frame = ctk.CTkFrame(container, fg_color=("gray85", "gray30"), corner_radius=15, height=32)

        # Label avec wraplength pour éviter qu'un nom ultra long ne déborde
        label = ctk.CTkLabel(
            badge_frame,
            text=display_text,
            font=("Arial", 11, "bold"),
            anchor="w",
        )
        label.pack(side="left", padx=(12, 5), pady=4, fill="x", expand=True)

        # Bouton 'x' de suppression
        del_btn = ctk.CTkButton(
            badge_frame,
            text="x",
            width=22,
            height=22,
            fg_color="transparent",
            text_color=self.__theme["red"]["fg_color"],
            hover_color=("gray75", "gray40"),
            font=("Arial", 13, "bold"),
            command=lambda p_id=portfolio_id, t=ticker: self.__remove_ticker_from_portfolio(p_id, t),
        )
        del_btn.pack(side="right", padx=(2, 6))

        return badge_frame

    def __open_add_stock_window(self, portfolio_id: int) -> None:
        """Ouvre la fenêtre modale AddStockWindow."""
        AddStockWindow(
            parent=self.__master.winfo_toplevel(),
            db_stock=self.__stock_db,
            portfolio_id=portfolio_id,
            on_stock_added_callback=self.display,
        )

    def __remove_ticker_from_portfolio(self, portfolio_id: int, ticker: str) -> None:
        """Retire le ticker du portefeuille et le nettoie s'il est devenu orphelin."""
        if not messagebox.askyesno(
            "Confirmation",
            f"Voulez-vous retirer '{ticker}' de ce portefeuille ?\n\nCela supprimera toutes ses transactions.",
        ):
            return

        try:
            self.__stock_db.remove_ticker_from_portfolio(portfolio_id, ticker)
            self.display()
        except Exception:
            messagebox.showerror("Erreur", "Impossible de supprimer le titre")
