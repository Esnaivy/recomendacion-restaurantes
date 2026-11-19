const CATEGORIAS = ["Carne", "Tacos", "Pizza / Italiana", "Asiatica", "Mariscos"];
let catalogo = (typeof RESTAURANTES !== "undefined") ? RESTAURANTES.slice() : [];

function usarCatalogo(lista) {
  if (Array.isArray(lista) && lista.length) catalogo = lista;
}

function usarCatalogoDesdeFirestore(texto) {
  const datos = JSON.parse(texto);
  const documentos = Array.isArray(datos)
    ? datos.map((item) => item.document).filter(Boolean)
    : (datos.documents || []);
  const lista = documentos.map((documento) => {
    const campos = documento.fields || {};
    const leer = (nombre) => {
      const campo = campos[nombre] || {};
      if (campo.stringValue !== undefined) return campo.stringValue;
      if (campo.integerValue !== undefined) return Number(campo.integerValue);
      if (campo.doubleValue !== undefined) return Number(campo.doubleValue);
      if (campo.booleanValue !== undefined) return campo.booleanValue ? 1 : 0;
      return "";
    };
    return {
      nombre: leer("restaurante"),
      zona: leer("zona"),
      tipo: leer("tipo_comida"),
      ambiente: Number(leer("ambiente")),
      presupuesto: Number(leer("presupuesto")),
      vegetariano: Number(leer("vegetariano")),
      lat: Number(leer("latitud")),
      lon: Number(leer("longitud")),
      id: Number(leer("id")),
    };
  }).sort((a, b) => a.id - b.id);
  usarCatalogo(lista);
}

if (typeof window !== "undefined") {
  window.usarCatalogo = usarCatalogo;
  window.usarCatalogoDesdeFirestore = usarCatalogoDesdeFirestore;
}

function codificarComida(tipo) {
  const vector = [0, 0, 0, 0, 0];
  const indice = CATEGORIAS.indexOf(tipo);
  if (indice >= 0) vector[indice] = 1;
  return vector;
}

function capaDensa(entrada, capa, usarRelu) {
  const pesos = capa.kernel;
  const sesgo = capa.bias;
  const salida = new Array(sesgo.length);
  for (let j = 0; j < sesgo.length; j++) {
    let suma = sesgo[j];
    for (let i = 0; i < entrada.length; i++) suma += entrada[i] * pesos[i][j];
    salida[j] = usarRelu ? Math.max(0, suma) : suma;
  }
  return salida;
}

function softmax(valores) {
  let maximo = valores[0];
  for (let i = 1; i < valores.length; i++) if (valores[i] > maximo) maximo = valores[i];
  const exponenciales = valores.map((valor) => Math.exp(valor - maximo));
  const total = exponenciales.reduce((acum, valor) => acum + valor, 0);
  return exponenciales.map((valor) => valor / total);
}

function predecir(vector) {
  let activacion = vector;
  activacion = capaDensa(activacion, MODELO.dense, true);
  activacion = capaDensa(activacion, MODELO.dense_1, true);
  activacion = capaDensa(activacion, MODELO.dense_2, true);
  activacion = capaDensa(activacion, MODELO.dense_3, false);
  return softmax(activacion);
}

function distanciaKm(lat1, lon1, lat2, lon2) {
  const aRadianes = Math.PI / 180;
  const dLat = (lat2 - lat1) * aRadianes;
  const dLon = (lon2 - lon1) * aRadianes;
  const lat1r = lat1 * aRadianes;
  const lat2r = lat2 * aRadianes;
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(lat1r) * Math.cos(lat2r) * Math.sin(dLon / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.min(1, Math.sqrt(h)));
}

function coincidencia(lugar, datos) {
  const tipo = lugar.tipo === datos.tipo_comida ? 1 : 0;
  const ambiente = 1 - Math.abs(Number(lugar.ambiente) - Number(datos.ambiente)) / 3;
  const presupuesto = 1 - Math.abs(Number(lugar.presupuesto) - Number(datos.presupuesto)) / 3;
  const vegetariano = Number(datos.vegetariano) === 1
    ? (Number(lugar.vegetariano) === 1 ? 1 : 0)
    : 1;
  return (tipo + ambiente + presupuesto + vegetariano) / 4;
}

function sugerir(datos) {
  const comida = codificarComida(datos.tipo_comida || "Carne");
  const vector = comida.concat([
    Number(datos.ambiente) / 4,
    Number(datos.presupuesto) / 4,
    Number(datos.vegetariano),
    0.1,
  ]);
  const afinidad = predecir(vector);
  const lat = Number(datos.latitud);
  const lon = Number(datos.longitud);
  const quiereVegetariano = Number(datos.vegetariano) === 1;

  let candidatos = catalogo
    .map((lugar, posicion) => ({ lugar, posicion }))
    .filter((item) => item.lugar.tipo === (datos.tipo_comida || "Carne"));
  if (quiereVegetariano) {
    const vegetarianos = candidatos.filter((item) => Number(item.lugar.vegetariano) === 1);
    if (vegetarianos.length) candidatos = vegetarianos;
  }
  if (!candidatos.length) {
    candidatos = catalogo.map((lugar, posicion) => ({ lugar, posicion }));
  }

  let sumaRed = 0;
  candidatos.forEach((item) => {
    sumaRed += item.posicion < afinidad.length ? afinidad[item.posicion] : 0;
  });

  let mejor = null;
  candidatos.forEach((item) => {
    const km = distanciaKm(lat, lon, item.lugar.lat, item.lugar.lon);
    const cercania = Math.max(0.05, 1 - km / 25);
    const cruda = item.posicion < afinidad.length ? afinidad[item.posicion] : 0;
    const red = sumaRed > 0 ? cruda / sumaRed : 1 / candidatos.length;
    const ajuste = coincidencia(item.lugar, datos);
    const score = ajuste * 0.55 + red * 0.15 + cercania * 0.30;
    if (!mejor || score > mejor.score) {
      mejor = { lugar: item.lugar, km, score, afinidad: ajuste };
    }
  });

  return {
    nombre: mejor.lugar.nombre,
    zona: mejor.lugar.zona,
    tipo_comida: mejor.lugar.tipo,
    distancia: `${mejor.km.toFixed(2)} km`,
    afinidad: `${(mejor.afinidad * 100).toFixed(1)}%`,
    lat: mejor.lugar.lat,
    lon: mejor.lugar.lon,
  };
}

if (typeof globalThis !== "undefined") globalThis.sugerir = sugerir;

if (typeof window !== "undefined") {
  const boton = document.getElementById("btn-consultar");
  const errorBox = document.getElementById("error");
  const resultado = document.getElementById("resultado");

  boton.addEventListener("click", obtenerRecomendacion);

  async function obtenerRecomendacion() {
    boton.textContent = "Buscando cerca de ti…";
    boton.disabled = true;
    errorBox.hidden = true;

    let latitud = 25.6667;
    let longitud = -100.3167;

    if (navigator.geolocation) {
      try {
        const posicion = await new Promise((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(resolve, reject, {
            timeout: 8000,
            enableHighAccuracy: true,
          });
        });
        latitud = posicion.coords.latitude;
        longitud = posicion.coords.longitude;
      } catch (err) {
        console.log("Sin GPS; se usa el centro de Monterrey.");
      }
    }

    try {
      const datos = sugerir({
        tipo_comida: document.getElementById("tipo_comida").value,
        vegetariano: document.getElementById("vegetariano").value,
        presupuesto: document.getElementById("presupuesto").value,
        ambiente: document.getElementById("ambiente").value,
        latitud,
        longitud,
      });

      document.getElementById("res_nombre").textContent = datos.nombre;
      document.getElementById("res_zona").textContent = datos.zona;
      document.getElementById("res_tipo").textContent = datos.tipo_comida;
      document.getElementById("res_distancia").textContent = datos.distancia;
      document.getElementById("res_afinidad").textContent = datos.afinidad;

      const margen = 0.012;
      const bbox = [
        datos.lon - margen,
        datos.lat - margen * 0.7,
        datos.lon + margen,
        datos.lat + margen * 0.7,
      ].join(",");
      document.getElementById("iframe-mapa").src =
        `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${datos.lat},${datos.lon}`;
      document.getElementById("mapa-link").href =
        `geo:${datos.lat},${datos.lon}?q=${datos.lat},${datos.lon}(${encodeURIComponent(datos.nombre)})`;

      resultado.hidden = false;
      resultado.classList.remove("enter");
      void resultado.offsetWidth;
      resultado.classList.add("enter");
      resultado.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      errorBox.textContent = "No se pudo armar la sugerencia.";
      errorBox.hidden = false;
    } finally {
      boton.textContent = "Buscar lugar";
      boton.disabled = false;
    }
  }
}

if (typeof module !== "undefined") {
  module.exports = { sugerir, predecir };
}
