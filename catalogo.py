"""Catálogo de restaurantes. Firestore es la fuente; el CSV queda de respaldo."""

import json
import os
import time
import urllib.parse
import urllib.request

import pandas as pd

COLUMNAS = [
    "id",
    "restaurante",
    "zona",
    "tipo_comida",
    "ambiente",
    "presupuesto",
    "vegetariano",
    "latitud",
    "longitud",
]

_cache = {"momento": 0.0, "df": None, "fuente": "csv"}


def _config():
    ruta = os.path.join(os.path.dirname(__file__), "firebase_public.json")
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def _valor(campo):
    if "stringValue" in campo:
        return campo["stringValue"]
    if "integerValue" in campo:
        return int(campo["integerValue"])
    if "doubleValue" in campo:
        return float(campo["doubleValue"])
    if "booleanValue" in campo:
        return int(campo["booleanValue"])
    return None


def _desde_csv():
    df = pd.read_csv(os.path.join(os.path.dirname(__file__), "restaurantes.csv"))
    df.columns = df.columns.str.strip()
    return df.sort_values("id").reset_index(drop=True)


def _desde_firestore(config):
    url = (
        "https://firestore.googleapis.com/v1/projects/"
        f"{config['projectId']}/databases/{config['databaseId']}/documents:runQuery"
        f"?key={urllib.parse.quote(config['apiKey'])}"
    )
    pedido = {"structuredQuery": {"from": [{"collectionId": "restaurantes"}], "limit": 300}}
    solicitud = urllib.request.Request(
        url,
        data=json.dumps(pedido).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(solicitud, timeout=8) as respuesta:
        datos = json.loads(respuesta.read().decode())
    filas = []
    for item in datos:
        documento = item.get("document")
        if not documento:
            continue
        campos = {nombre: _valor(valor) for nombre, valor in documento["fields"].items()}
        filas.append(campos)
    if not filas:
        raise RuntimeError("Firestore respondió sin restaurantes")
    df = pd.DataFrame(filas)
    for columna in COLUMNAS:
        if columna not in df.columns:
            raise RuntimeError(f"Falta la columna {columna} en Firestore")
    return df[COLUMNAS].sort_values("id").reset_index(drop=True)


def cargar_catalogo(forzar=False):
    """Devuelve el catálogo y de dónde salió: 'firestore' o 'csv'."""
    ahora = time.time()
    if not forzar and _cache["df"] is not None and ahora - _cache["momento"] < 30:
        return _cache["df"].copy(), _cache["fuente"]

    config = _config()
    if config:
        try:
            df = _desde_firestore(config)
            _cache.update(momento=ahora, df=df, fuente="firestore")
            return df.copy(), "firestore"
        except Exception as error:
            print(f"No se pudo leer Firestore ({error}). Se usa restaurantes.csv.")

    df = _desde_csv()
    _cache.update(momento=ahora, df=df, fuente="csv")
    return df.copy(), "csv"
