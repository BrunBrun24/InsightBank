import calendar
from datetime import datetime

import customtkinter as ctk

from config import load_config


class CustomCalendar(ctk.CTkToplevel):
    """Fenêtre surgissante affichant un calendrier interactif pour choisir une date."""

    def __init__(self, parent: ctk.CTkToplevel, current_date_str: str, callback: callable) -> None:
        super().__init__(parent)
        self.title("Choisir une date")
        self.geometry("300x350")
        self.transient(parent)
        self.grab_set()

        self.__theme = load_config()["theme"]
        self.__callback = callback
        # Parsing de la date actuelle ou défaut à aujourd'hui
        try:
            self.__current_date = datetime.strptime(current_date_str, "%Y-%m-%d")
        except Exception:
            self.__current_date = datetime.now()

        self.__view_month = self.__current_date.month
        self.__view_year = self.__current_date.year

        self.__setup_ui()

    def __setup_ui(self) -> None:
        """Ajoute l'entête pour les mois et la navigation."""

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(
            header,
            text="<",
            width=30,
            fg_color=self.__theme["blue_01"]["fg_color"],
            hover_color=self.__theme["blue_01"]["hover_color"],
            command=lambda: self.__change_month(-1),
        ).pack(side="left")

        self.__month_label = ctk.CTkLabel(header, text="", font=("Arial", 14, "bold"))
        self.__month_label.pack(side="left", expand=True)

        ctk.CTkButton(
            header,
            text=">",
            width=30,
            fg_color=self.__theme["blue_01"]["fg_color"],
            hover_color=self.__theme["blue_01"]["hover_color"],
            command=lambda: self.__change_month(1),
        ).pack(side="left")

        # Grille des jours
        self.__days_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.__days_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.__draw_calendar()

    def __draw_calendar(self) -> None:
        """Affiche le calendrier"""

        for widget in self.__days_frame.winfo_children():
            widget.destroy()

        # Nom du mois
        month_name = calendar.month_name[self.__view_month]
        self.__month_label.configure(text=f"{month_name} {self.__view_year}")

        # En-têtes Jours (L, M, M...)
        days = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        for i, day in enumerate(days):
            ctk.CTkLabel(self.__days_frame, text=day, font=("Arial", 11)).grid(row=0, column=i, sticky="nsew")

        # Calcul des jours du mois
        month_days = calendar.monthcalendar(self.__view_year, self.__view_month)

        for r, week in enumerate(month_days):
            for c, day in enumerate(week):
                if day != 0:
                    # Style différent pour le jour aujourd'hui
                    is_today = (
                        day == datetime.now().day
                        and self.__view_month == datetime.now().month
                        and self.__view_year == datetime.now().year
                    )

                    btn = ctk.CTkButton(
                        self.__days_frame,
                        text=str(day),
                        width=35,
                        height=35,
                        fg_color=self.__theme["blue_01"]["fg_color"],
                        hover_color=self.__theme["green"]["hover_color"],
                        border_width=1 if is_today else 0,
                        command=lambda d=day: self.__select_date(d),
                    )
                    btn.grid(row=r + 1, column=c, padx=1, pady=1)

    def __change_month(self, delta) -> None:
        """Décale le mois affiché et ajuste l'année en cas de dépassement."""

        self.__view_month += delta
        if self.__view_month > 12:
            self.__view_month = 1
            self.__view_year += 1
        elif self.__view_month < 1:
            self.__view_month = 12
            self.__view_year -= 1
        self.__draw_calendar()

    def __select_date(self, day) -> None:
        """Formate la date sélectionnée, exécute le callback et ferme la vue."""

        selected = datetime(self.__view_year, self.__view_month, day)
        self.__callback(selected.strftime("%Y-%m-%d"))
        self.destroy()
