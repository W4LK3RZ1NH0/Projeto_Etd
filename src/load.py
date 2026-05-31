# src/load.py
import os
import logging
import pandas as pd
from sqlalchemy import create_engine
import config

# Configuração do Log oficial da Fase de Carregamento
logging.basicConfig(
    filename="data/logs/load.log", level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s", encoding="utf-8"
)

def carregar_camada_platinum():
    logging.info("==================================================")
    logging.info("INÍCIO DO CARREGAMENTO (LOAD) - SEMANA 3")
    logging.info("==================================================")
    print("A iniciar o carregamento para o Data Warehouse analítico...\n")
    
    # 1. Configurar Conexão (Centralizada via config)
    # Atualmente usa SQLite local, mas a infraestrutura está pronta para PostgreSQL
    engine = create_engine("sqlite:///data/db/analytics_dw.db")
    
    # 2. Ler os dados finais validados na camada Gold
    caminho_gold = config.OUTPUT_CURATED_FILE  # Usa o caminho centralizado do config
    if not os.path.exists(caminho_gold):
        logging.error(f"Ficheiro Gold não encontrado em: {caminho_gold}")
        print(f"[ERRO] Camada Gold não encontrada. Executar o transform.py primeiro.")
        return
        
    df_gold = pd.read_csv(caminho_gold)
    logging.info(f"Dados da camada Gold lidos com sucesso: {len(df_gold):,} linhas.")
    
    # 3. Povoar a Dimensão de Países (Garantindo registos únicos)
    print("1/3 A estruturar e carregar 'dim_paises'...")
    df_paises = df_gold[["codigo_pais", "nome_pais", "regiao", "grupo_rendimento"]].drop_duplicates("codigo_pais")
    df_paises.to_sql("dim_paises", con=engine, if_exists="replace", index=False)
    logging.info(f"Dimensão 'dim_paises' carregada: {len(df_paises)} países únicos.")
    
    # 4. Povoar a Dimensão de Indicadores (Garantindo registos únicos)
    print("2/3 A estruturar e carregar 'dim_indicadores'...")
    df_indicadores = df_gold[["codigo_indicador", "nome_indicador"]].drop_duplicates("codigo_indicador")
    df_indicadores.to_sql("dim_indicadores", con=engine, if_exists="replace", index=False)
    logging.info(f"Dimensão 'dim_indicadores' carregada: {len(df_indicadores)} indicadores únicos.")
    
    # 5. Povoar a Tabela de Factos Central
    print("3/3 A carregar tabela de factos 'fact_indicadores_macro'...")
    df_fact = df_gold[["codigo_pais", "codigo_indicador", "ano", "decada", "valor", "valor_imf", "crescimento_anual_pct", "fonte"]]
    df_fact.to_sql("fact_indicadores_macro", con=engine, if_exists="replace", index=False)
    logging.info(f"Tabela de Factos carregada com sucesso: {len(df_fact):,} linhas.")
    
    print("\nDados persistidos no motor de armazenamento.")
    
    # =========================================================================
    # ATIVIDADE-CHAVE: Validação pós-carga, integridade e coerência
    # =========================================================================
    print("\nA iniciar validações de integridade pós-carga...")
    logging.info("A executar testes de validação pós-carga...")
    
    # Validação 1: Verificação de volume (Contagem de linhas)
    linhas_banco = pd.read_sql("SELECT COUNT(*) FROM fact_indicadores_macro", con=engine).iloc[0, 0]
    if linhas_banco == len(df_gold):
        print(f"  [OK] Teste de Volume: {linhas_banco:,} linhas integradas corretamente.")
        logging.info("Sucesso: A contagem de linhas no banco bate com o ficheiro Gold.")
    else:
        print(f"  [AVISO] Divergência de dados detetada no volume das tabelas!")
        logging.warning(f"Divergência: Gold={len(df_gold)} | Banco={linhas_banco}")
        
    # Validação 2: Coerência Temporal (Detetar anos fora da fronteira do projeto)
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

    logging.info("==================================================")
    logging.info("FIM DA FASE DE CARREGAMENTO COM SUCESSO")
    logging.info("==================================================")
    print("\nCarregamento da Semana 3 concluído!")

if __name__ == "__main__":
    carregar_camada_platinum()