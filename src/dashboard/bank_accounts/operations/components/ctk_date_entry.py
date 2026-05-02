from datetime import datetime

import customtkinter as ctk

from config import load_config
from dashboard.bank_accounts.operations.components.custom_calendar import CustomCalendar


class CtkDateEntry(ctk.CTkFrame):
    """Widget simulant une entrée de date avec un bouton calendrier intégré."""

    def __init__(self, master: ctk.CTkFrame, initial_date=None) -> None:
        super().__init__(master, fg_color="transparent")

        self.__date_var = ctk.StringVar(value=initial_date or datetime.now().strftime("%Y-%m-%d"))

        # Champ de texte
        self.__entry = ctk.CTkEntry(self, textvariable=self.__date_var, width=150)
        self.__entry.pack(side="left", padx=(0, 5))

        self.__btn = ctk.CTkButton(
            self,
            text="📅",
            width=40,
            fg_color=load_config()["theme"]["blue_01"]["fg_color"],
            hover_color=load_config()["theme"]["blue_01"]["hover_color"],
            command=self.__open_calendar,
        )
        self.__btn.pack(side="left")

    def get(self) -> str:
        return self.__date_var.get()

    def __open_calendar(self) -> None:
        cal = CustomCalendar(self.winfo_toplevel(), self.__date_var.get(), self.__set_date)
        self.__center_calendar(cal)

    def __set_date(self, date_str: str) -> None:
        self.__date_var.set(date_str)

    def __center_calendar(self, calendar_window: ctk.CTkInputDialog) -> None:
        """Centre le calendrier par rapport à la fenêtre principale."""

        # On force la mise à jour pour avoir les vraies dimensions du calendrier
        calendar_window.update_idletasks()

        main_app = self.winfo_toplevel()

        # Calcul des coordonnées
        x = main_app.winfo_x() + (main_app.winfo_width() // 2) - (calendar_window.winfo_width() // 2)
        y = main_app.winfo_y() + (main_app.winfo_height() // 2) - (calendar_window.winfo_height() // 2)

        calendar_window.geometry(f"+{x}+{y}")
