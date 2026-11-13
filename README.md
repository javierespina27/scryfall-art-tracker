# 🎨 Scryfall Art Tracker - Artistas de Magic: The Gathering

Script en Python que recorre todos los sets de **Magic: The Gathering** a través de la [API pública de Scryfall](https://scryfall.com/docs/api) y construye un catálogo de **ilustraciones distintas por artista**, con estadísticas por set.

La ejecución es **incremental**: un CSV de *tracking* guarda el número de cartas de cada set, de modo que en cada pasada solo se procesan los sets nuevos o los que han cambiado.

---

## Qué hace

1. **Descarga la lista de sets** de Scryfall y compara su `card_count` con el tracking guardado.
2. **Detecta qué procesar:** sets nunca examinados (🆕) y sets cuyo número de cartas ha cambiado (🔄).
3. **Extrae cada arte distinto** (`unique=art`), incluidas las cartas de doble cara, con paginación y reintentos con *backoff* exponencial ante el límite de peticiones (HTTP 429).
4. **Calcula estadísticas por artista dentro de cada set:** número de artes y porcentaje sobre el total del set.
5. **Fusiona en un master** deduplicado por `(Nombre_Carta, Artista)`: una reimpresión con el mismo arte no se duplica, y un arte nuevo de la misma carta sí se añade.
6. **Actualiza el tracking** para la siguiente ejecución.

---

## Salidas

Todo se guarda en `My Drive/scrap_en_scryfall/`:

| Fichero | Contenido |
|---|---|
| `reporte_artes_all_sets.csv` | Master: una fila por arte distinto de toda la colección |
| `tracking_card_count.csv` | `set_code` y `card_count` de cada set en la última ejecución |
| `artes_<set>.csv` | Detalle de cada set procesado |

Columnas del master:

| Columna | Descripción |
|---|---|
| `Set_Code` | Set donde apareció ese arte por primera vez |
| `Nombre_Carta` | Nombre de la carta (o de la cara, en cartas dobles) |
| `Artista` | Ilustrador |
| `Illustration_ID` | Identificador de la ilustración en Scryfall |
| `Cartas_Del_Artista` | Artes de ese artista dentro del set |
| `Pct_Coleccion` | Porcentaje del set que ilustra ese artista |

---

## Cómo ejecutarlo

El script está pensado para **Google Colab**, porque guarda los resultados en Google Drive.

1. Abre un notebook nuevo en [Colab](https://colab.research.google.com/).
2. Pega el contenido de `scryfall_artes.py` en una celda y ejecútala.
3. Autoriza el acceso a Google Drive cuando lo pida.

La primera ejecución recorre todos los sets y tarda bastante. Las siguientes solo procesan las novedades.

Para ejecutarlo en local, elimina las líneas de `google.colab` (`drive.mount` y `files.download`), cambia `CARPETA` por una ruta de tu equipo e instala las dependencias:

```bash
pip install -r requirements.txt
```

---

## Uso responsable de la API

El script respeta las [buenas prácticas de Scryfall](https://scryfall.com/docs/api#rate-limits-and-good-citizenship): envía un `User-Agent` propio, espera entre páginas y entre sets, y reintenta con espera creciente si recibe un 429. No necesita clave de API.

Los datos de las cartas pertenecen a Scryfall y a Wizards of the Coast.
