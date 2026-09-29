# Plan v3: Bots de prospección para Kahabox

Esta versión reemplaza a la v2. Incorpora lo que hay en el repo de Kahabox (qué es, qué hace, cómo se registran los clientes) y el criterio de **precio a medida del negocio**.

---

## 1. Qué es Kahabox (según el repo)

**Kahabox** es un SaaS multi-tenant de gestión de stock y caja, pensado para comercios revendedores de Ciudad del Este, que funciona **desde el celular** (PWA instalable y app Android).

### Problema que resuelve
Muchos comercios llevan el stock en Excel, cuaderno o de memoria. Eso causa: vender algo que ya no hay, no saber cuánto queda de una variante (color, talle, capacidad) y no poder confirmar disponibilidad rápido desde el piso.

### Qué hace hoy (funciones para usar en los mensajes)
| Función | Beneficio para el dueño |
|---|---|
| Escaneo de productos con la cámara del celular | Cargar y vender sin lector ni computadora |
| Caja y cobro desde el celular | Vender en cualquier lado del local |
| Impresión de tickets por Bluetooth | Ticket impreso sin equipo extra |
| **Funciona sin internet** (offline-first) | Si se corta la señal, se sigue vendiendo y sincroniza después |
| Stock por variante (color, talle, capacidad) | Saber exactamente cuánto queda de cada una |
| Catálogo compartido | Si otro comercio ya cargó el producto, aparece cargado al escanear |
| Precios en guaraníes y dólares | Se adapta a cómo se vende en CDE |
| Equipo con roles (dueño, vendedores) | Cada empleado con su acceso |
| Varias sucursales | Un solo sistema para más de un local |
| Importar stock y proveedores | Migrar desde el Excel que ya tienen |
| Auditoría de movimientos | Saber quién hizo qué |

### Limitación a respetar en los mensajes
El repo aclara que **la venta por peso o a granel queda fuera del alcance inicial**. Cuidado con rubros que venden así (por ejemplo, alimento balanceado suelto en veterinarias o tornillos y cables por metro/peso en ferreterías). No prometer que sirve para eso.

---

## 2. Política de precios

- **Los mensajes de prospección no llevan precios.**
- Los precios se hablan **cuando el negocio responde o pide la prueba**, y se arman **según el negocio**.
- Kahabox ya tiene planes (Básico, Estándar, Pro) que se diferencian por cantidad de administradores, empleados y sucursales. Esos límites sirven como base para cotizar.

### Preguntas para cotizar (se hacen en la conversación, no en el primer mensaje)
1. ¿Cuántos locales o sucursales tiene?
2. ¿Cuántas personas venden o cargan stock?
3. ¿Aproximadamente cuántos productos maneja?
4. ¿Usa impresora de tickets?
5. ¿Vende en guaraníes, dólares o ambos?

### Regla del bot
El bot **nunca envía precios**. Cuando alguien responde con "¿cuánto sale?", el bot te avisa con prioridad y respondés vos a mano, con el plan adecuado al negocio.

---

## 3. Sistema completo

| Componente | Función |
|---|---|
| **Bot 1 – Recolector** | Junta negocios por rubro y zona desde fuentes públicas gratuitas y guarda sus teléfonos |
| **Base de datos** | Contactos, estados del embudo, variantes y respuestas |
| **Bot 2 – Mensajero** | Envía WhatsApp con variantes, respetando límites y horarios |
| **Módulo de respuestas** | Clasifica respuestas y te avisa al celular |
| **Módulo de seguimiento** | Recordatorio único y mensajes durante la prueba de 14 días |
| **Reportes** | Resultados por variante, rubro y horario |

```
[Fuentes públicas + CSV] → Bot 1 → [Base de datos] ← Bot 2 → [WhatsApp → negocios]
                                    ▲                          │
                                    ├── Módulo de respuestas ◄─┘
                                    └── Seguimiento y reportes
```

**Rubros**: ferretería, electrónica, veterinaria, tienda de ropa.
**Zona inicial**: Ciudad del Este, Presidente Franco, Hernandarias y barrios.

---

## 4. Advertencias

1. **Google Places API queda descartada**: exige tarjeta de crédito para facturar y cobra por consulta. No se usa. Tampoco se raspa Google Maps ni ningún otro sitio: va contra sus términos.
2. **Fuentes públicas**: los padrones oficiales del Gobierno (SENACSA y similares) son datos abiertos y se pueden usar. Ojo, tampoco son perfectos: muchas firmas cargaron solo teléfono fijo, y a veces el teléfono no existe o está desactualizado. Cada número se filtra y se valida antes de escribir.
3. **WhatsApp**: mensajes en frío en volumen desde un número personal pueden **bloquearlo**. Para volumen alto, usar la API oficial de WhatsApp Business con número de empresa aparte.
4. **Legalidad**: revisar la normativa local sobre datos personales y publicidad; ofrecer siempre la baja y respetarla.
5. **Los porcentajes son estimaciones**, no datos reales. El piloto sirve para medir los propios.

---

## 5. Bot 1 – Recolector de números

### Fuente de datos: gratuita y sin tarjeta
La vía pago queda **descartada**. Los datos salen del **portal de datos abiertos del Gobierno** y de padrones oficiales por rubro, que son públicos.

Los PDF de SENACSA vienen **escaneados** (son imágenes, no texto), así que el flujo real es:
1. Descargar el PDF oficial del rubro.
2. Convertir cada página a imagen (PyMuPDF).
3. **OCR** con Tesseract en español para convertirla en texto.
4. Parsear el texto con `parsear_padron.py`: nombre, rubro, ciudad, teléfono y dirección.
5. Filtrar por zona, rubro y celular válido.

### Flujo
1. Elegir **rubro** y **zona** (por barrio rinde más que por ciudad completa).
2. Bajar el padrón oficial correspondiente.
3. OCR + parseo, y **normalizar** el teléfono a formato internacional (`+595...`).
4. **Filtrar**: sin teléfono, duplicados, fijos (sin WhatsApp probable) y ciudades fuera de la zona.
5. Guardar con estado `pendiente`.

### Advertencia sobre el volumen
Los padrones oficiales **no cubren todos los rubros ni todas las ciudades**: el de veterinarias, por ejemplo, está completo a nivel nacional pero de las 33 páginas solo 3 son de Alto Paraná, y da alrededor de 34 negocios con celular en la zona. Para llegar a los 300 hay que **combinar varias fuentes** (padrones oficiales de otros rubros, listados de cámaras, y CSV armados a mano) y no esperar que un solo padrón entregue el lote.

### Datos guardados
id, nombre, rubro, teléfono, es_celular, dirección, link_maps, estado, fecha_captura.

### Tecnología
Python, `requests`, `pymupdf` (PDF→imagen), `pytesseract` + Tesseract (OCR), `phonenumbers`, SQLite, exportación e importación CSV.

### Pasos
1. Reúne los padrones oficiales de ferretería, electrónica y veterinaria, y **valida 10 negocios a mano** antes de extraer en masa.
2. Confirma que los 10 tienen nombre, rubro, ciudad, celular y dirección correctos.
3. Extrae el resto, combina fuentes y deduplica.
4. Sin claves de API ni tarjetas: el costo es cero.

---

## 6. Bot 2 – Mensajero de WhatsApp

### Opciones de envío
| Opción | Cómo funciona | Riesgo de bloqueo | Costo |
|---|---|---|---|
| **A. WhatsApp Business Cloud API** | Plantillas aprobadas por Meta, número de empresa | Bajo | Por conversación de marketing |
| **B. Semi-automático** | El bot abre `wa.me/número?text=...` y vos apretás enviar | Muy bajo | Gratis |
| **C. Automatizar WhatsApp Web** | El bot maneja WhatsApp Web solo | **Alto** | Gratis |

**Recomendación**: piloto con **B**; pasar a **A** para escalar (más de ~50 por día).

### Flujo
1. Lee contactos `pendiente` con celular válido.
2. Elige variante (rotando o al azar) y personaliza con `{nombre}` y `{rubro}`.
3. Envía respetando límites, horarios y pausas.
4. Registra fecha, variante y franja horaria.
5. Actualiza estado a `enviado`.

### Estructura del mensaje
- Saludo corto con el nombre del negocio.
- Qué es Kahabox en una línea.
- **Un** beneficio concreto para su rubro.
- Invitación: **prueba gratis 14 días** + link al video demo (1 a 2 minutos, grabado desde el celular).
- Pregunta simple para responder.
- Opción de baja: "Si no te interesa, respondé NO y no te escribo más."
- **Sin precios.**

El video va como **link** (YouTube no listado u otro), no como archivo adjunto pesado.

### Borradores de variantes (para ajustar con tu voz)

**Variante 1 – Directa**
> Hola {nombre}, te escribo por Kahabox: una app para llevar el stock y cobrar desde el celular, escaneando con la cámara. Grabé una demo corta de cómo funciona: {link_demo}. Podés probarla gratis 14 días. ¿Te interesa que te muestre? (Si no, respondé NO y no te escribo más.)

**Variante 2 – Problema**
> Buenas, ¿en {nombre} llevan el stock en Excel o cuaderno? Con Kahabox ves cuánto queda de cada producto, color o talle desde el celular y evitás vender lo que ya no hay. Demo de 1 minuto: {link_demo}. Prueba gratis por 14 días. ¿Querés verla? (Respondé NO si no querés más mensajes.)

**Variante 3 – Corta y casual**
> Hola {nombre}! Hice una app para controlar stock y cobrar desde el celular, y funciona aunque se corte el internet. Mirá la demo: {link_demo}. ¿Te la muestro en tu local? (NO para dejar de recibir.)

**Variante 4 – Prueba gratis**
> Buen día, {nombre}. Te ofrezco probar Kahabox 14 días sin costo: escaneás productos con el celular, cobrás e imprimís el ticket por Bluetooth. Acá está la demo: {link_demo}. ¿Te armo la cuenta de prueba? (NO si no te interesa.)

**Variante 5 – Por rubro** (cambiar solo la frase del beneficio)
- **Ferretería**: "controlás el stock de tus productos y sabés cuándo reponer, sin planillas."
- **Electrónica**: "cada producto se carga escaneando el código de barras, y si otro comercio ya lo cargó aparece solo."
- **Veterinaria**: "llevás el stock de tus productos y accesorios al día desde el celular." *(no mencionar alimento suelto o a granel)*
- **Tienda de ropa**: "controlás el stock por talle y color, para saber qué te queda de cada prenda."

Además se rota el saludo (Hola / Buenas / Buen día) y el cierre. Cada envío guarda qué variante se usó.

> **Antes de enviar**: confirmar con vos qué tono usás (vos/tú, más formal o más casual) y que el link de la demo funcione desde el celular.

### Límites y horarios
| Etapa | Mensajes por día |
|---|---|
| Piloto (número normal) | 30 a 40, repartidos en 5 a 7 días |
| Si no hay problemas | Subir de a poco hasta 50 a 80 |
| API oficial | Límite inicial de Meta (~250 contactos nuevos por día; confirmar al configurar) |

| Franja | Uso |
|---|---|
| 9:00 a 11:00 | La mejor |
| 14:30 a 16:30 | Buena |
| 12:00 a 14:00 | Evitar (almuerzo/siesta) |
| Después de 18:00, domingos y feriados | Evitar |

- Mejores días: martes a jueves.
- Dos tandas por día de 15 a 20 mensajes.
- Pausas aleatorias de **45 a 120 segundos**.

---

## 7. Base de datos y embudo

```
pendiente → enviado → respondió → pidió_demo → empezó_prueba → compró
                 │           └→ no_interesado
                 └→ sin_respuesta (tras el recordatorio)
cualquiera → no_contactar (lista negra permanente)
```

Campos extra: variante_usada, fecha_envío, franja_horaria, clic_en_link, fecha_respuesta, texto_respuesta, fecha_inicio_prueba, fecha_compra, fecha_recordatorio, plan_cotizado.

### Conexión con el sistema de Kahabox (oportunidad)
El repo ya tiene un flujo de **registro con aprobación manual**: cuando un negocio se registra, se crea un tenant y llega un aviso por Discord/email con links para aprobar o rechazar. Se puede aprovechar para que el bot sepa **automáticamente quién empezó la prueba**, cruzando el teléfono o nombre del negocio, sin cargarlo a mano. A definir: cómo se relaciona el registro con el número al que se le escribió (por ejemplo, pedir el WhatsApp en el registro).

> **A verificar en el repo**: existe el estado `trial` en los tenants, pero no confirmé que la duración de **14 días** esté implementada (vencimiento automático). Conviene revisarlo antes de prometerla en los mensajes.

---

## 8. Módulo de respuestas

- Detectar quién contestó y **avisarte al celular al instante**.
- Clasificar:
  - **Interesado / pide demo** → `pidió_demo`, aviso inmediato.
  - **Pregunta o "¿cuánto sale?"** → aviso prioritario; respondés vos a mano con el precio a medida.
  - **"No me interesa"** → `no_interesado`.
  - **"NO", "basta", "no molestar"** → `no_contactar`, nunca más se le escribe.
- Con la opción B, este módulo es manual (anotás en la base). Con la API oficial se automatiza vía webhook.

---

## 9. Seguimiento

### Recordatorio único (no respondieron)
A los 3 o 4 días, un solo mensaje con **otra variante**. Si sigue sin respuesta → `sin_respuesta`. No insistir más.

### Prueba de 14 días
| Día | Mensaje |
|---|---|
| 1 | Bienvenida y ayuda para cargar los primeros productos (escanear o importar el Excel) |
| 2 | "¿Pudiste entrar? ¿Te ayudo?" |
| 7 | Chequeo de uso y dudas |
| 12 | Cierre: conversar el plan que le conviene según su negocio |

El **día 12** es donde se habla de precio, con las preguntas de la sección 2.

---

## 10. Controles de seguridad

- Límite diario configurable que el bot no puede superar.
- **Modo de prueba (dry run)** que simula sin enviar.
- Freno automático ante errores, bloqueos o quejas seguidas.
- Lista negra permanente.
- Filtro previo de números fijos o inválidos.
- Reintentos y log de todo lo enviado.
- Respaldo periódico de la base.
- Secretos y número en `.env`, fuera del código. Al no usar Places, **no hay claves de API de terceros** en el proyecto.
- Con API oficial: plantillas aprobadas por Meta.

---

## 11. Piloto y estimaciones

### Piloto
- **Tamaño**: mínimo 200 a 300; ideal **500 a 1.000**.
- **Ritmo**: 30 a 40 por día. **No 300 en un solo día.**
- **Medir**: respuestas, demos pedidas, pruebas iniciadas, quejas, y qué variante/rubro/horario rinde más.

### Embudo estimado (supuestos, no datos reales)
| Etapa | Bajo | Medio | Alto |
|---|---|---|---|
| Reciben el mensaje (tienen WhatsApp) | 60% | 70% | 80% |
| Piden demo/prueba | 1% | 2% | 4% |
| Compran tras probar | 10% | 15% | 25% |

### Pruebas iniciadas con 1.000 envíos
| Escenario | % que empieza prueba | Esperadas | Prob. ≥5 | Prob. ≥10 |
|---|---|---|---|---|
| Muy pesimista | 0,3% | 3 | 18% | 0,1% |
| Pesimista | 0,6% | 6 | 71% | 8% |
| Realista | 1,4% | 14 | 99,9% | 89% |
| Optimista | 3% | 30 | ~100% | ~100% |

Negocios necesarios para 10 pruebas (promedio): optimista ~330, realista ~710, pesimista ~1.670, muy pesimista ~3.300.

### Cómo leer el resultado de 1.000 envíos
| Pruebas | Significado |
|---|---|
| 0 a 2 | Mensaje u oferta no funcionan; rehacerlos |
| 3 a 6 | Pesimista; mejorar y seguir |
| 7 a 15 | Realista; vale escalar |
| 16 o más | Optimista; escalar con confianza |

Con 200 a 300 envíos esperá entre 0 y 2 pruebas: sirve para ver tendencias, no para concluir.

---

## 12. Reportes

- Enviados, respondieron, demos, pruebas, compras.
- Tasa de respuesta por variante, rubro y franja horaria.
- Clics en el link del video.
- Quejas y bajas.
- Costo por prueba y por cliente (hoy 0, porque la única fuente de datos es gratuita; solo aparece costo si más adelante se migra a la API de WhatsApp).

---

## 13. Estructura del proyecto

```
kahabots/
├── bot1_recolector.py       # arma la lista desde CSV / padrones, normaliza y deduplica
├── bot2_mensajero.py        # abre wa.me con límite diario y dry run
├── respuestas.py            # clasifica respuestas y avisa
├── seguimiento.py           # recordatorio y mensajes de los 14 días
├── reportes.py              # métricas del piloto
├── database.py              # SQLite: contactos, estados, envíos
├── config.py                # límites, horarios, zonas
├── mensajes.json            # variantes por rubro y seguimiento (sin precios)
├── .env                     # secretos, fuera del repo
├── contactos.db
├── requirements.txt
└── datos/                   # padrones oficiales, OCR y parser
    ├──padrones/*.pdf
    ├── ocr/*.txt            # texto extraído por Tesseract
    ├── ocr_padron.py        # PDF → imagen → OCR
    └── parsear_padron.py    # texto OCR → negocios filtrados
```

---

## 14. Fases de trabajo

| Fase | Tarea | Resultado |
|---|---|---|
| 1 | Reunir padrones oficiales de los rubros y dejarlos OCR'd | `datos/ocr/` con texto |
| 2 | **Validar 10 negocios a mano** (nombre, rubro, ciudad, teléfono, dirección) | Confirmación del usuario |
| 3 | Base de datos con estados del embudo | `database.py` |
| 4 | Extraer en masa combinando fuentes y deduplicando | Lista de contactos |
| 5 | Ajustar y cargar variantes en `mensajes.json` | Mensajes listos |
| 6 | Bot 2 semi-automático con límite diario y dry run | Pruebas con 5-10 contactos |
| 7 | **Piloto** 30-40 por día hasta 300-1.000 | Datos reales |
| 8 | Respuestas y reportes | Saber qué funciona |
| 9 | Seguimiento de los 14 días | Mejor conversión |
| 10 | Migrar a WhatsApp Business API | Escalar seguro |

---

## 15. Lo que falta definir

1. **Video demo** grabado y subido a un link.
2. **Tono** de los mensajes (vos / tú, formal o casual) y tu nombre para firmarlos.
3. **Zonas y barrios** a cubrir.
4. **Fuentes de datos**: conseguir el padrón oficial de ferretería y el de electrónica, que son los que faltan. El de veterinaria ya está.
5. **Opción de envío** para el piloto (A, B o C).
6. **Número** desde el que se envía y dónde llegan las respuestas.
7. Verificar en el repo que la **prueba de 14 días** funcione (vencimiento) y cómo se vincula el registro con el contacto.
8. Definir qué responder a quienes pregunten por **venta a granel/por peso**.
