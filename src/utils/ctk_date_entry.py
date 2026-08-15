from datetime import datetime

import customtkinter as ctk

from config import load_config
from dashboard.bank_accounts.operations.components.custom_calendar import CustomCalendar
from utils.window_utils import center_window_on_parent


class CtkDateEntry(ctk.CTkFrame):
    """Widget simulant une entrée de date avec un bouton calendrier intégré et callback optionnel."""

    def __init__(
        self,
        master: ctk.CTkFrame | ctk.CTk | ctk.CTkToplevel,
        initial_date: str | None = None,
        command: str | None = None,
        block_future_dates: bool = False,
    ) -> None:
        super().__init__(master, fg_color="transparent")

        self.__command = command
        self.__block_future_dates = block_future_dates

        default_date = initial_date or datetime.now().strftime("%Y-%m-%d")
        if self.__block_future_dates and self.__is_future_date(default_date):
            default_date = datetime.now().strftime("%Y-%m-%d")

        self.__date_var = ctk.StringVar(value=default_date)
        theme_blue = load_config()["theme"]["blue_01"]

        # Validation Tkinter à la perte de focus pour la saisie manuelle
        vcmd = (self.register(self.__validate_on_focus_out), "%P")

        # Champ de texte
        self.__entry = ctk.CTkEntry(
            self,
            textvariable=self.__date_var,
            width=150,
            validate="focusout",
            validatecommand=vcmd,
        )
        self.__entry.pack(side="left", padx=(0, 5))

        # Déclenchement du callback applicatif lors d'une modification
        self.__date_var.trace_add("write", self.__on_date_var_change)

        # Bouton Calendrier
        self.__btn = ctk.CTkButton(
            self,
            text="📅",
            width=40,
            fg_color=theme_blue["fg_color"],
            hover_color=theme_blue["hover_color"],
            command=self.__open_calendar,
        )
        self.__btn.pack(side="left")

    def __is_future_date(self, date_str: str) -> bool:
        """Vérifie si la date au format YYYY-MM-DD est strictement supérieure à aujourd'hui."""
        try:
            parsed_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
            return parsed_date > datetime.now().date()
        except ValueError:
            return False

    def __validate_on_focus_out(self, proposed_val: str) -> bool:
        """Valide la date lorsque l'utilisateur quitte le champ de texte."""
        if self.__block_future_dates and self.__is_future_date(proposed_val):
            today_str = datetime.now().strftime("%Y-%m-%d")
            self.__date_var.set(today_str)
            return False
        return True

    def __on_date_var_change(self, *args) -> None:
        current_val = self.__date_var.get()
        if callable(self.__command):
            self.__command(current_val)

    def get(self) -> str:
        return self.__date_var.get()

    def set(self, date_str: str) -> None:
        """Définit programmatiquement la date du composant en appliquant le verrouillage."""

        if self.__block_future_dates and self.__is_future_date(date_str):
            date_str = datetime.now().strftime("%Y-%m-%d")
        self.__date_var.set(date_str)

    def __open_calendar(self) -> None:
        cal = CustomCalendar(
            self.winfo_toplevel(),
            self.__date_var.get(),
            self.__set_date,
        )
        center_window_on_parent(cal, self.winfo_toplevel())

    def __set_date(self, date_str: str) -> None:
        """Reçoit la date sélectionnée dans le calendrier et applique la restriction."""
        if self.__block_future_dates and self.__is_future_date(date_str):
            date_str = datetime.now().strftime("%Y-%m-%d")
        self.set(date_str)
