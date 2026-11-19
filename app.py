import os
import traceback
from flask import Flask, render_template, request, jsonify, send_from_directory
import pandas as pd
import numpy as np
import tensorflow as tf
from geopy.distance import geodesic
import folium

from catalogo import cargar_catalogo

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

app = Flask(__name__)

def cargar_modelo(ruta):
    """Abre el .keras guardado.

    El archivo original se exportó con Keras 2.15 en Windows. Keras 3 rechaza
    `batch_input_shape` y no encuentra los pesos porque las rutas del HDF5 usan
    barras invertidas. Si la carga directa falla, se reconstruye la misma red
    y se copian kernel y bias de cada capa densa.
    """
    try:
        return tf.keras.models.load_model(ruta)
    except (TypeError, ValueError, OSError):
        import zipfile
        import tempfile
        import h5py
        from tensorflow.keras import Sequential
        from tensorflow.keras.layers import Input, Dense, Dropout

        with zipfile.ZipFile(ruta) as archivo, tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
            tmp.write(archivo.read("model.weights.h5"))
            pesos = tmp.name

        with h5py.File(pesos, "r") as f:
            salida = int(f["layers\\dense_3"]["vars"]["0"].shape[1])
            modelo = Sequential([
                Input(shape=(9,)),
                Dense(128, activation="relu", name="dense"),
                Dropout(0.2, name="dropout"),
                Dense(64, activation="relu", name="dense_1"),
                Dropout(0.1, name="dropout_1"),
                Dense(32, activation="relu", name="dense_2"),
                Dense(salida, activation="softmax", name="dense_3"),
            ])
            modelo.build((None, 9))
            for capa in modelo.layers:
                grupo = f.get(f"layers\\{capa.name}")
                if grupo is None or "0" not in grupo.get("vars", {}):
                    continue
                capa.set_weights([
                    grupo["vars"]["0"][:],
                    grupo["vars"]["1"][:],
                ])
        os.unlink(pesos)
        return modelo

model = cargar_modelo("modelo_restaurantes.keras")

CATEGORIAS_COMIDA = ["Carne", "Tacos", "Pizza / Italiana", "Asiatica", "Mariscos"]

def codificar_comida(tipo_str):
    vector = [0.0] * len(CATEGORIAS_COMIDA)
    if tipo_str in CATEGORIAS_COMIDA:
        vector[CATEGORIAS_COMIDA.index(tipo_str)] = 1.0
    return vector

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.svg', mimetype='image/svg+xml')

@app.route('/recomendar', methods=['POST'])
def recomendar():
    try:
        df, fuente = cargar_catalogo()
        datos = request.get_json(force=True)

        comida_vec = codificar_comida(datos.get('tipo_comida', 'Carne'))
        ambiente_norm = float(datos.get('ambiente', 1)) / 4.0
        presupuesto_norm = float(datos.get('presupuesto', 1)) / 4.0
        vegetariano_val = float(datos.get('vegetariano', 0))

        # 1. Coordenadas reales del usuario enviadas por el navegador
        lat_usr = float(datos.get('latitud', 25.6667))
        lon_usr = float(datos.get('longitud', -100.3167))

        # 2. Inferencia de afinidad con la red neuronal
        distancia_ref = 0.1  
        vector = comida_vec + [ambiente_norm, presupuesto_norm, vegetariano_val, distancia_ref]
        vector_entrada = np.array([vector], dtype=np.float32)

        predicciones = model.predict(vector_entrada, verbose=0)[0]

        # 3. Detectar nombres de columnas del CSV
        cols_lower = {col.lower(): col for col in df.columns}
        col_rest = cols_lower.get('restaurante', cols_lower.get('nombre', df.columns[1]))
        col_zona = cols_lower.get('zona', df.columns[2] if len(df.columns) > 2 else None)
        col_tipo = cols_lower.get('tipo_comida', cols_lower.get('tipo', None))
        col_amb = cols_lower.get('ambiente')
        col_pre = cols_lower.get('presupuesto')
        col_veg = cols_lower.get('vegetariano')
        col_lat = cols_lower.get('latitud', df.columns[-2])
        col_lon = cols_lower.get('longitud', df.columns[-1])

        tipo_pedido = datos.get('tipo_comida', 'Carne')
        ambiente_pedido = float(datos.get('ambiente', 1))
        presupuesto_pedido = float(datos.get('presupuesto', 1))
        quiere_vegetariano = vegetariano_val >= 1

        def coincide(fila):
            tipo = 1.0 if str(fila[col_tipo]) == tipo_pedido else 0.0
            ambiente = 1.0 - abs(float(fila[col_amb]) - ambiente_pedido) / 3.0
            presupuesto = 1.0 - abs(float(fila[col_pre]) - presupuesto_pedido) / 3.0
            if quiere_vegetariano:
                vegetariano = 1.0 if float(fila[col_veg]) >= 1 else 0.0
            else:
                vegetariano = 1.0
            return (tipo + ambiente + presupuesto + vegetariano) / 4.0

        # Solo entran lugares de la comida pedida. Si pidió vegetariano,
        # se quedan los que sí lo ofrecen. La red desempató dentro de ese grupo.
        candidatos = [i for i, fila in df.iterrows() if str(fila[col_tipo]) == tipo_pedido]
        if quiere_vegetariano:
            vegetarianos = [i for i in candidatos if float(df.loc[i, col_veg]) >= 1]
            if vegetarianos:
                candidatos = vegetarianos
        if not candidatos:
            candidatos = list(df.index)

        suma_red = 0.0
        for i in candidatos:
            if i < len(predicciones):
                suma_red += float(predicciones[i])

        mejor_score = -1.0
        mejor_idx = candidatos[0]
        mejor_distancia = 0.0
        mejor_ajuste = 0.0

        for i in candidatos:
            fila = df.loc[i]
            prob_red = float(predicciones[i]) if i < len(predicciones) else 0.0
            red = prob_red / suma_red if suma_red > 0 else 1.0 / len(candidatos)
            d_km = geodesic((lat_usr, lon_usr), (float(fila[col_lat]), float(fila[col_lon]))).km
            factor_cercania = max(0.05, 1.0 - (d_km / 25.0))
            ajuste = coincide(fila)
            score_final = (ajuste * 0.55) + (red * 0.15) + (factor_cercania * 0.30)

            if score_final > mejor_score:
                mejor_score = score_final
                mejor_idx = i
                mejor_distancia = d_km
                mejor_ajuste = ajuste

        restaurante = df.loc[mejor_idx]
        afinidad_pct = mejor_ajuste * 100.0

        lat_rest = float(restaurante[col_lat])
        lon_rest = float(restaurante[col_lon])
        nombre_rest = str(restaurante[col_rest])

        print(f"Mejor seleccionado: {nombre_rest} con afinidad {afinidad_pct:.1f}%")

        # 5. Generar y guardar el mapa interactivo con Folium en la carpeta static
        mapa_restaurante = folium.Map(location=[lat_rest, lon_rest], zoom_start=15)
        folium.Marker(
            [lat_rest, lon_rest],
            popup=nombre_rest,
            tooltip="¡Tu restaurante recomendado!"
        ).add_to(mapa_restaurante)
        
        os.makedirs("static", exist_ok=True)
        mapa_restaurante.save("static/mapa_recomendado.html")

        return jsonify({
            "nombre": nombre_rest,
            "zona": str(restaurante[col_zona]) if col_zona else "Monterrey",
            "tipo_comida": str(restaurante[col_tipo]) if col_tipo else str(datos.get('tipo_comida')),
            "distancia": f"{mejor_distancia:.2f} km",
            "afinidad": f"{afinidad_pct:.1f}%",
            "fuente": fuente
        })

    except Exception as e:
        print("\n--- ERROR EN /recomendar ---")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    puerto = int(os.environ.get('PORT', '8742'))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=puerto, debug=debug)