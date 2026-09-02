from datetime import datetime, timedelta
from tkinter import messagebox

import pandas as pd
import yfinance as yf

from accounts.stock.importers.fetch_stock import fetch_stock_data
from config import load_config, update_config_last_login

from ...shared.database_base import DatabaseBase


class StockDB(DatabaseBase):
    """Gère l'accès et la manipulation des données financières d'un portefeuille boursier."""

    def __init__(self, db_path: str) -> None:
        super().__init__(db_path)

        self._create_database()
        self.__symbols = [
            "EURUSD=X",  # Euro / US Dollar
            "EURCAD=X",  # Euro / Dollar Canadien
            "EURMXN=X",  # Euro / Peso Mexicain
            "EURBRL=X",  # Euro / Real Brésilien
            "EURGBP=X",  # Euro / Livre Sterling
            "GBPUSD=X",  # Livre Sterling / US Dollar
            "EURCHF=X",  # Euro / Franc Suisse
            "EURSEK=X",  # Euro / Couronne Suédoise
            "EURNOK=X",  # Euro / Couronne Norvégienne
            "EURDKK=X",  # Euro / Couronne Danoise
            "EURJPY=X",  # Euro / Yen Japonais
            "EURHKD=X",  # Euro / Dollar de Hong Kong
            "EURCNY=X",  # Euro / Yuan Chinois
            "EURINR=X",  # Euro / Roupie Indienne
            "EURAUD=X",  # Euro / Dollar Australien
            "AUDUSD=X",  # Dollar Australien / US Dollar
            "EURNZD=X",  # Euro / Dollar Néo-Zélandais
            "NZDUSD=X",  # Dollar Néo-Zélandais / US Dollar
            "^GSPC",     # S&P 500
            "^FCHI",     # CAC 40
            "^IXIC",     # NASDAQ
            "URTH",      # MSCI World
        ]

        # Ajoute les données de conversion pour chaque symbol
        tickers = self.get_tickers()
        for symb in self.__symbols:
            if symb not in tickers:
                df = pd.DataFrame(columns=["symbol"], data=[symb])
                extracted_data, isin_ticker_add = fetch_stock_data(self, df)
                tickers_to_add = [isin_ticker["ticker"] for isin_ticker in isin_ticker_add]
                self.add_data_tickers(tickers_to_add, extracted_data)

        if self.__should_update_stock():
            self.__stock_update()

        update_config_last_login()

    def get_all_portfolios(self) -> pd.DataFrame:
        query = """
            SELECT 
                p.id, 
                p.name, 
                p.currency, 
                p.amount,
                COUNT(pt.id) AS transaction_count
            FROM portfolio p
            LEFT JOIN portfolio_transaction pt ON p.id = pt.portfolio_id
            GROUP BY p.id, p.name, p.currency, p.amount
            ORDER BY p.id DESC;
        """
        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn)

    def get_portfolio_currency_symbol(self, portfolio_id: int) -> str:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT currency FROM portfolio WHERE id = ?", (portfolio_id,))
            result = cursor.fetchone()[0]

        if result == "EUR":
            return "€"
        elif result == "USD":
            return "$"

    def get_portfolio_currency(self, portfolio_id: int) -> str:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT currency FROM portfolio WHERE id = ?", (portfolio_id,))
            row = cursor.fetchone()
            return row[0]

    def get_portfolio_name(self, portfolio_id: int) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM portfolio WHERE id = ?", (portfolio_id,))
            row = cursor.fetchone()
            return row[0]

    def get_portfolio_ticker_ids(self, portfolio_id: int) -> dict[str, int]:
        query = "SELECT ticker, id FROM portfolio_ticker WHERE portfolio_id = ?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (portfolio_id,))
            return dict(cursor.fetchall())

    def get_company_name(self, ticker: str) -> str | None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT company_name FROM stock WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_transactions_by_stock_account(self, portfolio_id: int) -> pd.DataFrame:
        query = """
            SELECT 
                pt.id,
                st.ticker,
                st.company_name AS name,
                pt.type,
                pt.date,
                pt.amount,
                pt.fee,
                pt.price,
                pt.shares,
                p.currency AS account_currency
            FROM portfolio_transaction pt
            JOIN portfolio p ON pt.portfolio_id = p.id
            LEFT JOIN portfolio_ticker pk ON pt.portfolio_ticker_id = pk.id
            LEFT JOIN stock st ON pk.ticker = st.ticker
            WHERE pt.portfolio_id = ?
            ORDER BY pt.date DESC
        """
        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=(portfolio_id,))

    def get_all_transactions_converted(self, target_currency: str) -> pd.DataFrame:
        """
        Récupère l'ensemble des transactions et convertit leurs montants dans la
        devise cible à la date exacte de chaque transaction via l'historique FX.
        """
        # Récupération de l'ensemble des transactions avec leur devise source
        query_tx = """
                SELECT 
                pt.id,
                pt.portfolio_id,
                p.currency AS currency,
                pt.portfolio_ticker_id,
                s.ticker AS ticker,
                s.company_name AS name,
                pt.type,
                pt.date,
                pt.shares,
                pt.original_amount,
                pt.original_price,
                pt.original_fee,
                pt.amount,
                pt.price,
                pt.fee
            FROM portfolio_transaction pt
            JOIN portfolio p ON pt.portfolio_id = p.id
            LEFT JOIN portfolio_ticker pot ON pt.portfolio_ticker_id = pot.id
            LEFT JOIN stock s ON pot.ticker = s.ticker
            ORDER BY pt.date ASC, pt.id ASC
        """
        with self._get_connection() as conn:
            df = pd.read_sql_query(query_tx, conn)

        if df.empty:
            return df

        # Identifie toutes les devises sources distinctes (excluant la devise cible)
        source_currencies = [c for c in df["currency"].unique() if c != target_currency]

        if not source_currencies:
            df["fx_rate"] = 1.0
            return df

        # Construction des tickers FX nécessaires
        fx_tickers = []
        for curr in source_currencies:
            fx_tickers.extend([f"{curr}{target_currency}=X", f"{target_currency}{curr}=X"])

        placeholders = ",".join(["?"] * len(fx_tickers))
        query_fx = f"""
            SELECT date, ticker, close_price 
            FROM stock_price 
            WHERE ticker IN ({placeholders}) 
            ORDER BY date ASC
        """

        with self._get_connection() as conn:
            fx_df = pd.read_sql_query(query_fx, conn, params=fx_tickers)

        # Traitement des cours par paire de devises
        rates_list = []
        for curr in source_currencies:
            direct_ticker = f"{curr}{target_currency}=X"
            inverse_ticker = f"{target_currency}{curr}=X"

            sub_fx = fx_df[fx_df["ticker"].isin([direct_ticker, inverse_ticker])].copy()
            if sub_fx.empty:
                continue

            # Séparation direct / inverse
            direct = sub_fx[sub_fx["ticker"] == direct_ticker][["date", "close_price"]].rename(
                columns={"close_price": "fx_rate"}
            )
            if not direct.empty:
                curr_rates = direct
            else:
                inverse = sub_fx[sub_fx["ticker"] == inverse_ticker][["date", "close_price"]]
                inverse["fx_rate"] = 1.0 / inverse["close_price"]
                curr_rates = inverse[["date", "fx_rate"]]

            curr_rates["currency"] = curr
            rates_list.append(curr_rates)

        if rates_list:
            all_fx_rates = pd.concat(rates_list, ignore_index=True)
        else:
            all_fx_rates = pd.DataFrame(columns=["date", "fx_rate", "currency"])

        # Conversion et alignement temporel via merge_asof (par devise)
        df["date"] = pd.to_datetime(df["date"])
        all_fx_rates["date"] = pd.to_datetime(all_fx_rates["date"])

        df = df.sort_values("date")
        all_fx_rates = all_fx_rates.sort_values("date")

        df = pd.merge_asof(
            df,
            all_fx_rates,
            on="date",
            by="currency",
            direction="backward",
        )
        df["fx_rate"] = df["fx_rate"].fillna(1.0)

        # Calcul des montants convertis
        df["amount"] = (df["amount"] * df["fx_rate"]).round(2)
        df["price"] = (df["price"] * df["fx_rate"]).round(2)
        df["fee"] = (df["fee"] * df["fx_rate"]).round(2)

        df["date"] = df["date"].dt.strftime("%Y-%m-%d")

        return df

    def get_transaction_by_id(self, transaction_id: int) -> dict | None:
        query = """
            SELECT pt.*, pt_tick.ticker
            FROM portfolio_transaction pt
            LEFT JOIN portfolio_ticker pt_tick ON pt.portfolio_ticker_id = pt_tick.id
            WHERE pt.id = ?
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (transaction_id,))
            row = cursor.fetchone()

            if row:
                columns = [column[0] for column in cursor.description]
                return dict(zip(columns, row))

        return None

    def get_currency(self, ticker: str) -> str:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT currency FROM stock WHERE ticker = ?", (ticker,))
            res = cursor.fetchone()
            return res[0]

    def get_currency_conversion_rates(self, source_currency: str, target_currency: str) -> pd.Series:
        """Calcule la série temporelle du taux de conversion (multiplicateur)."""
        # Même devise : multiplicateur neutre 1.0
        if source_currency == target_currency:
            query = "SELECT DISTINCT date FROM stock_price ORDER BY date ASC"
            with self._get_connection() as conn:
                df = pd.read_sql_query(query, conn)
            if df.empty:
                return pd.Series(dtype=float)
            df["date"] = pd.to_datetime(df["date"])
            return pd.Series(1.0, index=df["date"])

        # Format du ticker Yahoo Finance : Ex "EURUSD=X" donne le prix de 1 EUR en USD
        fx_ticker = f"{source_currency}{target_currency}=X"
        is_inverse = False

        query = """
            SELECT date, close_price 
            FROM stock_price 
            WHERE ticker = ? 
            ORDER BY date ASC
        """
        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=(fx_ticker,))

        # Si le ticker direct n'existe pas, on tente la paire inverse (ex: "USDEUR=X")
        if df.empty:
            fx_ticker_reverse = f"{target_currency}{source_currency}=X"
            with self._get_connection() as conn:
                df = pd.read_sql_query(query, conn, params=(fx_ticker_reverse,))
            is_inverse = True

        if df.empty:
            return pd.Series(dtype=float)

        df["date"] = pd.to_datetime(df["date"])
        series = df.set_index("date")["close_price"].ffill()

        # Si on a utilisé le ticker inverse, le taux multiplicateur est 1 / prix
        if is_inverse:
            return 1.0 / series

        return series

    def get_tickers_prices(
        self, portfolio_id: int | None, tickers: list[str], first_date: str, target_currency: str | None = None
    ) -> pd.DataFrame:
        if not tickers:
            return pd.DataFrame()

        placeholders = ",".join(["?"] * len(tickers))

        if portfolio_id is not None:
            query = f"""
                SELECT 
                    sp.date,
                    sp.ticker,
                    sp.close_price,
                    s.currency AS stock_currency,
                    p.currency AS target_currency,
                    fx.close_price AS fx_rate
                FROM stock_price sp
                JOIN stock s ON sp.ticker = s.ticker
                JOIN portfolio p ON p.id = ?
                LEFT JOIN stock_price fx 
                       ON fx.ticker = p.currency || s.currency || '=X' 
                      AND fx.date = sp.date
                WHERE sp.ticker IN ({placeholders}) 
                  AND sp.date >= ?
                ORDER BY sp.ticker ASC, sp.date ASC;
            """
            params = [portfolio_id] + list(tickers) + [first_date]
        else:
            # Retourne tous les tickers de la bdd
            query = f"""
                SELECT 
                    sp.date,
                    sp.ticker,
                    sp.close_price,
                    s.currency AS stock_currency,
                    ? AS target_currency,
                    fx.close_price AS fx_rate
                FROM stock_price sp
                JOIN stock s ON sp.ticker = s.ticker
                LEFT JOIN stock_price fx 
                       ON fx.ticker = ? || s.currency || '=X' 
                      AND fx.date = sp.date
                WHERE sp.ticker IN ({placeholders}) 
                  AND sp.date >= ?
                ORDER BY sp.ticker ASC, sp.date ASC;
            """
            params = [target_currency, target_currency] + list(tickers) + [first_date]

        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        if df.empty:
            return pd.DataFrame()

        # Initialisation de la colonne de conversion
        df["converted_price"] = df["close_price"].astype(float)

        # Masque pour identifier les lignes nécessitant une conversion de devise
        mask = (df["stock_currency"] != df["target_currency"]) & df["fx_rate"].notna()

        # Application de la conversion uniquement si le masque sélectionne au moins une ligne
        if mask.any():
            df.loc[mask, "converted_price"] = df.loc[mask, "close_price"] / df.loc[mask, "fx_rate"]

        df["date"] = pd.to_datetime(df["date"])
        df_pivoted = df.pivot(index="date", columns="ticker", values="converted_price")

        return df_pivoted.ffill()

    def get_stock_splits(self, tickers: list[str], first_date: str) -> pd.DataFrame:
        """Récupère l'historique des splits pour une liste de tickers à partir d'une date donnée."""
        if not tickers:
            return pd.DataFrame()

        placeholders = ",".join(["?"] * len(tickers))
        query = f"""
            SELECT 
                ticker,
                date,
                ratio
            FROM stock_split
            WHERE ticker IN ({placeholders}) AND date >= ?
            ORDER BY date ASC;
        """

        params = list(tickers) + [first_date]

        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def get_rate(self, date: str, ticker: str) -> float | None:
        """Récupère le prix de clôture à la date donnée, ou la dernière valeur connue antérieure."""

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT close_price 
                FROM stock_price 
                WHERE ticker = ? AND date <= ? 
                ORDER BY date DESC 
                LIMIT 1
                """,
                (ticker, date),
            )
            res = cursor.fetchone()
            return res[0] if res else None

    def get_latest_fx_rate(
        self,
        source_currency: str,
        target_currency: str,
    ) -> float | None:
        """Récupère le tout dernier taux de change disponible entre deux devises."""
        if source_currency == target_currency:
            return 1.0

        direct_ticker = f"{source_currency}{target_currency}=X"
        inverse_ticker = f"{target_currency}{source_currency}=X"

        # Recherche du dernier cours pour le ticker direct
        direct_rate = self.__get_latest_price_by_ticker(direct_ticker)
        if direct_rate is not None:
            return float(direct_rate)

        # Recherche du dernier cours pour le ticker inverse (1 / taux)
        inverse_rate = self.__get_latest_price_by_ticker(inverse_ticker)
        if inverse_rate is not None and inverse_rate != 0:
            return float(1.0 / inverse_rate)

        return None

    def __get_latest_price_by_ticker(self, ticker: str) -> float | None:
        """Exécute la requête SQL pour récupérer la valeur la plus récente d'un ticker."""
        query = """
            SELECT close_price 
            FROM stock_price 
            WHERE ticker = ? 
            ORDER BY date DESC 
            LIMIT 1
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (ticker,))
            res = cursor.fetchone()
            return res[0] if res else None

    def __get_last_date(self) -> str | None:
        """Retourne la date la plus récente présente dans la table stock_price."""
        query = "SELECT date FROM stock_price ORDER BY date DESC LIMIT 1"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            return row[0] if row else None

    def get_tickers(self) -> list[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker FROM stock")
            rows = cursor.fetchall()
            return [row[0] for row in rows]

    def get_stock_price_at_date(self, ticker: str, date_str: str) -> float | None:
        query = """
            SELECT close_price 
            FROM stock_price 
            WHERE ticker = ? AND date <= ?
            ORDER BY date DESC 
            LIMIT 1
        """

        result = self._db.execute_query(query, (ticker, date_str), fetchone=True)

        if result:
            return float(result[0])
        return None

    def add_data_tickers(self, tickers: list[str], extracted_data: dict[str, list[tuple]]) -> None:
        tickers_to_add = set(tickers) - set(self.get_tickers())
        if not tickers_to_add:
            return

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Table stock
            query_stock = """
                INSERT OR REPLACE INTO stock (ticker, isin, company_name, currency, country)
                VALUES (?, ?, ?, ?, ?);
            """
            cursor.executemany(query_stock, extracted_data["stock"])

            # Table stock_price
            query_price = """
                INSERT OR REPLACE INTO stock_price (ticker, date, close_price)
                VALUES (?, ?, ?);
            """
            cursor.executemany(query_price, extracted_data["price"])

            # Table stock_dividend
            query_dividend = """
                INSERT OR REPLACE INTO stock_dividend (ticker, date, amount)
                VALUES (?, ?, ?);
            """
            cursor.executemany(query_dividend, extracted_data["stock_dividend"])

            # Table stock_split
            query_split = """
                INSERT OR REPLACE INTO stock_split (ticker, date, ratio)
                VALUES (?, ?, ?);
            """
            cursor.executemany(query_split, extracted_data["stock_split"])

            conn.commit()

    def add_tickers_in_portfolio_ticker(self, portfolio_id: int, tickers: list[str]) -> None:
        data_to_insert = [(portfolio_id, ticker.strip()) for ticker in tickers if ticker and ticker.strip()]

        query = """
            INSERT OR IGNORE INTO portfolio_ticker (portfolio_id, ticker)
            VALUES (?, ?)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, data_to_insert)

    def get_portfolios(self) -> list[tuple[int, str]]:
        query = "SELECT id, name FROM portfolio ORDER BY name ASC"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def get_tickers_by_portfolio(self, portfolio_id: int) -> list[tuple[str, str]]:
        """Récupère les tickers d'un portefeuille en excluant les devises et benchmark."""
        placeholders = ",".join("?" for _ in self.__symbols)
        query = f"""
            SELECT s.ticker, s.company_name
            FROM portfolio_ticker pt
            JOIN stock s ON pt.ticker = s.ticker
            WHERE pt.portfolio_id = ?
              AND s.ticker NOT IN ({placeholders})
            ORDER BY s.ticker ASC
        """
        params = [portfolio_id] + self.__symbols
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def remove_ticker_from_portfolio(self, portfolio_id: int, ticker: str) -> None:
        """Retire un ticker d'un portefeuille."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Supprimer l'association du portefeuille (et ses transactions liées en cascade)
            cursor.execute("DELETE FROM portfolio_ticker WHERE portfolio_id = ? AND ticker = ?", (portfolio_id, ticker))

            # Vérifier s'il reste au moins une liaison dans un autre portefeuille
            cursor.execute("SELECT COUNT(*) FROM portfolio_ticker WHERE ticker = ?", (ticker,))
            count = cursor.fetchone()[0]

            # Si plus aucun portefeuille n'utilise ce ticker, suppression globale de la table stock
            if count == 0:
                cursor.execute("DELETE FROM stock WHERE ticker = ?", (ticker,))

            conn.commit()

    def add_transactions(self, transactions: pd.DataFrame) -> None:
        """Insère ou fusionne (UPSERT) les transactions selon les contraintes d'unicité de la BDD."""
        if transactions.empty:
            return

        df = transactions.copy()
        records = df.to_dict(orient="records")
        query = """
            INSERT INTO portfolio_transaction (
                portfolio_id, portfolio_ticker_id, type, date, fx_rate,
                original_amount, original_price, original_fee, amount, price, fee
            ) VALUES (
                :portfolio_id, :portfolio_ticker_id, :type, :date, :fx_rate,
                :original_amount, :original_price, :original_fee, :amount, :price, :fee
            )
            ON CONFLICT DO UPDATE SET
                original_amount = portfolio_transaction.original_amount + excluded.original_amount,
                original_fee    = portfolio_transaction.original_fee + excluded.original_fee,
                amount          = COALESCE(portfolio_transaction.amount, 0) + COALESCE(excluded.amount, 0),
                fee             = COALESCE(portfolio_transaction.fee, 0) + COALESCE(excluded.fee, 0);
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, records)
            conn.commit()

    def update_transaction(self, updated_data: dict) -> None:
        transaction_id = updated_data.get("transaction_id") or updated_data.get("id")

        if not transaction_id:
            return

        query = """
            UPDATE portfolio_transaction
            SET portfolio_ticker_id = ?,
                type = ?,
                date = ?,
                original_amount = ?,
                original_price = ?,
                original_fee = ?,
                fx_rate = ?,
                amount = ?,
                price = ?,
                fee = ?
            WHERE id = ?
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    updated_data.get("portfolio_ticker_id"),
                    updated_data.get("type", "buy"),
                    updated_data.get("date"),
                    updated_data.get("original_amount"),
                    updated_data.get("original_price"),
                    updated_data.get("original_fee"),
                    updated_data.get("fx_rate"),
                    updated_data.get("amount"),
                    updated_data.get("price"),
                    updated_data.get("fee"),
                    transaction_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_transaction(self, transaction_id: int) -> None:
        with self._get_connection() as conn:
            conn.cursor().execute(
                "DELETE FROM portfolio_transaction WHERE id = ?",
                (transaction_id,),
            )

    def add_portfolio(self, name: str, currency: str) -> None:
        clean_name = name.strip()
        clean_currency = currency.strip().upper()

        if not clean_name:
            raise ValueError("Le nom du portefeuille ne peut pas être vide.")

        if len(clean_currency) != 3:
            raise ValueError("La devise doit comporter exactement 3 caractères (ex: EUR, USD).")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM portfolio WHERE name = ?", (clean_name,))
            if cursor.fetchone():
                raise ValueError(f"Le portefeuille '{clean_name}' existe déjà.")

            cursor.execute(
                "INSERT INTO portfolio (name, currency) VALUES (?, ?)",
                (clean_name, clean_currency),
            )

    def update_portfolio_name(self, portfolio_id: int, new_name: str) -> None:
        with self._get_connection() as conn:
            conn.cursor().execute(
                "UPDATE portfolio SET name = ? WHERE id = ?",
                (new_name, portfolio_id),
            )

    def delete_portfolio(self, portfolio_id: int) -> None:
        with self._get_connection() as conn:
            conn.cursor().execute("DELETE FROM portfolio WHERE id = ?", (portfolio_id,))

    def update_portfolio_amount(self, portfolio_id: int, amount: float) -> None:
        query = """
            UPDATE portfolio
            SET amount = ?
            WHERE id = ?;
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (amount, portfolio_id))

    def _create_database(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS stock (
                    ticker       VARCHAR(12) PRIMARY KEY,
                    isin         VARCHAR(12),
                    company_name VARCHAR(100) NOT NULL,
                    country      VARCHAR(12),
                    currency     CHAR(3) NOT NULL,

                    CONSTRAINT check_currency_len CHECK (LENGTH(currency) = 3)
                );

                CREATE TABLE IF NOT EXISTS stock_price (
                    ticker      VARCHAR(12) REFERENCES stock(ticker) ON DELETE CASCADE,
                    date        DATE NOT NULL,
                    close_price NUMERIC(12, 2),

                    PRIMARY KEY (ticker, date)
                );

                CREATE TABLE IF NOT EXISTS stock_split (
                    ticker VARCHAR(12) REFERENCES stock(ticker) ON DELETE CASCADE,
                    date   DATE NOT NULL,
                    ratio  FLOAT NOT NULL,

                    PRIMARY KEY (ticker, date)
                );

                CREATE TABLE IF NOT EXISTS stock_dividend (
                    ticker VARCHAR(12) REFERENCES stock(ticker) ON DELETE CASCADE,
                    date   DATE NOT NULL,
                    amount NUMERIC(12, 2) NOT NULL,

                    PRIMARY KEY (ticker, date)
                );

                CREATE TABLE IF NOT EXISTS portfolio (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        VARCHAR(100) NOT NULL,
                    currency    CHAR(3) NOT NULL,
                    amount      NUMERIC(12, 2) NOT NULL DEFAULT 0.00
                );

                CREATE TABLE IF NOT EXISTS portfolio_ticker (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    portfolio_id INT NOT NULL REFERENCES portfolio(id) ON DELETE CASCADE,
                    ticker       VARCHAR(12) NOT NULL REFERENCES stock(ticker),

                    CONSTRAINT uq_portfolio_ticker UNIQUE (portfolio_id, ticker)
                );

                CREATE TABLE IF NOT EXISTS portfolio_transaction (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    portfolio_id        INT NOT NULL REFERENCES portfolio(id) ON DELETE CASCADE,
                    portfolio_ticker_id INT REFERENCES portfolio_ticker(id) ON DELETE CASCADE,
                    type                VARCHAR(10) NOT NULL,
                    date                DATE NOT NULL,
                    fx_rate             NUMERIC(10, 6) DEFAULT 1.0, 
                    
                    -- Données sur le ticker dans sa devise
                    original_amount     NUMERIC(12, 2) NOT NULL,
                    original_price      NUMERIC(12, 2),
                    original_fee        NUMERIC(12, 2) NOT NULL DEFAULT 0,
                    shares              NUMERIC(12, 6) GENERATED ALWAYS AS (
                        CASE 
                            WHEN type IN ('buy', 'sell') AND original_amount IS NOT NULL AND original_price > 0 
                            THEN (original_amount * 1.0) / original_price 
                            ELSE NULL 
                        END
                    ) STORED,

                    -- Données sur le ticker dans la devise du portefeuile
                    amount              NUMERIC(12, 2),
                    price               NUMERIC(12, 2),
                    fee                 NUMERIC(12, 2) DEFAULT 0,
                    
                    CONSTRAINT type_choice CHECK (
                        type IN ('buy', 'sell', 'dividend', 'interest', 'deposit', 'withdrawal')
                    )
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_uniq_cash 
                ON portfolio_transaction(portfolio_id, date, type) 
                WHERE type IN ('deposit', 'withdrawal', 'interest');

                CREATE UNIQUE INDEX IF NOT EXISTS idx_uniq_div 
                ON portfolio_transaction(portfolio_id, date, type, portfolio_ticker_id) 
                WHERE type = 'dividend';

                CREATE UNIQUE INDEX IF NOT EXISTS idx_uniq_trade 
                ON portfolio_transaction(portfolio_id, date, type, portfolio_ticker_id, price) 
                WHERE type IN ('buy', 'sell');
            """)

    def __stock_update(self) -> None:
        """Met à jour les cours, dividendes et splits d'actions dans la base de données."""

        tickers = self.get_tickers() + self.__symbols
        if not tickers:
            return

        end_date = (datetime.today() - timedelta(days=1)).date()
        last_date_query = self.__get_last_date()

        if last_date_query:
            last_date = datetime.strptime(last_date_query, "%Y-%m-%d").date()
            start_date = last_date - timedelta(days=3)
        else:
            start_date = datetime(1800, 1, 1).date()

        if start_date > end_date:
            return

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")

        price_records = []
        dividend_records = []
        split_records = []

        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(start=start_str, end=end_str, actions=True, auto_adjust=False)

                if hist.empty:
                    continue

                hist = hist.reset_index()

                for _, row in hist.iterrows():
                    date_str = pd.to_datetime(row["Date"]).strftime("%Y-%m-%d")

                    close_price = row.get("Close")
                    if pd.notna(close_price):
                        price_records.append((ticker, date_str, float(close_price)))

                    dividend = row.get("Dividends", 0.0)
                    if pd.notna(dividend) and dividend > 0:
                        dividend_records.append((ticker, date_str, float(dividend)))

                    split_ratio = row.get("Stock Splits", 0.0)
                    if pd.notna(split_ratio) and split_ratio > 0:
                        split_records.append((ticker, date_str, float(split_ratio)))

            except Exception as e:
                messagebox.showinfo(f"Erreur lors du téléchargement des données pour {ticker} : {e}")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if price_records:
                cursor.executemany(
                    """
                    INSERT OR REPLACE INTO stock_price (ticker, date, close_price)
                    VALUES (?, ?, ?)
                    """,
                    price_records,
                )

            if dividend_records:
                cursor.executemany(
                    """
                    INSERT OR REPLACE INTO stock_dividend (ticker, date, amount)
                    VALUES (?, ?, ?)
                    """,
                    dividend_records,
                )

            if split_records:
                cursor.executemany(
                    """
                    INSERT OR REPLACE INTO stock_split (ticker, date, ratio)
                    VALUES (?, ?, ?)
                    """,
                    split_records,
                )

            conn.commit()

    def __should_update_stock(self) -> bool:
        """Vérifie si la mise à jour doit être exécutée."""
        config = load_config()
        last_login_str = config.get("last_login_at")
        now = datetime.now()

        # Avant 8h du matin, aucune mise à jour
        if now.hour < 8:
            return False

        # Si aucune date n'est enregistrée, exécuter la mise à jour
        if not last_login_str:
            return True

        # Conversion du texte en objet datetime complet
        last_login_dt = datetime.strptime(last_login_str, "%Y-%m-%d %H:%M:%S")
        today = now.date()

        # Exécution si la dernière date était un jour précédent
        if last_login_dt.date() < today:
            return True

        # Exécution si même jour, il est 20h+ et la dernière exécution s'est faite avant 20h
        return bool(last_login_dt.date() == today and now.hour >= 20 and last_login_dt.hour < 20)
