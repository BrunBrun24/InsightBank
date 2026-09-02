from types import SimpleNamespace
from typing import Any

import pandas as pd
import xlsxwriter
import xlsxwriter.utility

from accounts.stock.processing.portfolio_tracker import PortfolioTracker


class StockExcelGenerator:
    """Générateur de tableaux de bord Excel pour portefeuille boursier."""

    def __init__(
        self,
        portfolio_tracker: PortfolioTracker | dict[str, Any],
        output_path: str,
        currency_symbol: str,
        portfolio_name: str,
    ) -> None:
        output_path.mkdir(parents=True, exist_ok=True)

        if isinstance(portfolio_tracker, dict):
            portfolio_tracker = SimpleNamespace(**portfolio_tracker)

        self.__tracker = portfolio_tracker
        self.__portfolio_name = portfolio_name
        self.__file_path = output_path / f"{self.__portfolio_name}.xlsx"
        self.__currency_symbol = currency_symbol

    def generate_report(self) -> str:
        """Génère le fichier Excel complet du portefeuille."""

        wb = xlsxwriter.Workbook(str(self.__file_path), {"nan_inf_to_errors": True})
        fmt = self.__get_excel_formats(wb)

        # Création des onglets
        self.__build_dashboard_sheet(wb, fmt)
        self.__build_positions_sheet(wb, fmt)
        self.__build_transactions_sheet(wb, fmt)
        self.__build_correlation_sheet(wb, fmt)

        wb.close()
        return str(self.__file_path)

    def __build_dashboard_sheet(self, wb: xlsxwriter.Workbook, fmt: dict[str, Any]) -> None:
        ws = wb.add_worksheet("Tableau de Bord")
        ws.hide_gridlines(2)

        ws.set_column("A:A", 4)
        ws.set_column("B:C", 22)
        ws.set_column("D:D", 16)
        ws.set_column("E:E", 4)
        ws.set_column("F:G", 22)
        ws.set_column("H:H", 16)
        ws.set_column("I:I", 4)

        ws.merge_range("B2:D2", "TABLEAU DE BORD PORTEFEUILLE", fmt["title"])
        ws.merge_range("F2:H2", self.__portfolio_name.upper(), fmt["header_tag"])

        # KPI Bloc 1 : Valorisation & Trésorerie
        ws.merge_range("B4:D4", "VALORISATION & TRÉSORERIE", fmt["section_header"])

        gross_val = (
            float(self.__tracker.portfolio_gross_value.iloc[-1])
            if not self.__tracker.portfolio_gross_value.empty
            else 0.0
        )
        stock_val = (
            float(self.__tracker.portfolio_values.iloc[-1]) if not self.__tracker.portfolio_values.empty else 0.0
        )
        cash_val = float(self.__tracker.portfolio_cash.iloc[-1]) if not self.__tracker.portfolio_cash.empty else 0.0
        deposit_val = (
            float(self.__tracker.portfolio_deposit.iloc[-1]) if not self.__tracker.portfolio_deposit.empty else 0.0
        )

        kpi_rows_1 = [
            ("Valeur Totale Brut", gross_val, fmt["currency_bold"]),
            ("Valorisation Actions", stock_val, fmt["currency"]),
            ("Trésorerie Disponible", cash_val, fmt["currency"]),
            ("Apports Totaux Dépensés", deposit_val, fmt["currency"]),
        ]

        for idx, (label, val, f_val) in enumerate(kpi_rows_1, start=5):
            ws.write(idx, 1, label, fmt["kpi_label"])
            ws.merge_range(idx, 2, idx, 3, val, f_val)

        # KPI Bloc 2 : Performance & Risque
        ws.merge_range("F4:H4", "PERFORMANCE & RISQUE", fmt["section_header"])

        total_gain = (
            float(self.__tracker.portfolio_total_gains.iloc[-1])
            if not self.__tracker.portfolio_total_gains.empty
            else 0.0
        )
        latent_gain = (
            float(self.__tracker.portfolio_latent_gain.iloc[-1])
            if not self.__tracker.portfolio_latent_gain.empty
            else 0.0
        )
        perf_pct = float(self.__tracker.portfolio_pct.iloc[-1]) if not self.__tracker.portfolio_pct.empty else 0.0
        volatility = self.__tracker.volatility_portfolio
        sharpe = self.__tracker.sharpe_ratio
        sortino = self.__tracker.sortino_ratio

        kpi_rows_2 = [
            (
                f"Plus-Value Globale ({self.__currency_symbol})",
                total_gain,
                fmt["currency_bold_green_center"] if total_gain >= 0 else fmt["currency_bold_red_center"],
            ),
            (
                f"Plus-Value Latente ({self.__currency_symbol})",
                latent_gain,
                fmt["currency_green_center"] if latent_gain >= 0 else fmt["currency_red_center"],
            ),
            (
                "Performance Cumulée (%)",
                perf_pct / 100.0,
                fmt["percent_bold_green"] if perf_pct >= 0 else fmt["percent_bold_red"],
            ),
            ("Volatilité Annualisée", volatility / 100.0, fmt["percent"]),
            ("Ratio de Sharpe", sharpe, fmt["number"]),
            ("Ratio de Sortino", sortino, fmt["number"]),
        ]

        for idx, (label, val, f_val) in enumerate(kpi_rows_2, start=5):
            ws.write(idx, 5, label, fmt["kpi_label"])
            ws.merge_range(idx, 6, idx, 7, val, f_val)

        # Répartition des actifs
        ws.merge_range("B11:D11", "RÉPARTITION DU PORTEFEUILLE", fmt["section_header"])
        ws.write(11, 1, "Ticker", fmt["table_header"])
        ws.merge_range(11, 2, 11, 3, "Poids (%)", fmt["table_header_center"])

        ticker_values = self.__tracker.ticker_values
        if not ticker_values.empty and stock_val > 0:
            last_weights = (ticker_values.iloc[-1] / stock_val).sort_values(ascending=False)
            row_idx = 12
            for ticker, weight in last_weights.items():
                if weight > 0:
                    ws.write(row_idx, 1, ticker, fmt["cell_left_bold"])
                    ws.merge_range(row_idx, 2, row_idx, 3, float(weight), fmt["percent"])
                    row_idx += 1

    def __build_positions_sheet(self, wb: xlsxwriter.Workbook, fmt: dict[str, Any]) -> None:
        ws = wb.add_worksheet("Positions")
        ws.hide_gridlines(2)

        headers = [
            "Ticker",
            "Nombre d'actions",
            f"PRU ({self.__currency_symbol})",
            f"Montant Investi ({self.__currency_symbol})",
            f"Valorisation Actuelle ({self.__currency_symbol})",
            f"P&L Latent ({self.__currency_symbol})",
            "P&L Latent (%)",
            "Poids (%)",
        ]

        cols_width = [14, 18, 14, 20, 22, 16, 16, 14]
        for col_idx, width in enumerate(cols_width):
            col_letter = xlsxwriter.utility.xl_col_to_name(col_idx)
            ws.set_column(f"{col_letter}:{col_letter}", width)

        ws.merge_range("A2:H2", "DÉTAIL DES POSITIONS OUVERTES", fmt["title_sheet"])

        ticker_values_df = self.__tracker.ticker_values
        if ticker_values_df.empty:
            return

        last_date = ticker_values_df.index[-1]
        all_tickers = ticker_values_df.columns.tolist()

        total_portfolio_val = float(ticker_values_df.loc[last_date].sum())

        row = 4
        for ticker in all_tickers:
            val_current = float(self.__tracker.ticker_values.loc[last_date, ticker])

            # On ne conserve que les positions encore ouvertes (valorisation > 0)
            if val_current <= 0:
                continue

            invested = float(self.__tracker.ticker_investments.loc[last_date, ticker])
            pnl_latent = float(self.__tracker.ticker_latent_gains.loc[last_date, ticker])
            pnl_pct = float(self.__tracker.ticker_latent_gains_pct.loc[last_date, ticker]) / 100.0

            current_price = 0.0
            if ticker in self.__tracker.ticker_prices.columns:
                current_price = float(self.__tracker.ticker_prices.loc[last_date, ticker])

            shares = val_current / current_price if current_price > 0 else 0.0
            pru = invested / shares if shares > 0 else 0.0
            weight = (val_current / total_portfolio_val) if total_portfolio_val > 0 else 0.0

            ws.write(row, 0, ticker, fmt["cell_left_bold"])
            ws.write(row, 1, shares, fmt["number_2dec"])
            ws.write(row, 2, pru, fmt["currency"])
            ws.write(row, 3, invested, fmt["currency"])
            ws.write(row, 4, val_current, fmt["currency_bold"])
            ws.write(row, 5, pnl_latent, fmt["currency_green"] if pnl_latent >= 0 else fmt["currency_red"])
            ws.write(row, 6, pnl_pct, fmt["percent_green"] if pnl_pct >= 0 else fmt["percent_red"])
            ws.write(row, 7, weight, fmt["percent"])

            row += 1

        end_row = row - 1

        # Si aucune position n'est ouverte
        if end_row < 4:
            return

        table_columns = [{"header": h} for h in headers]
        ws.add_table(
            3,
            0,
            end_row,
            len(headers) - 1,
            {
                "columns": table_columns,
                "style": "Table Style Medium 2",
                "autofilter": True,
            },
        )

        ws.write(row, 0, "TOTAL", fmt["total_label"])
        ws.write(row, 1, "", fmt["total_val"])
        ws.write(row, 2, "", fmt["total_val"])
        ws.write_formula(row, 3, f"=SUBTOTAL(109, D5:D{row})", fmt["total_currency"])
        ws.write_formula(row, 4, f"=SUBTOTAL(109, E5:E{row})", fmt["total_currency"])
        ws.write_formula(row, 5, f"=SUBTOTAL(109, F5:F{row})", fmt["total_currency"])
        ws.write_formula(
            row,
            6,
            f"=IF(SUBTOTAL(109, D5:D{row})>0, SUBTOTAL(109, F5:F{row})/SUBTOTAL(109, D5:D{row}), 0)",
            fmt["total_percent"],
        )
        ws.write_formula(row, 7, f"=SUBTOTAL(109, H5:H{end_row + 1})", fmt["total_percent"])

    def __build_transactions_sheet(self, wb: xlsxwriter.Workbook, fmt: dict[str, Any]) -> None:
        ws = wb.add_worksheet("Transactions")
        ws.hide_gridlines(2)

        headers = [
            "Date",
            "Type",
            "Ticker",
            "Nombre d'actions",
            f"Prix unitaire ({self.__currency_symbol})",
            f"Montant ({self.__currency_symbol})",
            f"Frais ({self.__currency_symbol})",
        ]
        cols_width = [14, 14, 12, 18, 18, 16, 14]

        for col_idx, width in enumerate(cols_width):
            col_letter = xlsxwriter.utility.xl_col_to_name(col_idx)
            ws.set_column(f"{col_letter}:{col_letter}", width)

        ws.merge_range("A2:G2", "HISTORIQUE COMPLET DES TRANSACTIONS", fmt["title_sheet"])

        df_tx = self.__tracker.transactions
        if df_tx.empty:
            return

        row = 4
        for _, tx in df_tx.iterrows():
            date_str = pd.to_datetime(tx["date"]).strftime("%Y-%m-%d")
            tx_type = str(tx["type"]).upper()
            ticker = str(tx["ticker"]) if pd.notna(tx["ticker"]) else "-"
            shares = float(tx["shares"]) if pd.notna(tx["shares"]) else 0.0
            price = float(tx["price"]) if pd.notna(tx["price"]) else 0.0
            amount = float(tx["amount"]) if pd.notna(tx["amount"]) else 0.0
            fee = float(tx["fee"]) if pd.notna(tx["fee"]) else 0.0

            type_fmt = (
                fmt["type_buy"] if tx_type == "BUY" else (fmt["type_sell"] if tx_type == "SELL" else fmt["type_other"])
            )

            ws.write(row, 0, date_str, fmt["cell_center"])
            ws.write(row, 1, tx_type, type_fmt)
            ws.write(row, 2, ticker, fmt["cell_center_bold"])
            ws.write(row, 3, shares if shares != 0 else "-", fmt["number_2dec"] if shares != 0 else fmt["cell_center"])
            ws.write(row, 4, price if price != 0 else "-", fmt["currency"] if price != 0 else fmt["cell_center"])
            ws.write(row, 5, amount, fmt["currency"])
            ws.write(row, 6, fee, fmt["currency"])
            row += 1

        end_row = row - 1

        table_columns = [{"header": h} for h in headers]
        ws.add_table(
            3,
            0,
            end_row,
            len(headers) - 1,
            {
                "columns": table_columns,
                "style": "Table Style Medium 2",
                "autofilter": True,
            },
        )

    def __build_correlation_sheet(self, wb: xlsxwriter.Workbook, fmt: dict[str, Any]) -> None:
        ws = wb.add_worksheet("Corrélation")
        ws.hide_gridlines(2)

        corr_df = self.__tracker.correlation
        if corr_df.empty:
            return

        ws.merge_range("B2:K2", "MATRICE DE CORRÉLATION DES RENDEMENTS QUOTIDIENS", fmt["title_sheet"])

        tickers = corr_df.columns.tolist()
        ws.set_column("B:B", 16)

        for idx, tck in enumerate(tickers, start=2):
            col_letter = xlsxwriter.utility.xl_col_to_name(idx)
            ws.set_column(f"{col_letter}:{col_letter}", 12)
            ws.write(3, idx, tck, fmt["table_header_center"])

        for r_idx, tck_row in enumerate(tickers, start=4):
            ws.write(r_idx, 1, tck_row, fmt["table_header"])
            for c_idx, tck_col in enumerate(tickers, start=2):
                val = float(corr_df.loc[tck_row, tck_col])

                if tck_row == tck_col:
                    cell_fmt = fmt["corr_self"]
                elif val < 0.0:
                    cell_fmt = fmt["corr_negative"]
                elif val > 0.6:
                    cell_fmt = fmt["corr_high"]
                else:
                    cell_fmt = fmt["corr_normal"]

                ws.write(r_idx, c_idx, val, cell_fmt)

    def __get_excel_formats(self, wb: xlsxwriter.Workbook) -> dict[str, Any]:
        border_thin = {"border": 1, "border_color": "#D3D3D3"}

        return {
            "title": wb.add_format({"font_name": "Arial", "font_size": 18, "bold": True, "font_color": "#1F77B4"}),
            "title_sheet": wb.add_format(
                {
                    "font_name": "Arial",
                    "font_size": 14,
                    "bold": True,
                    "font_color": "#1F77B4",
                    "bottom": 2,
                    "bottom_color": "#1F77B4",
                }
            ),
            "header_tag": wb.add_format(
                {
                    "bg_color": "#1F77B4",
                    "font_color": "white",
                    "bold": True,
                    "align": "center",
                    "valign": "vcenter",
                    "font_size": 11,
                }
            ),
            "section_header": wb.add_format(
                {
                    "font_name": "Arial",
                    "font_size": 11,
                    "bold": True,
                    "font_color": "#1F77B4",
                    "bg_color": "#E6F2FF",
                    "bottom": 2,
                    "bottom_color": "#1F77B4",
                    "align": "center",
                }
            ),
            "kpi_label": wb.add_format({"font_name": "Arial", "font_size": 10, "font_color": "#333333", **border_thin}),
            "table_header": wb.add_format(
                {
                    "font_name": "Arial",
                    "font_size": 10,
                    "bold": True,
                    "font_color": "white",
                    "bg_color": "#1F77B4",
                    "align": "left",
                    "valign": "vcenter",
                }
            ),
            "table_header_center": wb.add_format(
                {
                    "font_name": "Arial",
                    "font_size": 10,
                    "bold": True,
                    "font_color": "white",
                    "bg_color": "#1F77B4",
                    "align": "center",
                    "valign": "vcenter",
                }
            ),
            "currency_green_center": wb.add_format(
                {
                    "num_format": f"#,##0.00 {self.__currency_symbol}",
                    "font_size": 10,
                    "font_color": "#008000",
                    "align": "center",
                    **border_thin,
                }
            ),
            "currency_red_center": wb.add_format(
                {
                    "num_format": f"#,##0.00 {self.__currency_symbol}",
                    "font_size": 10,
                    "font_color": "#CC0000",
                    "align": "center",
                    **border_thin,
                }
            ),
            "currency_bold_green_center": wb.add_format(
                {
                    "num_format": f"#,##0.00 {self.__currency_symbol}",
                    "font_size": 10,
                    "bold": True,
                    "font_color": "#008000",
                    "align": "center",
                    **border_thin,
                }
            ),
            "currency_bold_red_center": wb.add_format(
                {
                    "num_format": f"#,##0.00 {self.__currency_symbol}",
                    "font_size": 10,
                    "bold": True,
                    "font_color": "#CC0000",
                    "align": "center",
                    **border_thin,
                }
            ),
            "currency": wb.add_format(
                {"num_format": f"#,##0.00 {self.__currency_symbol}", "font_size": 10, **border_thin}
            ),
            "currency_bold": wb.add_format(
                {"num_format": f"#,##0.00 {self.__currency_symbol}", "font_size": 10, "bold": True, **border_thin}
            ),
            "currency_green": wb.add_format(
                {
                    "num_format": f"#,##0.00 {self.__currency_symbol}",
                    "font_size": 10,
                    "font_color": "#008000",
                    **border_thin,
                }
            ),
            "currency_red": wb.add_format(
                {
                    "num_format": f"#,##0.00 {self.__currency_symbol}",
                    "font_size": 10,
                    "font_color": "#CC0000",
                    **border_thin,
                }
            ),
            "percent": wb.add_format({"num_format": "0.00%", "font_size": 10, "align": "center", **border_thin}),
            "percent_green": wb.add_format(
                {"num_format": "0.00%", "font_size": 10, "align": "center", "font_color": "#008000", **border_thin}
            ),
            "percent_red": wb.add_format(
                {"num_format": "0.00%", "font_size": 10, "align": "center", "font_color": "#CC0000", **border_thin}
            ),
            "percent_bold_green": wb.add_format(
                {
                    "num_format": "0.00%",
                    "font_size": 10,
                    "bold": True,
                    "align": "center",
                    "font_color": "#008000",
                    **border_thin,
                }
            ),
            "percent_bold_red": wb.add_format(
                {
                    "num_format": "0.00%",
                    "font_size": 10,
                    "bold": True,
                    "align": "center",
                    "font_color": "#CC0000",
                    **border_thin,
                }
            ),
            "number": wb.add_format({"num_format": "0.00", "font_size": 10, "align": "center", **border_thin}),
            "number_2dec": wb.add_format({"num_format": "#,##0.00", "font_size": 10, "align": "center", **border_thin}),
            "cell_left": wb.add_format({"font_size": 10, "align": "left", **border_thin}),
            "cell_left_bold": wb.add_format({"font_size": 10, "bold": True, "align": "left", **border_thin}),
            "cell_center": wb.add_format({"font_size": 10, "align": "center", **border_thin}),
            "cell_center_bold": wb.add_format({"font_size": 10, "bold": True, "align": "center", **border_thin}),
            "type_buy": wb.add_format(
                {
                    "font_size": 10,
                    "bold": True,
                    "font_color": "#008000",
                    "bg_color": "#E6F5E6",
                    "align": "center",
                    **border_thin,
                }
            ),
            "type_sell": wb.add_format(
                {
                    "font_size": 10,
                    "bold": True,
                    "font_color": "#CC0000",
                    "bg_color": "#FFE6E6",
                    "align": "center",
                    **border_thin,
                }
            ),
            "type_other": wb.add_format(
                {"font_size": 10, "font_color": "#1F77B4", "bg_color": "#E6F2FF", "align": "center", **border_thin}
            ),
            "total_label": wb.add_format({"font_size": 10, "bold": True, "bg_color": "#F2F2F2", "top": 1, "bottom": 2}),
            "total_val": wb.add_format(
                {"font_size": 10, "bold": True, "bg_color": "#F2F2F2", "top": 1, "bottom": 2, "align": "center"}
            ),
            "total_currency": wb.add_format(
                {
                    "num_format": f"#,##0.00 {self.__currency_symbol}",
                    "font_size": 10,
                    "bold": True,
                    "bg_color": "#F2F2F2",
                    "top": 1,
                    "bottom": 2,
                }
            ),
            "total_percent": wb.add_format(
                {
                    "num_format": "0.00%",
                    "font_size": 10,
                    "bold": True,
                    "bg_color": "#F2F2F2",
                    "top": 1,
                    "bottom": 2,
                    "align": "center",
                }
            ),
            "corr_self": wb.add_format(
                {"num_format": "0.00", "bg_color": "#D9D9D9", "bold": True, "align": "center", **border_thin}
            ),
            "corr_high": wb.add_format(
                {"num_format": "0.00", "bg_color": "#C6EFCE", "font_color": "#006100", "align": "center", **border_thin}
            ),
            "corr_negative": wb.add_format(
                {"num_format": "0.00", "bg_color": "#FFC7CE", "font_color": "#9C0006", "align": "center", **border_thin}
            ),
            "corr_normal": wb.add_format({"num_format": "0.00", "align": "center", **border_thin}),
        }
