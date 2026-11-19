# Recomendación de restaurantes (Monterrey)

Aplicación Flask que sugiere un restaurante de Monterrey. Combina una red neuronal (tipo de comida, ambiente, presupuesto y opción vegetariana) con la distancia al punto que envía el navegador, y muestra el resultado en un mapa.

El código parte de [mikemi48/Recomendaci-n-de-Restaurantes-](https://github.com/mikemi48/Recomendaci-n-de-Restaurantes-). El modelo `modelo_restaurantes.keras` se entrenó con Keras 2.15; `app.py` lo abre también en Keras 3.

Los restaurantes viven en Cloud Firestore, proyecto `antojo-restaurantes`, base `antojo`, colección `restaurantes`. `restaurantes.csv` se usa solo si Firestore no responde. Para volver a entrenar con lo que haya en la base: `python3 entrenar.py`.

## Cómo usarla

1. Elige tipo de comida, si quieres opciones vegetarianas, presupuesto y ambiente.
2. Pulsa **Buscar lugar**.
3. El navegador pide tu ubicación. Si la niegas, el cálculo usa el centro de Monterrey.
4. La página muestra el restaurante, la zona, la distancia aproximada, la afinidad del modelo y un mapa.

## Cómo correrla

Python 3.12.

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

La app escucha en el puerto `8742`. Para otro puerto: `PORT=5001 python3 app.py`.

Para volver a entrenar con `restaurantes.csv`:

```bash
python3 entrenar.py
```

Eso sobrescribe `modelo_restaurantes.keras`.

## App de Android

`antojo.apk` es la misma recomendación empaquetada para el teléfono. No usa el servidor de Flask: la red corre dentro de la app. Para regenerarlo, con el Android SDK instalado:

```bash
android/build-apk.sh antojo.apk
```
