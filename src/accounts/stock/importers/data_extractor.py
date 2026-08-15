from tkinter import filedialog, messagebox

import customtkinter as ctk
import pandas as pd
import xlrd

from utils.data_utils import excel_date_to_datetime, prompt_data_source


class DataExtractor:
    """Classe responsable de la sélection, de l'extraction et du nettoyage de données issues de fichiers."""

    def __init__(self, portfolio_id: int, master: ctk.CTkFrame | ctk.CTk | None = None) -> None:
        self.__portfolio_id = portfolio_id
        self.__master = master

    def run_extraction(self) -> tuple[pd.DataFrame | None, str]:
        """Demande d'abord la source des données via une fenêtre modale, puis lance la sélection des fichiers pour l'extraction."""

        bank_account_sources = {"Non précisé": "*.xls *.xlsx", "Trade Republic": "*.csv"}
        source = prompt_data_source(list(bank_account_sources.keys()), self.__master)
        if not source:
            return None, None

        paths = filedialog.askopenfilenames(
            title="Choisir un ou plusieurs fichiers",
            filetypes=[
                ("Fichiers Excel", bank_account_sources[source]),
            ],
        )

        if not paths:
            return None, None

        file_paths = list(paths)
        all_dfs = []

        # Traitement selon l'extension
        for file_path in file_paths:
            extension = f".{file_path.lower().split('.')[-1]}"
            if source == "Trade Republic":
                df_temp = self.__extract_csv_trade_republic(file_path)
            else:
                df_temp = self.__extract_file_data(file_path, extension)

            if df_temp is not None:
                all_dfs.append(df_temp)

        if all_dfs:
            df = pd.concat(all_dfs, ignore_index=True)
            df["portfolio_id"] = self.__portfolio_id
            return df, source

        return None, source

    def __extract_file_data(self, file_path: str, extension: str) -> pd.DataFrame | None:
        try:
            if extension == ".xls":
                workbook = xlrd.open_workbook(file_path)
                sheet = workbook.sheet_by_index(0)
                raw_rows = [sheet.row_values(i) for i in range(sheet.nrows)]
            else:
                df_raw = pd.read_excel(file_path, engine="openpyxl", header=None)
                raw_rows = df_raw.values.tolist()

            if not raw_rows:
                return None

            # On récupère les en-têtes sur la première ligne
            header_labels = [str(h).strip().lower() for h in raw_rows[0] if str(h).strip() != ""]

            # On extrait les données
            data = []
            for r in range(1, len(raw_rows)):
                row_data = raw_rows[r][: len(header_labels)]  # On s'aligne sur le nombre d'en-têtes

                # On ignore les lignes totalement vides
                if any(str(val).strip() for val in row_data if val is not None):
                    data.append(row_data)

            operations_df = pd.DataFrame(data, columns=header_labels)

            # Vérification du nom des colonnes
            operations_df.columns = [str(c).strip().lower() for c in operations_df.columns]
            key_cols = ["date", "devise", "type", "montant", "frais", "symbol", "prix d'achat"]
            missing = [c for c in key_cols if c not in operations_df.columns]
            if missing:
                messagebox.showerror(
                    "Erreur",
                    f"Il manque les colonnes suivantes : {missing}\n\nVos colonnes actuelles: {operations_df.columns.to_list()}",
                )
                return None

            # On renomme pour correspondre aux noms de la base de données
            column_mapping = {
                "montant": "amount",
                "devise": "currency",
                "frais": "fee",
                "prix d'achat": "price",
            }
            operations_df = operations_df.rename(columns=column_mapping)

            return operations_df

        except Exception:
            messagebox.showerror("Erreur", f"Erreur sur le fichier {file_path}.")
            return None

    def __extract_csv_trade_republic(self, file_path: str) -> pd.DataFrame | None:
        try:
            df = pd.read_csv(file_path)

            df = df[
                [
                    "date",
                    "category",
                    "type",
                    "name",
                    "symbol",
                    "shares",
                    "price",
                    "amount",
                    "fee",
                    "tax",
                    "currency",
                    "original_amount",
                    "original_currency",
                    "fx_rate",
                ]
            ]

            date_col = "date"
            df[date_col] = df[date_col].apply(excel_date_to_datetime)
            df[date_col] = pd.to_datetime(df[date_col])
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

            return df

        except Exception:
            messagebox.showerror(
                "Erreur",
                f"Erreur sur le fichier {file_path}.\n\nVous ne devez pas modifier le fichier que vous avez téléchargé sur Trade Republic.",
            )
            return None
