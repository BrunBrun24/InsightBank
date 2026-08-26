import tkinter as tk

import customtkinter as ctk

from utils.window_utils import center_window_on_parent


class LoadingPopup(tk.Toplevel):
    """Fenêtre modale bloquante affichant un indicateur de chargement adapté au texte."""

    def __init__(self, parent: ctk.CTkFrame | ctk.CTk, message: str) -> None:
        super().__init__(parent)
        self.title("Veuillez patienter")
        self.resizable(False, False)

        bg_color = ctk.ThemeManager.theme["CTkFrame"]["fg_color"][0 if ctk.get_appearance_mode() == "Light" else 1]
        self.configure(bg=bg_color)

        self.transient(parent.winfo_toplevel())
        self.grab_set()

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # Label avec retour à la ligne automatique si le message est long
        self.__label = ctk.CTkLabel(
            container,
            text=message,
            font=("Arial", 13, "bold"),
            wraplength=400,
        )
        self.__label.pack(pady=(20, 10), padx=20)

        # Barre de progression qui s'étire selon le conteneur
        self.__progress = ctk.CTkProgressBar(container, mode="indeterminate")
        self.__progress.pack(fill="x", pady=10, padx=20)
        self.__progress.start()

        self.protocol("WM_DELETE_WINDOW", lambda: None)

        self.__adjust_size_and_center(parent)

    def __adjust_size_and_center(self, parent: ctk.CTkFrame | ctk.CTk) -> None:
        """Calcule les dimensions nécessaires selon les éléments affichés et centre la fenêtre."""
        self.update_idletasks()

        # Récupération de la largeur et de la hauteur requises par les widgets internes
        req_width = max(300, self.winfo_reqwidth() + 40)
        req_height = max(130, self.winfo_reqheight() + 20)

        center_window_on_parent(self, parent, width=req_width, height=req_height)

    def close(self) -> None:
        """Arrête l'animation et détruit la fenêtre modale en toute sécurité."""
        try:
            self.__progress.stop()
            self.grab_release()
            self.destroy()
        except Exception:
            pass
