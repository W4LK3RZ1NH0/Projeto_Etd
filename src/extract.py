# src/extract.py
import os
import logging
import requests
import json
import config

logging.basicConfig(
    filename=config.LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

def extract_api_data():
    logging.info("Iniciando o processo de extração da API do Banco Mundial...")
    print("A iniciar a extração de dados da API...")
    
    url = f"{config.BASE_URL}/country/{config.COUNTRIES}/indicator/{config.INDICATOR}?format=json&per_page={config.PER_PAGE}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        with open(config.OUTPUT_API_FILE, "w", encoding="utf-8") as f:
            json.dump(response.json(), f, indent=4, ensure_ascii=False)
            
        logging.info(f"Sucesso: Dados guardados em {config.OUTPUT_API_FILE}")
        print("Extração da API concluída com sucesso! Ficheiro gerado.")
        
    except Exception as e:
        error_msg = f"Erro crítico na extração da API: {e}"
        logging.error(error_msg)
        print(f"Erro: {error_msg}. Verifica o ficheiro {config.LOG_FILE}")

if __name__ == "__main__":
    extract_api_data()