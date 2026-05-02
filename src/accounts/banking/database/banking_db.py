import os
import shutil
import sqlite3

import pandas as pd

from config import load_config

from ...shared.database_base import DatabaseBase


class BankingDB(DatabaseBase):
    """Gère l'accès et la manipulation des données financières d'un compte bancaire."""

    def __init__(self, db_path: str) -> None:
        super().__init__(db_path)

        self._create_database()
        self.__verify_category_consistency()

    def add_account(self, account_name: str) -> None:
        """Ajout d'un nouveau compte bancaire."""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Vérifier si le nom existe déjà
            cursor.execute("SELECT id FROM account WHERE name = ?", (account_name,))
            if cursor.fetchone():
                raise ValueError(f"Le compte '{account_name}' existe déjà.")

            cursor.execute("INSERT INTO account (name) VALUES (?)", (account_name,))

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

    def delete_account(self, account_id: str) -> None:
        """Ajout d'un nouveau compte bancaire."""

        with self._get_connection() as conn:
            conn.cursor().execute("DELETE FROM account WHERE id = ?", (account_id,))

    def delete_operation(self, account_id: int, raw_data_id: int) -> None:
        """Supprime une opération d'un compte bancaire"""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM raw_data WHERE account_id = ? AND id = ?",
                (
                    account_id,
                    raw_data_id,
                ),
            )

    def update_account_name(self, account_id: int, new_name: str) -> None:
        """Met à jour le nom d'un compte bancaire"""

        with self._get_connection() as conn:
            conn.cursor().execute(
                "UPDATE account SET name = ? WHERE id = ?",
                (new_name, account_id),
            )

    def update_operation(self, account_id: int, updated_data: dict) -> bool:
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
                    category_id = (SELECT id FROM categories WHERE name = ? AND account_id = ?),
                    sub_category_id = (SELECT id FROM sub_categories WHERE name = ? 
                                       AND category_id = (SELECT id FROM categories WHERE name = ? AND account_id = ?))
                WHERE id = ?
                """,
                (
                    updated_data["operation_date"],
                    updated_data["label"],
                    updated_data["amount"],
                    updated_data["short_label"],
                    updated_data["operation_type"],
                    updated_data["category"],
                    account_id,
                    updated_data["sub_category"],
                    updated_data["category"],
                    account_id,
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

    def get_operations_by_account(self, account_id: int) -> pd.DataFrame:
        """Retourne toutes les transactions liées à compte bancaire"""

        query = """
            SELECT 
                r.operation_date AS operation_date,
                r.label,
                r.short_label,
                r.operation_type,
                c.name AS category,
                s.name AS sub_category,
                r.amount,
                r.id AS id
            FROM raw_data r
            JOIN categories c ON r.category_id = c.id
            JOIN sub_categories s ON r.sub_category_id = s.id
            WHERE r.account_id = ?
            ORDER BY r.operation_date DESC
        """

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=(account_id,))

    def get_all_accounts(self) -> pd.DataFrame:
        """Retourne la table account triée par nombre d'opérations décroissant."""

        query = """
            SELECT b.*, COUNT(r.id) as nb_operations
            FROM account b
            LEFT JOIN raw_data r ON b.id = r.account_id
            GROUP BY b.id
            ORDER BY nb_operations DESC
        """

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn)

    def get_account_statistics(self, account_id: int) -> dict:
        """Calcule les statistiques d'utilisation d'un compte bancaire."""

        stats = {"total": 0, "processed": 0, "remaining": 0, "categories": 0, "account_amount": 0}

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Calcule le nombre total d'opérations et ceux qui sont déjà triés
            cursor.execute("SELECT COUNT(*), COUNT(category_id) FROM raw_data WHERE account_id = ?", (account_id,))

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
            cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM raw_data WHERE account_id = ?", (account_id,))
            res_sum = cursor.fetchone()
            stats["account_amount"] = res_sum[0]

        return stats

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

    def get_all_operations(self, table_name: str) -> pd.DataFrame:
        """Récupère toutes les opérations."""

        queries = {
            "categorized_operations": """
                SELECT 
                    co.id AS entry_id,
                    c.name AS category_name,
                    sc.name AS sub_category_name,
                    r.operation_date,
                    r.short_label,
                    r.operation_type,
                    r.label,
                    r.amount,
                    r.id AS raw_id
                FROM categorized_operations co
                JOIN categories c ON co.category_id = c.id
                JOIN sub_categories sc ON co.sub_category_id = sc.id
                JOIN raw_data r ON co.raw_data_id = r.id
            """,
            "sub_categories": """
                SELECT 
                    sc.id,
                    c.name AS parent_category,
                    sc.name AS sub_category_name
                FROM sub_categories sc
                JOIN categories c ON sc.category_id = c.id
            """,
        }

        query = queries.get(table_name, f'SELECT * FROM "{table_name}"')

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn)

    def get_unprocessed_raw_operations(self, account_id: int) -> list:
        """Récupère les transactions brutes non traitées"""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, operation_date, short_label, operation_type, label, amount
                FROM raw_data WHERE account_id = ? AND category_id IS NULL
                ORDER BY operation_date ASC, id ASC
                """,
                (account_id,),
            )

            rows = cursor.fetchall()
            return rows

    def get_categorized_operations_df(self, account_id: int) -> pd.DataFrame:
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
                WHERE account_id = ?
                ORDER BY r.operation_date ASC, r.id ASC
            """

            df = pd.read_sql_query(query, conn, params=(account_id,))

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

    def get_categorized_operations_by_year(self, account_id: int) -> dict[str, pd.DataFrame]:
        """Regroupe les opérations catégorisées par année et par type."""

        # 1. On récupère les différentes catégories pour les revenus et les dépenses
        incomes_list, expenses_list = self.get_category_lists()

        # 2. On récupère toutes les opérations
        operations = self.get_categorized_operations_df(account_id).reset_index(drop=True)
        operations["year"] = operations["operation_date"].dt.year
        operations["amount"] = operations["amount"].abs()

        # 3. On traite les données
        years_dict = {}
        for year, year_operations_df in operations.groupby("year"):
            incomes_df = year_operations_df[year_operations_df["category"].isin(incomes_list)]
            expenses_df = year_operations_df[year_operations_df["category"].isin(expenses_list)]

            years_dict[int(year)] = {"all": year_operations_df, "incomes": incomes_df, "expenses": expenses_df}

        return years_dict

    def __get_or_create_category_id(self, category_name: str, flow_type: str = "income", cursor=None) -> int:
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
                CREATE TABLE IF NOT EXISTS account (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,

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
                    account_id INTEGER NOT NULL,
                    category_id INTEGER,
                    sub_category_id INTEGER,
                    operation_date DATE NOT NULL,
                    short_label TEXT,
                    operation_type TEXT,
                    label TEXT NOT NULL,
                    amount REAL NOT NULL,
                    
                    FOREIGN KEY (account_id) REFERENCES account(id) ON DELETE CASCADE,
                    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
                    FOREIGN KEY (sub_category_id) REFERENCES sub_categories(id) ON DELETE SET NULL
                );
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

    @staticmethod  # TODO faire une grosse BDD avec tous les comptes
    def merge_account_databases(source_db_path: str, target_db_path: str, output_path: str) -> None:
        """
        Fusionne deux bases de données bancaires en préservant l'intégrité référentielle.

        Cette fonction crée une copie de la source, y attache la base cible,
        puis transfère les données en utilisant une table de correspondance temporaire
        pour réassocier correctement les nouveaux IDs générés.

        Args:
            - source_db_path (str) : Chemin vers la première base de données (base).
            - target_db_path (str) : Chemin vers la seconde base de données à intégrer.
            - output_path (str) : Chemin du fichier de destination final.
        """

        try:
            # Préparation du dossier de destination
            directory = os.path.dirname(output_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            # Copie de la base source vers la destination
            shutil.copy2(source_db_path, output_path)

            with sqlite3.connect(output_path) as conn:
                cursor = conn.cursor()

                # Attacher la base de données cible
                cursor.execute(f"ATTACH DATABASE '{target_db_path}' AS db_to_merge")

                # 1. Fusion des catégories et sous-catégories (sans doublons)
                cursor.execute("INSERT OR IGNORE INTO categories (name) SELECT name FROM db_to_merge.categories")

                cursor.execute("""
                    INSERT OR IGNORE INTO sub_categories (category_id, name) 
                    SELECT (SELECT id FROM categories WHERE name = c.name), sc.name 
                    FROM db_to_merge.sub_categories sc
                    JOIN db_to_merge.categories c ON sc.category_id = c.id
                """)

                # 2. Création d'une table de correspondance temporaire pour les IDs de raw_data
                # Cela permet de savoir quel ID de la base cible correspond à quel ID dans la nouvelle base.
                cursor.execute("CREATE TEMP TABLE id_mapping (old_id INTEGER, new_id INTEGER)")

                # 3. Insertion des données brutes et remplissage du mapping
                # On récupère les données de la base cible
                cursor.execute(
                    "SELECT id, operation_date, short_label, operation_type, label, amount FROM db_to_merge.raw_data"
                )
                rows_to_merge = cursor.fetchall()

                for row in rows_to_merge:
                    old_id = row[0]
                    cursor.execute(
                        """
                        INSERT INTO raw_data (operation_date, short_label, operation_type, label, amount)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        row[1:],
                    )
                    # On mémorise le lien (old -> new)
                    cursor.execute(
                        "INSERT INTO id_mapping VALUES (?, ?)",
                        (old_id, cursor.lastrowid),
                    )

                # 4. Fusion des opérations catégorisées en utilisant le mapping
                cursor.execute("""
                    INSERT INTO categorized_operations (category_id, sub_category_id, raw_data_id)
                    SELECT 
                        (SELECT id FROM categories WHERE name = c_merged.name),
                        (SELECT id FROM sub_categories WHERE name = sc_merged.name 
                            AND category_id = (SELECT id FROM categories WHERE name = c_merged.name)),
                        m.new_id
                    FROM db_to_merge.categorized_operations co_merged
                    JOIN db_to_merge.categories c_merged ON co_merged.category_id = c_merged.id
                    JOIN db_to_merge.sub_categories sc_merged ON co_merged.sub_category_id = sc_merged.id
                    JOIN id_mapping m ON co_merged.raw_data_id = m.old_id
                """)

                cursor.execute("DETACH DATABASE db_to_merge")

        except Exception as error:
            raise RuntimeError(f"Échec du processus de fusion : {str(error)}")
