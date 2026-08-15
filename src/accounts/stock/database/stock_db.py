from datetime import datetime, timedelta
from tkinter import messagebox

import pandas as pd
import yfinance as yf

from accounts.stock.importers.fetch_stock import fetch_stock_data

from ...shared.database_base import DatabaseBase


class StockDB(DatabaseBase):
    """Gère l'accès et la manipulation des données financières d'un portefeuille boursier."""

    def __init__(self, db_path: str) -> None:
        super().__init__(db_path)

        self._create_database()
        self.__currencies = ["EURUSD=X"]

        # Ajoute les données de conversion pour chaque devise
        tickers = self.get_tickers()
        for currency in self.__currencies:
            if currency not in tickers:
                df = pd.DataFrame(columns=["symbol"], data=[currency])
                extracted_data, isin_ticker_add = fetch_stock_data(self, df)
                tickers_to_add = [isin_ticker["ticker"] for isin_ticker in isin_ticker_add]
                self.add_data_tickers(tickers_to_add, extracted_data)
        self.__stock_update()

    def get_all_portfolios(self) -> pd.DataFrame:
        query = "SELECT id, name FROM portfolio ORDER BY id DESC"
        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn)

    def get_portfolio_currency(self, portfolio_id: int) -> str:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT currency FROM portfolio WHERE id = ?", (portfolio_id,))
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

    def add_transactions(self, transactions: pd.DataFrame) -> None:
        with self._get_connection() as conn:
            transactions.to_sql(
                name="portfolio_transaction",
                con=conn,
                if_exists="append",
                index=False,
            )

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
                    currency    CHAR(3) NOT NULL
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
            """)

    def __stock_update(self) -> None:
        """Met à jour les cours, dividendes et splits d'actions dans la base de données."""

        tickers = self.get_tickers() + self.__currencies
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
