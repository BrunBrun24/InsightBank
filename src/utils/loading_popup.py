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

        self._top_parent = parent.winfo_toplevel()
        self.transient(self._top_parent)
        self.grab_set()

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # Label d'information
        self.__label = ctk.CTkLabel(
            container,
            text=message,
            font=("Arial", 13, "bold"),
            wraplength=400,
        )
        self.__label.pack(pady=(20, 10), padx=20)

        # Barre de progression
        self.__progress = ctk.CTkProgressBar(container, mode="indeterminate")
        self.__progress.pack(fill="x", pady=10, padx=20)
        self.__progress.start()

        self.protocol("WM_DELETE_WINDOW", lambda: None)

        # Écoute les mouvements et redimensionnements de la fenêtre principale
        self._configure_binding = self._top_parent.bind("<Configure>", self.__on_parent_configure, add="+")

        # Repousse le centrage initial
        self.after(50, lambda: self.__adjust_size_and_center(parent))

    def __adjust_size_and_center(self, parent: ctk.CTkFrame | ctk.CTk) -> None:
        """Calcule les dimensions nécessaires selon les éléments affichés et centre la fenêtre."""
        self._top_parent.update_idletasks()
        self.update_idletasks()

        req_width = max(300, self.winfo_reqwidth() + 40)
        req_height = max(130, self.winfo_reqheight() + 20)

        center_window_on_parent(self, self._top_parent, width=req_width, height=req_height)

    def __on_parent_configure(self, event: tk.Event) -> None:
        """Recentre le popup lorsque la fenêtre principale se déplace ou change de taille."""
        # Filtre pour ne réagir qu'aux événements venant directement de la fenêtre principale
        if event.widget == self._top_parent:
            req_width = self.winfo_width()
            req_height = self.winfo_height()
            center_window_on_parent(self, self._top_parent, width=req_width, height=req_height)

    def close(self) -> None:
        """Arrête l'animation, retire le listener et détruit la fenêtre modale."""
        try:
            # Suppression du lien d'événement pour éviter les erreurs après destruction
            if hasattr(self, "_configure_binding"):
                self._top_parent.unbind("<Configure>", self._configure_binding)

            self.__progress.stop()
            self.grab_release()
            self.destroy()
        except Exception:
            pass
