# src/load.py
import os
import logging
import pandas as pd
from sqlalchemy import create_engine, text
import config

# Garantir que a pasta de logs existe antes de configurar o logging
os.makedirs("data/logs", exist_ok=True)
os.makedirs("data/db", exist_ok=True)

logging.basicConfig(
    filename="data/logs/load.log", level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s", encoding="utf-8"
)


def _criar_indices(engine):
    """Cria índices para otimizar queries analíticas do dashboard."""
    indices = [
        # Índices na tabela de factos (coluna mais consultada em filtros/joins)
        "CREATE INDEX IF NOT EXISTS idx_fact_pais       ON fact_indicadores_macro (codigo_pais)",
        "CREATE INDEX IF NOT EXISTS idx_fact_indicador  ON fact_indicadores_macro (codigo_indicador)",
        "CREATE INDEX IF NOT EXISTS idx_fact_ano        ON fact_indicadores_macro (ano)",
        "CREATE INDEX IF NOT EXISTS idx_fact_decada     ON fact_indicadores_macro (decada)",
        # Índice composto para lookups comuns no dashboard (país + indicador + ano)
        "CREATE INDEX IF NOT EXISTS idx_fact_pk         ON fact_indicadores_macro (codigo_pais, codigo_indicador, ano)",
    ]
    with engine.connect() as conn:
        for ddl in indices:
            conn.execute(text(ddl))
        conn.commit()
    logging.info(f"Índices criados/verificados: {len(indices)} índices.")


def carregar_camada_platinum():
    logging.info("==================================================")
    logging.info("INÍCIO DO CARREGAMENTO (LOAD) - SEMANA 3")
    logging.info("==================================================")
    print("A iniciar o carregamento para o Data Warehouse analítico...\n")

    engine = create_engine(config.DB_PATH)

    # Ler os dados finais validados na camada Gold
    caminho_gold = config.OUTPUT_CURATED_FILE
    if not os.path.exists(caminho_gold):
        logging.error(f"Ficheiro Gold não encontrado em: {caminho_gold}")
        print("[ERRO] Camada Gold não encontrada. Executar o transform.py primeiro.")
        return

    df_gold = pd.read_csv(caminho_gold)
    logging.info(f"Dados da camada Gold lidos com sucesso: {len(df_gold):,} linhas.")


    # POPULAR PAISES
    print("1/3 A estruturar e carregar 'dim_paises'...")
    df_paises = df_gold[["codigo_pais", "nome_pais", "regiao", "grupo_rendimento"]].drop_duplicates("codigo_pais")
    df_paises.to_sql("dim_paises", con=engine, if_exists="replace", index=False)
    logging.info(f"Dimensão 'dim_paises' carregada: {len(df_paises)} países únicos.")

    # POPULAR INDICADORES
    print("2/3 A estruturar e carregar 'dim_indicadores'...")
    df_indicadores = df_gold[["codigo_indicador", "nome_indicador"]].drop_duplicates("codigo_indicador")
    df_indicadores.to_sql("dim_indicadores", con=engine, if_exists="replace", index=False)
    logging.info(f"Dimensão 'dim_indicadores' carregada: {len(df_indicadores)} indicadores únicos.")

    # POPULAR TABELA DE FACTOS    
    print("3/3 A carregar tabela de factos 'fact_indicadores_macro'...")
    df_fact = df_gold[[
        "codigo_pais", "codigo_indicador", "ano", "decada",
        "valor", "valor_imf", "crescimento_anual_pct", "fonte"
    ]]

    try:
        existentes = pd.read_sql(
            "SELECT codigo_pais, codigo_indicador, ano FROM fact_indicadores_macro",
            con=engine
        )
        df_novos = df_fact.merge(
            existentes, on=["codigo_pais", "codigo_indicador", "ano"],
            how="left", indicator=True
        )
        df_novos = df_novos[df_novos["_merge"] == "left_only"].drop(columns=["_merge"])

        if df_novos.empty:
            print("  [INFO] Sem novos registos para inserir (base já atualizada).")
            logging.info("Carga incremental: 0 novos registos - base já estava atualizada.")
        else:
            df_novos.to_sql("fact_indicadores_macro", con=engine, if_exists="append", index=False)
            logging.info(f"Carga incremental: {len(df_novos):,} novos registos inseridos.")
            print(f"  [OK] {len(df_novos):,} novos registos inseridos (incremental).")

    except Exception:
        # Primeira execução - tabela ainda não existe
        df_fact.to_sql("fact_indicadores_macro", con=engine, if_exists="replace", index=False)
        logging.info(f"Carga inicial: {len(df_fact):,} registos inseridos.")
        print(f"  [OK] Carga inicial: {len(df_fact):,} registos.")

    # Criar índices após carga
    print("\nA criar índices de performance...")
    _criar_indices(engine)
    print("  [OK] Índices criados.")

    print("\nDados persistidos no motor de armazenamento.")

    
    # VALIDAÇÕES PÓS-CARGA
    
    print("\nA iniciar validações de integridade pós-carga...")
    logging.info("A executar testes de validação pós-carga...")

    # Validação 1: Volume
    linhas_banco = pd.read_sql(
        "SELECT COUNT(*) FROM fact_indicadores_macro", con=engine
    ).iloc[0, 0]
    if linhas_banco >= len(df_gold):
        print(f"  [OK] Teste de Volume: {linhas_banco:,} linhas no banco.")
        logging.info(f"Sucesso: Volume no banco ({linhas_banco:,}) >= Gold ({len(df_gold):,}).")
    else:
        print(f"  [AVISO] Divergência de dados detetada no volume das tabelas!")
        logging.warning(f"Divergência: Gold={len(df_gold)} | Banco={linhas_banco}")

    # Validação 2: Coerência Temporal
    anos_fora_limite = pd.read_sql(
        "SELECT COUNT(*) FROM fact_indicadores_macro WHERE ano < 1960 OR ano > 2026",
        con=engine
    ).iloc[0, 0]
    if anos_fora_limite == 0:
        print("  [OK] Teste de Coerência Temporal: Nenhum registo fora do intervalo 1960-2026.")
        logging.info("Sucesso: Todos os anos estão dentro do intervalo cronológico esperado.")
    else:
        print(f"  [ALERTA] Encontrados {anos_fora_limite} registos com anos inconsistentes.")
        logging.warning(f"Coerência: {anos_fora_limite} linhas fora do range padrão.")

    # Validação 3: Integridade Referencial (chaves órfãs)
    # Nota: SQLite não enforça FKs automaticamente - validamos programaticamente
    orfaos_pais = pd.read_sql("""
        SELECT COUNT(*) FROM fact_indicadores_macro f
        LEFT JOIN dim_paises p ON f.codigo_pais = p.codigo_pais
        WHERE p.codigo_pais IS NULL
    """, con=engine).iloc[0, 0]

    orfaos_indicador = pd.read_sql("""
        SELECT COUNT(*) FROM fact_indicadores_macro f
        LEFT JOIN dim_indicadores i ON f.codigo_indicador = i.codigo_indicador
        WHERE i.codigo_indicador IS NULL
    """, con=engine).iloc[0, 0]

    if orfaos_pais == 0:
        print("  [OK] Integridade Referencial (países): Sem chaves órfãs.")
        logging.info("Integridade referencial OK: 0 países órfãos na tabela de factos.")
    else:
        print(f"  [ALERTA] {orfaos_pais} registos na fact sem país correspondente na dim_paises!")
        logging.warning(f"Integridade: {orfaos_pais} chaves de país sem dimensão correspondente.")

    if orfaos_indicador == 0:
        print("  [OK] Integridade Referencial (indicadores): Sem chaves órfãs.")
        logging.info("Integridade referencial OK: 0 indicadores órfãos na tabela de factos.")
    else:
        print(f"  [ALERTA] {orfaos_indicador} registos na fact sem indicador correspondente!")
        logging.warning(f"Integridade: {orfaos_indicador} chaves de indicador sem dimensão correspondente.")

    logging.info("==================================================")
    logging.info("FIM DA FASE DE CARREGAMENTO COM SUCESSO")
    logging.info("==================================================")
    print("\nCarregamento da Semana 3 concluído!")


if __name__ == "__main__":
    carregar_camada_platinum()
