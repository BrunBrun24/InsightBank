import html
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox

import pandas as pd
import xlrd

from config import load_config


class DataExtractor:
    """Classe responsable de la sélection, de l'extraction et du nettoyage de données issues de fichiers."""

    def __init__(self) -> None:
        self.__config = load_config()
        self.__initial_dir = self.__config["extract_file"]

    def run_extraction(self, account_id: int) -> pd.DataFrame | None:
        """Lance la fenêtre pour l'extraction des données."""

        paths = filedialog.askopenfilenames(
            title="Choisir un ou plusieurs fichiers",
            initialdir=self.__initial_dir,
            filetypes=[
                ("Fichiers Excel", "*.xls *.xlsx *.csv"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if paths:
            file_paths = list(paths)
        else:
            return None

        all_dfs = []
        for file_path in file_paths:
            extension = f".{file_path.lower().split('.')[-1]}"
            if extension in [".xls", ".xlsx"]:
                df_temp = self.__extract_file_data(file_path, extension)
            elif extension == ".csv":
                df_temp = self.__extract_csv_data(file_path)

            if df_temp is not None:
                all_dfs.append(df_temp)

        if all_dfs:
            df = pd.concat(all_dfs, ignore_index=True)
            df["account_id"] = account_id

            return df

        return None

    def __extract_file_data(self, file_path: str, extension: str) -> pd.DataFrame | None:
        """Extrait dynamiquement les données du fichier de donnée."""

        try:
            # Extraction brute selon l'extension
            if extension == ".xls":
                workbook = xlrd.open_workbook(file_path)
                sheet = workbook.sheet_by_index(0)
                raw_rows = [sheet.row_values(i) for i in range(sheet.nrows)]
            else:
                df_raw = pd.read_excel(file_path, engine="openpyxl", header=None)
                raw_rows = df_raw.values.tolist()

            # S'il n'y a pas de données
            if not raw_rows:
                return None

            # On regarde d'où provienne les données
            if self.__config["bank"] == "BNP Paribas":
                return self.__extract_bnp_paribas(raw_rows)

            # On récupère les en-têtes sur la première ligne
            header_labels = [str(h).strip().lower() for h in raw_rows[0] if str(h).strip() != ""]

            # On extrait les données
            data = []
            for r in range(1, len(raw_rows)):
                row_data = raw_rows[r][: len(header_labels)]  # On s'aligne sur le nombre d'en-têtes

                # On ignore les lignes totalement vides
                if any(str(val).strip() for val in row_data if val is not None):
                    data.append(row_data)

            # Création du DataFrame
            operations_df = pd.DataFrame(data, columns=header_labels)

            # Vérification du nom des colonnes
            operations_df.columns = [str(c).strip().lower() for c in operations_df.columns]
            key_cols = ["date operation", "libelle operation", "montant operation en euro"]
            missing = [c for c in key_cols if c not in operations_df.columns]
            if missing:
                messagebox.showerror(
                    "Erreur",
                    f"Il manque les colonnes suivantes : {missing}\n\nVos colonnes actuelles: {operations_df.columns.to_list()}",
                )
                return None

            # Conversion des dates
            date_col = "date operation"
            operations_df[date_col] = operations_df[date_col].apply(self.__excel_date_to_datetime)
            operations_df[date_col] = pd.to_datetime(operations_df[date_col])

            # On renomme pour correspondre aux noms de la base de données
            column_mapping = {
                "date operation": "operation_date",
                "libelle operation": "label",
                "montant operation en euro": "amount",
            }
            operations_df = operations_df.rename(columns=column_mapping)
            operations_df["operation_date"] = pd.to_datetime(operations_df["operation_date"]).dt.strftime("%Y-%m-%d")

            return operations_df[["operation_date", "label", "amount"]]

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur sur le fichier {file_path} : {str(e)}")
            return None

    def __extract_csv_data(self, file_path: str) -> pd.DataFrame | None:
        """Extrait les données brutes d'un fichier csv."""

        try:
            df = pd.read_csv(
                file_path,
                sep=";",
                encoding="utf-8",
                header=None,
                on_bad_lines="skip",
                decimal=",",
            )

            # Nettoyage HTML
            df = df.map(lambda x: html.unescape(str(x)) if isinstance(x, str) else x)

            # Filtrage des lignes de transactions uniquement
            df = df[df[0].str.contains(r"\d{2}/\d{2}/\d{4}", na=False)].copy()

            df = df.iloc[:, 0:5]
            df.columns = [
                "operation_date",
                "libelle_court",
                "type_operation",
                "libelle_operation",
                "montant",
            ]

            df["montant"] = pd.to_numeric(df["montant"], errors="coerce")
            df = df.dropna(subset=["montant"])
            df["operation_date"] = pd.to_datetime(df["operation_date"], dayfirst=True)

            self.__apply_business_rules(df)
            return df

        except Exception as e:
            messagebox.showerror("Erreur CSV", f"Erreur sur le fichier {file_path} : {str(e)}")
            raise
            return None

    def __extract_bnp_paribas(self, raw_rows: list) -> pd.DataFrame:
        """Extrait les données du fichier provenant de la banque BNP Paribas."""

        # 1. Recherche des coordonnées de "Date operation"
        start_row, start_col = None, None
        for r_idx, row in enumerate(raw_rows):
            for c_idx, value in enumerate(row):
                if str(value).strip().lower() == "date operation":
                    start_row, start_col = r_idx, c_idx
                    break
            if start_row is not None:
                break

        if start_row is None:
            messagebox.showerror("Erreur", "'Date operation' est introuvable.")
            return None

        # 2. Récupération des en-têtes (toutes les colonnes à droite de start_col)
        # On nettoie les noms pour éviter les espaces inutiles
        header_labels = [str(h).strip() for h in raw_rows[start_row][start_col:]]

        # 3. Extraction des données
        data = []
        for r in range(start_row + 1, len(raw_rows)):
            # On prend la ligne à partir de start_col jusqu'au bout
            row_data = raw_rows[r][start_col:]

            # Ajuste la longueur de row_data si elle diffère des headers (cas rares sur XLS)
            if len(row_data) > len(header_labels):
                row_data = row_data[: len(header_labels)]

            # Arrête si la ligne est vide
            if not any(str(val).strip() for val in row_data if val is not None and str(val).strip() != ""):
                break

            data.append(row_data)

        # 4. Création du DataFrame avec les colonnes nommées
        operations_df = pd.DataFrame(data, columns=header_labels)

        # Vérification du nom des colonnes
        operations_df.columns = [str(c).strip().lower() for c in operations_df.columns]
        key_cols = ["date operation", "libelle operation", "montant operation en euro"]
        missing = [c for c in key_cols if c not in operations_df.columns]
        if missing:
            messagebox.showerror("Erreur", f"Il manque des colonnes : {missing}")
            return None

        # Conversion des dates
        date_col = "date operation"
        operations_df[date_col] = operations_df[date_col].apply(self.__excel_date_to_datetime)
        operations_df[date_col] = pd.to_datetime(operations_df[date_col])

        # On renomme pour correspondre aux noms de la base de données
        column_mapping = {
            "date operation": "operation_date",
            "libelle court": "short_label",
            "type operation": "operation_type",
            "libelle operation": "label",
            "montant operation en euro": "amount",
        }
        operations_df = operations_df.rename(columns=column_mapping)

        self.__apply_business_rules(operations_df)
        operations_df["operation_date"] = pd.to_datetime(operations_df["operation_date"]).dt.strftime("%Y-%m-%d")

        return operations_df[["operation_date", "short_label", "operation_type", "label", "amount"]]

    def __apply_business_rules(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applique les transformations de nettoyage sur les libellés et les dates."""

        for index, row in df.iterrows():
            libelle = str(row["label"])

            if row["short_label"] == "PAIEMENT CB":
                df.at[index, "label"] = self.__extract_between_slashes(libelle, 0, -2)
                new_date, new_libelle = self.__extract_date_from_libelle(libelle)
                if new_date:
                    df.at[index, "operation_date"] = new_date
                if new_libelle:
                    df.at[index, "label"] = self.__clean_libelle_spacing(new_libelle)

            elif row["operation_type"] == "VIR CPTE A CPTE EMIS":
                clean_txt = self.__extract_between_slashes(libelle, 0, -2)
                df.at[index, "label"] = self.__clean_libelle_spacing(clean_txt)

            elif row["operation_type"] in ["VIR CPTE A CPTE RECU", "VIR SEPA RECU"]:
                clean_txt = self.__extract_between_slashes(libelle, 0, -1)
                df.at[index, "label"] = self.__clean_libelle_spacing(clean_txt)

            elif row["operation_type"] == "REMISE CHEQUES":
                clean_txt = self.__extract_between_slashes(libelle, 0, 0)
                df.at[index, "label"] = self.__clean_libelle_spacing(clean_txt)

        return df

    def __excel_date_to_datetime(self, excel_date: float) -> datetime:
        """Convertit un nombre Excel en objet datetime."""

        if not isinstance(excel_date, (int, float)):
            return excel_date

        return datetime(1899, 12, 30) + timedelta(days=excel_date)

    def __extract_between_slashes(self, text: str, start: int, end: int) -> str:
        """Extrait le texte situé entre des slashs selon les indices fournis."""

        slash_positions = [i for i, char in enumerate(text) if char == "/"]

        if end == 0 and slash_positions:
            return text[: slash_positions[0]].strip()

        if len(slash_positions) >= abs(end) and len(slash_positions) > start:
            return text[slash_positions[start] + 1 : slash_positions[end]].strip()

        return text

    def __extract_date_from_libelle(self, libelle: str) -> tuple[datetime, str] | tuple[None, None]:
        """Extrait une date jj/mm/aa après le mot clé 'DU'."""

        if "DU" in libelle:
            try:
                start_index = libelle.find("DU") + 3
                date_str = libelle[start_index : start_index + 6]
                formatted_date = datetime.strptime(date_str, "%d%m%y")
                new_libelle = libelle[start_index + 7 :]
                return formatted_date, new_libelle
            except (ValueError, IndexError):
                return None, None

        return None, None

    def __clean_libelle_spacing(self, libelle: str) -> str:
        """Supprime le contenu après un double espace."""

        double_space_index = libelle.find("  ")
        if double_space_index != -1:
            return libelle[:double_space_index].strip()

        return libelle.strip()
