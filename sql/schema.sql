-- sql/schema.sql

-- 1. Tabela com os dados dos Países (Dimensão)
CREATE TABLE IF NOT EXISTS dim_paises (
    codigo_pais VARCHAR(3) PRIMARY KEY,
    nome_pais VARCHAR(100) NOT NULL,
    regiao VARCHAR(100),
    grupo_rendimento VARCHAR(50)
);

-- 2. Tabela com os nomes dos Indicadores (Dimensão)
CREATE TABLE IF NOT EXISTS dim_indicadores (
    codigo_indicador VARCHAR(50) PRIMARY KEY,
    nome_indicador VARCHAR(150) NOT NULL
);

-- 3. Tabela Central com os Valores Numéricos (Tabela de Factos)
CREATE TABLE IF NOT EXISTS fact_indicadores_macro (
    id_fact SERIAL PRIMARY KEY,
    codigo_pais VARCHAR(3),
    codigo_indicador VARCHAR(50),
    ano INT NOT NULL,
    decada INT,
    valor NUMERIC,
    valor_imf NUMERIC,
    crescimento_anual_pct NUMERIC,
    fonte VARCHAR(20),
    -- Criação dos caminhos que ligam as tabelas (Integridade Referencial)
    FOREIGN KEY (codigo_pais) REFERENCES dim_paises(codigo_pais),
    FOREIGN KEY (codigo_indicador) REFERENCES dim_indicadores(codigo_indicador)
);