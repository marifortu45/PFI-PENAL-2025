"""pip install tqdm"""
import requests
import pandas as pd
import time
from tqdm import tqdm

def obtener_todos_eventos(api_key, archivo_fixtures, archivo_salida):
    # Leer el archivo de fixtures
    try:
        df_fixtures = pd.read_excel(archivo_fixtures)
        print(f"Se leyeron {len(df_fixtures)} partidos del archivo {archivo_fixtures}")
    except Exception as e:
        print(f"Error al leer el archivo Excel: {e}")
        return False

    # Preparar lista para almacenar todos los eventos
    todos_eventos = []

    # Configuración API
    base_url = "https://v3.football.api-sports.io"
    endpoint = "/fixtures/events"
    headers = {'x-apisports-key': api_key}

    # Procesar cada fixture con barra de progreso
    for _, fixture in tqdm(df_fixtures.iterrows(), total=len(df_fixtures), desc="Procesando fixtures"):
        fixture_id = fixture['Fixture ID']
        params = {"fixture": fixture_id}  # Removido el filtro por goals

        try:
            response = requests.get(f"{base_url}{endpoint}", headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get('response'):
                for event in data['response']:
                    # Determinar equipo oponente
                    if event['team']['id'] == fixture['Local ID']:
                        oponente = fixture['Visitante']
                        oponente_id = fixture['Visitante ID']
                    else:
                        oponente = fixture['Local']
                        oponente_id = fixture['Local ID']
                    
                    # Extraer todos los campos disponibles
                    evento_data = {
                        'Fixture ID': fixture_id,
                        'League ID': fixture['League ID'],
                        'League Name': fixture['League Name'],
                        'Season': fixture['Season'],
                        'Event ID': event.get('id'),
                        'Tipo Evento': event.get('type'),
                        'Detalle Evento': event.get('detail'),
                        'Minuto': event['time']['elapsed'],
                        'Minuto Extra': event['time'].get('extra'),
                        'Equipo': event['team']['name'],
                        'Equipo ID': event['team']['id'],
                        'Equipo Oponente': oponente,
                        'Equipo Oponente ID': oponente_id,
                        'Jugador': event['player']['name'] if 'player' in event else None,
                        'Jugador ID': event['player']['id'] if 'player' in event else None,
                        'Asistente': event['assist']['name'] if 'assist' in event and event['assist'] else None,
                        'Asistente ID': event['assist']['id'] if 'assist' in event and event['assist'] else None,
                        'Comentario': event.get('comments')
                    }
                    todos_eventos.append(evento_data)

            # Tiempo de espera reducido
            time.sleep(0.25)  # 0.25 segundos entre requests

        except requests.exceptions.RequestException as e:
            print(f"\nError al obtener eventos para fixture {fixture_id}: {e}")
            continue

    # Guardar en nuevo Excel
    if todos_eventos:
        df_eventos = pd.DataFrame(todos_eventos)
        try:
            # Ordenar columnas lógicamente
            column_order = [
                'Fixture ID', 'League ID', 'League Name', 'Season',
                'Event ID', 'Tipo Evento', 'Detalle Evento',
                'Minuto', 'Minuto Extra',
                'Equipo', 'Equipo ID', 'Equipo Oponente', 'Equipo Oponente ID',
                'Jugador', 'Jugador ID', 'Asistente', 'Asistente ID',
                'Comentario'
            ]
            df_eventos = df_eventos[column_order]
            
            df_eventos.to_excel(archivo_salida, index=False, engine='openpyxl')
            print(f"\nTodos los eventos guardados exitosamente en {archivo_salida}")
            print(f"Total de eventos registrados: {len(df_eventos)}")
            return True
        except Exception as e:
            print(f"\nError al guardar el archivo Excel: {e}")
            return False
    else:
        print("\nNo se encontraron eventos para guardar")
        return False

# Configuración
api_key = "6ec4d0f2e2466ea1d79888381a37f7f8"  # Reemplaza con tu API key
archivo_partidos = "fixtures_argentinos.xlsx"  # Archivo generado previamente
archivo_eventos = "goles_argentinos_v2.xlsx"  # Nuevo archivo a generar

# Ejecutar
obtener_todos_eventos(api_key, archivo_partidos, archivo_eventos)