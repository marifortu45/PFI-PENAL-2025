import argparse
import os
import sys
import time
import glob
import shutil
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

import pandas as pd
from yt_dlp import YoutubeDL


# -----------------------------
# Utilidades
# -----------------------------
VALID_FINAL_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".mp3", ".aac", ".opus", ".m4a"}
TEMP_EXT_CONTAINS = (".part", ".ytdl", ".temp", ".tmp")


def ffmpeg_available() -> bool:
    """Devuelve True si ffmpeg está disponible en PATH."""
    return shutil.which("ffmpeg") is not None


def read_excel(excel_path: str, sheet: Optional[str] = None) -> pd.DataFrame:
    """
    Lee el Excel y devuelve DataFrame con columnas:
    - A -> internal_penalty_id
    - M -> url
    Accede por posición, independientemente de los nombres.
    """
    df = pd.read_excel(excel_path, sheet_name=sheet, engine="openpyxl", header=0)
    if df.shape[1] < 13:
        raise ValueError("El Excel no tiene al menos 13 columnas (A..M).")
    out = df.iloc[:, [0, 12]].copy()
    out.columns = ["internal_penalty_id", "url"]
    # Limpieza básica
    out["internal_penalty_id"] = out["internal_penalty_id"].astype(str).str.strip()
    out["url"] = out["url"].astype(str).str.strip()
    out = out[(out["internal_penalty_id"] != "") &
              (out["url"] != "") &
              (~out["url"].str.lower().eq("nan"))]
    return out


def build_ydl_opts(output_dir: str,
                   filename_no_ext: str,
                   browser: Optional[str],
                   profile: Optional[str],
                   cookie_file: Optional[str],
                   want_max_quality_mp4: bool = True) -> dict:
    """
    Construye las opciones de yt-dlp:
    - Si hay ffmpeg y want_max_quality_mp4=True: bestvideo+bestaudio con remux/convert a MP4.
    - Si no hay ffmpeg: usa 'best' (formato combinado) para evitar merge y no fallar.
    - Maneja cookies del navegador (--browser/--profile) o archivo --cookie-file.
    """
    os.makedirs(output_dir, exist_ok=True)
    outtmpl = os.path.join(output_dir, f"{filename_no_ext}.%(ext)s")

    have_ffmpeg = ffmpeg_available()
    if want_max_quality_mp4 and have_ffmpeg:
        fmt = "bestvideo*+bestaudio/best"
        postprocessors = [
            {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
        ]
        merge_out = "mp4"
    else:
        fmt = "best"
        postprocessors = []
        merge_out = None

    ydl_opts = {
        "format": fmt,
        "noplaylist": True,
        "ignoreerrors": False,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "outtmpl": outtmpl,
        "paths": {"home": output_dir},
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        },
        "retry_sleep_functions": {
            "http": lambda n: min(5 * n, 30),
            "fragment": lambda n: min(2 * n, 10),
            "extractor": lambda n: min(2 * n, 10),
        },
        "quiet": False,
        "no_warnings": False,
    }

    if postprocessors:
        ydl_opts["postprocessors"] = postprocessors
    if merge_out:
        ydl_opts["merge_output_format"] = merge_out

    # Cookies
    if cookie_file:
        if not os.path.exists(cookie_file):
            raise FileNotFoundError(f"Cookie file no encontrado: {cookie_file}")
        ydl_opts["cookiefile"] = cookie_file
    elif browser:
        ydl_opts["cookiesfrombrowser"] = (browser, profile, None)

    return ydl_opts


def find_existing_asset(output_dir: str, stem: str) -> Optional[str]:
    """
    Busca si ya existe un archivo final para ese 'stem' con cualquier extensión válida.
    Ignora archivos temporales (.part, .ytdl, etc.)
    """
    pattern = os.path.join(output_dir, f"{stem}.*")
    for path in glob.glob(pattern):
        _, ext = os.path.splitext(path)
        if any(t in path.lower() for t in TEMP_EXT_CONTAINS):
            continue
        if ext.lower() in VALID_FINAL_EXTS and os.path.getsize(path) > 0:
            return path
    return None


def ensure_mp4_final_path(path: str) -> str:
    """
    Si el archivo final no terminó en .mp4 (por falta de ffmpeg),
    devuelve la ruta real por si se quiere registrar igual.
    """
    base, _ = os.path.splitext(path)
    if os.path.exists(path):
        return path

    folder = os.path.dirname(path) or "."
    stem = os.path.basename(base)
    return find_existing_asset(folder, stem) or path


def filesize(path: str) -> Optional[int]:
    try:
        return os.path.getsize(path)
    except Exception:
        return None


def download_one(url: str,
                 output_dir: str,
                 final_stem: str,
                 ydl_opts: dict) -> Tuple[str, str, Optional[str], Optional[int]]:
    """
    Lógica por item:
    - Si ya existe archivo final para final_stem: SKIPPED.
    - Si no existe: intenta descargar y retorna status.
    Devuelve: (status, message, final_path, size_bytes)
    """
    os.makedirs(output_dir, exist_ok=True)
    desired_mp4 = os.path.join(output_dir, f"{final_stem}.mp4")

    # Check previo (cualquier extensión válida)
    existing = find_existing_asset(output_dir, final_stem)
    if existing:
        return "SKIPPED", f"⏭️ Ya existe: {existing}", existing, filesize(existing)

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                return "ERROR", f"❌ No se pudo extraer info: {url}", None, None
            ydl.download([url])
    except Exception as e:
        return "ERROR", f"❌ Error descargando {url}: {e}", None, None

    final_path = ensure_mp4_final_path(desired_mp4)
    if os.path.exists(final_path) and filesize(final_path):
        # Diferenciar mp4 o combinado
        if final_path.lower().endswith(".mp4"):
            return "OK", f"✅ OK: {final_path}", final_path, filesize(final_path)
        else:
            return "OK", f"✅ OK (no MP4 por falta de ffmpeg): {final_path}", final_path, filesize(final_path)

    return "ERROR", "⚠️ Descargado pero no se encontró archivo final. Revisar ffmpeg/post-procesado.", None, None


# -----------------------------
# Main CLI
# -----------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Lee Excel (A=INTERNAL_PENALTY_ID, M=YouTube URL) y descarga MP4 en máxima calidad. "
                    "Chequea si el archivo ya existe y genera un reporte de status."
    )
    parser.add_argument("-i", "--input", required=True, help="Excel de entrada.")
    parser.add_argument("-s", "--sheet", default=None, help="Nombre de la hoja (opcional).")
    parser.add_argument("-o", "--output", default="downloads", help="Directorio de salida (default: downloads).")
    parser.add_argument("--sleep", type=float, default=0.0, help="Pausa (seg) entre descargas.")
    # Autenticación/cookies
    parser.add_argument("--browser",
                        choices=["chrome", "edge", "brave", "firefox", "opera"],
                        help="Usar cookies desde el navegador (tené la sesión iniciada en YouTube).")
    parser.add_argument("--profile", default=None,
                        help="Perfil del navegador (ej.: 'Default', 'Profile 1').")
    parser.add_argument("--cookie-file", default=None,
                        help="Ruta a cookies.txt exportado (alternativa a --browser).")
    # Calidad/ffmpeg
    parser.add_argument("--no-max-quality-mp4", action="store_true",
                        help="Si se pasa, descarga el mejor formato combinado (sin ffmpeg).")
    # Reporte
    parser.add_argument("--report", default=None,
                        help="Ruta de reporte (CSV o XLSX). Por defecto: {output}/download_report.csv")

    args = parser.parse_args()

    # Mensajes de contexto
    print(f"📘 Leyendo: {args.input} | Hoja: {args.sheet or '(por defecto)'}")
    print(f"📁 Salida: {os.path.abspath(args.output)}")
    if args.cookie_file:
        print(f"🍪 Cookie file: {args.cookie_file}")
    elif args.browser:
        print(f"🍪 Cookies del navegador: {args.browser} | Perfil: {args.profile or '(por defecto)'}")
    else:
        print("ℹ️ Sin cookies: si YouTube pide verificación anti-bot, puede fallar. Recomendado --browser o --cookie-file.")

    if not args.no_max_quality_mp4 and not ffmpeg_available():
        print("⚠️ ffmpeg NO detectado. Se descargará el mejor formato combinado (sin merge) para evitar errores.")
        print("   Sugerencia: instalá ffmpeg y agregalo al PATH para obtener MP4 garantizado en máxima calidad.\n")

    # Reporte por defecto
    if not args.report:
        os.makedirs(args.output, exist_ok=True)
        args.report = os.path.join(args.output, "download_report.csv")

    try:
        df = read_excel(args.input, args.sheet)
    except Exception as e:
        print(f"❌ Error leyendo Excel: {e}")
        sys.exit(1)

    print(f"🧾 Filas a procesar: {len(df)}")
    print("-" * 60)

    rows: list[Dict[str, Any]] = []
    ok_count = 0

    for _, row in df.iterrows():
        pen_id = str(row["internal_penalty_id"]).strip()
        url = str(row["url"]).strip()
        ts = datetime.now().isoformat(timespec="seconds")

        if not pen_id or not url or url.lower() == "nan":
            msg = "❌ Datos incompletos"
            print(f"{pen_id or 'ID?'}: {msg}")
            rows.append({
                "timestamp": ts,
                "internal_penalty_id": pen_id,
                "url": url,
                "status": "ERROR",
                "message": msg,
                "filepath": None,
                "size_bytes": None,
            })
            continue

        ydl_opts = build_ydl_opts(
            output_dir=args.output,
            filename_no_ext=pen_id,
            browser=args.browser,
            profile=args.profile,
            cookie_file=args.cookie_file,
            want_max_quality_mp4=not args.no_max_quality_mp4
        )

        status, msg, fpath, fsize = download_one(url, args.output, pen_id, ydl_opts)
        print(f"{pen_id}: {msg}")
        ok_count += int(status == "OK")

        rows.append({
            "timestamp": ts,
            "internal_penalty_id": pen_id,
            "url": url,
            "status": status,
            "message": msg,
            "filepath": fpath,
            "size_bytes": fsize,
        })

        if args.sleep > 0:
            time.sleep(args.sleep)

    fail_count = len(df) - ok_count
    print("-" * 60)
    print(f"✅ Éxitos: {ok_count} | ❌ Fallos: {fail_count}")

    # Guardar reporte
    rep_ext = os.path.splitext(args.report)[1].lower()
    rep_dir = os.path.dirname(args.report) or "."
    os.makedirs(rep_dir, exist_ok=True)
    rep_df = pd.DataFrame(rows)

    if rep_ext == ".xlsx":
        rep_df.to_excel(args.report, index=False)
    else:
        # Default CSV
        rep_df.to_csv(args.report, index=False, encoding="utf-8")

    print(f"🗂️  Reporte guardado en: {args.report}")
    if fail_count:
        print("🔎 Si ves 'Sign in to confirm you’re not a bot', usá --browser chrome/edge/brave/firefox (y --profile si corresponde) "
              "o --cookie-file con cookies de youtube.com.")


if __name__ == "__main__":
    main()
