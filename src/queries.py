# src/queries.py
import pandas as pd
from sqlalchemy import create_engine
import config


def _get_engine():
    return create_engine(config.DB_PATH)


# ─────────────────────────────────────────────────────────────────────────────
# FUNÇÕES STANDALONE — usam o engine SQLAlchemy via config.DB_PATH
# (úteis para scripts externos, testes, orquestração, etc.)
# ─────────────────────────────────────────────────────────────────────────────

def obter_visao_geral_paises():
    """Retorna todos os países com código, nome, região e grupo de rendimento."""
    engine = _get_engine()
    query = """
        SELECT codigo_pais, nome_pais, regiao, grupo_rendimento
        FROM dim_paises
        ORDER BY nome_pais;
    """
    return pd.read_sql(query, con=engine)


def obter_evolucao_temporal(codigo_pais, codigos_indicadores):
    """
    Retorna a evolução temporal de um ou mais indicadores para um país.

    Args:
        codigo_pais: código ISO do país (ex: 'PRT')
        codigos_indicadores: string ou lista de códigos de indicadores
    """
    engine = _get_engine()

    if isinstance(codigos_indicadores, str):
        codigos_indicadores = [codigos_indicadores]

    placeholder = ", ".join([f"'{c}'" for c in codigos_indicadores])

    query = f"""
        SELECT
            f.ano,
            i.nome_indicador,
            f.valor,
            f.valor_imf,
            f.crescimento_anual_pct,
            f.fonte
        FROM fact_indicadores_macro f
        JOIN dim_indicadores i ON f.codigo_indicador = i.codigo_indicador
        WHERE f.codigo_pais = '{codigo_pais}'
          AND f.codigo_indicador IN ({placeholder})
        ORDER BY f.ano ASC;
    """
    return pd.read_sql(query, con=engine)


def comparar_grupos_rendimento(codigo_indicador, ano):
    """
    Compara a média de um indicador entre grupos de rendimento para um dado ano.

    Args:
        codigo_indicador: código do indicador (ex: 'NY.GDP.PCAP.CD')
        ano: ano de referência (int)
    """
    engine = _get_engine()
    query = f"""
        SELECT
            p.grupo_rendimento,
            COUNT(DISTINCT f.codigo_pais) AS num_paises,
            AVG(f.valor)                  AS media_valor
        FROM fact_indicadores_macro f
        JOIN dim_paises p ON f.codigo_pais = p.codigo_pais
        WHERE f.codigo_indicador = '{codigo_indicador}'
          AND f.ano = {ano}
          AND p.grupo_rendimento IS NOT NULL
        GROUP BY p.grupo_rendimento
        ORDER BY media_valor DESC;
    """
    return pd.read_sql(query, con=engine)


def analisar_correlacao_investimento_crescimento(codigo_pais):
    """
    Retorna séries paralelas de formação bruta de capital (% PIB)
    e crescimento do PIB anual para análise de correlação.

    Args:
        codigo_pais: código ISO do país (ex: 'BRA')
    """
    engine = _get_engine()
    query = f"""
        SELECT
            f1.ano,
            f1.valor AS investimento_pct_pib,
            f2.valor AS crescimento_pib_anual
        FROM fact_indicadores_macro f1
        JOIN fact_indicadores_macro f2
            ON f1.codigo_pais = f2.codigo_pais
           AND f1.ano        = f2.ano
        WHERE f1.codigo_pais      = '{codigo_pais}'
          AND f1.codigo_indicador = 'NE.GDI.FTOT.ZS'   -- Formação bruta de capital (% do PIB)
          AND f2.codigo_indicador = 'NY.GDP.MKTP.KD.ZG' -- Crescimento do PIB (% anual)
        ORDER BY f1.ano ASC;
    """
    return pd.read_sql(query, con=engine)


def ranking_paises_por_indicador(codigo_indicador, ano, limite=10):
    """
    Retorna o ranking dos países com maior valor para um indicador num dado ano.

    Args:
        codigo_indicador: código do indicador
        ano: ano de referência (int)
        limite: número máximo de países a retornar (default 10)
    """
    engine = _get_engine()
    query = f"""
        SELECT
            p.nome_pais,
            p.regiao,
            f.valor
        FROM fact_indicadores_macro f
        JOIN dim_paises p ON f.codigo_pais = p.codigo_pais
        WHERE f.codigo_indicador = '{codigo_indicador}'
          AND f.ano = {ano}
          AND p.regiao != 'Aggregates'  -- Filtra agregados regionais
        ORDER BY f.valor DESC
        LIMIT {limite};
    """
    return pd.read_sql(query, con=engine)


# ─────────────────────────────────────────────────────────────────────────────
# FUNÇÕES DE DASHBOARD — aceitam conn (sqlite3 ou SQLAlchemy) para
# compatibilidade com o caching do Streamlit (@st.cache_data / @st.cache_resource)
# ─────────────────────────────────────────────────────────────────────────────

def carregar_indicadores(conn):
    """
    Retorna todos os indicadores disponíveis, ordenados por nome.

    Args:
        conn: conexão sqlite3 ou engine SQLAlchemy
    """
    return pd.read_sql(
        "SELECT * FROM dim_indicadores ORDER BY nome_indicador",
        conn,
    )


def carregar_paises(conn):
    """
    Retorna todos os países disponíveis, ordenados por nome.

    Args:
        conn: conexão sqlite3 ou engine SQLAlchemy
    """
    return pd.read_sql(
        "SELECT * FROM dim_paises ORDER BY nome_pais",
        conn,
    )


def carregar_facts(conn, indicador_code, pais_codes=None, ano_min=1990, ano_max=2023):
    """
    Retorna factos para um indicador, com filtros opcionais de países e período.

    Args:
        conn: conexão sqlite3 ou engine SQLAlchemy
        indicador_code: código do indicador (ex: 'NY.GDP.MKTP.KD.ZG')
        pais_codes: lista de códigos ISO de países (opcional)
        ano_min: ano de início do período
        ano_max: ano de fim do período
    """
    pais_filter = ""
    params = [indicador_code, ano_min, ano_max]

    if pais_codes:
        placeholders = ",".join(["?" for _ in pais_codes])
        pais_filter = f"AND f.codigo_pais IN ({placeholders})"
        params += pais_codes

    query = f"""
        SELECT
            f.ano,
            f.codigo_pais,
            p.nome_pais,
            p.regiao,
            p.grupo_rendimento,
            f.codigo_indicador,
            i.nome_indicador,
            f.valor
        FROM fact_indicadores_macro f
        JOIN dim_paises     p ON f.codigo_pais      = p.codigo_pais
        JOIN dim_indicadores i ON f.codigo_indicador = i.codigo_indicador
        WHERE f.codigo_indicador = ?
          AND f.ano BETWEEN ? AND ?
          {pais_filter}
        ORDER BY f.ano, p.nome_pais
    """
    return pd.read_sql(query, conn, params=params)


def carregar_todos_indicadores_por_ano(conn, ano):
    """
    Retorna todos os indicadores de todos os países para um ano específico.

    Args:
        conn: conexão sqlite3 ou engine SQLAlchemy
        ano: ano de referência (int)
    """
    query = """
        SELECT
            f.codigo_pais,
            p.nome_pais,
            p.regiao,
            p.grupo_rendimento,
            f.codigo_indicador,
            i.nome_indicador,
            f.valor
        FROM fact_indicadores_macro f
        JOIN dim_paises     p ON f.codigo_pais      = p.codigo_pais
        JOIN dim_indicadores i ON f.codigo_indicador = i.codigo_indicador
        WHERE f.ano = ?
        ORDER BY p.nome_pais, i.nome_indicador
    """
    return pd.read_sql(query, conn, params=[ano])


def carregar_facts_multi(conn, indicador_codes, ano_min=1990, ano_max=2023):
    """
    Retorna factos para múltiplos indicadores num período.

    Args:
        conn: conexão sqlite3 ou engine SQLAlchemy
        indicador_codes: lista de códigos de indicadores
        ano_min: ano de início do período
        ano_max: ano de fim do período
    """
    placeholders = ",".join(["?" for _ in indicador_codes])
    query = f"""
        SELECT
            f.ano,
            f.codigo_pais,
            p.nome_pais,
            p.regiao,
            p.grupo_rendimento,
            f.codigo_indicador,
            i.nome_indicador,
            f.valor
        FROM fact_indicadores_macro f
        JOIN dim_paises     p ON f.codigo_pais      = p.codigo_pais
        JOIN dim_indicadores i ON f.codigo_indicador = i.codigo_indicador
        WHERE f.codigo_indicador IN ({placeholders})
          AND f.ano BETWEEN ? AND ?
        ORDER BY f.ano, p.nome_pais
    """
    params = indicador_codes + [ano_min, ano_max]
    return pd.read_sql(query, conn, params=params)


def carregar_serie_temporal_por_paises(conn, indicador_code, paises_nomes):
    """
    Retorna a série temporal de um indicador filtrada por lista de nomes de países.
    Usada, por exemplo, para traçar a evolução dos top-N países no mapa global.

    Args:
        conn: conexão sqlite3 ou engine SQLAlchemy
        indicador_code: código do indicador
        paises_nomes: lista de nomes de países (ex: ['Portugal', 'Spain'])
    """
    placeholders = ",".join(["?" for _ in paises_nomes])
    query = f"""
        SELECT
            f.ano,
            p.nome_pais,
            f.valor
        FROM fact_indicadores_macro f
        JOIN dim_paises p ON f.codigo_pais = p.codigo_pais
        WHERE f.codigo_indicador = ?
          AND p.nome_pais IN ({placeholders})
        ORDER BY f.ano, p.nome_pais
    """
    return pd.read_sql(query, conn, params=[indicador_code] + paises_nomes)