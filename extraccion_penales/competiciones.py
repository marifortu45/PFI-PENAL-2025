"""pip install pandas openpyxl"""
import requests
import pandas as pd

def obtener_ligas_argentinas_y_guardar_excel(api_key):
    base_url = "https://v3.football.api-sports.io"
    endpoint = "/leagues"
    params = {
        "country": "Argentina"
    }
    headers = {
        'x-apisports-key': api_key
    }

    try:
        response = requests.get(f"{base_url}{endpoint}", headers=headers, params=params)
        response.raise_for_status()
        
        datos = response.json()
        
        if datos.get('response'):
            # Preparar los datos para el DataFrame
            ligas_data = []
            for liga in datos['response']:
                for season in liga['seasons']:  # Iterar por todas las temporadas
                    liga_info = {
                        'ID': liga['league']['id'],
                        'Nombre': liga['league']['name'],
                        'Tipo': liga['league']['type'],
                        'País': liga['country']['name'],
                        'Temporada': season['year'],
                        'Inicio': season['start'],
                        'Fin': season['end']
                    }
                    ligas_data.append(liga_info)
            
            # Crear DataFrame
            df = pd.DataFrame(ligas_data)
            
            # Guardar en Excel
            nombre_archivo = 'competiciones_argentinas.xlsx'
            df.to_excel(nombre_archivo, index=False, engine='openpyxl')
            
            print(f"Datos guardados exitosamente en '{nombre_archivo}'")
            print(f"Total de registros: {len(df)}")
            
            return True
            
        else:
            print("No se encontraron competiciones.")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Error al conectarse a la API: {e}")
        return False

# Ejemplo de uso
api_key = "6ec4d0f2e2466ea1d79888381a37f7f8"  # Reemplaza con tu API key de API-Football
obtener_ligas_argentinas_y_guardar_excel(api_key)