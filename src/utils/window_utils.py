import customtkinter as ctk


def center_window_on_screen(
    window: ctk.CTkToplevel | ctk.CTk, width: int, height: int, y_offset_ratio: float = 3.0
) -> None:
    """Centre une fenêtre au milieu de l'écran principal."""

    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    x = (screen_width - width) // 2
    y = int((screen_height - height) // y_offset_ratio)

    window.geometry(f"{width}x{height}+{x}+{y}")


def center_window_on_parent(
    window: ctk.CTkToplevel | ctk.CTkInputDialog,
    parent: ctk.CTkFrame | ctk.CTk | ctk.CTkToplevel,
    width: int | None = None,
    height: int | None = None,
) -> None:
    """Centre une fenêtre modale par rapport à sa fenêtre parente."""

    window.update_idletasks()
    parent_top = parent.winfo_toplevel()
    parent_top.update_idletasks()

    p_x = parent_top.winfo_x()
    p_y = parent_top.winfo_y()
    p_w = parent_top.winfo_width()
    p_h = parent_top.winfo_height()

    # Si la largeur/hauteur ne sont pas passées explicitement, on lit celles du widget
    w_w = width if width is not None else window.winfo_width()
    w_h = height if height is not None else window.winfo_height()

    x = p_x + (p_w - w_w) // 2
    y = p_y + (p_h - w_h) // 2

    window.geometry(f"{w_w}x{w_h}+{x}+{y}")
