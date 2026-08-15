import tkinter as tk

import customtkinter as ctk

from utils.window_utils import center_window_on_parent


class LoadingPopup(tk.Toplevel):
    """Fenêtre modale bloquante affichant un indicateur de chargement."""

    def __init__(self, parent: ctk.CTkFrame | ctk.CTk, message: str = "Importation des données en cours...") -> None:
        super().__init__(parent)
        self.title("Veuillez patienter")
        self.resizable(False, False)

        # Style de fond cohérent avec CustomTkinter
        bg_color = ctk.ThemeManager.theme["CTkFrame"]["fg_color"][0 if ctk.get_appearance_mode() == "Light" else 1]
        self.configure(bg=bg_color)

        # Rendre la fenêtre modale
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        # Conteneur principal CustomTkinter
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # Interface
        self.__label = ctk.CTkLabel(container, text=message, font=("Arial", 13, "bold"))
        self.__label.pack(pady=(20, 10), padx=20)

        self.__progress = ctk.CTkProgressBar(container, width=280, mode="indeterminate")
        self.__progress.pack(pady=10, padx=20)
        self.__progress.start()

        center_window_on_parent(self, parent, width=350, height=140)

        # Empêche la fermeture manuelle par l'utilisateur (Croix rouge)
        self.protocol("WM_DELETE_WINDOW", lambda: None)

    def close(self) -> None:
        """Arrête l'animation et détruit la fenêtre modale en toute sécurité."""

        try:
            self.__progress.stop()
            self.grab_release()
            self.destroy()
        except Exception:
            pass
