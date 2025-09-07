"""pip install pandas openpyxl requests"""
import requests
import pandas as pd
from openpyxl import load_workbook
import time

def obtener_fixtures_desde_excel(api_key, archivo_entrada, archivo_salida):
    # Leer el archivo Excel de entrada
    try:
        df_ligas = pd.read_excel(archivo_entrada)
        print(f"Se leyeron {len(df_ligas)} registros de ligas del archivo {archivo_entrada}")
    except Exception as e:
        print(f"Error al leer el archivo Excel: {e}")
        return False

    # Preparar lista para almacenar todos los fixtures
    todos_fixtures = []

    # Configuración de la API
    base_url = "https://v3.football.api-sports.io"
    endpoint = "/fixtures"
    headers = {
        'x-apisports-key': api_key
    }

    # Procesar cada liga
    for index, row in df_ligas.iterrows():
        league_id = row['ID']
        season = row['Temporada']
        league_name = row['Nombre']

        print(f"\nObteniendo fixtures para {league_name} (ID: {league_id}), Temporada: {season}...")

        params = {
            "league": league_id,
            "season": season
        }

        try:
            response = requests.get(f"{base_url}{endpoint}", headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get('response'):
                for fixture in data['response']:
                    # Aplanar la estructura anidada del fixture
                    fixture_data = {
                        'League ID': league_id,
                        'League Name': league_name,
                        'Season': season,
                        'Fixture ID': fixture['fixture']['id'],
                        'Fecha': fixture['fixture']['date'],
                        'Estado': fixture['fixture']['status']['short'],
                        'Jornada': fixture['league']['round'],
                        'Local ID': fixture['teams']['home']['id'],
                        'Local': fixture['teams']['home']['name'],
                        'Visitante ID': fixture['teams']['away']['id'],
                        'Visitante': fixture['teams']['away']['name'],
                        'Goles Local': fixture['goals']['home'],
                        'Goles Visitante': fixture['goals']['away'],
                        'Estadio': fixture['fixture']['venue']['name'],
                        'Ciudad': fixture['fixture']['venue']['city'],
                        'Árbitro': fixture['fixture']['referee'],
                        'Timestamp': fixture['fixture']['timestamp']
                    }
                    todos_fixtures.append(fixture_data)

                print(f"Encontrados {len(data['response'])} partidos")
            else:
                print("No se encontraron fixtures para esta liga/temporada")

            # Esperar para no exceder límites de la API
            time.sleep(6)  # API-Football tiene límite de 10 solicitudes por minuto

        except requests.exceptions.RequestException as e:
            print(f"Error al obtener fixtures: {e}")
            continue

    # Guardar todos los fixtures en un nuevo Excel
    if todos_fixtures:
        df_fixtures = pd.DataFrame(todos_fixtures)
        try:
            df_fixtures.to_excel(archivo_salida, index=False, engine='openpyxl')
            print(f"\nTodos los fixtures guardados exitosamente en {archivo_salida}")
            print(f"Total de partidos registrados: {len(df_fixtures)}")
            return True
        except Exception as e:
            print(f"Error al guardar el archivo Excel: {e}")
            return False
    else:
        print("No se encontraron fixtures para guardar")
        return False

# Configuración
api_key = "6ec4d0f2e2466ea1d79888381a37f7f8"  # Reemplaza con tu API key
archivo_ligas = "competiciones_argentinas.xlsx"  # Archivo generado previamente
archivo_fixtures = "fixtures_argentinos.xlsx"  # Nuevo archivo a generar

# Ejecutar
obtener_fixtures_desde_excel(api_key, archivo_ligas, archivo_fixtures)