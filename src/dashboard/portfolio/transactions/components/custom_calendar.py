import calendar
from datetime import date, datetime

import customtkinter as ctk


class CustomCalendar(ctk.CTkToplevel):
    """Fenêtre modale de sélection de date via un calendrier."""

    def __init__(
        self,
        parent: ctk.CTkFrame | ctk.CTk | ctk.CTkToplevel,
        initial_date: str,
        callback: str,
        block_future_dates: bool = False,
    ) -> None:
        super().__init__(parent)

        self._callback = callback
        self._block_future_dates = block_future_dates
        self._today = datetime.now().date()

        try:
            parsed_date = datetime.strptime(initial_date.strip(), "%Y-%m-%d").date()
        except (ValueError, AttributeError):
            parsed_date = self._today

        self._current_year = parsed_date.year
        self._current_month = parsed_date.month

        self.title("Sélectionner une date")
        self.geometry("320x340")
        self.transient(parent)
        self.grab_set()

        self.__setup_ui()

    def __setup_ui(self) -> None:
        """Construit la grille du calendrier."""
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(header_frame, text="<", width=30, command=self._prev_month).pack(side="left")

        self._month_label = ctk.CTkLabel(header_frame, text="", font=("Arial", 14, "bold"))
        self._month_label.pack(side="left", expand=True)

        ctk.CTkButton(header_frame, text=">", width=30, command=self._next_month).pack(side="right")

        # Conteneur des jours
        self._calendar_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._calendar_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self._render_calendar()

    def _render_calendar(self) -> None:
        """Rend visuellement les jours du mois sélectionné."""
        for widget in self._calendar_frame.winfo_children():
            widget.destroy()

        # Nom des jours de la semaine
        days_header = ["Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di"]
        for col, day_name in enumerate(days_header):
            ctk.CTkLabel(self._calendar_frame, text=day_name, font=("Arial", 10, "bold")).grid(
                row=0, column=col, padx=2, pady=2
            )

        self._month_label.configure(text=f"{calendar.month_name[self._current_month]} {self._current_year}")

        month_calendar = calendar.monthcalendar(self._current_year, self._current_month)

        for row_idx, week in enumerate(month_calendar, start=1):
            for col_idx, day in enumerate(week):
                if day == 0:
                    continue

                cell_date = date(self._current_year, self._current_month, day)
                is_future = self._block_future_dates and cell_date > self._today

                if is_future:
                    # Bouton désactivé et grisé pour les dates futures
                    btn = ctk.CTkButton(
                        self._calendar_frame,
                        text=str(day),
                        width=35,
                        height=30,
                        state="disabled",
                        fg_color="transparent",
                        text_color_disabled="#6c757d",
                    )
                else:
                    btn = ctk.CTkButton(
                        self._calendar_frame,
                        text=str(day),
                        width=35,
                        height=30,
                        command=lambda d=cell_date: self._select_date(d),
                    )

                btn.grid(row=row_idx, column=col_idx, padx=2, pady=2)

    def _select_date(self, selected_date: date) -> None:
        """Retourne la date au format YYYY-MM-DD et ferme le calendrier."""
        if callable(self._callback):
            self._callback(selected_date.strftime("%Y-%m-%d"))
        self.destroy()

    def _prev_month(self) -> None:
        if self._current_month == 1:
            self._current_month = 12
            self._current_year -= 1
        else:
            self._current_month -= 1
        self._render_calendar()

    def _next_month(self) -> None:
        if self._current_month == 12:
            self._current_month = 1
            self._current_year += 1
        else:
            self._current_month += 1
        self._render_calendar()
