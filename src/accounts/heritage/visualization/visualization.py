import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from config import load_config


def generate_standalone_heritage_report(data: dict[str, Any], currency: str) -> None:
    """Génère un fichier HTML autonome contenant tout le CSS, le JS Highcharts et les données."""
    static_dir = Path("src/static")
    vendor_dir = static_dir / "vendor"
    heritage_dir = static_dir / "heritage"

    # Chargement des scripts vendor
    vendor_files = [
        "highstock.js",
        "highcharts-more.js",
        "heatmap.js",
        "treemap.js",
        "exporting.js",
        "accessibility.js",
    ]

    vendor_scripts = "\n".join(
        [(vendor_dir / file).read_text(encoding="utf-8") for file in vendor_files if (vendor_dir / file).exists()]
    )

    # Lecture des assets spécifiques au module heritage
    heritage_css = (heritage_dir / "heritage.css").read_text(encoding="utf-8")
    heritage_js = (heritage_dir / "heritage.js").read_text(encoding="utf-8")

    # Formatage des données Pandas vers JSON
    heritage_series_data = [[int(ts.timestamp() * 1000), round(val, 2)] for ts, val in data["heritage_series"].items()]

    accounts_series_data = []
    for account_name in data["all_accounts_df"].columns:
        series_points = [
            [int(ts.timestamp() * 1000), round(val, 2)] for ts, val in data["all_accounts_df"][account_name].items()
        ]
        accounts_series_data.append({"name": str(account_name), "data": series_points})

    distribution_data = [
        {"name": name, "y": round(details["amount"], 2)}
        for name, details in data["account_distribution"].items()
        if details["amount"] > 0
    ]

    # Formatage du DataFrame yearly_growth pour Highcharts
    yearly_growth_data = []
    yearly_df = data.get("yearly_growth")
    if yearly_df is not None and not yearly_df.empty:
        for year, row in yearly_df.iterrows():
            yearly_growth_data.append(
                {
                    "year": str(year),
                    "gainLoss": float(row["gain_loss"]),
                    "percentage": float(row["percentage_change"]),
                }
            )

    total_amount = data["heritage_series"].iloc[-1] if not data["heritage_series"].empty else 0.0

    payload = {
        "currency": currency,
        "totalAmount": round(total_amount, 2),
        "heritageSeries": heritage_series_data,
        "accountsSeries": accounts_series_data,
        "distribution": distribution_data,
        "yearlyGrowth": yearly_growth_data,
    }

    # Configuration Jinja2 et Rendu
    env = Environment(loader=FileSystemLoader(heritage_dir))
    template = env.get_template("heritage.html")

    html_rendu = template.render(
        vendor_scripts=vendor_scripts,
        heritage_css=heritage_css,
        heritage_js=heritage_js,
        data=json.dumps(payload, ensure_ascii=False),
    )

    output_path = Path(load_config()["destination_path"]) / "heritage" / "heritage_global.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_rendu, encoding="utf-8")
