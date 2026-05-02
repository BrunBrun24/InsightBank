import json
import os
import uuid

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import load_config
from accounts.banking.database.banking_db import BankingDB


class FinancialChart:
    """
    Génère différents graphiques financiers à partir des opérations catégorisées d'un compte bancaire.
    Elle hérite de `BankingDB` et fournit des méthodes pour :

    - Créer des dossiers annuels pour organiser les graphiques.
    - Générer des graphiques Sankey, en barres empilées et circulaires (sunburst) pour visualiser
    les revenus, les dépenses et leur répartition par catégorie et sous-catégorie.
    - Combiner plusieurs graphiques côte à côte si nécessaire pour éviter les doublons.
    - Produire des bilans annuels et mensuels en créant et sauvegardant automatiquement les fichiers HTML.
    """

    def __init__(self, db: BankingDB, bank_account_name: str) -> None:
        self.__db = db
        self.__root_path = os.path.join(load_config()["destination_path"], bank_account_name)
        self.__file_highcharts = []

        os.makedirs(self.__root_path, exist_ok=True)

    def generate_all_reports(self, bank_account_id: int) -> None:
        """
        Génère les bilans financiers annuels à partir des opérations catégorisées.

        Cette méthode crée pour chaque année :
        - Des graphiques Sankey pour visualiser les flux financiers.
        - Des graphiques circulaires (sunburst) pour détailler la répartition des revenus et dépenses.
        - Des histogrammes empilés pour visualiser les dépenses par mois.

        Les fichiers HTML correspondants sont sauvegardés dans des dossiers par année.
        """

        years_data = self.__db.get_categorized_operations_by_year(bank_account_id)

        all_years_incomes = []
        all_years_expenses = []
        all_years_combined = []

        for year, data in years_data.items():
            self.__output_file = f"{self.__root_path}/Bilan {year}.html"
            self.__generate_annual_report(data["incomes"], data["expenses"], data["all"])

            all_years_incomes.append(data["incomes"])
            all_years_expenses.append(data["expenses"])
            all_years_combined.append(data["all"])

        # Bilan Global
        if years_data:
            years = sorted(years_data.keys())
            self.__output_file = f"{self.__root_path}/Bilan {years[0]}-{years[-1]}.html"
            self.__generate_annual_report(
                pd.concat(all_years_incomes), pd.concat(all_years_expenses), pd.concat(all_years_combined)
            )

    # --- [ Production des Bilans ] ---
    def __generate_annual_report(
        self, incomes_df: pd.DataFrame, expenses_df: pd.DataFrame, incomes_expenses_df: pd.DataFrame
    ) -> None:
        """
        Génère et organise les graphiques pour un compte avec revenus et dépenses.

        Actions :
            - Crée un graphique Sankey pour l’ensemble des opérations.
            - Crée un histogramme empilé pour les dépenses.
            - Génère des graphiques circulaires des dépenses et des revenus.
            - Combine plusieurs graphiques côte à côte si nécessaire.
            - Sauvegarde tous les graphiques générés dans un fichier HTML.
        """

        # S'il y a des revenus et des dépenses
        if not expenses_df.empty and not incomes_df.empty:
            self.__generate_html_file(incomes_expenses_df, False)

            fig_pie_expenses = self.__create_pie_chart(df=expenses_df, name="Dépenses", save=False)
            fig_pie_incomes = self.__create_pie_chart(df=incomes_df, name="Revenus", save=False)
            self.__create_combined_charts(fig_pie_expenses, fig_pie_incomes)

        # S'il y a que des dépenses
        elif not expenses_df.empty and incomes_df.empty:
            self.__generate_html_file(incomes_expenses_df, True)
            fig_pie_expenses = self.__create_pie_chart(df=expenses_df, name="Dépenses", save=True)

        # S'il y a que des revenus
        elif expenses_df.empty and not incomes_df.empty:
            self.__generate_html_file(incomes_expenses_df, True)
            fig_pie_incomes = self.__create_pie_chart(df=incomes_df, name="Revenus", save=True)

        self.__save_in_file()

    def __save_in_file(self) -> None:
        """
        Enregistre tous les graphiques générés dans un fichier HTML.

        Accepte à la fois :
        - des figures Plotly (go.Figure)
        - du HTML brut (str)
        """

        with open(self.__output_file, "w", encoding="utf-8") as f:
            for item in self.__file_highcharts:
                if isinstance(item, str):
                    # HTML brut (ex: Highcharts)
                    f.write(item)
                else:
                    # Figure Plotly
                    item.write_html(f, include_plotlyjs="cdn")

        # Reset après écriture
        self.__file_highcharts = []

    # --- [ Génération de Graphiques ] ---
    def __create_sankey_chart(self, incomes_expenses_df: pd.DataFrame) -> str:
        """
        Génère le code HTML/JavaScript pour un diagramme de Sankey dynamique.
        Utilise la liste des catégories de revenus de la base de données pour
        regrouper les flux vers le nœud central.
        """

        # 1. Récupération dynamique des catégories de revenus
        # On suppose que self.__db est ton instance de BankingDB
        incomes_categories, _ = self.__db.get_category_lists()

        # Génération d'un ID unique pour éviter les conflits si plusieurs graphiques
        graph_id = "sankey_" + str(uuid.uuid4()).replace("-", "_")

        # Préparation des données
        years = sorted([int(y) for y in incomes_expenses_df["year"].unique()], reverse=True)
        multiple_years = len(years) > 1

        df_copy = incomes_expenses_df.copy()
        df_copy["operation_date"] = df_copy["operation_date"].astype(str)
        df_copy["amount"] = df_copy["amount"].astype(float)
        df_copy["year"] = df_copy["year"].astype(int)

        # Sérialisation pour injection JS
        data_json = json.dumps(df_copy.to_dict(orient="records"), ensure_ascii=False)
        incomes_list_json = json.dumps(incomes_categories, ensure_ascii=False)

        colors = [
            "#544FC5",
            "#2CAFFE",
            "#FF7F50",
            "#32CD32",
            "#FF69B4",
            "#FFA500",
            "#8A2BE2",
            "#00CED1",
            "#DC143C",
            "#7FFF00",
        ]

        html = ""
        if multiple_years:
            html += "<h2>Choisir l'année pour Sankey :</h2>"
            html += f'<select id="sankeyYearSelect_{graph_id}">'
            for i, y in enumerate(years):
                is_selected = "selected" if i == 0 else ""
                html += f'<option value="{y}" {is_selected}>{y}</option>'
            html += "</select>"

        html += f'<div id="sankeyContainer_{graph_id}" style="width:100%; height:950px; margin-top:20px;"></div>'

        html += f"""
            <script>
            (function() {{
                const sankeyData = {data_json};
                const incomesList = {incomes_list_json}; // Liste dynamique des revenus
                const sankeyColors = {json.dumps(colors)};
                const sankeyYears = {json.dumps(years)};
                const containerId = 'sankeyContainer_{graph_id}';
                const yearSelectId = 'sankeyYearSelect_{graph_id}';

                function round2(value) {{ return Math.round((value + Number.EPSILON) * 100) / 100; }}

                function buildSankeyLinks(selectedYear) {{
                    let links = [];
                    const filteredData = sankeyData.filter(d => d.year === selectedYear);

                    // --- LOGIQUE DYNAMIQUE DES REVENUS ---
                    // On identifie comme revenu toute ligne dont la catégorie est dans incomesList
                    const revenus = filteredData.filter(d => incomesList.includes(d.category));
                    const revenus_souscat = {{}};
                    
                    revenus.forEach(d => {{ 
                        revenus_souscat[d.sub_category] = (revenus_souscat[d.sub_category] || 0) + d.amount; 
                    }});
                    
                    Object.entries(revenus_souscat).forEach(([s, v]) => {{
                        links.push({{ from: s, to: "Revenus", weight: round2(v) }});
                    }});
                    
                    // --- LOGIQUE DYNAMIQUE DES DÉPENSES ---
                    // Une dépense est tout ce qui n'est pas dans la liste des revenus
                    const depenses = filteredData.filter(d => !incomesList.includes(d.category)).map(d => ({{
                        ...d,
                        amount: Math.abs(d.amount)
                    }}));

                    const depCatsTotals = {{}};
                    depenses.forEach(d => {{ 
                        depCatsTotals[d.category] = (depCatsTotals[d.category] || 0) + d.amount; 
                    }});
                    
                    let sortedDepCats = Object.entries(depCatsTotals).sort(([, a], [, b]) => b - a);

                    sortedDepCats.forEach(([cat, catTotal], idx) => {{
                        const color = sankeyColors[idx % sankeyColors.length];
                        
                        // Flux de Revenus vers Catégorie de dépense
                        links.push({{ 
                            from: "Revenus", 
                            to: cat, 
                            weight: round2(catTotal), 
                            color: color 
                        }});

                        // Flux de Catégorie vers Sous-catégories
                        const subs = {{}};
                        depenses.filter(d => d.category === cat).forEach(d => {{ 
                            subs[d.sub_category] = (subs[d.sub_category] || 0) + d.amount; 
                        }});
                        
                        Object.entries(subs).forEach(([s, amt]) => {{
                            links.push({{ 
                                from: cat, 
                                to: s, 
                                weight: round2(amt), 
                                color: color 
                            }});
                        }});
                    }});

                    return links;
                }}

                function renderSankey(selectedYear) {{
                    if(!selectedYear) {{
                        const selectEl = document.getElementById(yearSelectId);
                        selectedYear = selectEl ? parseInt(selectEl.value) : (sankeyYears.length > 0 ? sankeyYears[0] : null);
                    }}
                    
                    if(!selectedYear) return;
                    
                    const links = buildSankeyLinks(selectedYear);
                    
                    Highcharts.chart(containerId, {{
                        chart: {{ type: 'sankey', height: 850 }},
                        title: {{ text: 'Répartition des flux financiers : ' + selectedYear }},
                        tooltip: {{
                            pointFormatter: function () {{
                                return this.toNode.name === 'Revenus' 
                                    ? this.fromNode.name + ': <b>' + this.weight.toFixed(2) + ' €</b>'
                                    : this.fromNode.name + ' \\u2192 ' + this.toNode.name + ': <b>' + this.weight.toFixed(2) + ' €</b>';
                            }}
                        }},
                        series:[{{
                            keys: ['from', 'to', 'weight', 'color'],
                            data: links,
                            type: 'sankey',
                            dataLabels: {{
                                nodeFormatter: function() {{ return this.point.name; }}
                            }}
                        }}]
                    }});
                }}

                const sankeySelect = document.getElementById(yearSelectId);
                if(sankeySelect) {{
                    sankeySelect.addEventListener('change', (e) => renderSankey(parseInt(e.target.value)));
                }}
                
                renderSankey();
            }})();
            </script>
        """
        return html

    def __create_pie_chart(self, df: pd.DataFrame, name: str, save: bool) -> go.Figure:
        """
        Crée un graphique circulaire (sunburst) représentant la répartition des montants par catégorie et sous-catégorie.

        Args :
            df (pd.DataFrame) : DataFrame contenant les opérations catégorisées.
            name (str) : nom du graphique ou du nœud racine.
            save (bool, optionnel) : indique si le graphique doit être sauvegardé dans la liste interne (par défaut True).

        Returns :
            go.Figure : objet figure Plotly contenant le graphique circulaire généré.
        """

        labels = [name]
        parents = [""]
        values = [df["amount"].sum()]

        for category in df["category"].unique():
            labels.append(category)
            parents.append(name)
            values.append(df[df["category"] == category]["amount"].sum())

            for type_op in df[df["category"] == category]["sub_category"].unique():
                labels.append(type_op)
                parents.append(category)
                values.append(df[(df["category"] == category) & (df["sub_category"] == type_op)]["amount"].sum())

        fig = go.Figure(
            go.Sunburst(
                labels=labels,
                parents=parents,
                values=values,
                branchvalues="total",
                textinfo="label+percent entry",
            )
        )
        fig.update_layout(
            showlegend=True,
            width=1800,
            height=900,
            margin=dict(l=200, r=100, t=50, b=50),
        )
        if save:
            self.__file_highcharts.append(fig)
        return fig

    def __create_incomes_expenses_evolution_chart(self, incomes_expenses_df: pd.DataFrame) -> str:
        """
        Génère un tableau de bord interactif Highcharts avec bascule Revenus/Dépenses.

        Cette méthode produit un graphique hybride (Colonnes + Courbes) permettant
        d'analyser l'évolution financière selon deux axes temporels (Annuel ou Mensuel)
        et d'observer soit la somme Total, soit la somme par Catégorie, soit la somme
        par sous-catégorie.

        Returns:
            str: Fragment HTML/JS complet incluant le CSS personnalisé (switch toggle),
                 les contrôles d'interface (radio, select) et la logique Highcharts.
        """

        incomes_expenses_df["operation_date"] = pd.to_datetime(incomes_expenses_df["operation_date"])
        incomes_expenses_df["year"] = incomes_expenses_df["operation_date"].dt.year
        incomes_expenses_df["month"] = incomes_expenses_df["operation_date"].dt.month

        years = sorted(incomes_expenses_df["year"].unique().tolist(), reverse=True)

        months_labels = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]

        incomes_list, expenses_list = self.__db.get_category_lists()

        incomes_df = incomes_expenses_df[incomes_expenses_df["category"].isin(incomes_list)]
        expenses_df = incomes_expenses_df[incomes_expenses_df["category"].isin(expenses_list)]

        def build_nested(df):
            result = {}
            for cat, cat_df in df.groupby("category"):
                result[cat] = {}
                for sub, sub_df in cat_df.groupby("sub_category"):
                    result[cat][sub] = {}
                    for y in sorted(years):
                        monthly = (
                            sub_df[sub_df["year"] == y]
                            .groupby("month")["amount"]
                            .sum()
                            .abs()
                            .reindex(range(1, 13), fill_value=0)
                            .tolist()
                        )
                        result[cat][sub][y] = [round(v, 2) for v in monthly]
            return result

        datasets = {
            "Revenus": build_nested(incomes_df),
            "Depenses": build_nested(expenses_df),
        }

        graph_id = "switch_" + str(uuid.uuid4()).replace("-", "_")

        return f"""
            <style>
            .switch_{graph_id} {{
                position: relative;
                display: inline-block;
                width: 50px;
                height: 26px;
                margin: 0 10px;
            }}
            .switch_{graph_id} input {{ opacity: 0; width: 0; height: 0; }}
            .slider_{graph_id} {{
                position: absolute;
                cursor: pointer;
                top:0; left:0; right:0; bottom:0;
                background:#2CAFFE;
                border-radius:34px;
                transition:.4s;
            }}
            .slider_{graph_id}:before {{
                position:absolute;
                content:"";
                height:18px; width:18px;
                left:4px; bottom:4px;
                background:white;
                border-radius:50%;
                transition:.4s;
            }}
            input:checked + .slider_{graph_id} {{
                background:#544FC5;
            }}
            input:checked + .slider_{graph_id}:before {{
                transform:translateX(24px);
            }}
            </style>

            <div style="background:#f9f9f9;padding:15px;border-radius:8px;">

                <span id="label_{graph_id}" style="font-weight:bold;color:#2CAFFE;">Dépenses</span>

                <label class="switch_{graph_id}">
                    <input type="checkbox" id="switch_{graph_id}">
                    <span class="slider_{graph_id}"></span>
                </label>

                <span style="margin-left:20px;">
                    <label><input type="radio" name="mode_{graph_id}" value="year" checked> Par année</label>
                    <label><input type="radio" name="mode_{graph_id}" value="month"> Par mois</label>
                </span>

                <select id="year_{graph_id}" style="display:none;">
                    {"".join([f'<option value="{y}">{y}</option>' for y in years])}
                </select>

                <span style="margin-left:20px;">
                    <label><input type="radio" name="gran_{graph_id}" value="total" checked> Total</label>
                    <label><input type="radio" name="gran_{graph_id}" value="cat"> Catégories</label>
                    <label><input type="radio" name="gran_{graph_id}" value="sub"> Sous-catégories</label>
                </span>

                <div id="chart_{graph_id}" style="height:850px;"></div>
            </div>

            <script>
            (function(){{
                const DATA = {json.dumps(datasets)};
                const years = {json.dumps(sorted(years))};
                const months = {json.dumps(months_labels)};

                let type = "Depenses";
                let mode = "year";
                let gran = "total";
                let chart;

                function round(v){{return Math.round((v+Number.EPSILON)*100)/100;}}

                function getColor(){{
                    return type === "Revenus" ? "#544FC5" : "#2CAFFE";
                }}

                function getRandomColor(i){{
                    const colors = Highcharts.getOptions().colors;
                    let base = Highcharts.color(colors[i % colors.length]);
                    return base.brighten((Math.random() - 0.5) * 0.3).get();
                }}

                function aggregate(selectedYear){{
                    let result;
                    if(mode==="year"){{
                        result = years.map(y =>
                            Object.values(DATA[type]).reduce((s,c)=>
                                s + Object.values(c).reduce((s2,sub)=>
                                    s2 + (sub[y]?.reduce((a,b)=>a+b,0)||0)
                                ,0)
                            ,0)
                        );
                    }} else {{
                        result = Array.from({{length:12}},(_,i)=>
                            Object.values(DATA[type]).reduce((s,c)=>
                                s + Object.values(c).reduce((s2,sub)=>
                                    s2 + (sub[selectedYear]?.[i]||0)
                                ,0)
                            ,0)
                        );
                    }}
                    return result.map(round);
                }}

                function pct(values){{
                    let res = [];
                    for(let i=0;i<values.length;i++){{
                        if(i===0 || values[i-1]===0){{
                            res.push(null);
                        }} else {{
                            let val = round((values[i]-values[i-1])/values[i-1]*100);
                            res.push(val);
                        }}
                    }}
                    return res;
                }}

                function buildSeries(){{
                    const y = parseInt(document.getElementById("year_{graph_id}").value)||years[years.length-1];
                    let series=[];
                    let totals;

                    if(gran==="total"){{
                        totals = aggregate(y);
                        series.push({{
                            name:type,
                            data:totals,
                            type:"column",
                            color:getColor()
                        }});
                    }}

                    if(gran==="cat"){{
                        Object.entries(DATA[type]).forEach(([cat,subs])=>{{
                            let data = mode==="year"
                                ? years.map(y=>Object.values(subs).reduce((s,sub)=>s+(sub[y]?.reduce((a,b)=>a+b,0)||0),0))
                                : Object.values(subs).reduce((arr,sub)=>arr.map((v,i)=>v+(sub[y]?.[i]||0)),Array(12).fill(0));

                            series.push({{
                                name:cat,
                                data:data.map(round),
                                type:"column",
                                stack:"t",
                                color:getRandomColor(series.length)
                            }});
                        }});
                    }}

                    if(gran==="sub"){{
                        Object.entries(DATA[type]).forEach(([cat,subs])=>{{
                            Object.entries(subs).forEach(([sub,dataObj])=>{{
                                let data = mode==="year"
                                    ? years.map(y=>dataObj[y]?.reduce((a,b)=>a+b,0)||0)
                                    : dataObj[y]||Array(12).fill(0);

                                series.push({{
                                    name:sub,
                                    data:data.map(round),
                                    type:"column",
                                    stack:"t",
                                    color:getRandomColor(series.length)
                                }});
                            }});
                        }});
                    }}

                    totals = aggregate(y);
                    const avg = totals.reduce((a,b)=>a+b,0)/totals.length;

                    series.push({{
                        name:"Moyenne",
                        data:Array(totals.length).fill(round(avg)),
                        type:"line",
                        dashStyle:"Dot",
                        color:"#FF0000",
                        marker:{{enabled:false}},
                        showInLegend:false
                    }});

                    if(mode==="year"){{
                        series.push({{
                            name:"Variation %",
                            data:pct(totals),
                            type:"line",
                            yAxis:1,
                            showInLegend:false,
                            lineWidth:2,
                            marker:{{enabled:true,symbol:'circle',radius:4}},
                            zones:[{{
                                value:0,
                                color:"#FF0000"
                            }}, {{
                                color:"#00E272"
                            }}]
                        }});
                    }}

                    return series;
                }}

                function render(){{
                    mode = document.querySelector('input[name="mode_{graph_id}"]:checked').value;
                    gran = document.querySelector('input[name="gran_{graph_id}"]:checked').value;

                    const categories = mode==="year"?years:months;

                    chart = Highcharts.chart("chart_{graph_id}",{{
                        chart:{{type:"column"}},
                        title:{{text:"Evolution "+type}},
                        xAxis:{{categories}},
                        yAxis:[
                            {{title:{{text:"€"}}}},
                            {{title:{{text:"%"}},opposite:true}}
                        ],
                        tooltip: {{
                            shared: false,
                            useHTML: true,
                            formatter: function () {{
                                const header = this.key; 
                                
                                const name = this.series.name;
                                const value = this.y;
                                const color = this.point.color;
                                let displayValue = value;
                                let suffix = name === "Variation %" ? "%" : "€";

                                let displayName = name === "Variation %" ? "Variation" : name;

                                let valueStyle = "";
                                if (name === "Variation %") {{
                                    const statusColor = value >= 0 ? "#00E272" : "#FF0000";
                                    const sign = value > 0 ? "+" : "";
                                    displayValue = sign + value;
                                    valueStyle = `style="color:${{statusColor}}"`;
                                }}

                                return `
                                    <span style="font-size: 10px">${{header}}</span><br/>
                                    <span style="color:${{color}}">\u25cf</span> ${{displayName}}: 
                                    <b><span ${{valueStyle}}>${{displayValue}}${{suffix}}</span></b>
                                `;
                            }}
                        }},
                        plotOptions:{{
                            column:{{stacking:gran==="total"?null:"normal"}}
                        }},
                        series:buildSeries()
                    }});
                }}

                document.getElementById("switch_{graph_id}").onchange = e=>{{
                    type = e.target.checked ? "Revenus":"Depenses";
                    document.getElementById("label_{graph_id}").innerText = type==="Revenus"?"Revenus":"Dépenses";
                    document.getElementById("label_{graph_id}").style.color = getColor();
                    render();
                }};

                document.querySelectorAll('input[name="mode_{graph_id}"]').forEach(r=>r.onchange=e=>{{
                    document.getElementById("year_{graph_id}").style.display = e.target.value==="month"?"inline":"none";
                    render();
                }});

                document.querySelectorAll('input[name="gran_{graph_id}"]').forEach(r=>r.onchange=render);
                document.getElementById("year_{graph_id}").onchange=render;

                render();
            }})();
            </script>
        """

    def __create_combined_charts(self, fig1: go.Figure, fig2: go.Figure, save: bool = True) -> go.Figure:
        """
        Combine deux graphiques sunburst côte à côte dans une seule figure.

        Args :
            fig1 (go.Figure) : premier graphique sunburst.
            fig2 (go.Figure) : second graphique sunburst.
            save (bool, optionnel) : indique si la figure combinée doit être sauvegardée dans la liste interne (par défaut True).

        Returns :
            go.Figure : objet figure Plotly contenant les deux graphiques combinés.
        """

        fig_combined = make_subplots(rows=1, cols=2, specs=[[{"type": "sunburst"}, {"type": "sunburst"}]])

        for trace in fig1.data:
            fig_combined.add_trace(trace, row=1, col=1)
        for trace in fig2.data:
            fig_combined.add_trace(trace, row=1, col=2)

        fig_combined.update_layout(
            showlegend=True,
            width=1800,
            height=900,
            margin=dict(l=200, r=100, t=50, b=50),
        )
        if save:
            self.__file_highcharts.append(fig_combined)
        return fig_combined

    def __create_incomes_expenses_bar_chart(self, incomes_expenses_df: pd.DataFrame) -> str:
        """
        Génère un histogramme comparatif empilé (Stacked Bar Chart) pour l'analyse globale.

        Cette méthode est le pivot de l'analyse comparative. Elle permet de visualiser
        simultanément les flux entrants (Revenus) et sortants (Dépenses) afin d'en
        déduire l'épargne nette.

        Returns:
            str: Code HTML/JS complet intégrant le sélecteur d'année, les options de vue
                 et le graphique Highcharts avec calcul automatique de l'épargne.
        """

        # 1. Récupération des catégories depuis la DB
        incomes_categories, _ = self.__db.get_category_lists()

        incomes_expenses_df["operation_date"] = pd.to_datetime(incomes_expenses_df["operation_date"])
        incomes_expenses_df["year"] = incomes_expenses_df["operation_date"].dt.year
        incomes_expenses_df["month"] = incomes_expenses_df["operation_date"].dt.month

        # Construction de la structure DATA
        data_dict = {}
        for cat, cat_df in incomes_expenses_df.groupby("category"):
            data_dict[cat] = {}
            for sub_cat, sub_df in cat_df.groupby("sub_category"):
                data_dict[cat][sub_cat] = {}
                for year, year_df in sub_df.groupby("year"):
                    monthly = (
                        year_df.groupby(year_df["operation_date"].dt.month)["amount"]
                        .sum()
                        .abs()
                        .reindex(range(1, 13), fill_value=0)
                        .tolist()
                    )
                    data_dict[cat][sub_cat][int(year)] = [round(m, 2) for m in monthly]

        json_data = json.dumps(data_dict, indent=2)
        incomes_list_json = json.dumps(incomes_categories, ensure_ascii=False)

        return f"""
            <div class="controls" style="margin-bottom: 20px;">
                <label><input type="radio" name="viewMode" value="years" checked /> Années</label>
                <label style="margin-left: 10px;"><input type="radio" name="viewMode" value="months" /> Mois</label>
                <select id="yearSelect" style="display:none; padding: 5px; margin-left:10px;"></select>
                
                <span style="margin-left: 25px; border-left: 1px solid #ccc; padding-left: 15px;">
                    <label><input type="radio" name="granularity" value="none" checked> Total</label>
                    <label style="margin-left: 15px;"><input type="radio" name="granularity" value="category"> Catégories</label>
                    <label style="margin-left: 15px;"><input type="radio" name="granularity" value="subcategory"> Sous-catégories</label>
                </span>
            </div>

            <div id="container_bar" style="width:100%; height:875px"></div>

            <script>
            (function() {{
                const DATA = {json_data};
                const incomesList = {incomes_list_json};
                let chart;
                let viewMode = 'years';
                let detailLevel = 'none'; 

                const months = ['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Août','Sep','Oct','Nov','Déc'];
                function round_amount(v) {{ return Math.round((v + Number.EPSILON) * 100) / 100; }}
                function isIncome(catName) {{ return incomesList.includes(catName); }}

                function getAllYears() {{
                    const yearSet = new Set();
                    Object.keys(DATA).forEach(cat => {{
                        Object.values(DATA[cat]).forEach(sub => {{
                            Object.keys(sub).forEach(y => yearSet.add(Number(y)));
                        }});
                    }});
                    return Array.from(yearSet).sort((a,b) => b - a);
                }}

                let allYears = getAllYears();
                let selectedYear = allYears.length > 0 ? allYears[0] : new Date().getFullYear();

                function buildSeries() {{
                    let categories = (viewMode === 'years') ? [...allYears].sort((a,b) => a - b) : months;
                    let columnSeries = []; 
                    let depSeries = [];
                    let revSeries = [];

                    if (detailLevel === 'none') {{
                        const depData = categories.map((label, idx) => {{
                            const y = (viewMode === 'years') ? label : selectedYear;
                            return round_amount(Object.keys(DATA).filter(c => !isIncome(c)).reduce((s, c) => {{
                                return s + Object.values(DATA[c]).reduce((s2, sub) => {{
                                    if (!sub[y]) return s2;
                                    return s2 + (viewMode === 'years' ? sub[y].reduce((a, b) => a + b, 0) : sub[y][idx]);
                                }}, 0);
                            }}, 0));
                        }});

                        const revData = categories.map((label, idx) => {{
                            const y = (viewMode === 'years') ? label : selectedYear;
                            return round_amount(Object.keys(DATA).filter(c => isIncome(c)).reduce((s, c) => {{
                                return s + Object.values(DATA[c]).reduce((s2, sub) => {{
                                    if (!sub[y]) return s2;
                                    return s2 + (viewMode === 'years' ? sub[y].reduce((a, b) => a + b, 0) : sub[y][idx]);
                                }}, 0);
                            }}, 0));
                        }});
                        
                        columnSeries.push({{ name: 'Dépenses', type: 'column', stack: 'depenses', color: '#2CAFFE', data: depData }});
                        columnSeries.push({{ name: 'Revenus', type: 'column', stack: 'revenus', color: '#544FC5', data: revData }});

                    }} else if (detailLevel === 'category') {{
                        Object.keys(DATA).forEach(cat => {{
                            const isInc = isIncome(cat);
                            const data = categories.map((label, idx) => {{
                                const y = (viewMode === 'years') ? label : selectedYear;
                                return round_amount(Object.values(DATA[cat]).reduce((s,sub) => s + (viewMode === 'years' ? (sub[y]?.reduce((a,b)=>a+b,0) || 0) : (sub[y]?.[idx] || 0)), 0));
                            }});
                            if (data.some(v=>v!==0)) {{
                                const s = {{ name: cat, type: 'column', stack: isInc ? 'revenus' : 'depenses', data }};
                                isInc ? revSeries.push(s) : depSeries.push(s);
                            }}
                        }});
                    }} else if (detailLevel === 'subcategory') {{
                        Object.keys(DATA).forEach(cat => {{
                            const isInc = isIncome(cat);
                            Object.keys(DATA[cat]).forEach(sub => {{
                                const data = categories.map((label, idx) => {{
                                    const y = (viewMode === 'years') ? label : selectedYear;
                                    return viewMode === 'years' ? round_amount(DATA[cat][sub][y]?.reduce((a,b)=>a+b,0) || 0) : round_amount(DATA[cat][sub][y]?.[idx] || 0);
                                }});
                                if (data.some(v=>v!==0)) {{
                                    const s = {{ name: sub, type: 'column', stack: isInc ? 'revenus' : 'depenses', data }};
                                    isInc ? revSeries.push(s) : depSeries.push(s);
                                }}
                            }});
                        }});
                    }}

                    // Fusionner avec tri alphabétique interne par groupe pour la propreté
                    if (detailLevel !== 'none') {{
                        depSeries.sort((a, b) => a.name.localeCompare(b.name));
                        revSeries.sort((a, b) => a.name.localeCompare(b.name));
                        columnSeries = [...depSeries, ...revSeries];
                    }}

                    // Ajout de la ligne d'épargne (toujours en dernier pour être au-dessus)
                    columnSeries.push({{
                        name:'Épargne nette', type:'line', yAxis:1, color:'#00E272',
                        data: categories.map(()=>0), lineWidth:2,
                        showInLegend: false,
                        marker:{{enabled:true,symbol:'circle',radius:4}},
                        zones:[{{value:0,color:'#FF0000'}},{{color:'#00E272'}}]
                    }});

                    return {{ categories, series: columnSeries }};
                }}

                function updateNetSavings() {{
                    const net = chart.series.find(s=>s.name==='Épargne nette');
                    if(!net) return;
                    const data = chart.xAxis[0].categories.map((_,i)=> {{
                        const r = chart.series.filter(s=>s.visible && s.options.stack==='revenus').reduce((s,ser)=> s + (ser.data[i]?.y || 0), 0);
                        const d = chart.series.filter(s=>s.visible && s.options.stack==='depenses').reduce((s,ser)=> s + (ser.data[i]?.y || 0), 0);
                        return round_amount(r - d);
                    }});
                    net.setData(data,true);
                }}

                function renderChart() {{
                    const data = buildSeries();
                    if (!chart) {{
                        chart = Highcharts.chart('container_bar', {{
                            chart: {{ type:'column' }},
                            title: {{ text: 'Analyse Financière Globale' }},
                            xAxis: {{ categories: data.categories, crosshair: true }},
                            yAxis:[ {{ title:{{text:'Montant (€)'}} }}, {{ title:{{text:'Épargne nette (€)'}}, opposite:true }} ],
                            tooltip: {{
                                shared: false, useHTML: true,
                                formatter: function() {{
                                    let color_amount;
                                    // On vérifie le stack défini dans la série
                                    const stack = this.series.userOptions.stack;
                                    const name = this.series.name;

                                    if (stack === 'depenses') {{
                                        color_amount = '#FF0000';
                                    }} else if (stack === 'revenus') {{
                                        color_amount = '#00E272';
                                    }} else if (name === 'Épargne nette') {{
                                        color_amount = this.y >= 0 ? '#00E272' : '#FF0000';
                                    }}

                                    let tooltipHtml = `<span style="color:${{color_amount}}">\u25cf</span> <b>${{this.series.name}}</b><br/>` +
                                                    `Montant: <b style="color:${{color_amount}}">${{this.y}} €</b>`;
                                    
                                    if(this.series.name === 'Épargne nette' && viewMode === 'years') {{
                                        const index = this.point.index;
                                        if (index > 0) {{
                                            const prevY = this.series.points[index - 1].y;
                                            if (prevY && prevY !== 0) {{
                                                const change = ((this.y - prevY) / Math.abs(prevY)) * 100;
                                                const color_v = change >= 0 ? '#00E272' : '#FF0000';
                                                tooltipHtml += `<br/>Variation: <b style="color:${{color_v}}">${{change > 0 ? '+' : ''}}${{change.toFixed(1)}}%</b>`;
                                            }}
                                        }}
                                    }}
                                    return tooltipHtml;
                                }}
                            }},
                            plotOptions: {{ 
                                column: {{ stacking:'normal' }}, 
                                series: {{ events: {{ legendItemClick: () => setTimeout(updateNetSavings, 50) }} }} 
                            }},
                            series: data.series
                        }});
                    }} else {{
                        while(chart.series.length) chart.series[0].remove(false);
                        data.series.forEach(s=>chart.addSeries(s,false));
                        chart.xAxis[0].setCategories(data.categories,false);
                        chart.redraw();
                    }}
                    updateNetSavings();
                }}

                // --- GESTION DES ÉVÉNEMENTS ---
                document.querySelectorAll('input[name="granularity"]').forEach(r => {{
                    r.onchange = (e) => {{ detailLevel = e.target.value; renderChart(); }};
                }});

                document.querySelectorAll('input[name="viewMode"]').forEach(r => r.onchange = () => {{
                    viewMode = r.value;
                    document.getElementById('yearSelect').style.display = viewMode==='months' ? 'inline' : 'none';
                    renderChart();
                }});

                const yearSelect = document.getElementById('yearSelect');
                allYears.forEach((y, i) => {{ 
                    const opt = document.createElement('option'); opt.value = y; opt.text = y; 
                    if(i===0) opt.selected = true; yearSelect.appendChild(opt); 
                }});
                yearSelect.onchange = () => {{ selectedYear = Number(yearSelect.value); renderChart(); }};

                renderChart();
            }})();
            </script>
        """

    def __generate_html_file(self, incomes_expenses_df: pd.DataFrame, incomes_or_expenses_empty: bool) -> None:
        """Assemble et compile l'ensemble des visualisations dans un document HTML unique."""

        js_files = [
            "src/static/js/highcharts.js",
            "src/static/js/sankey.js",
            "src/static/js/exporting.js",
        ]
        js_content = ""

        for js_file in js_files:
            try:
                with open(js_file, "r", encoding="utf-8") as f:
                    js_content += f"\n/* --- Source: {js_file} --- */\n{f.read()}"
            except FileNotFoundError:
                raise FileNotFoundError(f"Erreur de concaténation : {js_file} est manquant.")

        html = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <meta charset="utf-8">
            <title>Graphiques Financiers</title>
            <script>{js_content}</script>
            </head>
            <body>
        """

        # On vérifie qu'il y a pas des revenus ou des dépenses pour créer le graphique suivant
        if not incomes_or_expenses_empty:
            html += self.__create_incomes_expenses_bar_chart(incomes_expenses_df)

        html += self.__create_incomes_expenses_evolution_chart(incomes_expenses_df)

        # On vérifie qu'il y a pas des revenus ou des dépenses pour créer le graphique suivant
        if not incomes_or_expenses_empty:
            html += self.__create_sankey_chart(incomes_expenses_df)

        html += "</body></html>"

        self.__file_highcharts.append(html)
