import base64
import os
import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Generator


class DatabaseBase(ABC):
    """Fournit une interface de base pour interagir avec une base de données SQLite."""

    def __init__(self, db_path: str) -> None:
        """Initialise la connexion et crée le dossier parent si nécessaire."""

        self._db_path = db_path

        # Création automatique du dossier si inexistant
        folder = os.path.dirname(self._db_path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, Any, None]:
        """
        Gestionnaire de contexte qui valide les modifications en cas de réussite,
        annule les modifications en cas d'erreur et se ferme systématiquement.
        """

        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        except sqlite3.Error as error:
            conn.rollback()
            raise Exception(f"Erreur SQL : {error}")
        finally:
            conn.close()

    @abstractmethod
    def _create_database() -> None:
        """Chaque BDD doit définir ses propres tables ici."""
        pass

    def export_database_to_dict(self) -> dict:
        """Exporte l'ensemble des tables de la base de données en se basant strictement sur les types SQL."""
        data = {}

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                # Récupère les types de chaque colonne (ex: {'file_data': 'BLOB', 'name': 'TEXT', ...})
                cursor.execute(f"PRAGMA table_info('{table}');")
                column_types = {row[1]: row[2].upper() for row in cursor.fetchall()}

                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()

                table_records = []
                for row in rows:
                    row_dict = dict(row)
                    for key, value in row_dict.items():
                        col_type = column_types.get(key, "")

                        # Seules les colonnes de type BLOB (ou valeurs binaires brutes) sont converties en Base64
                        if ("BLOB" in col_type or isinstance(value, bytes)) and value is not None:
                            if isinstance(value, bytes):
                                row_dict[key] = base64.b64encode(value).decode("utf-8")
                        # Les types TEXT, VARCHAR, INTEGER, REAL, etc. restent strictement intacts
                    table_records.append(row_dict)

                data[table] = table_records

        return data

    def import_database_from_dict(self, tables_data: dict) -> None:
        """Restaure ou fusionne les tables de la base de données en conservant les données existantes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Désactivation temporaire des clés étrangères pour éviter les conflits d'ordre
            cursor.execute("PRAGMA foreign_keys = OFF;")

            for table, records in tables_data.items():
                if not records:
                    continue

                # Récupère les types de colonnes standard
                cursor.execute(f"PRAGMA table_info('{table}');")
                column_types = {row[1]: row[2].upper() for row in cursor.fetchall()}

                # Récupère les colonnes générées (hidden = 2 ou 3 dans table_xinfo) pour les exclure
                cursor.execute(f"PRAGMA table_xinfo('{table}');")
                generated_cols = {row[1] for row in cursor.fetchall() if row[6] in (2, 3)}

                # Sélectionne uniquement les colonnes valides (hors colonnes générées)
                columns = [col for col in column_types.keys() if col not in generated_cols]
                placeholders = ", ".join(["?"] * len(columns))
                cols_str = ", ".join([f'"{col}"' for col in columns])

                # Ignore les lignes déjà existantes
                insert_sql = f"INSERT OR IGNORE INTO {table} ({cols_str}) VALUES ({placeholders})"

                rows_to_insert = []
                for record in records:
                    row_values = []
                    for col in columns:
                        value = record.get(col)
                        col_type = column_types.get(col, "")

                        # Si la colonne est un BLOB et que la valeur est en Base64, on décode en binaire
                        if "BLOB" in col_type and isinstance(value, str):
                            try:
                                decoded_bytes = base64.b64decode(value)
                                row_values.append(sqlite3.Binary(decoded_bytes))
                            except Exception:
                                row_values.append(value)
                        else:
                            row_values.append(value)
                    rows_to_insert.append(tuple(row_values))

                if rows_to_insert:
                    cursor.executemany(insert_sql, rows_to_insert)

            # Réactivation des contraintes de clés étrangères
            cursor.execute("PRAGMA foreign_keys = ON;")
