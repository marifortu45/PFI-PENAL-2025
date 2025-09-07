import os
import time
import argparse
import requests
import pandas as pd
from typing import List, Dict, Any

API_URL = "https://v3.football.api-sports.io/players/profiles"

def get_api_key(cli_key: str | None) -> str:
    key = cli_key or os.getenv("API_FOOTBALL_KEY")
    if not key:
        raise RuntimeError(
            "Falta la API key. Pasala con --api-key o definí la variable de entorno API_FOOTBALL_KEY."
        )
    return key

def fetch_profile(player_id: int | str, headers: Dict[str, str], max_retries: int = 3, backoff: float = 1.5) -> Dict[str, Any] | None:
    """
    Devuelve dict con campos {id, name, firstname, lastname} o None si no hay datos.
    Incluye reintentos ante 429 o errores transitorios.
    """
    params = {"player": player_id}
    for attempt in range(1, max_retries + 1):
        resp = requests.get(API_URL, headers=headers, params=params, timeout=20)
        # Manejo de rate limit 429
        if resp.status_code == 429:
            # Si el header de reset existe, lo respetamos; si no, backoff exponencial
            reset = resp.headers.get("X-RateLimit-Reset", "")
            try:
                wait_s = max(float(reset), backoff * attempt)
            except Exception:
                wait_s = backoff * attempt
            time.sleep(wait_s)
            continue
        if resp.status_code >= 500:
            time.sleep(backoff * attempt)
            continue
        if resp.status_code != 200:
            # Error no recuperable (400/401/403/404/etc.)
            return None

        data = resp.json().get("response", [])
        if not data:
            return None

        # La estructura típica: response = [ { "player": { ... } } ]
        player = data[0].get("player", {})
        return {
            "id": player.get("id"),
            "name": player.get("name"),
            "firstname": player.get("firstname"),
            "lastname": player.get("lastname"),
        }
    return None

def read_player_ids_from_excel(path: str) -> List[Any]:
    df = pd.read_excel(path, engine="openpyxl")
    if df.shape[1] < 1:
        raise ValueError("El Excel no tiene columnas. La primera columna debe contener los IDs de jugadores.")
    # Tomamos la primera columna sin importar el nombre
    first_col_name = df.columns[0]
    ids = df[first_col_name].dropna().tolist()
    return ids

def main():
    parser = argparse.ArgumentParser(description="Descarga perfiles de jugadores (API-Football) a Excel.")
    parser.add_argument("--input", "-i", required=True, help="Ruta del Excel de entrada con IDs en la primera columna.")
    parser.add_argument("--output", "-o", default="players_profiles.xlsx", help="Ruta del Excel de salida.")
    parser.add_argument("--api-key", help="API key de API-Football (alternativamente usar env API_FOOTBALL_KEY).")
    #parser.add_argument("--sleep", type=float, default=0.0, help="Pausa (segundos) entre requests para cuidar rate limit (opcional).")
    args = parser.parse_args()

    api_key = get_api_key(args.api_key)
    headers = {"x-apisports-key": api_key}

    player_ids = read_player_ids_from_excel(args.input)
    results: List[Dict[str, Any]] = []

    for idx, pid in enumerate(player_ids, start=1):
        profile = fetch_profile(pid, headers=headers)
        if profile is None:
            profile = {"id": pid, "name": None, "firstname": None, "lastname": None}
        results.append(profile)

        """
        if args.sleep > 0:
            time.sleep(args.sleep)
        """

    out_df = pd.DataFrame(results, columns=["id", "name", "firstname", "lastname"])
    out_df.to_excel(args.output, index=False)
    print(f"✅ Listo. Se generó: {args.output} (total filas: {len(out_df)})")

if __name__ == "__main__":
    main()
