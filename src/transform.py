# src/transform.py
import os, json, logging
import pandas as pd
import config

logging.basicConfig(
    filename=config.TRANSFORM_LOG_FILE, level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s", encoding="utf-8"
)

# Indicadores a extrair do WDICSV — adiciona ou remove aqui conforme necessário
INDICADORES_GDP = [
    "NY.GDP.MKTP.CD",    # PIB (USD correntes)
    "NY.GDP.MKTP.KD",    # PIB (USD constantes 2015)
    "NY.GDP.MKTP.KD.ZG", # Crescimento do PIB (% anual)
    "NY.GDP.PCAP.CD",    # PIB per capita (USD correntes)
    "NY.GDP.PCAP.KD.ZG", # Crescimento do PIB per capita (% anual)
    "FP.CPI.TOTL.ZG",    # Inflação (% anual)
    "SL.UEM.TOTL.ZS",    # Desemprego (%)
    "NE.GDI.TOTL.ZS",    # Formação bruta de capital (% do PIB)
    "NE.EXP.GNFS.ZS",    # Exportações (% do PIB)
    "NE.IMP.GNFS.ZS",    # Importações (% do PIB)
]

# Códigos do World Bank que são agregados regionais, não países soberanos
AGREGADOS_WB = {
    "AFE","AFW","ARB","CEB","CSS","EAP","EAR","EAS","ECA","ECS","EMU","EUU",
    "FCS","HIC","HPC","IBD","IBT","IDA","IDB","IDX","LAC","LCN","LDC","LIC",
    "LMC","LMY","LTE","MEA","MIC","MNA","NAC","OED","OSS","PRE","PSS","PST",
    "SAS","SSA","SSF","SST","TEA","TEC","TLA","TMN","TSA","TSS","UMC","WLD",
}


# Ler o WDICSV em chunks (ficheiro grande) e converter de wide para long
def carregar_bulk(caminho: str) -> pd.DataFrame:
    logging.info(f"A ler WDICSV em chunks: {caminho}")
    chunks = []
    for chunk in pd.read_csv(caminho, chunksize=5000, encoding="utf-8"):
        filtrado = chunk[chunk["Indicator Code"].isin(INDICADORES_GDP)]
        if not filtrado.empty:
            chunks.append(filtrado)

    df_wide = pd.concat(chunks, ignore_index=True)
    logging.info(f"Bulk carregado: {len(df_wide)} séries encontradas no WDICSV")

    colunas_ano = [c for c in df_wide.columns if c.strip().isdigit()]
    df_long = df_wide.melt(
        id_vars=["Country Name", "Country Code", "Indicator Name", "Indicator Code"],
        value_vars=colunas_ano,
        var_name="ano", value_name="valor"
    ).rename(columns={
        "Country Name":   "nome_pais",
        "Country Code":   "codigo_pais",
        "Indicator Name": "nome_indicador",
        "Indicator Code": "codigo_indicador",
    })

    df_long["ano"]   = pd.to_numeric(df_long["ano"],   errors="coerce").astype("Int64")
    df_long["valor"] = pd.to_numeric(df_long["valor"], errors="coerce")
    df_long["fonte"] = "wdi_bulk"

    logging.info(f"Bulk convertido para formato longo: {len(df_long):,} linhas")
    return df_long


# Ler o JSON extraído da API do Banco Mundial
def carregar_api(caminho: str) -> pd.DataFrame:
    logging.info(f"A carregar JSON da API: {caminho}")
    with open(caminho, encoding="utf-8") as f:
        raw = json.load(f)

    metadados, registos = raw[0], raw[1]
    paginas = metadados.get("pages", 1)
    total   = metadados.get("total", len(registos))
    logging.info(f"API: {len(registos)} registos carregados (página 1 de {paginas}, total na API: {total})")
    if paginas > 1:
        logging.warning(f"ATENÇÃO: Apenas a página 1 de {paginas} foi extraída. Correr o extract com paginação completa.")

    df = pd.DataFrame([{
        "nome_pais":        r.get("country", {}).get("value"),
        "codigo_pais":      r.get("countryiso3code"),
        "codigo_indicador": r.get("indicator", {}).get("id"),
        "nome_indicador":   r.get("indicator", {}).get("value"),
        "ano":              r.get("date"),
        "valor":            r.get("value"),
        "fonte":            "api",
    } for r in registos])

    df["ano"]   = pd.to_numeric(df["ano"],   errors="coerce").astype("Int64")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df


# Juntar as fontes e enriquecer com metadados de países (camada Silver)
def construir_silver(df_bulk: pd.DataFrame, df_api: pd.DataFrame) -> pd.DataFrame:
    logging.info("A construir camada Silver...")
    df = pd.concat([df_bulk, df_api], ignore_index=True)
    logging.info(f"União bulk + API: {len(df):,} linhas")

    # Em conflito (mesmo país + indicador + ano), o valor da API tem prioridade
    antes = len(df)
    df = (df.sort_values("fonte", ascending=False)
            .drop_duplicates(subset=["codigo_pais", "codigo_indicador", "ano"]))
    logging.info(f"Desduplicação cross-source: {antes - len(df)} linhas removidas, {len(df):,} restantes")

    # Enriquecer com região e grupo de rendimento do WDICountry
    meta = pd.read_csv(config.WDICOUNTRY_FILE, encoding="utf-8")
    mapa = {}
    for col in meta.columns:
        cl = col.strip().lower()
        if "country code" in cl:   mapa[col] = "codigo_pais"
        elif "region" in cl:       mapa[col] = "regiao"
        elif "income group" in cl: mapa[col] = "grupo_rendimento"
    meta = meta.rename(columns=mapa)[["codigo_pais","regiao","grupo_rendimento"]].drop_duplicates("codigo_pais")

    df = df.merge(meta, on="codigo_pais", how="left")
    paises_sem_meta = df[df["regiao"].isnull()]["codigo_pais"].nunique()
    logging.info(f"Enriquecimento com WDICountry: {paises_sem_meta} países sem metadados (territórios não classificados)")

    df = df.sort_values(["codigo_pais", "codigo_indicador", "ano"]).reset_index(drop=True)
    logging.info(f"Camada Silver concluída: {len(df):,} linhas")
    return df


# Registar relatório de qualidade no log
def registar_qualidade(df: pd.DataFrame) -> None:
    logging.info("=" * 60)
    logging.info("RELATÓRIO DE QUALIDADE DE DADOS")
    logging.info("=" * 60)

    logging.info(f"Total de linhas na camada Silver: {len(df):,}")
    logging.info(f"Intervalo de anos: {int(df['ano'].min())} – {int(df['ano'].max())}")
    logging.info(f"Fontes presentes: {df['fonte'].value_counts().to_dict()}")
    logging.info(f"Países distintos: {df['codigo_pais'].nunique()}")
    logging.info(f"Indicadores distintos: {df['codigo_indicador'].nunique()}")

    logging.info("--- Valores em falta por indicador (%) ---")
    nulos = (
        df.groupby("codigo_indicador")["valor"]
          .apply(lambda s: round(s.isnull().mean() * 100, 1))
    )
    for indicador, pct in nulos.items():
        logging.info(f"  {indicador}: {pct}% nulos")

    logging.info("--- Nulos por coluna ---")
    for col, n in df.isnull().sum().items():
        if n > 0:
            logging.info(f"  {col}: {n:,} nulos ({round(n/len(df)*100,1)}%)")

    paises_sem_dados = (
        df.groupby("codigo_pais")["valor"]
          .apply(lambda s: s.notna().sum())
          .pipe(lambda s: s[s == 0].index.tolist())
    )
    if paises_sem_dados:
        logging.warning(f"Países sem nenhum valor em nenhum indicador: {paises_sem_dados}")
    else:
        logging.info("Todos os países têm pelo menos um valor registado.")

    valores_negativos = df[df["valor"] < 0][["codigo_pais","codigo_indicador","ano","valor"]]
    logging.info(f"Valores negativos inesperados (ex: PIB < 0): {len(valores_negativos)}")

    logging.info("=" * 60)
    logging.info("FIM DO RELATÓRIO DE QUALIDADE")
    logging.info("=" * 60)


# Filtrar e enriquecer para análise final (camada Gold)
def construir_gold(df: pd.DataFrame) -> pd.DataFrame:
    logging.info("A construir camada Gold...")

    antes = len(df)
    df = df[~df["codigo_pais"].isin(AGREGADOS_WB)].copy()
    logging.info(f"Agregados regionais removidos: {antes - len(df)} linhas")

    antes = len(df)
    df = df.dropna(subset=["valor"])
    logging.info(f"Linhas sem valor removidas: {antes - len(df)}, restam {len(df):,}")

    # Crescimento anual (%) por país e indicador
    df = df.sort_values(["codigo_pais", "codigo_indicador", "ano"])
    df["crescimento_anual_pct"] = (
        df.groupby(["codigo_pais", "codigo_indicador"])["valor"]
          .pct_change() * 100
    ).round(2)

    # Década
    df["decada"] = (df["ano"] // 10 * 10).astype("Int64")

    logging.info(f"Camada Gold concluída: {len(df):,} linhas")
    return df.reset_index(drop=True)


# --- MAIN ---
if __name__ == "__main__":
    print("A transformar dados...\n")
    logging.info("=" * 60)
    logging.info("INÍCIO DA TRANSFORMAÇÃO")
    logging.info("=" * 60)

    print("1/4  A ler WDICSV e API...")
    df_bulk = carregar_bulk(config.WDICSV_FILE)
    df_api  = carregar_api(config.OUTPUT_API_FILE)

    print("2/4  A construir camada Silver...")
    df_silver = construir_silver(df_bulk, df_api)
    os.makedirs(os.path.dirname(config.OUTPUT_STAGING_FILE), exist_ok=True)
    df_silver.to_csv(config.OUTPUT_STAGING_FILE, index=False, encoding="utf-8")
    print(f"     {len(df_silver):,} linhas -> {config.OUTPUT_STAGING_FILE}")

    print("3/4  A registar relatório de qualidade...")
    registar_qualidade(df_silver)
    print(f"     Relatório escrito em {config.TRANSFORM_LOG_FILE}")

    print("4/4  A construir camada Gold...")
    df_gold = construir_gold(df_silver)
    os.makedirs(os.path.dirname(config.OUTPUT_CURATED_FILE), exist_ok=True)
    df_gold.to_csv(config.OUTPUT_CURATED_FILE, index=False, encoding="utf-8")
    print(f"     {len(df_gold):,} linhas -> {config.OUTPUT_CURATED_FILE}")

    logging.info("TRANSFORMAÇÃO CONCLUÍDA COM SUCESSO")
    print("\nTransformação concluída!")