# src/queries.py
import pandas as pd
from sqlalchemy import create_engine
import config

def _get_engine():

    return create_engine(config.DB_PATH)

def obter_visao_geral_paises():

    engine = _get_engine()
    query = """
        SELECT codigo_pais, nome_pais, regiao, grupo_rendimento 
        FROM dim_paises
        ORDER BY nome_pais;
    """
    return pd.read_sql(query, con=engine)

def obter_evolucao_temporal(codigo_pais, codigos_indicadores):

    engine = _get_engine()
    
    # Permitir passar um único indicador ou uma lista
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

    engine = _get_engine()
    query = f"""
        SELECT 
            p.grupo_rendimento,
            COUNT(DISTINCT f.codigo_pais) as num_paises,
            AVG(f.valor) as media_valor
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

    engine = _get_engine()
    query = f"""
        SELECT 
            f1.ano,
            f1.valor as investimento_pct_pib,
            f2.valor as crescimento_pib_anual
        FROM fact_indicadores_macro f1
        JOIN fact_indicadores_macro f2 ON f1.codigo_pais = f2.codigo_pais AND f1.ano = f2.ano
        WHERE f1.codigo_pais = '{codigo_pais}'
          AND f1.codigo_indicador = 'NE.GDI.FTOT.ZS' -- Formação bruta de capital (% do PIB)
          AND f2.codigo_indicador = 'NY.GDP.MKTP.KD.ZG' -- Crescimento do PIB (% anual)
        ORDER BY f1.ano ASC;
    """
    return pd.read_sql(query, con=engine)

def ranking_paises_por_indicador(codigo_indicador, ano, limite=10):

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
          AND p.regiao != 'Aggregates' -- Filtra agregados regionais se existirem
        ORDER BY f.valor DESC
        LIMIT {limite};
    """
    return pd.read_sql(query, con=engine)