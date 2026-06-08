import os
import sys
import sqlite3

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Garante que o diretório src/ está no path para importar queries
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import queries  # noqa: E402  (importação local intencional após manipulação do path)

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "db", "analytics_dw.db")

st.set_page_config(
    page_title="Global Economy Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────
# ESTILO CSS
# ─────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0f1117; color: #e0e0e0; }
    .block-container { padding-top: 1.5rem; }

    /* Métricas */
    [data-testid="stMetric"] {
        background: #1c1f2b;
        border: 1px solid #2e3248;
        border-radius: 10px;
        padding: 1rem 1.2rem;
    }
    [data-testid="stMetricLabel"] { color: #8892b0; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; }
    [data-testid="stMetricValue"] { color: #64ffda; font-size: 1.8rem; font-weight: 700; }

    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #151820; border-right: 1px solid #2e3248; }

    /* Botões de navegação na sidebar */
    div[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        text-align: left;
        background: transparent;
        border: none;
        color: #8892b0;
        padding: 0.6rem 0.8rem;
        border-radius: 6px;
        font-size: 0.9rem;
        transition: all 0.15s ease;
    }
    div[data-testid="stSidebar"] .stButton > button:hover {
        background: #1c1f2b;
        color: #ccd6f6;
    }
    div[data-testid="stSidebar"] .stButton[data-active="true"] > button {
        background: #1c1f2b;
        color: #64ffda;
        border-left: 3px solid #64ffda;
    }

    /* Títulos */
    h1 { color: #ccd6f6; font-weight: 800; letter-spacing: -0.02em; }
    h2, h3 { color: #a8b2d8; }
    hr { border-color: #2e3248; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# CONEXÃO E FUNÇÕES DE DADOS
# A lógica SQL está centralizada em queries.py.
# Estas funções são wrappers finos que aplicam o caching do Streamlit.
# ─────────────────────────────────────────

@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


@st.cache_data(ttl=300)
def load_indicadores():
    return queries.carregar_indicadores(get_connection())


@st.cache_data(ttl=300)
def load_paises():
    return queries.carregar_paises(get_connection())


@st.cache_data(ttl=300)
def load_facts(indicador_code, pais_codes=None, ano_min=1990, ano_max=2023):
    return queries.carregar_facts(get_connection(), indicador_code, pais_codes, ano_min, ano_max)


@st.cache_data(ttl=300)
def load_todos_indicadores_por_ano(ano):
    return queries.carregar_todos_indicadores_por_ano(get_connection(), ano)


@st.cache_data(ttl=300)
def load_facts_multi(indicador_codes, ano_min=1990, ano_max=2023):
    return queries.carregar_facts_multi(get_connection(), indicador_codes, ano_min, ano_max)


# ─────────────────────────────────────────
# CARREGAR DADOS BASE
# ─────────────────────────────────────────
try:
    df_ind = load_indicadores()
    df_paises = load_paises()
except Exception as e:
    st.error(f"Erro ao ligar ao DW: {e}\n\nVerifica que `data/db/analytics_dw.db` existe.")
    st.stop()


# ─────────────────────────────────────────
# NAVEGAÇÃO — SIDEBAR
# ─────────────────────────────────────────
PAGES = {
    "🌍 Visão Global": "mapa_global",
    "🌎 Análise Continental": "analise_continental",
    "📈 Relações entre Indicadores": "relacoes_indicadores",
    "🏳️ Comparação entre Países": "comparacao_paises",
    "💡 Insights e Conclusões": "insights",
}

if "page" not in st.session_state:
    st.session_state.page = "mapa_global"

with st.sidebar:
    st.markdown("## 🌍 Global Economy")
    st.markdown("---")
    st.markdown("### Navegação")

    for label, key in PAGES.items():
        is_active = st.session_state.page == key
        btn_label = f"▶ {label}" if is_active else f"   {label}"
        if st.button(btn_label, key=f"nav_{key}", width='stretch'):
            st.session_state.page = key
            st.rerun()

page = st.session_state.page


# ═════════════════════════════════════════
# PÁGINA 1 — MAPA GLOBAL
# ═════════════════════════════════════════
if page == "mapa_global":
    st.title("🌐 Visão Global")
    st.markdown("Passa o cursor sobre cada país para ver todos os indicadores disponíveis.")

    # Carregar com ano default inicial
    if "map_ano" not in st.session_state:
        st.session_state.map_ano = 2020

    # Caixa de seleção do indicador — na própria página
    indicador_opcoes = dict(zip(df_ind["nome_indicador"], df_ind["codigo_indicador"]))
    ind_cor_nome = st.selectbox("🎨 Indicador para o mapa de calor", list(indicador_opcoes.keys()), key="map_ind")
    ind_cor_code = indicador_opcoes[ind_cor_nome]

    with st.spinner(f"A carregar dados de {st.session_state.map_ano}..."):
        df_ano = load_todos_indicadores_por_ano(st.session_state.map_ano)

    if df_ano.empty:
        st.warning(f"Sem dados para o ano {st.session_state.map_ano}.")
        st.stop()

    # Pivot: uma linha por país, uma coluna por indicador
    df_pivot = df_ano.pivot_table(
        index=["codigo_pais", "nome_pais", "regiao", "grupo_rendimento"],
        columns="nome_indicador",
        values="valor",
        aggfunc="first",
    ).reset_index()
    df_pivot.columns.name = None

    # Valor de cor = indicador selecionado na sidebar
    df_cor = df_ano[df_ano["codigo_indicador"] == ind_cor_code][
        ["codigo_pais", "valor"]
    ].rename(columns={"valor": "valor_cor"})
    df_pivot = df_pivot.merge(df_cor, on="codigo_pais", how="left")

    def build_hover(row):
        val = f"{row['valor_cor']:,.2f}" if pd.notna(row["valor_cor"]) else "N/D"
        return f"<b>{row['nome_pais']}</b><br>{ind_cor_nome}: {val}"

    df_pivot["hover_text"] = df_pivot.apply(build_hover, axis=1)

    fig_map = go.Figure(go.Choropleth(
        locations=df_pivot["codigo_pais"],
        z=df_pivot["valor_cor"],
        text=df_pivot["hover_text"],
        hovertemplate="%{text}<extra></extra>",
        colorscale="RdBu",
        reversescale=True,
        colorbar=dict(
            title=dict(text=ind_cor_nome[:35], font=dict(color="#a8b2d8")),
            tickfont=dict(color="#a8b2d8"),
            bgcolor="#1c1f2b",
            bordercolor="#2e3248",
        ),
        marker_line_color="#2e3248",
        marker_line_width=0.5,
    ))

    fig_map.update_layout(
        geo=dict(
            bgcolor="#0f1117",
            showframe=False,
            showcoastlines=True,
            coastlinecolor="#2e3248",
            showland=True,
            landcolor="#1c1f2b",
            showocean=True,
            oceancolor="#0f1117",
            showlakes=False,
            projection_type="equirectangular",
        ),
        paper_bgcolor="#0f1117",
        margin=dict(l=0, r=0, t=10, b=0),
        height=540,
    )

    st.plotly_chart(fig_map, width='stretch')

    # ── Slider de ano + métricas abaixo do mapa ──
    ano_novo = st.slider(
        "Ano",
        min_value=1960,
        max_value=2023,
        value=st.session_state.map_ano,
        key="slider_map_ano",
    )
    if ano_novo != st.session_state.map_ano:
        st.session_state.map_ano = ano_novo
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Países com dados", df_pivot["codigo_pais"].nunique())
    with col2:
        st.metric("Indicadores disponíveis", df_ind["codigo_indicador"].nunique())

    st.markdown("---")

    # ── Top 15 países ──
    ordem = st.radio("Ordenação", ["Decrescente", "Crescente"], horizontal=True, key="top15_ordem")
    ascending = ordem == "Crescente"

    df_top15 = (
        df_pivot[["nome_pais", "valor_cor"]]
        .dropna(subset=["valor_cor"])
        .sort_values("valor_cor", ascending=ascending)
        .head(15)
    )

    col_bar, col_line = st.columns(2)

    with col_bar:
        fig_bar = px.bar(
            df_top15,
            x="valor_cor",
            y="nome_pais",
            orientation="h",
            labels={"valor_cor": ind_cor_nome, "nome_pais": "País"},
            template="plotly_dark",
            color="valor_cor",
            color_continuous_scale="RdBu",
        )
        fig_bar.update_layout(
            plot_bgcolor="#1c1f2b",
            paper_bgcolor="#1c1f2b",
            showlegend=False,
            coloraxis_showscale=False,
            yaxis=dict(autorange="reversed" if not ascending else True),
            title=dict(text=f"Top 15 — {ind_cor_nome[:40]}", font=dict(color="#a8b2d8")),
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig_bar, width='stretch')

    with col_line:
        top7_paises = df_top15["nome_pais"].tolist()[:7]

        # Carregar série temporal para esses 7 países (query centralizada em queries.py)
        df_temporal = queries.carregar_serie_temporal_por_paises(
            get_connection(), ind_cor_code, top7_paises
        )

        fig_line = px.line(
            df_temporal,
            x="ano",
            y="valor",
            color="nome_pais",
            labels={"ano": "Ano", "valor": ind_cor_nome, "nome_pais": "País"},
            template="plotly_dark",
            color_discrete_sequence=px.colors.qualitative.Bold,
        )
        fig_line.update_layout(
            plot_bgcolor="#1c1f2b",
            paper_bgcolor="#1c1f2b",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="left", x=0, font=dict(size=9)),
            title=dict(text=f"Evolução Temporal — {ind_cor_nome[:40]}", font=dict(color="#a8b2d8")),
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig_line, width='stretch')


# ═════════════════════════════════════════
# PÁGINA 2 — ANÁLISE CONTINENTAL
# ═════════════════════════════════════════
elif page == "analise_continental":
    st.title("🌍 Análise Continental")

    # ── Seletores inline (como página 1) ──
    indicador_opcoes_c = dict(zip(df_ind["nome_indicador"], df_ind["codigo_indicador"]))
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        indicador_sel_nome = st.selectbox(
            "🎨 Indicador para o mapa de calor",
            list(indicador_opcoes_c.keys()),
            key="cont_ind",
        )
    with col_sel2:
        continentes = ["Todos"] + sorted(df_paises["regiao"].dropna().unique().tolist())
        continente_sel = st.selectbox("🌍 Continente / Região", continentes, key="cont_sel")

    indicador_sel_code = indicador_opcoes_c[indicador_sel_nome]

    # ── Session state para o ano do mapa continental ──
    if "cont_ano" not in st.session_state:
        st.session_state.cont_ano = 2020

    # ── Carregar dados do ano ──
    with st.spinner(f"A carregar dados de {st.session_state.cont_ano}..."):
        df_ano_c = load_todos_indicadores_por_ano(st.session_state.cont_ano)

    if df_ano_c.empty:
        st.warning(f"Sem dados para o ano {st.session_state.cont_ano}.")
        st.stop()

    # Filtrar pelo continente selecionado
    if continente_sel != "Todos":
        df_ano_c_filt = df_ano_c[df_ano_c["regiao"] == continente_sel].copy()
    else:
        df_ano_c_filt = df_ano_c.copy()

    # Valor de cor = indicador selecionado
    df_cor_c = df_ano_c_filt[df_ano_c_filt["codigo_indicador"] == indicador_sel_code][
        ["codigo_pais", "nome_pais", "regiao", "valor"]
    ].rename(columns={"valor": "valor_cor"})

    def build_hover_c(row):
        val = f"{row['valor_cor']:,.2f}" if pd.notna(row["valor_cor"]) else "N/D"
        return f"<b>{row['nome_pais']}</b><br>{indicador_sel_nome}: {val}"

    df_cor_c["hover_text"] = df_cor_c.apply(build_hover_c, axis=1)

    # Mapeamento região → scope plotly para zoom automático
    _scope_map = {
        "Europe & Central Asia": "europe",
        "East Asia & Pacific": "asia",
        "South Asia": "asia",
        "Middle East & North Africa": "africa",
        "Sub-Saharan Africa": "africa",
        "Latin America & Caribbean": "south america",
        "North America": "north america",
    }
    geo_scope = _scope_map.get(continente_sel, "world") if continente_sel != "Todos" else "world"

    fig_map_c = go.Figure(go.Choropleth(
        locations=df_cor_c["codigo_pais"],
        z=df_cor_c["valor_cor"],
        text=df_cor_c["hover_text"],
        hovertemplate="%{text}<extra></extra>",
        colorscale="RdBu",
        reversescale=True,
        colorbar=dict(
            title=dict(text=indicador_sel_nome[:35], font=dict(color="#a8b2d8")),
            tickfont=dict(color="#a8b2d8"),
            bgcolor="#1c1f2b",
            bordercolor="#2e3248",
        ),
        marker_line_color="#2e3248",
        marker_line_width=0.5,
    ))

    fig_map_c.update_layout(
        geo=dict(
            scope=geo_scope,
            bgcolor="#0f1117",
            showframe=False,
            showcoastlines=True,
            coastlinecolor="#2e3248",
            showland=True,
            landcolor="#1c1f2b",
            showocean=True,
            oceancolor="#0f1117",
            showlakes=False,
            projection_type="equirectangular",
            fitbounds="locations" if continente_sel != "Todos" else False,
        ),
        paper_bgcolor="#0f1117",
        margin=dict(l=0, r=0, t=10, b=0),
        height=500,
    )

    st.plotly_chart(fig_map_c, width='stretch')

    # ── Slider de ano (mesmo padrão da página 1) ──
    ano_novo_c = st.slider(
        "Ano",
        min_value=1960,
        max_value=2023,
        value=st.session_state.cont_ano,
        key="slider_cont_ano",
    )
    if ano_novo_c != st.session_state.cont_ano:
        st.session_state.cont_ano = ano_novo_c
        st.rerun()

    st.markdown("---")

    # ── A partir daqui usa o período completo para as análises abaixo ──
    # Carregar série temporal completa (1960-2023) filtrada pelo continente
    df_all = load_facts(indicador_sel_code, None, 1960, 2023)
    if continente_sel != "Todos":
        df_all = df_all[df_all["regiao"] == continente_sel].copy()

    titulo_cont = continente_sel if continente_sel != "Todos" else "Todos os Continentes"

    # Último ano com dados disponíveis
    ultimo_ano = df_all["ano"].max() if not df_all.empty else st.session_state.cont_ano
    df_ultimo = df_all[df_all["ano"] == ultimo_ano] if not df_all.empty else pd.DataFrame()

    if df_all.empty or df_ultimo.empty:
        st.warning("Sem dados suficientes para análise. Tenta outro indicador ou continente.")
        st.stop()

    st.markdown(f"**Indicador:** `{indicador_sel_nome}` · **Continente:** {titulo_cont}")

    # ── KPIs ──
    col1, col2, col3, col4, col5 = st.columns(5)
    media_val  = df_ultimo["valor"].mean()
    median_val = df_ultimo["valor"].median()
    top_row    = df_ultimo.dropna(subset=["valor"]).sort_values("valor", ascending=False)
    pais_max   = top_row.iloc[0]["nome_pais"] if not top_row.empty else "N/D"
    pais_min   = top_row.iloc[-1]["nome_pais"] if not top_row.empty else "N/D"
    n_paises   = df_ultimo["codigo_pais"].nunique()

    with col1:
        st.metric("Média", f"{media_val:,.2f}" if pd.notna(media_val) else "N/D")
    with col2:
        st.metric("Mediana", f"{median_val:,.2f}" if pd.notna(median_val) else "N/D")
    with col3:
        st.metric("País com maior valor", pais_max)
    with col4:
        st.metric("País com menor valor", pais_min)
    with col5:
        st.metric("Nº países analisados", n_paises)

    st.markdown("---")

    # ── Gráfico 1 — Distribuição ──
    st.subheader(f"📦 Distribuição de {indicador_sel_nome} — {titulo_cont} ({int(ultimo_ano)})")
    st.caption("Os países são homogéneos ou existem grandes disparidades?")

    col_box, col_hist = st.columns(2)
    with col_box:
        fig_box = px.box(
            df_ultimo.dropna(subset=["valor"]),
            y="valor", points="all", hover_name="nome_pais",
            labels={"valor": indicador_sel_nome},
            template="plotly_dark",
            color_discrete_sequence=["#64ffda"],
            title="Boxplot",
        )
        fig_box.update_layout(
            plot_bgcolor="#1c1f2b", paper_bgcolor="#1c1f2b",
            showlegend=False, title=dict(font=dict(color="#a8b2d8")),
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig_box, width='stretch')

    with col_hist:
        fig_hist = px.histogram(
            df_ultimo.dropna(subset=["valor"]),
            x="valor", nbins=20, hover_name="nome_pais",
            labels={"valor": indicador_sel_nome},
            template="plotly_dark",
            color_discrete_sequence=["#64ffda"],
            title="Histograma",
        )
        fig_hist.update_layout(
            plot_bgcolor="#1c1f2b", paper_bgcolor="#1c1f2b",
            showlegend=False, title=dict(font=dict(color="#a8b2d8")),
            margin=dict(t=40, b=20), bargap=0.05,
        )
        st.plotly_chart(fig_hist, width='stretch')

    st.markdown("---")

    # ── Gráfico 2 — Top 10 países ──
    st.subheader(f"🏆 Top 10 Países — {titulo_cont} ({int(ultimo_ano)})")
    df_top10 = (
        df_ultimo.dropna(subset=["valor"])
        .sort_values("valor", ascending=False)
        .head(10)
    )
    fig_top10 = px.bar(
        df_top10, x="valor", y="nome_pais", orientation="h",
        color="valor", color_continuous_scale="Teal",
        hover_name="nome_pais",
        labels={"valor": indicador_sel_nome, "nome_pais": "País"},
        template="plotly_dark",
    )
    fig_top10.update_layout(
        plot_bgcolor="#1c1f2b", paper_bgcolor="#1c1f2b",
        yaxis=dict(autorange="reversed"),
        coloraxis_showscale=False,
        margin=dict(t=20, b=20), height=380,
    )
    st.plotly_chart(fig_top10, width='stretch')

    st.markdown("---")

    # ── Gráfico 3 — Evolução da média continental ──
    st.subheader(f"📈 Evolução da Média Continental — {indicador_sel_nome}")
    st.caption("Como evoluíram os continentes ao longo das últimas décadas?")

    # Sempre carregar todos os continentes para comparação
    df_all_conts = load_facts(indicador_sel_code, None, 1960, 2023)
    df_media_cont = (
        df_all_conts.dropna(subset=["valor"])
        .groupby(["ano", "regiao"])["valor"]
        .mean()
        .reset_index()
        .rename(columns={"regiao": "Continente", "valor": f"Média — {indicador_sel_nome}"})
    )
    fig_linha = px.line(
        df_media_cont,
        x="ano", y=f"Média — {indicador_sel_nome}", color="Continente",
        labels={"ano": "Ano"},
        template="plotly_dark",
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    if continente_sel != "Todos":
        for trace in fig_linha.data:
            if trace.name == continente_sel:
                trace.line.width = 4
            else:
                trace.line.width = 1.5
                trace.opacity = 0.4
    fig_linha.update_layout(
        plot_bgcolor="#1c1f2b", paper_bgcolor="#1c1f2b",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=40, b=20),
    )
    st.plotly_chart(fig_linha, width='stretch')

    st.markdown("---")

    # ── Gráfico 4 — Participação no Top 20 mundial ──
    st.subheader(f"🌐 Participação no Top 20 Mundial ({int(ultimo_ano)})")
    st.caption("Quantos países de cada continente estão no Top 20 do indicador?")

    df_mundial_all = load_facts(indicador_sel_code, None, 1960, 2023)
    df_mundial_ano = df_mundial_all[df_mundial_all["ano"] == ultimo_ano].dropna(subset=["valor"])
    top20_paises = df_mundial_ano.sort_values("valor", ascending=False).head(20)["codigo_pais"].tolist()
    df_top20 = df_mundial_ano[df_mundial_ano["codigo_pais"].isin(top20_paises)]
    participacao = (
        df_top20.groupby("regiao")["codigo_pais"].nunique().reset_index()
        .rename(columns={"regiao": "Continente", "codigo_pais": "Países no Top 20"})
        .sort_values("Países no Top 20", ascending=False)
    )
    col_part_bar, col_part_tbl = st.columns([2, 1])
    with col_part_bar:
        fig_part = px.bar(
            participacao, x="Continente", y="Países no Top 20",
            color="Continente", text="Países no Top 20",
            template="plotly_dark",
            color_discrete_sequence=px.colors.qualitative.Bold,
        )
        fig_part.update_traces(textposition="outside")
        fig_part.update_layout(
            plot_bgcolor="#1c1f2b", paper_bgcolor="#1c1f2b",
            showlegend=False, margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig_part, width='stretch')
    with col_part_tbl:
        st.markdown("**Tabela resumo**")
        st.dataframe(participacao.reset_index(drop=True), width='stretch', hide_index=True)


# ═════════════════════════════════════════
# PÁGINA 3 — RELAÇÕES ENTRE INDICADORES
# ═════════════════════════════════════════
elif page == "relacoes_indicadores":
    import numpy as np
    from scipy import stats as scipy_stats

    st.title("📈 Relações entre Indicadores")
    st.markdown("Analisa correlações e tendências entre indicadores macroeconómicos chave.")

    # ── Identificar códigos dos indicadores relevantes ──
    ind_map = dict(zip(df_ind["nome_indicador"], df_ind["codigo_indicador"]))
    ind_map_rev = dict(zip(df_ind["codigo_indicador"], df_ind["nome_indicador"]))

    # Pares de análise disponíveis — o utilizador pode personalizar
    pares_disponiveis = [
        ("NY.GDP.MKTP.KD.ZG", "FP.CPI.TOTL.ZG"),   # GDP Growth vs Inflação
        ("NY.GDP.MKTP.KD.ZG", "SL.UEM.TOTL.ZS"),   # GDP Growth vs Desemprego
        ("NY.GDP.MKTP.KD.ZG", "NE.EXP.GNFS.ZS"),   # GDP Growth vs Exportações
        ("NY.GDP.MKTP.KD.ZG", "NE.GDI.TOTL.ZS"),   # GDP Growth vs Formação Bruta Capital
    ]

    # Fallback genérico: deixar o utilizador escolher qualquer par
    all_ind_nomes = list(ind_map.keys())

    st.markdown("### ⚙️ Configuração")
    col_cfg1, col_cfg2, col_cfg3 = st.columns(3)
    with col_cfg1:
        ind_x_nome = st.selectbox("Indicador X (eixo horizontal)", all_ind_nomes, key="rel_x",
                                   index=0 if all_ind_nomes else 0)
    with col_cfg2:
        ind_y_nome = st.selectbox("Indicador Y (eixo vertical)", all_ind_nomes, key="rel_y",
                                   index=min(1, len(all_ind_nomes)-1))
    with col_cfg3:
        ano_rel_min, ano_rel_max = st.slider(
            "Período", min_value=1960, max_value=2023,
            value=(2000, 2023), key="rel_periodo"
        )

    ind_x_code = ind_map[ind_x_nome]
    ind_y_code = ind_map[ind_y_nome]

    regiao_opts = ["Todos"] + sorted(df_paises["regiao"].dropna().unique().tolist())
    regiao_rel = st.selectbox("🌍 Filtrar por região", regiao_opts, key="rel_regiao")

    st.markdown("---")

    # ── Carregar dados ──
    df_rel = load_facts_multi([ind_x_code, ind_y_code], ano_rel_min, ano_rel_max)
    if regiao_rel != "Todos":
        df_rel = df_rel[df_rel["regiao"] == regiao_rel]

    df_pivot_rel = df_rel.pivot_table(
        index=["codigo_pais", "nome_pais", "regiao", "ano"],
        columns="codigo_indicador",
        values="valor",
        aggfunc="first",
    ).reset_index()
    df_pivot_rel.columns.name = None

    if ind_x_code not in df_pivot_rel.columns or ind_y_code not in df_pivot_rel.columns:
        st.warning("Não foram encontrados dados suficientes para os indicadores selecionados. Tenta outro par ou período.")
        st.stop()

    df_scatter = df_pivot_rel[[
        "codigo_pais", "nome_pais", "regiao", "ano", ind_x_code, ind_y_code
    ]].dropna(subset=[ind_x_code, ind_y_code]).copy()
    df_scatter = df_scatter.rename(columns={ind_x_code: "val_x", ind_y_code: "val_y"})

    if df_scatter.empty:
        st.warning("Sem dados para este par de indicadores no período/região selecionados.")
        st.stop()

    # ── Correlação ──
    corr_val, p_value = scipy_stats.pearsonr(df_scatter["val_x"], df_scatter["val_y"])
    slope, intercept, _, _, _ = scipy_stats.linregress(df_scatter["val_x"], df_scatter["val_y"])
    x_range = np.linspace(df_scatter["val_x"].min(), df_scatter["val_x"].max(), 200)
    y_range = slope * x_range + intercept

    # ── KPIs de correlação ──
    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    with col_k1:
        st.metric("Correlação de Pearson", f"{corr_val:.3f}")
    with col_k2:
        interpretacao = (
            "Forte positiva" if corr_val > 0.6 else
            "Moderada positiva" if corr_val > 0.3 else
            "Fraca positiva" if corr_val > 0 else
            "Forte negativa" if corr_val < -0.6 else
            "Moderada negativa" if corr_val < -0.3 else
            "Fraca negativa"
        )
        st.metric("Interpretação", interpretacao)
    with col_k3:
        st.metric("p-value", f"{p_value:.4f}")
    with col_k4:
        sig = "✅ Significativa" if p_value < 0.05 else "❌ Não significativa"
        st.metric("Significância (p<0.05)", sig)

    st.markdown("---")

    # ── Scatter plot com linha de regressão ──
    fig_scat = px.scatter(
        df_scatter,
        x="val_x", y="val_y",
        color="regiao",
        hover_name="nome_pais",
        hover_data={"ano": True, "val_x": ":.2f", "val_y": ":.2f"},
        labels={"val_x": ind_x_nome, "val_y": ind_y_nome, "regiao": "Região"},
        template="plotly_dark",
        opacity=0.65,
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    # Linha de regressão
    fig_scat.add_trace(go.Scatter(
        x=x_range, y=y_range,
        mode="lines",
        line=dict(color="#64ffda", width=2.5, dash="dash"),
        name=f"Regressão (r={corr_val:.2f})",
    ))
    fig_scat.update_layout(
        plot_bgcolor="#1c1f2b", paper_bgcolor="#1c1f2b",
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=40, b=20),
        height=520,
    )
    st.subheader(f"🔵 {ind_x_nome} vs {ind_y_nome}")
    st.plotly_chart(fig_scat, width='stretch')

    st.markdown("---")

    # ── Matriz de correlação rápida entre todos os indicadores (último ano com dados) ──
    st.subheader("🧮 Matriz de Correlação — Todos os Indicadores")
    st.caption("Correlação de Pearson calculada com os dados do período selecionado.")

    df_matrix = load_facts_multi(list(ind_map.values()), ano_rel_min, ano_rel_max)
    if regiao_rel != "Todos":
        df_matrix = df_matrix[df_matrix["regiao"] == regiao_rel]

    df_matrix_piv = df_matrix.pivot_table(
        index=["codigo_pais", "ano"],
        columns="nome_indicador",
        values="valor",
        aggfunc="first",
    )
    df_matrix_piv.columns.name = None
    corr_matrix = df_matrix_piv.corr(numeric_only=True)

    if not corr_matrix.empty:
        fig_heat = px.imshow(
            corr_matrix,
            color_continuous_scale="RdBu",
            zmin=-1, zmax=1,
            aspect="auto",
            template="plotly_dark",
            text_auto=".2f",
        )
        fig_heat.update_layout(
            plot_bgcolor="#1c1f2b", paper_bgcolor="#1c1f2b",
            margin=dict(t=20, b=20),
            height=500,
            coloraxis_colorbar=dict(tickfont=dict(color="#a8b2d8")),
        )
        fig_heat.update_traces(textfont=dict(size=9))
        st.plotly_chart(fig_heat, width='stretch')
    else:
        st.info("Dados insuficientes para calcular a matriz de correlação.")


# ═════════════════════════════════════════
# PÁGINA 4 — COMPARAÇÃO ENTRE PAÍSES
# ═════════════════════════════════════════
elif page == "comparacao_paises":
    st.title("🏳️ Comparação entre Países")
    st.markdown("Seleciona países e indicadores para comparar diretamente.")

    # ── Seletores ──
    todos_paises_nomes = sorted(df_paises["nome_pais"].dropna().unique().tolist())
    defaults_paises = [p for p in ["Portugal", "Spain", "Germany", "France", "United States"] if p in todos_paises_nomes]
    paises_sel = st.multiselect(
        "🌍 Países a comparar",
        todos_paises_nomes,
        default=defaults_paises[:4],
        key="comp_paises",
    )

    if not paises_sel:
        st.warning("Seleciona pelo menos um país.")
        st.stop()

    paises_codes = df_paises[df_paises["nome_pais"].isin(paises_sel)]["codigo_pais"].tolist()

    col_ci1, col_ci2 = st.columns(2)
    with col_ci1:
        ind_comp_nomes = st.multiselect(
            "📊 Indicadores a comparar",
            list(dict(zip(df_ind["nome_indicador"], df_ind["codigo_indicador"])).keys()),
            default=list(dict(zip(df_ind["nome_indicador"], df_ind["codigo_indicador"])).keys())[:4],
            key="comp_inds",
        )
    with col_ci2:
        ano_comp_min, ano_comp_max = st.slider(
            "Período",
            min_value=1960, max_value=2023,
            value=(2000, 2023), key="comp_periodo"
        )

    if not ind_comp_nomes:
        st.warning("Seleciona pelo menos um indicador.")
        st.stop()

    ind_comp_map = dict(zip(df_ind["nome_indicador"], df_ind["codigo_indicador"]))
    ind_comp_codes = [ind_comp_map[n] for n in ind_comp_nomes]

    st.markdown("---")

    df_comp = load_facts_multi(ind_comp_codes, ano_comp_min, ano_comp_max)
    df_comp = df_comp[df_comp["codigo_pais"].isin(paises_codes)].copy()

    if df_comp.empty:
        st.warning("Sem dados para a seleção atual.")
        st.stop()

    # ── Para cada indicador: linha temporal com os países selecionados ──
    st.subheader("📈 Evolução Temporal por Indicador")
    for ind_nome in ind_comp_nomes:
        ind_code = ind_comp_map[ind_nome]
        df_ind_comp = df_comp[df_comp["codigo_indicador"] == ind_code].dropna(subset=["valor"])
        if df_ind_comp.empty:
            st.caption(f"Sem dados: {ind_nome}")
            continue

        fig_comp = px.line(
            df_ind_comp,
            x="ano", y="valor", color="nome_pais",
            labels={"ano": "Ano", "valor": ind_nome, "nome_pais": "País"},
            template="plotly_dark",
            color_discrete_sequence=px.colors.qualitative.Bold,
            markers=True,
        )
        fig_comp.update_layout(
            plot_bgcolor="#1c1f2b", paper_bgcolor="#1c1f2b",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=50, b=20),
            title=dict(text=ind_nome, font=dict(color="#ccd6f6", size=14)),
            height=360,
        )
        st.plotly_chart(fig_comp, width='stretch')

    st.markdown("---")

    # ── Tabela comparativa — último ano disponível ──
    st.subheader("📋 Tabela Comparativa — Último Ano Disponível")
    ultimo_ano_comp = df_comp["ano"].max()
    df_ultimo_comp = df_comp[df_comp["ano"] == ultimo_ano_comp]
    df_tabela = df_ultimo_comp.pivot_table(
        index="nome_pais",
        columns="nome_indicador",
        values="valor",
        aggfunc="first",
    ).reset_index()
    df_tabela.columns.name = None
    df_tabela = df_tabela.rename(columns={"nome_pais": "País"})
    st.dataframe(df_tabela, width='stretch', hide_index=True)

    st.markdown("---")

    # ── Radar/spider chart — último ano ──
    st.subheader(f"🕸️ Radar de Comparação ({int(ultimo_ano_comp)})")
    st.caption("Valores normalizados (0–1) para permitir comparação entre escalas diferentes.")

    df_radar = df_ultimo_comp.pivot_table(
        index="nome_pais",
        columns="nome_indicador",
        values="valor",
        aggfunc="first",
    )
    if not df_radar.empty:
        df_norm = (df_radar - df_radar.min()) / (df_radar.max() - df_radar.min() + 1e-9)
        categorias = df_norm.columns.tolist()
        fig_radar = go.Figure()
        cores = px.colors.qualitative.Bold
        for i, pais in enumerate(df_norm.index):
            vals = df_norm.loc[pais].tolist()
            vals += [vals[0]]  # fechar o polígono
            fig_radar.add_trace(go.Scatterpolar(
                r=vals,
                theta=categorias + [categorias[0]],
                fill="toself",
                name=pais,
                line=dict(color=cores[i % len(cores)]),
                opacity=0.6,
            ))
        fig_radar.update_layout(
            polar=dict(
                bgcolor="#1c1f2b",
                radialaxis=dict(visible=True, range=[0, 1], color="#8892b0"),
                angularaxis=dict(color="#8892b0"),
            ),
            paper_bgcolor="#0f1117",
            legend=dict(font=dict(color="#a8b2d8")),
            margin=dict(t=40, b=40),
            height=480,
        )
        st.plotly_chart(fig_radar, width='stretch')


# ═════════════════════════════════════════
# PÁGINA 5 — INSIGHTS E CONCLUSÕES
# ═════════════════════════════════════════
elif page == "insights":
    st.title("💡 Insights e Conclusões")
    st.markdown("Síntese analítica das principais descobertas do projeto.")

    st.markdown("---")

    # ── Resumo global ──
    ultimo_ano_ins = 2022
    df_ins = load_todos_indicadores_por_ano(ultimo_ano_ins)

    n_paises_total = df_ins["codigo_pais"].nunique()
    n_indicadores = df_ins["codigo_indicador"].nunique()
    n_obs = len(df_ins.dropna(subset=["valor"]))

    col_i1, col_i2, col_i3 = st.columns(3)
    with col_i1:
        st.metric("Países com dados", n_paises_total)
    with col_i2:
        st.metric("Indicadores carregados", n_indicadores)
    with col_i3:
        st.metric(f"Observações em {ultimo_ano_ins}", n_obs)

    st.markdown("---")

    # ── Insights estáticos + dinâmicos ──
    st.subheader("🔍 Principais Observações")

    insights = [
        ("🌍 Disparidades regionais", "Os indicadores económicos mostram grandes assimetrias entre regiões. A Europa e a América do Norte concentram consistentemente os países com maior PIB per capita, enquanto a África Subsaariana apresenta os menores valores."),
        ("📈 Crescimento e Inflação", "Existe uma correlação moderada negativa entre crescimento económico e inflação elevada. Países com inflação controlada tendem a apresentar crescimento mais estável no longo prazo."),
        ("🎓 Educação e Desenvolvimento", "Os países com maior cobertura de ensino superior apresentam, em média, rendimentos per capita significativamente mais altos — sugerindo que o capital humano é um preditor relevante do desenvolvimento económico."),
        ("📉 Desemprego pós-crise", "Os dados revelam aumentos abruptos de desemprego em torno das crises de 2008–2009 e 2020, com recuperações distintas por região e grupo de rendimento."),
        ("🌿 Transição energética", "Países de rendimento alto mostram uma tendência de redução gradual da intensidade energética por unidade de PIB, compatível com avanços na eficiência e nas energias renováveis."),
        ("🔗 Integração e exportações", "As economias mais abertas ao comércio (alta proporção exportações/PIB) apresentam menor volatilidade nos indicadores de crescimento, possivelmente devido à diversificação dos mercados."),
    ]

    for titulo, texto in insights:
        with st.expander(titulo, expanded=True):
            st.markdown(texto)

    st.markdown("---")

    # ── Gráfico: distribuição de PIB per capita por grupo de rendimento ──
    st.subheader("📊 Distribuição do PIB per capita por Grupo de Rendimento")

    ind_gdp_pc_opts = df_ins[df_ins["codigo_indicador"].str.contains("NY.GDP.PCAP", na=False)]
    if not ind_gdp_pc_opts.empty:
        df_box_ins = ind_gdp_pc_opts.dropna(subset=["valor"])
        fig_box_ins = px.box(
            df_box_ins,
            x="grupo_rendimento", y="valor",
            color="grupo_rendimento",
            points="outliers",
            hover_name="nome_pais",
            labels={"valor": "PIB per capita (USD)", "grupo_rendimento": "Grupo de Rendimento"},
            template="plotly_dark",
            color_discrete_sequence=px.colors.qualitative.Bold,
        )
        fig_box_ins.update_layout(
            plot_bgcolor="#1c1f2b", paper_bgcolor="#1c1f2b",
            showlegend=False,
            margin=dict(t=20, b=20),
            height=400,
        )
        st.plotly_chart(fig_box_ins, width='stretch')
    else:
        st.info("Indicador de PIB per capita não encontrado na base de dados.")

    st.markdown("---")

    # ── Top 5 melhorias absolutas (PIB per capita) ──
    st.subheader("🚀 Top 5 Países com Maior Crescimento de PIB per capita (2000–2022)")
    if not ind_gdp_pc_opts.empty:
        ind_gdp_pc_code = ind_gdp_pc_opts["codigo_indicador"].iloc[0]
        df_gdp_series = load_facts(ind_gdp_pc_code, None, 2000, 2022)
        df_2000 = df_gdp_series[df_gdp_series["ano"] == 2000][["codigo_pais", "nome_pais", "valor"]].rename(columns={"valor": "val_2000"})
        df_2022 = df_gdp_series[df_gdp_series["ano"] == 2022][["codigo_pais", "valor"]].rename(columns={"valor": "val_2022"})
        df_delta = df_2000.merge(df_2022, on="codigo_pais").dropna()
        df_delta["variação"] = df_delta["val_2022"] - df_delta["val_2000"]
        df_delta["variação (%)"] = ((df_delta["val_2022"] / df_delta["val_2000"]) - 1) * 100
        top5 = df_delta.sort_values("variação (%)", ascending=False).head(5)

        fig_top5 = px.bar(
            top5, x="nome_pais", y="variação (%)",
            color="variação (%)", color_continuous_scale="Teal",
            text=top5["variação (%)"].apply(lambda v: f"+{v:.0f}%"),
            labels={"nome_pais": "País", "variação (%)": "Variação (%)"},
            template="plotly_dark",
        )
        fig_top5.update_traces(textposition="outside")
        fig_top5.update_layout(
            plot_bgcolor="#1c1f2b", paper_bgcolor="#1c1f2b",
            coloraxis_showscale=False,
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig_top5, width='stretch')

    st.markdown("---")

    st.subheader("📚 Limitações e Próximos Passos")
    with st.expander("Ver limitações", expanded=False):
        st.markdown("""
- **Dados em falta:** alguns países e indicadores têm séries incompletas, especialmente antes de 1980.
- **Qualidade da fonte:** os dados do World Bank são consolidados e fiáveis, mas podem divergir de fontes nacionais.
- **Causalidade vs correlação:** as relações observadas são correlações; inferência causal requer modelos mais robustos.
- **Granularidade:** os dados são anuais — flutuações intra-anuais não são capturadas.
        """)
    with st.expander("Próximos passos", expanded=False):
        st.markdown("""
- Integrar dados do FMI e OCDE para cruzamento adicional.
- Adicionar modelos de previsão (ARIMA, Prophet) para projeções temporais.
- Incluir dados sub-nacionais (regiões/províncias) para análises mais granulares.
- Desenvolver alertas automáticos para anomalias nos indicadores.
        """)