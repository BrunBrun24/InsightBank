from tkinter import messagebox

import pandas as pd
import xlrd


def extract_file_xlsx_xls(file_path: str, extension: str) -> list | None:
    try:
        if extension == ".xls":
            workbook = xlrd.open_workbook(file_path)
            sheet = workbook.sheet_by_index(0)
            return [sheet.row_values(i) for i in range(sheet.nrows)]
        else:
            df_raw = pd.read_excel(file_path, engine="openpyxl", header=None)
            return df_raw.values.tolist()

    except (pd.errors.EmptyDataError, KeyError, ValueError) as e:
        messagebox.showerror("Erreur d'extraction", f"Erreur sur le fichier {file_path} : {e}")
        return None
