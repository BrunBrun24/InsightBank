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
