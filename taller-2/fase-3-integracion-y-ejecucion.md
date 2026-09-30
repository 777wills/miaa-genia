# Fase 3 · Integración y ejecución del código

**Caso:** optimización de la atención al cliente en EcoMarket con generación aumentada por
recuperación
**Autores:** William Alberto Suaza · Anderson Trujillo · Bairon Gutiérrez

---

## 1. Qué construimos

Llevamos a código las decisiones de las fases 1 y 2. Contruimos un asistente de línea de
comandos que conserva la interfaz del Taller 1: recibe el archivo con el mensaje del cliente, un
archivo de configuración y, opcionalmente, un archivo de salida. Por dentro, ahora ejecuta una
cadena RAG completa.

| Archivo                                                            | Responsabilidad                                                                                                                                        |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [src/rag.py](src/rag.py)                                           | Núcleo compartido: carga y segmentación de documentos, embeddings, ChromaDB, recuperación, reranking, búsqueda exacta de pedidos, prompt y cadena LCEL |
| [src/indexar.py](src/indexar.py)                                   | Construye el índice vectorial persistente y, con `--listar`, vuelca los fragmentos a `outputs/indice/fragmentos.md`                                    |
| [src/app.py](src/app.py)                                           | Asistente: ejecuta la cadena para un mensaje y guarda la respuesta con la lista de fragmentos que la sustentan                                         |
| [src/interfaz.py](src/interfaz.py)                                 | Interfaz de chat con Gradio: conversación con historial, selector de variante y panel con lo que recibió el modelo (sección 7.1)                       |
| [src/experimento.py](src/experimento.py)                           | Mide la recuperación sin reranking y con reranking sobre 24 consultas etiquetadas                                                                      |
| [src/settings-sin-reranking.toml](src/settings-sin-reranking.toml) | Variante A: los 4 candidatos más similares según el bi-encoder                                                                                         |
| [src/settings-reranking.toml](src/settings-reranking.toml)         | Variante B: los 20 candidatos reordenados por el cross-encoder, con umbral de relevancia                                                               |
| [generar_salidas.sh](generar_salidas.sh)                           | Ejecuta de principio a fin: índice, ocho consultas con ambas variantes y experimento                                                                   |

Las dos configuraciones comparten el modelo, los prompts y los datos. Difieren solo en la sección
`[recuperacion]`, así que cualquier diferencia en los fragmentos que recibe el modelo se debe al
reranking. En la redacción de las respuestas influye además la variabilidad propia del modelo
generativo.

## 2. Los pasos del flujo RAG en nuestra implementación

Un sistema RAG se organiza en una secuencia de pasos: preparar la base de conocimiento, segmentar,
vectorizar, indexar, recuperar, reordenar los candidatos y generar la respuesta. Seguimos la
arquitectura en tres etapas que trabajamos en clase: recuperación rápida con un bi-encoder,
reordenamiento preciso con un cross-encoder y generación con el contexto resultante. La
implementamos con LangChain y le añadimos lo que exige el caso de EcoMarket: documentos
heterogéneos, recuperación exacta de pedidos y un umbral de abstención.

| Paso del flujo           | Pieza en nuestra implementación                                                           | Decisión para EcoMarket                                                                                                             |
| ------------------------ | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| 1. Base de conocimiento  | `construir_base_conocimiento()`, con un cargador por formato                              | Cuatro documentos de la empresa (Markdown, JSON, CSV y PDF) fuera del código: actualizar el conocimiento no exige tocar el programa |
| 2. Modelo de embeddings  | `obtener_embeddings()`: `HuggingFaceEmbeddings` con `intfloat/multilingual-e5-base`       | Modelo multilingüe entrenado para recuperación en español, con prefijos `query:` y `passage:` y vectores normalizados (Fase 1)      |
| 3. Segmentación          | `fragmentar_politica()`, `fragmentar_faq()`, `fragmentar_catalogo()`, `fragmentar_guia()` | Estrategia estructural por tipo de documento, con `RecursiveCharacterTextSplitter` como respaldo (Fase 2)                           |
| 4. Base vectorial        | `abrir_almacen()` y `obtener_almacen()`: Chroma persistente en `src/indice/`, coseno      | El índice se construye una vez con `indexar.py` y se reutiliza; cada fragmento lleva un identificador estable y metadatos           |
| 5. Recuperación          | `recuperar_candidatos()`                                                                  | 20 candidatos por similitud de coseno                                                                                               |
| 6. Reranking             | `puntuar_con_reranker()` y `seleccionar_fragmentos()`                                     | Segunda etapa con cross-encoder y umbral de relevancia, activable desde la configuración                                            |
| 7. Datos transaccionales | `recuperar_pedidos()`                                                                     | Búsqueda exacta por número de seguimiento, como en el Taller 1                                                                      |
| 8. Modelo de lenguaje    | `construir_llm()` con `ChatGoogleGenerativeAI` y `gemini-3.5-flash-lite`                  | Familia Gemini Flash del Taller 1 y el mismo modelo en ambas variantes, para que el efecto medido sea solo el de la recuperación    |
| 9. Cadena                | `construir_cadena()` con LCEL: recuperar → seleccionar → prompt → modelo → texto          | Composición explícita de pasos que devuelve, junto con la respuesta, los fragmentos usados; el prompt es el de Iris                 |
| 10. Interacción          | `app.py` con argumentos de línea de comandos; `cadena.invoke({"consulta": ...})`          | Misma interfaz del Taller 1; cada ejecución queda registrada en `outputs/` con los fragmentos que la sustentan                      |

## 3. Cómo se conectan las piezas

### 3.1 La cadena LCEL

La función `construir_cadena()` de `rag.py` arma la cadena completa. La cadena recibe un
diccionario `{"consulta": ...}` y, en cada eslabón, le agrega una clave nueva. Al final devuelve la
respuesta junto con todo lo que se usó para producirla.

```python
return (
    RunnablePassthrough.assign(candidatos=recuperar)       # etapa 1: bi-encoder + Chroma
    | RunnablePassthrough.assign(fragmentos=seleccionar)   # etapa 2: reranking o corte directo
    | RunnablePassthrough.assign(respuesta=generar)        # prompt → Gemini → texto
)
```

```mermaid
flowchart LR
    A["{consulta}"] --> B["recuperar<br/>recuperar_candidatos(k=20)"]
    B --> C["{consulta, candidatos}"]
    C --> D{"reranking<br/>en el TOML"}
    D -->|"false"| E["candidatos[:4]"]
    D -->|"true"| F["puntuar_con_reranker<br/>ordenar · top 4 · umbral"]
    E --> G["{consulta, candidatos, fragmentos}"]
    F --> G
    G --> GEN
    subgraph GEN["generar"]
        direction TB
        H1["pedidos ← recuperar_pedidos(consulta)"]
        H2["conocimiento ← formatear_conocimiento(fragmentos)"]
        H3["ChatPromptTemplate<br/>rol · ejemplos · contexto · consulta · instrucciones"]
        H4["ChatGoogleGenerativeAI"]
        H5["StrOutputParser"]
        H1 --> H3
        H2 --> H3
        H3 --> H4 --> H5
    end
    GEN --> I["{consulta, candidatos, fragmentos, respuesta}"]
```

Cada eslabón es un `Runnable` de LangChain, así que la cadena completa también lo es. Esto tiene
tres consecuencias prácticas:

- **La variante se elige por configuración.** `seleccionar_fragmentos()` lee `reranking` del TOML.
  La misma cadena sirve para las dos variantes del experimento, sin duplicar código.
- **La cadena es observable.** `app.py` recibe `fragmentos` en el resultado y los imprime en la
  cabecera de cada salida con su posición vectorial, su similitud y su puntaje del reranker, de modo
  que cada respuesta documenta de dónde proviene.
- **Las piezas son reemplazables.** Cambiar ChromaDB por otra base vectorial, E5 por otro modelo de
  embeddings o Gemini por otro modelo solo requiere modificar una función, no la cadena.

### 3.2 Etapa 1: recuperación vectorial

```python
def recuperar_candidatos(consulta: str, k: int) -> list[Document]:
    resultados = obtener_almacen().similarity_search_with_score(consulta, k=k)
    ...
        metadata = {**documento.metadata, "posicion_vectorial": posicion,
                    "similitud": round(1 - distancia, 4)}
```

`similarity_search_with_score` vectoriza la consulta con el mismo `HuggingFaceEmbeddings` que se
usó al indexar, con el prefijo `query:`, y le pide a Chroma los 20 vecinos más cercanos. Chroma
devuelve la distancia de coseno. La convertimos en similitud, restando la distancia de 1, y
guardamos junto con ella la posición original de cada candidato, para poder ver después cuánto lo
movió el reranker.

### 3.3 Etapa 2: reranking

```python
def puntuar_con_reranker(consulta, candidatos, nombre_modelo):
    pares = [(consulta, candidato.page_content) for candidato in candidatos]
    puntajes = obtener_reranker(nombre_modelo).predict(pares)
    ...
    return sorted(puntuados, key=lambda d: d.metadata["puntaje_reranker"], reverse=True)

def seleccionar_fragmentos(consulta, candidatos, recuperacion):
    n = recuperacion["n_finales"]
    if not recuperacion.get("reranking", False):
        return candidatos[:n]
    reordenados = puntuar_con_reranker(consulta, candidatos, recuperacion["modelo_reranker"])
    umbral = recuperacion.get("umbral_relevancia", 0.0)
    if not reordenados or reordenados[0].metadata["puntaje_reranker"] < umbral:
        return []
    return reordenados[:n]
```

El `CrossEncoder` de sentence-transformers recibe cada par (consulta, fragmento) en una sola
entrada. El modelo lee ambos textos juntos y devuelve un puntaje entre 0 y 1. Ordenamos por ese
puntaje y conservamos los cuatro mejores. El umbral se aplica al **mejor** candidato: si ni
siquiera el primero lo alcanza, interpretamos que la base no tiene respaldo para la consulta y la
lista queda vacía. En ese caso, `formatear_conocimiento()` escribe en el bloque CONOCIMIENTO que no
se recuperó información relevante. Esa es la señal que el prompt de Iris convierte en la
clasificación `SIN_INFORMACION_DISPONIBLE`.

Aplicar el umbral a cada fragmento por separado descartaría fragmentos relevantes que complementan
la respuesta, con puntajes bajos pero útiles (sección 5.6). Por eso el umbral decide si hay
respaldo o no, y el orden decide qué se entrega.

Implementamos el reranking como una función propia envuelta en `RunnableLambda` en lugar de usar
`CrossEncoderReranker` de LangChain por dos razones. Ese componente vive hoy en el paquete de
compatibilidad `langchain-classic` y descarta el puntaje, que necesitamos para el umbral y para el
experimento.

### 3.4 Generación

El prompt se construye con `ChatPromptTemplate` en el mismo orden que usamos en el Taller 1:
instrucción de sistema con el rol de Iris, ejemplos etiquetados como turnos humano–asistente,
contexto, consulta e instrucción final. Los textos fijos del TOML se insertan como mensajes ya
construidos (`SystemMessage`, `HumanMessage`, `AIMessage`), de modo que LangChain no intente
interpretar sus llaves como variables. Solo el contexto y la consulta son plantillas. El contexto
conserva los delimitadores del Taller 1:

```
>>>>> INICIO PEDIDOS
{pedidos}
<<<<< FIN PEDIDOS

>>>>> INICIO CONOCIMIENTO
{conocimiento}
<<<<< FIN CONOCIMIENTO
```

`ChatGoogleGenerativeAI` envía la secuencia al modelo configurado en el TOML, `gemini-3.5-flash-lite`,
y `StrOutputParser` extrae el texto de la respuesta.

## 4. Ajustes respecto al Taller 1

| Aspecto                    | Taller 1 (`settings-final.toml`)                         | Taller 2                                                                                                                                                                        |
| -------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cliente del modelo         | `google-genai` directo, con `types.Content`              | `ChatGoogleGenerativeAI` de LangChain, dentro de una cadena LCEL                                                                                                                |
| Contexto documental        | La política de devoluciones completa en cada llamada     | Los cuatro fragmentos más relevantes de cuatro documentos                                                                                                                       |
| Contexto transaccional     | Pedidos citados, por coincidencia exacta                 | Sin cambios: la misma función `recuperar_pedidos()`                                                                                                                             |
| Bloques delimitados        | PEDIDOS y POLITICA_DEVOLUCIONES                          | PEDIDOS y CONOCIMIENTO; cada fragmento lleva su fuente y su sección                                                                                                             |
| Instrucciones              | Diez pasos centrados en estado de pedidos y devoluciones | Nueve pasos para cualquier tema. Iris debe verificar que el fragmento trate exactamente lo que se pregunta, responder solo lo que tiene respaldo y decir qué no puede responder |
| Clasificación de salida    | `RESUELTO_POR_ASISTENTE` o `REQUIERE_AGENTE_HUMANO`      | Se añade `SIN_INFORMACION_DISPONIBLE`                                                                                                                                           |
| Ejemplos etiquetados       | Consulta de pedido y consulta de devolución              | Un ejemplo con un fragmento que sí responde y otro con el bloque CONOCIMIENTO vacío, que enseña a abstenerse                                                                    |
| Configuraciones comparadas | Prompt básico frente a prompt final                      | Sin reranking frente a con reranking, con el mismo prompt                                                                                                                       |
| Salida guardada            | Consulta, configuración, modelo y respuesta              | Se añaden los parámetros de recuperación y la lista de fragmentos entregados con sus puntajes                                                                                   |

## 5. Experimento: sin reranking frente a con reranking

### 5.1 Diseño

**Pregunta.** El modelo generativo solo puede responder bien si recibe los fragmentos correctos.
Queremos saber si el reranker mejora esa selección: si, entre los 20 candidatos que trae la
búsqueda vectorial, escoge mejor los cuatro que finalmente lee Iris.

**Cómo lo medimos.** Para cada consulta de prueba, [src/experimento.py](src/experimento.py) hace la
búsqueda vectorial **una sola vez** y obtiene los mismos 20 candidatos para todas las variantes. A
partir de ahí, cada variante elige sus cuatro fragmentos de una forma distinta:

```mermaid
flowchart LR
    Q["Consulta de prueba"] --> V["Búsqueda vectorial<br/>20 candidatos"]
    V --> A["Variante A<br/>los 4 más parecidos<br/>según el bi-encoder"]
    V --> R["El cross-encoder<br/>vuelve a leer los 20<br/>y los reordena"]
    R --> B["Variante B<br/>los 4 mejor puntuados<br/>por el reranker"]
    R --> C["Variante C<br/>igual que B, salvo que<br/>se abstiene si ni el mejor<br/>alcanza el umbral"]
    A --> K["Se comparan los 4 elegidos<br/>con la clave de respuestas"]
    B --> K
    C --> K
```

- **Variante A, sin reranking.** Toma los cuatro primeros candidatos en el orden en que los dejó el
  bi-encoder, es decir, los cuatro textos más parecidos a la consulta.
- **Variante B, con reranking.** El cross-encoder lee cada uno de los 20 candidatos junto con la
  consulta, le asigna un puntaje de relevancia y se quedan los cuatro mejores.
- **Variante C, con reranking y umbral.** Es la variante B tal como funciona en
  `settings-reranking.toml`: si ni siquiera el mejor candidato alcanza el umbral de relevancia, no
  entrega ningún fragmento y Iris debe decir que no tiene la información.

Como las tres variantes parten de los mismos 20 candidatos y entregan como máximo cuatro, cualquier
diferencia entre A y B se debe solo a **cómo se eligen** esos cuatro. La comparación entre A y C
muestra, además, cuánto cuesta la abstención en la configuración que usa el asistente.

El experimento no llama al modelo generativo. Evalúa el contexto que recibiría Iris, no la
redacción de su respuesta. Por eso da siempre el mismo resultado y no consume cuota de la API.

**La clave de respuestas.** Redactamos 24 consultas de prueba en
[consultas-evaluacion.json](src/datos/evaluacion/consultas-evaluacion.json), distintas de las ocho
consultas de cliente que usamos después para comparar respuestas. Para cada una revisamos la base y
anotamos qué fragmentos sirven para contestarla, con dos niveles:

- **Relevancia 2:** el fragmento responde directamente la pregunta.
- **Relevancia 1:** el fragmento no la responde por sí solo, pero aporta un dato complementario.

Con esa clave, el script puede revisar automáticamente si los cuatro fragmentos elegidos por cada
variante son los que debían llegar al modelo. Las consultas cubren cinco situaciones:

| Tipo             | Cantidad | Qué pone a prueba                                                            | Ejemplo                                                                                |
| ---------------- | -------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Directa          | 6        | Consultas con el mismo vocabulario del documento                             | «¿Qué métodos de pago aceptan?»                                                        |
| Paráfrasis       | 8        | Lenguaje coloquial y palabras distintas a las del documento                  | «se me olvidó la clave para entrar a la página, qué hago»                              |
| Distractor       | 4        | Consultas cuyo vocabulario coincide con un fragmento que **no** las responde | «¿Les puedo devolver la caja de cartón en la que me llegó el pedido?»                  |
| Multidocumento   | 2        | La respuesta completa exige fragmentos de dos o tres documentos              | «Si mando a grabar el termo con un nombre, ¿lo puedo devolver después si no me gusta?» |
| Fuera de alcance | 4        | Solicitudes sin respuesta en la base, para calibrar el umbral                | «¿Ustedes instalan paneles solares en el techo de las casas?»                          |

### 5.2 Métricas

Todas las métricas comparan los cuatro fragmentos elegidos con la clave de respuestas. El sufijo
«@4» indica que se calculan sobre esos cuatro, que son los que lee Iris. Cada métrica vale entre
0 y 1, y se promedia sobre las 20 consultas que tienen respuesta en la base.

| Métrica     | Pregunta que responde                                                  | Cómo se calcula                                                                             |
| ----------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Hit@4       | ¿Llegó al modelo al menos un fragmento útil?                           | Vale 1 si hay alguno entre los cuatro y 0 si no hay ninguno                                 |
| MRR@4       | ¿Qué tan arriba aparece el primer fragmento útil?                      | Vale 1 si está en el primer puesto, 1/2 en el segundo, 1/3 en el tercero y 1/4 en el cuarto |
| Precision@4 | De lo que recibe el modelo, ¿qué parte sirve?                          | Fragmentos útiles entre los cuatro, dividido entre cuatro                                   |
| Recall@4    | De lo que debía recibir el modelo, ¿qué parte le llegó?                | Fragmentos útiles entre los cuatro, dividido entre el total de útiles de la clave           |
| nDCG@4      | ¿Qué tan bueno es el conjunto elegido, comparado con el mejor posible? | Se explica abajo                                                                            |
| Recall@20   | ¿Cuántos fragmentos útiles alcanzó a traer la búsqueda vectorial?      | Como Recall@4, pero sobre los 20 candidatos                                                 |

**nDCG@4, la métrica central.** Las otras métricas tratan igual a todos los fragmentos útiles.
nDCG@4 distingue dos cosas más: si el fragmento responde la pregunta o solo la complementa, y en
qué puesto quedó. Funciona como un puntaje por puntos:

1. Cada fragmento útil suma puntos. Uno que responde directamente vale 3 puntos y uno que
   complementa vale 1.
2. Los puntos pesan menos cuanto más abajo queda el fragmento. En el primer puesto cuentan
   completos, en el segundo cuentan un 63%, en el tercero un 50% y en el cuarto un 43%. Así se
   premia que lo más importante quede primero.
3. El total se divide entre el puntaje que tendría la mejor selección posible para esa consulta.
   Un nDCG@4 de 1 significa que la variante eligió y ordenó los fragmentos de la mejor manera
   posible; uno de 0, que no entregó ninguno útil.

**Un ejemplo real.** Para la consulta «¿en cuánto tiempo me devuelven la plata después de
mandarles el producto de vuelta?», la clave marca tres fragmentos: los plazos generales de la
política, que responden directamente, y el proceso de devolución y los reembolsos al medio de
pago, que complementan.

| Puesto | Variante A, sin reranking           | Variante B, con reranking           |
| ------ | ----------------------------------- | ----------------------------------- |
| 1      | Proceso de devolución (complementa) | **Plazos generales (responde)**     |
| 2      | Pregunta frecuente sobre alimentos  | Proceso de devolución (complementa) |
| 3      | Categorías no retornables           | Excepciones de la política          |
| 4      | Cobros duplicados                   | Pregunta frecuente sobre garantías  |

| Métrica     | A    | B    | Lectura                                                         |
| ----------- | ---- | ---- | --------------------------------------------------------------- |
| Hit@4       | 1    | 1    | Las dos entregan algo útil                                      |
| MRR@4       | 1    | 1    | En las dos, el primer puesto es útil                            |
| Precision@4 | 0,25 | 0,50 | A acierta uno de cuatro; B, dos de cuatro                       |
| Recall@4    | 0,33 | 0,67 | A trae uno de los tres fragmentos de la clave; B, dos           |
| nDCG@4      | 0,24 | 0,88 | Solo B entrega el fragmento que responde, y en el primer puesto |

Hit@4 y MRR@4 no ven diferencia, porque en ambas variantes el primer fragmento sirve. Pero la
variante A nunca le entrega a Iris el plazo del reembolso, que es justo lo que el cliente
pregunta. nDCG@4 sí lo refleja. Por eso es la métrica central: el aporte que esperamos del reranker
es elegir y ordenar mejor, y nDCG@4 es la única de estas métricas que premia tener el fragmento
que responde por encima del que complementa.

**Recall@20, el techo del sistema.** El reranker solo puede reordenar lo que la búsqueda vectorial
trajo. Si un fragmento útil no está entre los 20 candidatos, ninguna variante puede entregarlo.
Recall@20 mide ese límite, y depende del modelo de embeddings y de la segmentación, no del
reranker.

### 5.3 Resultados agregados

El reporte completo generado por el script está en
[outputs/experimento/reporte.md](outputs/experimento/reporte.md) y los valores por consulta, en
[metricas.csv](outputs/experimento/metricas.csv).

Sobre las 20 consultas que tienen respuesta en la base, en promedio:

| Métrica     | Sin reranking (A) | Con reranking (B) | B − A      | Con reranking y umbral (C) | C − A  |
| ----------- | ----------------- | ----------------- | ---------- | -------------------------- | ------ |
| Hit@4       | 0,900             | 1,000             | +0,100     | 0,900                      | +0,000 |
| MRR@4       | 0,863             | 0,929             | +0,067     | 0,900                      | +0,037 |
| **nDCG@4**  | **0,765**         | **0,908**         | **+0,144** | **0,866**                  | +0,101 |
| Precision@4 | 0,325             | 0,400             | +0,075     | 0,375                      | +0,050 |
| Recall@4    | 0,783             | 0,933             | +0,150     | 0,858                      | +0,075 |

En palabras: sin reranking, los cuatro fragmentos elegidos alcanzan en promedio el 76,5% del puntaje
de la mejor selección posible; con reranking, el 90,8%. Con reranking, algún fragmento útil llega
en las 20 consultas, frente a 18 sin reranking, y en promedio el modelo recibe el 93,3% de lo que
debía recibir, frente al 78,3%.

La variante C pierde frente a B dos consultas, P04 y P06. En ambas el reranker había subido el
fragmento correcto a los cuatro primeros, pero el mejor candidato no alcanza el umbral (0,0033 y
0,0004) y el sistema se abstiene. Aun con ese costo, la configuración que usa el asistente supera a
la variante sin reranking en todas las métricas salvo Hit@4, donde empata, y a cambio identifica
tres de las cuatro consultas fuera de alcance (sección 5.6), algo que la variante A no puede hacer.

El techo de la primera etapa es **Recall@20 = 0,975**: el 97,5% de los fragmentos útiles llega a los
20 candidatos. Con reranking, el Recall@4 es 0,933, es decir, el reranker lleva a los cuatro
primeros puestos casi todo lo que la búsqueda vectorial encontró.

Consulta por consulta, el reranking mejora nDCG@4 en 10, lo empeora en
1 y lo deja igual en 9. Para saber si ese balance podría deberse al azar, aplicamos una prueba de
signos a las 11 consultas en las que hubo cambio. La idea es la de lanzar una moneda: si el
reranking no tuviera ningún efecto, en cada consulta sería igual de probable que mejorara o que
empeorara, como sacar cara o sello. Obtener por puro azar un resultado tan desequilibrado como 10
de 11, hacia cualquiera de los dos lados, ocurre en poco más de 1 de cada 100 intentos (p ≈ 0,012).
Es lo bastante improbable para descartar la casualidad con el criterio habitual del 5%, aunque con
solo 20 consultas la prueba no permite estimar con precisión el tamaño de la mejora.

Los valores de Precision@4 son bajos en ambas variantes por construcción: la mayoría de las
consultas tiene uno o dos fragmentos útiles en la clave, así que, aunque la variante acierte todos,
tres o dos de los cuatro puestos quedan con fragmentos que no estaban en la clave. Lo informativo
es la diferencia entre variantes, no el valor.

### 5.4 Resultados por tipo de consulta

| Tipo           | Consultas | MRR@4 sin | MRR@4 con | nDCG@4 sin | nDCG@4 con |
| -------------- | --------- | --------- | --------- | ---------- | ---------- |
| Directa        | 6         | 1,000     | 1,000     | 0,988      | 0,991      |
| Paráfrasis     | 8         | 0,656     | 0,823     | 0,554      | **0,842**  |
| Distractor     | 4         | 1,000     | 1,000     | 0,913      | 0,957      |
| Multidocumento | 2         | 1,000     | 1,000     | 0,639      | **0,832**  |

**Consultas directas: el reranker casi no aporta.** Cuando el cliente usa las palabras del
documento, el bi-encoder ya pone el fragmento correcto en el primer lugar en las seis consultas.

**Paráfrasis: el reranker aporta más.** Es el tipo de consulta que más se parece a como escriben
los clientes reales, y donde el bi-encoder más falla:

| Consulta                                                                              | Fragmento principal             | Posición sin reranking | Posición con reranking |
| ------------------------------------------------------------------------------------- | ------------------------------- | ---------------------- | ---------------------- |
| «¿en cuánto tiempo me devuelven la plata después de mandarles el producto de vuelta?» | Plazos generales de la política | 5 (fuera de los 4)     | **1**                  |
| «quiero dejar de usar papel film para tapar la comida, ¿qué me sirve?»                | Envolturas de cera de abejas    | 4                      | **1**                  |
| «me mudé y el paquete ya salió de la bodega, ¿me lo pueden llevar a la casa nueva?»   | Cambios de dirección            | 13 (fuera de los 4)    | **3**                  |
| «¿por qué en mi pedido dice que todavía no tiene empresa de mensajería?»              | Transportadoras aliadas         | 14 (fuera de los 4)    | **4**                  |
| «necesito que la cuenta de cobro salga a nombre de mi empresa, ¿se puede?»            | Facturación electrónica         | 2                      | **1**                  |

En los casos con mayor salto, el bi-encoder ve «devolver», «comida», «bodega» o «pedido» y
prioriza fragmentos que comparten esas palabras. El cross-encoder lee la consulta y el fragmento
juntos, y reconoce que «me devuelven la plata» pregunta por el plazo del reembolso, que las
envolturas de cera reemplazan al papel film aunque el cliente nunca diga «cera», que «me mudé»
plantea un cambio de dirección y que «empresa de mensajería» equivale a «transportadora».

**Distractores: el encabezado contextual ya protege la primera posición.** Anticipábamos que este
sería el terreno del reranker. Sin embargo, el bi-encoder acertó el primer lugar en los cuatro
casos. Nuestra hipótesis es que lo explica el encabezado contextual de la Fase 2, aunque no la
aislamos con un experimento sin encabezados: el fragmento del programa «Devuelve
tu caja» empieza con «Preguntas frecuentes > Sostenibilidad» y la pregunta sobre cobros duplicados
recupera un fragmento titulado «Pagos rechazados y cobros duplicados». El reranker mejoró el orden
de los fragmentos complementarios (nDCG de 0,913 a 0,957).

**Multidocumento: el reranker completa el contexto.** En la consulta sobre grabar el termo, el
bi-encoder encontraba la pregunta frecuente sobre personalización, pero no la ficha del termo. El
reranker sube la ficha a los cuatro primeros (nDCG de 0,673 a 0,987), y así el modelo recibe la regla general y
el producto concreto.

### 5.5 Casos negativos

- **El único empeoramiento es menor.** En «¿Qué métodos de pago aceptan?», el reranker intercambia
  la posición 3 y la 4. La pregunta frecuente sobre seguridad de pagos, marcada con relevancia 1,
  baja un lugar, y sube la sección de pagos a cuotas, que no marcamos como relevante aunque
  razonablemente lo es. nDCG baja de 0,964 a 0,945.
- **El reranker no rescata lo que la etapa 1 no encontró.** En la consulta P06 sobre la
  transportadora pendiente, el fragmento complementario de tiempos de alistamiento no llega a los
  20 candidatos, y ningún reordenamiento puede traerlo. Es el único fragmento relevante de todo el
  conjunto que se queda fuera, y por eso el Recall@20 es 0,975 y no 1.
- **Mejorar el promedio no garantiza mejorar cada posición.** En «Me llegó el desodorante con el
  sello roto», el fragmento de excepciones baja de la posición 3 a la 4, aunque sigue dentro de los
  cuatro entregados. nDCG mejora porque el reranker sube la ficha del desodorante y la tabla de
  categorías no retornables.

### 5.6 Umbral de relevancia: cuándo decir «no tengo esa información»

EcoMarket necesita que el asistente avise cuando no tiene con qué atender una solicitud. La variante
sin reranking no tiene forma de detectarlo: siempre entrega los cuatro fragmentos más similares,
aunque la consulta sea sobre el precio del dólar. Evaluamos si alguna de las dos puntuaciones
disponibles permite distinguir las consultas con respuesta de las que no la tienen.

| Puntuación del mejor candidato   | Con respuesta (20 consultas) | Fuera de alcance (4 consultas) | ¿Separa?                  |
| -------------------------------- | ---------------------------- | ------------------------------ | ------------------------- |
| Similitud de coseno (bi-encoder) | de 0,811 a 0,917             | de 0,777 a 0,826               | No: los rangos se solapan |
| Puntaje del reranker             | de 0,0004 a 0,9997           | de 0,0000 a 0,0331             | Parcialmente              |

La similitud de coseno de E5 se concentra en un rango estrecho, de 0,78 a 0,92, sea cual sea la
consulta. Por eso no sirve como señal de abstención. El puntaje del reranker, en cambio, se extiende
por casi todo el intervalo de 0 a 1: tres de las cuatro consultas fuera de alcance obtienen menos de
0,001, y 17 de las 20 con respuesta superan 0,06.

**Qué umbral separa mejor el conjunto de evaluación.** Sobre las 24 consultas etiquetadas,
cualquier umbral entre 0,034 y 0,068, por ejemplo 0,05, atrapa las cuatro consultas fuera de
alcance con tres abstenciones indebidas. Pero ese valor no resiste los mensajes de cliente. La
consulta 01, «Me voy de camping… ¿qué me recomiendan, cuánto cuesta y tiene garantía?», obtiene
un puntaje máximo de 0,033, aunque el cargador solar está entre los primeros candidatos. Con un
umbral de 0,05, Iris respondería que no tiene información. Las consultas del conjunto de
evaluación son cortas y tienen una sola intención. Los mensajes reales, como este, combinan tres
preguntas, y el cross-encoder reparte su confianza entre ellas: ningún fragmento responde todo,
así que ninguno obtiene un puntaje alto. La consulta sobre envíos a Leticia muestra lo mismo, con
0,023.

**Umbral adoptado.** Por eso el umbral no tiene la tarea de decidir todos los casos, sino la de
descartar lo **claramente ajeno**. Los casos dudosos quedan para el paso 6 del prompt, que ordena a
Iris abstenerse cuando los fragmentos no responden la pregunta. Con ese criterio fijamos el umbral
en **0,005**:

| Umbral    | Abstenciones correctas (de 4) | Abstenciones indebidas (de 20) | Consultas de cliente bloqueadas por error |
| --------- | ----------------------------- | ------------------------------ | ----------------------------------------- |
| 0,05      | 4                             | 3 (P04, P05, P06)              | 01, 02 y 06                               |
| **0,005** | **3**                         | **2 (P04, P06)**               | **Ninguna**                               |

De las dos abstenciones indebidas, la de P06 tiene el puntaje más bajo de todas las consultas con
respuesta (0,0004), por debajo de dos de las consultas fuera de alcance, así que ningún umbral la
rescata sin dejar pasar lo ajeno. La de P04 queda muy cerca del umbral (0,0033): el reranker sube
el fragmento correcto a la posición 3, pero el mejor candidato no alcanza 0,005. No ajustamos el
umbral para rescatarla, porque sería calibrarlo a una consulta concreta del conjunto que
reportamos. La consulta fuera de alcance que supera el umbral, «¿Tienen vacantes
de trabajo en la bodega de Funza?», menciona una bodega que sí aparece en las preguntas
frecuentes. Ese caso queda en manos del prompt.

El costo de los errores no es simétrico, y eso justifica un umbral bajo. Una abstención indebida
deja sin respuesta a un cliente que preguntaba por un producto del catálogo. Una consulta ajena que
supera el umbral llega a Iris con fragmentos que no la responden, y el prompt le ordena reconocerlo.
Aplicar el umbral al mejor candidato, y no a cada fragmento, también reduce la pérdida de
información. Con el umbral de 0,005, un filtro por fragmento descartaría 5 fragmentos relevantes de los cuatro
entregados. Con el criterio adoptado, aplicado al mejor candidato, se pierden 2: los de P04 y P06, las
consultas en que el sistema se abstiene.

### 5.7 Costo en latencia

| Etapa                                           | Media por consulta en CPU |
| ----------------------------------------------- | ------------------------- |
| Búsqueda vectorial (embedding + Chroma, k = 20) | 169 ms                    |
| Reranking de 20 candidatos                      | 29.461 ms                 |

Son los valores de la ejecución reportada. En otras ejecuciones medimos entre 76 y 288 ms para la
búsqueda y entre 19,6 y 35,8 s para el reranking; la diferencia se debe a la carga del equipo en
cada momento. Las métricas de recuperación son idénticas entre ejecuciones, porque la recuperación
es determinista; solo cambia el tiempo. El reranker
multiplica por más de 100 el costo de la recuperación. En CPU, la ganancia en nDCG cuesta entre 20
y 36 segundos por consulta. Es aceptable para un asistente que hoy responde en
veinticuatro horas, pero no para un chat en tiempo real. En producción habría tres salidas, de menor
a mayor costo. La primera es bajar k de 20 a 10, que reduce la latencia a la mitad pero renuncia a
rescates como los de P04 y P06, cuyos fragmentos venían de las posiciones 13 y 14. La segunda es cambiar a un reranker
liviano, recalibrando el umbral porque su escala de puntajes es distinta. La tercera es ejecutar el
reranker en GPU.

## 6. Efecto en las respuestas de Iris

Las métricas muestran que el contexto mejora, pero lo que percibe el cliente es la respuesta. Para
observar el cambio en el **comportamiento del asistente** ejecutamos ocho consultas de cliente nuevas,
que no forman parte del conjunto de evaluación, con las dos configuraciones. Modelo, prompt, datos y
candidatos son idénticos. El modelo aplica parámetros de muestreo fijos que no controlamos (sección
8.1). Por eso atribuimos al reranking solo las diferencias que se explican por los fragmentos
entregados, que sí son deterministas, y no las diferencias de redacción. Las respuestas completas,
con la lista de fragmentos que recibió el modelo en cada caso, están en
[outputs/sin-reranking](outputs/sin-reranking) y [outputs/reranking](outputs/reranking).

| Consulta                                                | Sin reranking                                                                                                                                                                      | Con reranking                                                                                                                                     | Resultado               |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| 01 · Cargador para camping, precio y garantía           | Recomienda el cargador solar con precio y garantía correctos                                                                                                                       | Igual, y suma la pregunta frecuente de garantía, que aclara que las reclamaciones las atiende un agente                                           | Mejora de completitud   |
| 02 · ¿Envían a Leticia? ¿Cuánto cuesta y tarda?         | Recibe tarifas y tiempos por zona, pero no la lista de ciudades de cada zona: no puede ubicar a Leticia y lo reconoce, aunque clasifica la respuesta como `RESUELTO_POR_ASISTENTE` | El fragmento de cobertura sube de la posición 5 a la 1: confirma que Leticia es Zona 3, 24.900 pesos y de 6 a 10 días hábiles                     | **Mejora decisiva**     |
| 03 · Nequi, efectivo y cuotas                           | Correcta                                                                                                                                                                           | Correcta, con los mismos fragmentos; «Métodos de pago» sube de la posición 3 a la 2                                                               | Igual                   |
| 04 · «eso de los puntos cómo es?»                       | Explica el programa Semilla y remite a «Mi cuenta»                                                                                                                                 | Entra la pregunta frecuente sobre compras como invitado, e Iris advierte que esas compras no suman puntos                                         | Mejora de completitud   |
| 05 · No me devolvieron lo que pagué de envío            | Correcta: el fragmento sobre el reembolso del envío estaba en la posición 2, detrás de las excepciones de la política                                                              | El fragmento correcto pasa al primer lugar y la respuesta enumera en qué casos sí se reembolsa el envío                                           | Mejora de completitud   |
| 06 · Pedido ECO-2026-1372, el café llegó regado         | Aplica la excepción por producto averiado, no exige devolver el café y pide una foto, pero clasifica la respuesta como `REQUIERE_AGENTE_HUMANO` sin que la política lo exija       | Mismo contenido, pero el reranker pone primero el programa «Devuelve tu caja» y saca del contexto la tabla de categorías no retornables           | **Empeora el contexto** |
| 07 · Chaqueta de regalo: ¿devolución? ¿envío a Pereira? | Responde la devolución, pero dice no tener información sobre el costo del envío a Pereira                                                                                          | Suben la tabla de costos (14 → 3) y la de cobertura (12 → 4): Pereira es Zona 1 y la chaqueta de 289.000 pesos supera el mínimo para envío gratis | **Mejora decisiva**     |
| 08 · Quiero ser proveedor, ¿qué comisión cobran?        | Se abstiene: `SIN_INFORMACION_DISPONIBLE`                                                                                                                                          | Supera el umbral (0,010), pero los fragmentos no responden y el prompt hace que Iris se abstenga                                                  | Igual                   |

### 6.1 Qué muestran los casos

**Las mejoras decisivas aparecen en las consultas con más de una pregunta.** En las consultas 02 y
07, el cliente pregunta por dos cosas que viven en fragmentos distintos. El bi-encoder llena los
cuatro puestos con lo más parecido a la consulta completa y deja fuera el fragmento que resuelve la
segunda pregunta. El cross-encoder evalúa cada fragmento frente a la consulta y reconoce que la
lista de ciudades por zona es necesaria para responder «¿envían a Leticia?», aunque se parezca poco
al conjunto de la consulta. Sin reranking, Iris no inventa: reconoce que le falta información. El
reranking no la hace más confiable, la hace **más útil**.

**Cuando el bi-encoder ya acierta, el reranking no cambia la respuesta.** En las consultas 03 y 08
las respuestas son equivalentes. Esto coincide con las métricas de la sección 5.4 para las
consultas directas.

**El caso negativo es real y tiene una causa identificable.** En la consulta 06, «el grano venía
regado por toda la caja… ¿Les tengo que mandar el café de vuelta?» comparte palabras y sentido con
«¿Puedo devolverles la caja en la que llegó mi pedido?». Allí el cross-encoder cayó en el
distractor que el bi-encoder había resistido, y la tabla de categorías no retornables salió de los
cuatro entregados. La excepción de la política llegó en la segunda posición e Iris aplicó la regla correcta en
ambas variantes. Lo atribuible al reranking es el deterioro del contexto, no un error en la
respuesta. El reranker también es un modelo estadístico: reduce los errores de orden, no los
elimina.

**El reranking mejora el contexto, no la lectura del modelo.** En la consulta 06 sin reranking,
Iris recibió la excepción y la tabla de categorías no retornables, redactó bien la solución y aun
así clasificó el caso como `REQUIERE_AGENTE_HUMANO`, aunque la política no lo exige. En la
consulta 02 sin reranking reconoció que no podía confirmar el envío a Leticia, pero clasificó la
respuesta como resuelta. En los dos casos el contexto era suficiente para la clasificación correcta:
el error es de interpretación del modelo generativo. Esto refuerza la validación automática de la
respuesta que propusimos en la arquitectura del Taller 1: el RAG reduce las alucinaciones por falta
de información, pero no las que ocurren al interpretar la información recibida.

**Los pedidos no dependen del reranking.** En la consulta 06, ambas variantes identificaron el
pedido `ECO-2026-1372`, su titular y el café del pedido, porque ese dato llega por búsqueda exacta
y no por similitud.

En balance, en ocho consultas el reranking produjo dos mejoras decisivas, tres mejoras de
completitud, dos resultados iguales y un deterioro del contexto. Ocho consultas bastan para
ilustrar los mecanismos, pero no para estimar con precisión cuánto mejora la calidad de las
respuestas. Esa estimación la aportan las métricas de recuperación de la sección 5.

## 7. Ejecución

Las instrucciones completas de instalación están en el [README](README.md). En resumen:

```bash
python src/indexar.py --listar                    # construye el índice (una vez)
python src/app.py src/datos/consultas/07-multi-documento.txt \
  --configuracion src/settings-reranking.toml     # una consulta con reranking
python src/experimento.py                         # métricas de recuperación, sin API
python src/interfaz.py                            # chat en http://127.0.0.1:7860
./generar_salidas.sh                              # todo el flujo y las 16 respuestas
```

### 7.1 Interfaz de chat

[src/interfaz.py](src/interfaz.py) ofrece una conversación con Iris construida con Gradio. Usa la
misma cadena LCEL que `app.py`, con las dos configuraciones precargadas al arrancar, y un selector
permite alternar entre la variante con reranking y la variante sin reranking en cualquier momento
de la conversación. Cada respuesta indica con qué variante se generó.

La pantalla se divide en dos columnas. A la izquierda está la conversación, con la respuesta de
Iris escribiéndose a medida que Gemini la genera. A la derecha, un panel muestra lo que recibió el
modelo en el último turno:

- los fragmentos entregados, con su fuente y sección, su similitud, su posición vectorial y, con
  reranking, el puntaje del cross-encoder, junto con un extracto del texto;
- el pedido citado, cuando el mensaje incluye un número de seguimiento;
- un aviso cuando ningún fragmento alcanza el umbral de relevancia;
- la clasificación de la respuesta, que se retira del texto del chat y se muestra como etiqueta.

Mientras se procesa un mensaje, el panel indica la etapa en curso: la búsqueda vectorial, el
reordenamiento con el reranker o la redacción de la respuesta.

**Historial de la conversación.** El chat envía al modelo los tres turnos anteriores en un bloque
HISTORIAL, acompañado de la instrucción `historial_prompt` de los TOML. El historial solo sirve para
interpretar preguntas de seguimiento como «¿y cuánto cuesta?»: los datos de la respuesta siguen
saliendo únicamente de los bloques PEDIDOS y CONOCIMIENTO del turno. La recuperación de fragmentos
y la búsqueda de pedidos trabajan con el mensaje actual. `app.py`, `generar_salidas.sh` y el
experimento no envían historial, así que su prompt no incluye ese bloque.

La interfaz escucha solo en `127.0.0.1` para no exponer la clave ni la cuota de Gemini.

![Interfaz de chat de Iris con el panel de fragmentos consultados](imagenes/interfaz-chat.png)

La captura muestra la consulta «¿Qué métodos de pago aceptan?» con la variante con reranking. Iris
enumera los medios de pago y la respuesta queda marcada con la variante que la generó. A la derecha
aparecen la etiqueta «Resuelto por el asistente» y los cuatro fragmentos que recibió el modelo. La
sección «8. Métodos de pago» ocupa el primer puesto con un puntaje del reranker de 0,9599, muy por
encima del resto. En los puestos 3 y 4 se ve el intercambio que describe la sección 5.5: la sección
de pagos a cuotas, cuarta según la búsqueda vectorial, sube al tercer lugar y la pregunta frecuente
sobre seguridad de pagos baja al cuarto. El funcionamiento del chat puede verse en el
[video de demostración](https://www.youtube.com/watch?v=yllORKz-tu8).

## 8. Limitaciones y suposiciones

### 8.1 Limitaciones de recursos

| Limitación                 | Causa                                                                                                                                                                                                       | Efecto en lo presentado                                                                                                                                                       | Qué haríamos con más recursos                                                                            |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Sin GPU                    | El equipo disponible es un portátil con CPU de 16 hilos y 16 GB de RAM                                                                                                                                      | El reranking tarda entre 20 y 36 s por consulta y el flujo completo de `generar_salidas.sh` tarda alrededor de media hora                                                     | Ejecutar embeddings y reranker en GPU, o servirlos desde un proceso persistente con los modelos cargados |
| Memoria                    | Los dos modelos abiertos ocupan cerca de 3 GB en disco y 2,5 GB en RAM en precisión completa; `bfloat16` resultó más lento en esta CPU                                                                      | Se usan en `float32`                                                                                                                                                          | Cuantizar el reranker o usar hardware con soporte nativo de `bfloat16`                                   |
| Cuota de la API de Gemini  | El nivel gratuito de `gemini-3.6-flash`, el modelo del Taller 1, admite 20 solicitudes diarias por proyecto, que no alcanzan para las 16 respuestas de una ejecución completa más las pruebas de desarrollo | Las 16 respuestas se generaron con `gemini-3.5-flash-lite`, de la misma familia. Comparamos respuestas en 8 consultas, no en las 24 del experimento, y sin un juez automático | Usar un plan de pago con `gemini-3.6-flash` y evaluar la fidelidad de las respuestas a mayor escala      |
| Temperatura no controlable | La integración de LangChain advierte que estos modelos usan parámetros de muestreo fijos e ignora la temperatura                                                                                            | Las respuestas pueden variar entre ejecuciones; las de `outputs/` corresponden a una ejecución concreta                                                                       | Repetir cada consulta varias veces y reportar la variabilidad                                            |

### 8.2 Limitaciones metodológicas

- **Conjunto de evaluación pequeño y etiquetado por el propio equipo.** Veinticuatro consultas
  bastan para ver tendencias claras, pero una sola consulta mueve el promedio de su tipo en varios
  puntos. El etiquetado de relevancia contiene juicios nuestros; la sección de pagos a cuotas del
  caso D05 muestra que otro anotador habría marcado distinto.
- **Las decisiones de diseño se evaluaron con el mismo conjunto que se reporta.** El umbral se
  fijó con las 24 consultas etiquetadas y las ocho consultas de cliente, y la segmentación se
  validó con las mismas 24 consultas. Los resultados son, por tanto, optimistas. Un despliegue real
  debe confirmarlos con consultas nuevas y revisar el umbral con el registro de conversaciones.
- **Documentos ficticios y coherentes.** Redactamos los cuatro documentos cuidando que no se
  contradijeran. Los documentos reales de una empresa tienen versiones superpuestas, erratas y
  formatos irregulares que harían más difícil la recuperación.
- **Sin búsqueda híbrida.** Una consulta por SKU exacto depende solo de la similitud semántica. En
  la Fase 1 identificamos este caso como disparador para migrar a una base con BM25 integrado.
- **Memoria de conversación limitada.** La línea de comandos atiende cada mensaje de forma
  independiente. La interfaz de chat envía los tres turnos anteriores, pero solo para interpretar
  la pregunta: la recuperación usa el mensaje actual, así que un seguimiento como «¿y cuánto
  cuesta?» puede no traer la ficha del producto, e Iris debe reconocer que no tiene el dato. Tampoco
  medimos el efecto del historial en el experimento.

### 8.3 Suposiciones

- Los cuatro documentos son la fuente vigente de verdad y el índice se reconstruye cada vez que
  alguno cambia.
- Los clientes escriben en español y cada mensaje contiene una consulta completa.
- Los pedidos se identifican siempre con el formato `ECO-AAAA-NNNN`. Un cliente que no tenga el
  número recibe la indicación de buscarlo en su correo de confirmación.
- Una latencia de decenas de segundos es aceptable en esta etapa, porque el punto de comparación es
  el tiempo de respuesta actual de veinticuatro horas.
- La anonimización previa y la validación automática de la respuesta que propusimos en la
  arquitectura del Taller 1 siguen siendo necesarias en producción. Este taller no las implementa.

## 9. Conclusiones

- **El RAG amplía el alcance de Iris sin sacrificar lo que ya funcionaba.** Los pedidos se siguen
  resolviendo por número exacto. El resto del conocimiento llega en cuatro fragmentos de unos 800
  caracteres, en lugar de un documento completo por llamada, y cubre catálogo, envíos, pagos y
  preguntas frecuentes, que el Taller 1 no podía atender.
- **El reranking mejora la calidad del contexto donde más importa.** nDCG@4 sube de 0,765 a 0,908, y a 0,866 con el umbral de abstención activo.
  La ganancia se concentra en las paráfrasis y en las consultas que necesitan varios documentos, es
  decir, en la forma en que escriben los clientes reales. En las consultas que repiten el
  vocabulario del documento, el bi-encoder ya basta.
- **El reranker solo mejora lo que la segmentación permite.** Con un fragmento por sección, el
  97,5% de los fragmentos relevantes llega a los 20 candidatos, y el reranker lleva casi todos a los
  cuatro primeros puestos. Lo que la etapa 1 no encuentra, ningún reordenamiento lo rescata. El buen desempeño en los
  distractores probablemente se debe al encabezado contextual. La Fase 2 condiciona el resultado de
  la Fase 3.
- **El puntaje del reranker es una señal de abstención que la similitud de coseno no ofrece**,
  pero debe calibrarse con mensajes reales. Un umbral que separa bien las consultas cortas
  bloquearía consultas legítimas de varias preguntas. La combinación que adoptamos es un umbral bajo
  para lo claramente ajeno y una instrucción explícita en el prompt para los casos dudosos.
- **La precisión tiene un precio en latencia.** En CPU, el reranker multiplica por más de 100 el
  tiempo de recuperación. La arquitectura deja ese costo en un parámetro de configuración: el modelo
  de reranking, k y el umbral se ajustan en el TOML sin tocar el código.
