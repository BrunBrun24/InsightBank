import os
import shutil
import subprocess
import unicodedata
import webbrowser
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox

import customtkinter as ctk

from utils.window_utils import center_window_on_parent, center_window_on_screen


def remove_accents(input_str: str) -> str:
    """Remplace les lettres accentuées d'une chaîne par leurs équivalents sans accent."""

    if not isinstance(input_str, str):
        return input_str

    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def prompt_data_source(sources: list[str], master: ctk.CTkFrame | ctk.CTk | None = None) -> str | None:
    """Affiche une fenêtre modale centrée pour sélectionner la source des données."""

    selected_source = None
    width = 380
    height = 200

    dialog = ctk.CTkToplevel(master)
    dialog.title("Source des données")
    dialog.resizable(False, False)

    # Configuration des dimensions et centrage
    dialog.geometry(f"{width}x{height}")

    if master:
        dialog.transient(master)
        center_window_on_parent(dialog, master, width=width, height=height)
    else:
        center_window_on_screen(dialog, width=width, height=height)

    dialog.grab_set()

    ctk.CTkLabel(
        dialog,
        text="Sélectionnez l'origine du fichier :",
        font=("Arial", 14, "bold"),
    ).pack(pady=(20, 10))

    option_menu = ctk.CTkOptionMenu(
        dialog,
        values=sources,
        width=220,
    )
    option_menu.pack(pady=10)
    if sources:
        option_menu.set(sources[0])

    def on_confirm() -> None:
        nonlocal selected_source
        selected_source = option_menu.get()
        dialog.destroy()

    ctk.CTkButton(
        dialog,
        text="Valider",
        command=on_confirm,
        width=120,
    ).pack(pady=(15, 10))

    dialog.wait_window()

    return selected_source


def excel_date_to_datetime(excel_date: float) -> datetime:
    """Convertit un nombre Excel en objet datetime."""

    if not isinstance(excel_date, (int, float)):
        return excel_date

    return datetime(1899, 12, 30) + timedelta(days=excel_date)


def handle_download(file_path: str) -> None:
    """Permet à l'utilisateur de copier le bilan HTML vers un emplacement local."""

    try:
        if not os.path.exists(file_path):
            messagebox.showerror("Erreur", "Le fichier source est introuvable.")
            return

        default_filename = os.path.basename(file_path)

        # Ouvrir la boîte de dialogue pour choisir la destination
        destination_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            initialfile=default_filename,
            filetypes=[("Fichier HTML", "*.html"), ("Tous les fichiers", "*.*")],
            title="Télécharger le bilan",
        )

        # Si l'utilisateur n'a pas annulé, on copie le fichier
        if destination_path:
            shutil.copy2(file_path, destination_path)
            messagebox.showinfo(
                "Succès", f"Le bilan a été téléchargé avec succès :\n{os.path.basename(destination_path)}"
            )

    except Exception as e:
        messagebox.showerror("Erreur", f"Échec du téléchargement : {e}")


def open_in_browser(file_path: str) -> None:
    """Ouvre le fichier HTML dans le navigateur par défaut de l'utilisateur"""
    absolute_path = os.path.abspath(file_path)

    if os.path.exists(absolute_path):
        webbrowser.open(f"file://{absolute_path}", new=2)


def open_xlsx_window(file_path: str) -> None:
    """Ouvre le fichier Excel."""
    if not os.path.exists(file_path):
        messagebox.showerror("Erreur", "Le fichier Excel est introuvable.")
        return

    try:
        subprocess.Popen(["start", "excel", "/r", os.path.abspath(file_path)], shell=True)

    except (OSError, subprocess.SubprocessError):
        try:
            os.startfile(file_path)
        except OSError:
            messagebox.showerror(
                "Erreur critique", f"Aucun logiciel n'est associé aux fichiers {os.path.splitext(file_path)[1]}"
            )
