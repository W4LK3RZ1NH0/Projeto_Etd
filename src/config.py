LOG_FILE = "extraction.log"

# API do Banco Mundial (World Bank API v2)
BASE_URL = "http://api.worldbank.org/v2"
COUNTRIES = "ALL" 
INDICATOR = "NY.GDP.MKTP.CD"
PER_PAGE = 1000 

OUTPUT_API_FILE = "data/raw/api/gdp_all.json"

# Transformacao
# Inputs bulk
WDICSV_FILE       = "data/raw/bulk/WDICSV.csv"
WDICOUNTRY_FILE   = "data/raw/bulk/WDICountry.csv"
WDISERIES_FILE    = "data/raw/bulk/WDISeries.csv"
EXTRA_IMF_FILE    = "data/raw/extra/gdp.csv"

# Outputs
OUTPUT_STAGING_FILE   = "data/silver/wdi_staging.csv"
OUTPUT_CURATED_FILE   = "data/gold/wdi_gold.csv"
TRANSFORM_LOG_FILE    = "data/logs/transform.log"