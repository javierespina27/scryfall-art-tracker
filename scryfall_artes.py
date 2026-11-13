import requests
import pandas as pd
import time
from google.colab import drive
from google.colab import files

# ── 0. Configuración ─────────────────────────────────────────────
drive.mount('/content/drive')

CARPETA       = "/content/drive/My Drive/scrap_en_scryfall"
RUTA_MASTER   = f"{CARPETA}/reporte_artes_all_sets.csv"      # ← nuevo nombre (formato fila-por-arte)
RUTA_TRACKING = f"{CARPETA}/tracking_card_count.csv"

COLUMNAS = ['Set_Code', 'Nombre_Carta', 'Artista', 'Illustration_ID',
            'Cartas_Del_Artista', 'Pct_Coleccion']

HEADERS = {
    "User-Agent": "MtgArtistScript/1.0",
    "Accept": "application/json;q=0.9,*/*;q=0.8",
}


def get_con_reintento(url, max_intentos=5):
    for intento in range(1, max_intentos + 1):
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            return response
        elif response.status_code == 429:
            espera = 2 ** intento
            print(f"  ⏳ Rate limit (429) — esperando {espera}s ({intento}/{max_intentos})...")
            time.sleep(espera)
        else:
            print(f"  ⚠ Error {response.status_code} — se omite este set.")
            return None
    print(f"  ✗ Se agotaron los {max_intentos} intentos.")
    return None


def procesar_set(set_code):
    """Devuelve un DataFrame FILA-POR-ARTE para el set indicado.
    Una fila por cada combinación distinta (Nombre_Carta, Artista)."""
    api_url = f"https://api.scryfall.com/cards/search?q=set:{set_code}&unique=art"
    raw_data = []
    pagina = 1

    print(f"\n{'='*55}")
    print(f"  Procesando set: {set_code.upper()}")
    print(f"{'='*55}")

    while api_url:
        print(f"  📄 Página {pagina}: {api_url}")
        response = get_con_reintento(api_url)
        if response is None:
            return None

        json_res = response.json()
        cartas_pagina = len(json_res.get('data', []))
        print(f"     → {cartas_pagina} cartas · has_more: {json_res.get('has_more')}")

        for card in json_res.get('data', []):
            if 'card_faces' in card:
                for face in card['card_faces']:
                    raw_data.append({
                        "Set_Code":        set_code.upper(),
                        "Nombre_Carta":    face['name'],
                        # si la cara no trae artista/ilustración, cae al nivel carta
                        "Artista":         face.get('artist') or card.get('artist', 'Desconocido'),
                        "Illustration_ID": face.get('illustration_id') or card.get('illustration_id', ''),
                    })
            else:
                raw_data.append({
                    "Set_Code":        set_code.upper(),
                    "Nombre_Carta":    card['name'],
                    "Artista":         card.get('artist', 'Desconocido'),
                    "Illustration_ID": card.get('illustration_id', ''),
                })

        api_url = json_res.get('next_page') if json_res.get('has_more') else None
        pagina += 1
        if api_url:
            time.sleep(0.1)

    if not raw_data:
        print("  ⚠ Sin datos — set vacío o no encontrado.")
        return None

    df_detalle = pd.DataFrame(raw_data)

    # dedup INTERNO del set por (Nombre_Carta, Artista) → cada arte una sola vez
    df_detalle = df_detalle.drop_duplicates(
        subset=['Nombre_Carta', 'Artista']
    ).reset_index(drop=True)

    # ── stats por artista DENTRO de este set ─────────────────────
    total_set = len(df_detalle)            # total de artes distintos del set
    df_detalle['Cartas_Del_Artista'] = (
        df_detalle.groupby('Artista')['Nombre_Carta'].transform('count')
    )
    df_detalle['Pct_Coleccion'] = (
        df_detalle['Cartas_Del_Artista'] / total_set * 100
    ).round(2)

    df_detalle = df_detalle[COLUMNAS]      # ordena columnas según el esquema

    print(f"  ✓ {total_set} artes distintos en este set")
    return df_detalle


def exportar_csv(df, set_code):
    nombre_archivo = f"artes_{set_code.lower()}.csv"
    ruta = f"{CARPETA}/{nombre_archivo}"
    try:
        df.to_csv(ruta, index=False)
        print(f"  💾 Guardado: {nombre_archivo}")
    except Exception as e:
        print(f"  ✗ Error al guardar {nombre_archivo}: {e}")


# ── 1. Cargar master y tracking ───────────────────────────────────
try:
    df_master = pd.read_csv(RUTA_MASTER)
    if 'Nombre_Carta' not in df_master.columns:
        print("⚠ El master tiene formato ANTIGUO (agregado). Se reinicia con el "
              "nuevo formato fila-por-arte.")
        df_master = pd.DataFrame(columns=COLUMNAS)
    else:
        print(f"Master existente: {len(df_master)} artes")
except FileNotFoundError:
    df_master = pd.DataFrame(columns=COLUMNAS)
    print("No existe master → se construye desde cero.")

try:
    df_tracking = pd.read_csv(RUTA_TRACKING)
    tracking    = dict(zip(df_tracking['set_code'], df_tracking['card_count']))
    print(f"Tracking existente: {len(tracking)} sets registrados")
except FileNotFoundError:
    tracking = {}
    print("No existe tracking → todos los sets se consideran nuevos.")

# ── 2. Detectar sets nuevos y sets con cambios (basado en TRACKING) ──
resp_sets = get_con_reintento("https://api.scryfall.com/sets")
if resp_sets is None:
    raise RuntimeError("No se pudo obtener la lista de sets de Scryfall.")
all_sets = resp_sets.json()["data"]
print(f"Sets en Scryfall: {len(all_sets)}")

sets_nuevos     = []
sets_cambiados  = []
card_counts_now = {}

master_vacio = df_master.empty   # si el master se reinició, hay que reconstruirlo entero

for s in all_sets:
    code  = s["code"]
    count = s["card_count"]
    card_counts_now[code] = count

    if count == 0:                              # set anunciado pero vacío
        continue
    if master_vacio or code not in tracking:    # reconstrucción total o set nunca examinado
        sets_nuevos.append(code)
    elif tracking.get(code) != count:           # ha crecido / cambiado
        sets_cambiados.append(code)

sets_a_procesar = sets_nuevos + sets_cambiados

print(f"  ├─ 🆕 Nuevos (nunca examinados):  {len(sets_nuevos)}")
print(f"  ├─ 🔄 Con cambios (card_count ≠): {len(sets_cambiados)}")
if sets_cambiados:
    for c in sets_cambiados:
        print(f"  │     {c.upper()}: {tracking.get(c, '?')} → {card_counts_now[c]}")
print(f"  └─ Total esta ejecución:          {len(sets_a_procesar)}")

# ── 3. Procesar ───────────────────────────────────────────────────
resultados_nuevos = []

for set_code in sets_a_procesar:
    etiqueta = "🔄 cambios" if set_code in sets_cambiados else "🆕 nuevo"
    print(f"\n[{etiqueta}] {set_code.upper()}")
    df_set = procesar_set(set_code)
    if df_set is None:
        continue
    exportar_csv(df_set, set_code)
    resultados_nuevos.append(df_set)
    time.sleep(1)

# ── 4. Fusionar con master por ARTE DISTINTO y guardar ────────────
if resultados_nuevos:
    df_nuevos = pd.concat(resultados_nuevos, ignore_index=True)

    filas_antes = len(df_master)
    df_master = pd.concat([df_master, df_nuevos], ignore_index=True)

    # Cada arte = (Nombre_Carta, Artista).
    # keep='first' conserva la primera aparición → Set_Code = dónde se vio antes.
    # · Misma carta + mismo artista  → mismo arte (reimpresión) → NO duplica.
    # · Misma carta + artista nuevo  → arte nuevo → se conserva.
    df_master = df_master.drop_duplicates(
        subset=['Nombre_Carta', 'Artista'], keep='first'
    ).reset_index(drop=True)

    artes_nuevos = len(df_master) - filas_antes

    df_master.to_csv(RUTA_MASTER, index=False)
    print(f"\n✅ Master actualizado: {len(df_master)} artes · "
          f"{df_master['Set_Code'].nunique()} sets")
    print(f"   🎨 Artes nuevos añadidos en esta ejecución: {artes_nuevos}")

    print("\n📥 Descargando master...")
    files.download(RUTA_MASTER)
else:
    print("\n✅ Sin novedades: el master ya está al día.")

# ── 5. Actualizar tracking de card_count ──────────────────────────
df_tracking_new = pd.DataFrame([
    {"set_code": code, "card_count": count}
    for code, count in card_counts_now.items()
    if count > 0
])
df_tracking_new.to_csv(RUTA_TRACKING, index=False)
print(f"📊 Tracking actualizado: {len(df_tracking_new)} sets")