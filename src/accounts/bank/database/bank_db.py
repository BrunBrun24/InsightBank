import sqlite3
from typing import Literal

import pandas as pd

from accounts.stock.database.stock_db import StockDB
from config import load_config

from ...shared.database_base import DatabaseBase


class BankDB(DatabaseBase):
    """Gère l'accès et la manipulation des données financières d'un compte bancaire."""

    def __init__(self, db_path: str) -> None:
        super().__init__(db_path)

        self._create_database()
        self.__verify_category_consistency()

    def add_bank_account(self, bank_account_name: str, currency: str) -> None:
        """Ajout d'un nouveau compte bancaire."""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Vérifier si le nom existe déjà
            cursor.execute("SELECT id FROM bank_accounts WHERE name = ?", (bank_account_name,))
            if cursor.fetchone():
                raise ValueError(f"Le compte '{bank_account_name}' existe déjà.")

            cursor.execute("INSERT INTO bank_accounts (name, currency) VALUES (?, ?)", (bank_account_name, currency))

    def add_operations(self, operations_df: pd.DataFrame) -> None:
        """Ajoute plusieurs opérations dans la BDD."""

        if operations_df.empty:
            return

        if "category" in operations_df.columns:
            cat_name = operations_df["category"].iloc[0]
            cat_id = self.__get_or_create_category_id(cat_name)
            operations_df["category_id"] = cat_id

            if "sub_category" in operations_df.columns:
                sub_name = operations_df["sub_category"].iloc[0]
                sub_id = self.__get_or_create_sub_category_id(cat_id, sub_name)
                operations_df["sub_category_id"] = sub_id

            cols_to_drop = ["category", "sub_category", "id"]
            operations_df = operations_df.drop(columns=[c for c in cols_to_drop if c in operations_df.columns])

        with self._get_connection() as conn:
            operations_df.to_sql(name="raw_data", con=conn, if_exists="append", index=False)

    def delete_bank_account(self, bank_account_id: str) -> None:
        """Ajout d'un nouveau compte bancaire."""

        with self._get_connection() as conn:
            conn.cursor().execute("DELETE FROM bank_accounts WHERE id = ?", (bank_account_id,))

    def delete_operation(self, bank_account_id: int, raw_data_id: int) -> None:
        """Supprime une opération d'un compte bancaire"""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM raw_data WHERE bank_account_id = ? AND id = ?",
                (
                    bank_account_id,
                    raw_data_id,
                ),
            )

    def update_bank_account_name(self, bank_account_id: int, new_name: str) -> None:
        """Met à jour le nom d'un compte bancaire"""

        with self._get_connection() as conn:
            conn.cursor().execute(
                "UPDATE bank_accounts SET name = ? WHERE id = ?",
                (new_name, bank_account_id),
            )

    def update_operation(self, bank_account_id: int, updated_data: dict) -> bool:
        """Mets à jour une opération d'un compte bancaire"""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE raw_data
                SET operation_date = ?, 
                    label = ?, 
                    amount = ?, 
                    short_label = ?, 
                    operation_type = ?, 
                    category_id = (SELECT id FROM categories WHERE name = ? AND bank_account_id = ?),
                    sub_category_id = (SELECT id FROM sub_categories WHERE name = ? 
                                       AND category_id = (SELECT id FROM categories WHERE name = ? AND bank_account_id = ?))
                WHERE id = ?
                """,
                (
                    updated_data["operation_date"],
                    updated_data["label"],
                    updated_data["amount"],
                    updated_data["short_label"],
                    updated_data["operation_type"],
                    updated_data["category"],
                    bank_account_id,
                    updated_data["sub_category"],
                    updated_data["category"],
                    bank_account_id,
                    updated_data["id"],
                ),
            )

            return True

    def update_operation_according_classification(
        self,
        id: int,
        category_name: str,
        sub_category_name: str,
    ) -> None:
        """Enregistre la liaison entre une opération brute et ses catégories."""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Récupération ou création des identifiants techniques (IDs)
            category_id = self.__get_or_create_category_id(category_name)
            sub_category_id = self.__get_or_create_sub_category_id(category_id, sub_category_name)

            cursor.execute(
                """
                UPDATE raw_data
                SET category_id = ?, sub_category_id = ?
                WHERE id = ?
                """,
                (
                    category_id,
                    sub_category_id,
                    id,
                ),
            )

    def get_operations_by_bank_account(self, bank_account_id: int) -> pd.DataFrame:
        """Retourne toutes les transactions liées à un compte bancaire."""

        query = """
            SELECT 
                r.operation_date AS operation_date,
                r.label,
                r.short_label,
                r.operation_type,
                COALESCE(c.name, 'Non catégorisé') AS category,
                COALESCE(s.name, 'Non catégorisé') AS sub_category,
                r.amount,
                r.id AS id
            FROM raw_data r
            LEFT JOIN categories c ON r.category_id = c.id
            LEFT JOIN sub_categories s ON r.sub_category_id = s.id
            WHERE r.bank_account_id = ?
            ORDER BY r.operation_date DESC
        """

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=(bank_account_id,))

    def get_all_bank_accounts(self) -> pd.DataFrame:
        """Retourne la table bank_accounts triée par nombre d'opérations décroissant."""

        query = """
            SELECT b.*, COUNT(r.id) as nb_operations
            FROM bank_accounts b
            LEFT JOIN raw_data r ON b.id = r.bank_account_id
            GROUP BY b.id
            ORDER BY nb_operations DESC
        """

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn)

    def get_bank_account_statistics(self, bank_account_id: int) -> dict:
        """Calcule les statistiques d'utilisation d'un compte bancaire."""

        stats = {"total": 0, "processed": 0, "remaining": 0, "categories": 0, "bank_account_amount": 0}

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Calcule le nombre total d'opérations et ceux qui sont déjà triés
            cursor.execute(
                "SELECT COUNT(*), COUNT(category_id) FROM raw_data WHERE bank_account_id = ?", (bank_account_id,)
            )

            res = cursor.fetchone()
            if res:
                stats["total"] = res[0]
                stats["processed"] = res[1]
                stats["remaining"] = stats["total"] - stats["processed"]

            # Nombre de catégories créées
            cursor.execute("SELECT COUNT(*) FROM categories")
            res_cat = cursor.fetchone()
            stats["categories"] = res_cat[0] if res_cat else 0

            # Somme d'argent sur le compte
            cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM raw_data WHERE bank_account_id = ?", (bank_account_id,)
            )
            res_sum = cursor.fetchone()
            stats["bank_account_amount"] = res_sum[0]

        return stats

    def get_bank_account_currency_symbol(self, bank_account_id: int) -> str | None:
        """Récupère la devise d'un compte bancaire spécifique."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT currency FROM bank_accounts WHERE id = ?"
            cursor.execute(query, (bank_account_id,))
            result = cursor.fetchone()[0]

        if result == "EUR":
            return "€"
        elif result == "USD":
            return "$"

    def get_all_bank_account_currencies(self) -> list[dict[str, int | str]]:
        """Récupère la liste des comptes bancaires avec leur ID et leur devise."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT id, name, currency FROM bank_accounts"
            cursor.execute(query)

            return [{"id": row[0], "name": row[1], "currency": row[2]} for row in cursor.fetchall()]

    def get_categories_hierarchy(self) -> tuple[dict, dict]:
        """Récupère les catégories et sous-catégories pour les revenus et les dépenses."""

        query = """
            SELECT c.name, sc.name, c.type
            FROM categories c
            LEFT JOIN sub_categories sc ON c.id = sc.category_id
            ORDER BY c.name, sc.name
        """

        incomes = {}
        expenses = {}
        mapping = {"income": incomes, "expense": expenses}

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)

            for cat, sub, ty in cursor.fetchall():
                target_dict = mapping.get(ty)

                if cat not in target_dict:
                    target_dict[cat] = []

                if sub:
                    target_dict[cat].append(sub)

        return incomes, expenses

    def get_account_operations(self, account_id: int) -> pd.DataFrame:
        """Récupère les opérations d'un compte spécifique converties dans la devise cible."""

        query = """
            SELECT 
                r.id AS raw_id,
                r.bank_account_id,
                b.currency AS account_currency,
                c.name AS category_name,
                sc.name AS sub_category_name,
                r.operation_date,
                r.short_label,
                r.operation_type,
                r.label,
                r.amount
            FROM raw_data r
            JOIN bank_accounts b ON r.bank_account_id = b.id
            LEFT JOIN categories c ON r.category_id = c.id
            LEFT JOIN sub_categories sc ON r.sub_category_id = sc.id
            WHERE r.bank_account_id = ?
            ORDER BY r.operation_date ASC
        """

        with self._get_connection() as conn:
            df_ops = pd.read_sql_query(query, conn, params=(account_id,))

        if df_ops.empty:
            return df_ops

        return df_ops

    def get_categories_structure(self) -> pd.DataFrame:
        """Récupère l'ensemble des catégories principales et leurs sous-catégories associées."""
        query = """
            SELECT 
                c.name AS main_category,
                sc.name AS sub_category
            FROM categories c
            LEFT JOIN sub_categories sc ON sc.category_id = c.id
            ORDER BY main_category, sub_category
        """

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn)

    def get_unprocessed_raw_operations(self, bank_account_id: int) -> list[dict[str:str]]:
        """Récupère les transactions brutes non traitées"""

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, operation_date, short_label, operation_type, label, amount
                FROM raw_data WHERE bank_account_id = ? AND category_id IS NULL
                ORDER BY operation_date ASC, id ASC
                """,
                (bank_account_id,),
            )

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_categorized_operations_df(self, bank_account_id: int) -> pd.DataFrame:
        """Récupère les opérations catégorisées."""

        with self._get_connection() as conn:
            query = """
                SELECT 
                    r.id, 
                    c.name AS category, 
                    sc.name AS sub_category,
                    r.operation_date, 
                    r.short_label, 
                    r.operation_type,
                    r.label, 
                    r.amount
                FROM raw_data r
                JOIN categories c ON r.category_id = c.id
                JOIN sub_categories sc ON r.sub_category_id = sc.id
                WHERE bank_account_id = ?
                ORDER BY r.operation_date ASC, r.id ASC
            """

            df = pd.read_sql_query(query, conn, params=(bank_account_id,))

        df["operation_date"] = pd.to_datetime(df["operation_date"])

        return df

    def get_category_lists(self) -> tuple[list[str], list[str]]:
        """Récupère les différentes catégories pour les revenus et les dépenses"""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # On récupère la liste des revenues
            cursor.execute("SELECT c.name FROM categories c WHERE type = 'income'")
            incomes_list = [row[0] for row in cursor.fetchall()]

            # On récupère la liste des dépenses
            cursor.execute("SELECT c.name FROM categories c WHERE type = 'expense'")
            expenses_list = [row[0] for row in cursor.fetchall()]

        return incomes_list, expenses_list

    def get_categorized_operations_by_year(
        self, bank_accounts: list[dict] | int, stock_db: StockDB, is_heritage: bool
    ) -> dict[int, dict[str, pd.DataFrame]]:
        """Regroupe les opérations catégorisées par année pour une liste de comptes."""
        incomes_list, expenses_list = self.get_category_lists()
        target_currency = load_config()["currency"]

        if is_heritage:
            all_operations_dfs = []

            # Extraction et conversion compte par compte
            for account in bank_accounts:
                acc_id = account["id"]
                acc_currency = account["currency"]

                # Extraction des opérations du compte
                df_account = self.get_categorized_operations_df(acc_id).reset_index(drop=True)
                if df_account.empty:
                    continue

                df_account["amount"] = df_account["amount"].abs()

                # Conversion FX si la devise est différente et stock_db fourni
                if acc_currency != target_currency and stock_db is not None:
                    rates = stock_db.get_currency_conversion_rates(acc_currency, target_currency)

                    if not rates.empty:
                        rates_df = rates.reset_index()
                        rates_df.columns = ["operation_date", "rate"]
                        rates_df = rates_df.sort_values("operation_date")

                        df_account = df_account.sort_values("operation_date")
                        df_account = pd.merge_asof(
                            df_account,
                            rates_df,
                            on="operation_date",
                            direction="nearest",
                        )
                        df_account["rate"] = df_account["rate"].fillna(1.0)
                        df_account["amount"] = (df_account["amount"] * df_account["rate"]).round(2)
                        df_account = df_account.drop(columns=["rate"])

                all_operations_dfs.append(df_account)

            if not all_operations_dfs:
                return {}

        else:
            all_operations_dfs = [self.get_categorized_operations_df(bank_accounts).reset_index(drop=True)]

        # Fusion globale de toutes les opérations
        operations = pd.concat(all_operations_dfs, ignore_index=True)
        operations["year"] = operations["operation_date"].dt.year

        # Répartition par année
        years_dict = {}
        for year, year_operations_df in operations.groupby("year"):
            incomes_df = year_operations_df[year_operations_df["category"].isin(incomes_list)]
            expenses_df = year_operations_df[year_operations_df["category"].isin(expenses_list)]

            years_dict[int(year)] = {
                "all": year_operations_df,
                "incomes": incomes_df,
                "expenses": expenses_df,
            }

        return years_dict

    def get_category_by_exact_label(
        self,
        bank_account_id: int,
        label: str,
        short_label: str,
        operation_type: str,
    ) -> tuple[str | None, str | None]:
        """Recherche une opération strictement identique sur le libellé, le libellé court et le type d'opération"""

        query = """
            SELECT 
                c.name AS category_name,
                sc.name AS sub_category_name
            FROM raw_data r
            JOIN categories c ON r.category_id = c.id
            JOIN sub_categories sc ON r.sub_category_id = sc.id
            WHERE r.bank_account_id = ? 
              AND r.label = ? 
              AND r.short_label = ? 
              AND r.operation_type = ? 
              AND r.category_id IS NOT NULL
            LIMIT 1
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (bank_account_id, label, short_label, operation_type))
            row = cursor.fetchone()

            if row:
                return row[0], row[1]

            return None, None

    def __get_or_create_category_id(
        self, category_name: str, flow_type: Literal["income", "expense"] = "income", cursor=None
    ) -> int:
        """Récupère l'ID d'une catégorie ou la crée si elle n'existe pas pour ce compte."""

        if cursor is None:
            with self._get_connection() as conn:
                return self.__get_or_create_category_id(category_name, flow_type, conn.cursor())

        # Tentative de récupération
        cursor.execute(
            "SELECT id FROM categories WHERE name = ?",
            (category_name,),
        )
        result = cursor.fetchone()

        if result:
            return result[0]

        # Création si inexistante
        cursor.execute(
            "INSERT INTO categories (name, type) VALUES (?, ?)",
            (
                category_name,
                flow_type,
            ),
        )
        return cursor.lastrowid

    def __get_or_create_sub_category_id(self, category_id: int, sub_category_name: str, cursor=None) -> int:
        """Récupère l'ID d'une sous-catégorie ou la crée pour une catégorie parente donnée."""

        if cursor is None:
            with self._get_connection() as conn:
                return self.__get_or_create_sub_category_id(category_id, sub_category_name, cursor=conn.cursor())

        cursor.execute(
            """
            SELECT id FROM sub_categories 
            WHERE category_id = ? AND name = ?
            """,
            (category_id, sub_category_name),
        )
        result = cursor.fetchone()

        if result:
            sub_category_id = result[0]
        else:
            # Création liée à la catégorie parente
            cursor.execute(
                """
                INSERT INTO sub_categories (category_id, name) 
                VALUES (?, ?)
                """,
                (category_id, sub_category_name),
            )
            sub_category_id = cursor.lastrowid

        return sub_category_id

    def _create_database(self) -> None:
        """Crée le schéma SQLite optimisé avec index et triggers automatiques"""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS bank_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    currency CHAR(3) NOT NULL,

                    UNIQUE(name)
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                    
                    UNIQUE(name)
                );

                CREATE TABLE IF NOT EXISTS sub_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER NOT NULL,
                    name TEXT NOT NULL,

                    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
                    UNIQUE(category_id, name)
                );

                CREATE TABLE IF NOT EXISTS raw_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bank_account_id INTEGER NOT NULL,
                    category_id INTEGER,
                    sub_category_id INTEGER,
                    operation_date DATE NOT NULL,
                    short_label TEXT,
                    operation_type TEXT,
                    label TEXT NOT NULL,
                    amount REAL NOT NULL,
                    
                    FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE,
                    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
                    FOREIGN KEY (sub_category_id) REFERENCES sub_categories(id) ON DELETE SET NULL
                );
                
                CREATE TRIGGER IF NOT EXISTS force_category_null_on_sub_null
                AFTER UPDATE OF sub_category_id ON raw_data
                FOR EACH ROW
                WHEN NEW.sub_category_id IS NULL
                BEGIN
                    UPDATE raw_data
                    SET category_id = NULL
                    WHERE id = NEW.id;
                END;
            """)

    def __verify_category_consistency(self) -> None:
        """Vérifie la conformité des catégories en BDD de manière atomique."""

        # On charge la structure cible depuis le JSON
        full_config = load_config()["database"]
        target_structure = {
            "income": full_config["incomes"]["categories_subcategories"],
            "expense": full_config["expenses"]["categories_subcategories"],
        }

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for flow_type, categories_map in target_structure.items():
                # 1. Nettoyage
                allowed_cats = categories_map.keys()

                # Supprimer catégories obsolètes
                cursor.execute("SELECT id, name FROM categories WHERE type = ?", (flow_type,))
                for cat_id, cat_name in cursor.fetchall():
                    if cat_name not in allowed_cats:
                        cursor.execute("DELETE FROM categories WHERE id = ?", (cat_id,))

                # Supprimer sous-catégories obsolètes
                cursor.execute(
                    """
                    SELECT sc.id, sc.name, c.name 
                    FROM sub_categories sc
                    JOIN categories c ON sc.category_id = c.id
                    WHERE c.type = ?
                """,
                    (flow_type,),
                )
                for sub_id, sub_name, parent_name in cursor.fetchall():
                    is_valid = parent_name in categories_map and sub_name in categories_map[parent_name]
                    if not is_valid:
                        cursor.execute("DELETE FROM sub_categories WHERE id = ?", (sub_id,))

                # 2. Insertion / Mise à jour
                for cat_name, sub_list in categories_map.items():
                    cat_id = self.__get_or_create_category_id(cat_name, flow_type, cursor)

                    for sub_name in sub_list:
                        self.__get_or_create_sub_category_id(cat_id, sub_name, cursor)
