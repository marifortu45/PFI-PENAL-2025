import requests
import pandas as pd
import time
from tqdm import tqdm

def obtener_estadisticas_penales(api_key, archivo_fixtures, archivo_salida):
    # Leer el archivo de fixtures
    try:
        df_fixtures = pd.read_excel(archivo_fixtures)
        print(f"Se leyeron {len(df_fixtures)} partidos del archivo {archivo_fixtures}")
    except Exception as e:
        print(f"Error al leer el archivo Excel: {e}")
        return False

    # Preparar lista para almacenar estadísticas de penales
    stats_penales = []

    # Configuración API
    base_url = "https://v3.football.api-sports.io"
    endpoint = "/fixtures/players"
    headers = {'x-apisports-key': api_key}

    # Procesar cada fixture con barra de progreso
    for _, fixture in tqdm(df_fixtures.iterrows(), total=len(df_fixtures), desc="Procesando fixtures"):
        fixture_id = fixture['Fixture ID']
        
        try:
            response = requests.get(f"{base_url}{endpoint}", headers=headers, params={"fixture": fixture_id})
            response.raise_for_status()
            data = response.json()

            if data.get('response'):
                # Inicializar contadores para ambos equipos
                home_stats = {
                    'Fixture ID': fixture_id,
                    'League ID': fixture['League ID'],
                    'League Name': fixture['League Name'],
                    'Season': fixture['Season'],
                    'Team ID': fixture['Local ID'],
                    'Team': fixture['Local'],
                    'Is Home': True,
                    'Penalties Won': 0,
                    'Penalties Committed': 0,
                    'Penalties Scored': 0,
                    'Penalties Missed': 0,
                    'Penalties Saved': 0
                }
                
                away_stats = {
                    'Fixture ID': fixture_id,
                    'League ID': fixture['League ID'],
                    'Season': fixture['Season'],
                    'League Name': fixture['League Name'],
                    'Team ID': fixture['Visitante ID'],
                    'Team': fixture['Visitante'],
                    'Is Home': False,
                    'Penalties Won': 0,
                    'Penalties Committed': 0,
                    'Penalties Scored': 0,
                    'Penalties Missed': 0,
                    'Penalties Saved': 0
                }

                # Procesar datos de jugadores para ambos equipos
                for team_data in data['response']:
                    team_id = team_data['team']['id']
                    is_home = team_id == fixture['Local ID']
                    stats = home_stats if is_home else away_stats

                    for player in team_data['players']:
                        if 'penalty' in player['statistics'][0]:
                            penalty = player['statistics'][0]['penalty']
                            if penalty.get('won', 0):
                                stats['Penalties Won'] += penalty.get('won', 0)
                            if penalty.get('commited', 0):
                                stats['Penalties Committed'] += penalty.get('commited', 0)
                            if penalty.get('scored', 0):
                                stats['Penalties Scored'] += penalty.get('scored', 0)
                            if penalty.get('missed', 0):
                                stats['Penalties Missed'] += penalty.get('missed', 0)
                            if penalty.get('saved', 0):
                                stats['Penalties Saved'] += penalty.get('saved', 0)

                # Agregar estadísticas de ambos equipos
                stats_penales.append(home_stats)
                stats_penales.append(away_stats)

            # Respetar límite de la API
            time.sleep(0.25)

        except requests.exceptions.RequestException as e:
            print(f"\nError al obtener datos para fixture {fixture_id}: {e}")
            continue

    # Guardar en nuevo Excel
    if stats_penales:
        df_penales = pd.DataFrame(stats_penales)
        try:
            # Ordenar columnas
            column_order = [
                'Fixture ID', 'League ID', 'League Name', 'Season',
                'Team ID', 'Team', 'Is Home',
                'Penalties Won', 'Penalties Committed', 
                'Penalties Scored', 'Penalties Missed', 'Penalties Saved'
            ]
            df_penales = df_penales[column_order]
            
            df_penales.to_excel(archivo_salida, index=False, engine='openpyxl')
            print(f"\nEstadísticas de penales guardadas en {archivo_salida}")
            print(f"Total de registros: {len(df_penales)}")
            return True
        except Exception as e:
            print(f"\nError al guardar el archivo Excel: {e}")
            return False
    else:
        print("\nNo se encontraron estadísticas de penales")
        return False

# Configuración
api_key = "6ec4d0f2e2466ea1d79888381a37f7f8"  # Reemplaza con tu API key
archivo_partidos = "fixtures_argentinos.xlsx"  # Archivo de entrada
archivo_penales = "penales_equipos.xlsx"  # Archivo de salida

# Ejecutar
obtener_estadisticas_penales(api_key, archivo_partidos, archivo_penales)