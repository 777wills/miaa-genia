# Experimento: recuperación sin reranking frente a recuperación con reranking

- Consultas etiquetadas: 24 (20 con respuesta en la base, 4 fuera de alcance)
- Etapa 1 (ambas variantes): `intfloat/multilingual-e5-base` + ChromaDB, k = 20 candidatos
- Variante A: los 4 primeros candidatos según la similitud de coseno
- Variante B: los 4 primeros tras reordenar con `BAAI/bge-reranker-v2-m3`
- Variante C: la variante B con el umbral de relevancia (0.005) aplicado al mejor candidato, tal como opera `settings-reranking.toml`: si no lo alcanza, no se entrega ningún fragmento
- Techo de la etapa 1: Recall@20 = 0.975 (proporción de fragmentos relevantes que llegan a los 20 candidatos)

## 1. Métricas agregadas

| Métrica | Sin reranking | Con reranking | B − A | Con reranking y umbral | C − A |
| --- | --- | --- | --- | --- | --- |
| Hit@4 | 0.900 | 1.000 | +0.100 | 0.900 | +0.000 |
| MRR@4 | 0.863 | 0.929 | +0.067 | 0.900 | +0.037 |
| nDCG@4 | 0.765 | 0.908 | +0.144 | 0.866 | +0.101 |
| Precision@4 | 0.325 | 0.400 | +0.075 | 0.375 | +0.050 |
| Recall@4 | 0.783 | 0.933 | +0.150 | 0.858 | +0.075 |

Las secciones 2 a 4 comparan A y B para aislar el efecto del reordenamiento; el efecto del umbral se analiza en la sección 5.

## 2. Métricas por tipo de consulta

| Tipo | Consultas | MRR@4 A | MRR@4 B | nDCG@4 A | nDCG@4 B |
| --- | --- | --- | --- | --- | --- |
| directa | 6 | 1.000 | 1.000 | 0.988 | 0.991 |
| parafrasis | 8 | 0.656 | 0.823 | 0.554 | 0.842 |
| distractor | 4 | 1.000 | 1.000 | 0.913 | 0.957 |
| multidocumento | 2 | 1.000 | 1.000 | 0.639 | 0.832 |

## 3. Detalle por consulta

La columna «Posición del fragmento principal» indica dónde queda el fragmento de relevancia 2 entre los 20 candidatos: primero según el bi-encoder y luego tras el reranking.

| ID | Tipo | Consulta | Fragmento principal | Posición del fragmento principal | nDCG@4 A | nDCG@4 B | Δ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D01 | directa | ¿Cuánto cuesta el envío a una ciudad principal? | `guia-costos-de-envio-1` | 1 → 1 | 1.000 | 1.000 | +0.000 |
| D02 | directa | ¿Qué categorías de productos no admiten devolución? | `politica-categorias-que-no-admiten-devolucion-1` | 1 → 1 | 1.000 | 1.000 | +0.000 |
| D03 | directa | ¿Cómo funciona el programa de puntos Semilla? | `faq-12` | 1 → 1 | 1.000 | 1.000 | +0.000 |
| D04 | directa | ¿Cuál es el precio del kit de compostaje doméstico? | `catalogo-hog-0501` | 1 → 1 | 1.000 | 1.000 | +0.000 |
| D05 | directa | ¿Qué métodos de pago aceptan? | `guia-metodos-de-pago-1` | 1 → 1 | 0.964 | 0.945 | -0.019 |
| D06 | directa | ¿Cómo solicito la eliminación de mis datos personales? | `faq-04` | 1 → 1 | 0.964 | 1.000 | +0.036 |
| P01 | parafrasis | se me olvidó la clave para entrar a la página, qué hago | `faq-02` | 1 → 1 | 1.000 | 1.000 | +0.000 |
| P02 | parafrasis | ¿en cuánto tiempo me devuelven la plata después de mandarles el producto de vuelta? | `politica-plazos-generales-1` | 5 → 1 | 0.242 | 0.879 | +0.637 |
| P03 | parafrasis | necesito que la cuenta de cobro salga a nombre de mi empresa, ¿se puede? | `guia-facturacion-electronica-1` | 2 → 1 | 0.797 | 1.000 | +0.203 |
| P04 | parafrasis | me mudé y el paquete ya salió de la bodega, ¿me lo pueden llevar a la casa nueva? | `guia-cambios-de-direccion-1` | 13 → 3 | 0.000 | 0.500 | +0.500 |
| P05 | parafrasis | quiero dejar de usar papel film para tapar la comida, ¿qué me sirve? | `catalogo-hog-0233` | 4 → 1 | 0.431 | 1.000 | +0.569 |
| P06 | parafrasis | ¿por qué en mi pedido dice que todavía no tiene empresa de mensajería? | `guia-transportadoras-aliadas-1` | 14 → 4 | 0.000 | 0.356 | +0.356 |
| P07 | parafrasis | ¿puedo pasar a recoger mi compra en persona a algún local? | `faq-19` | 1 → 1 | 1.000 | 1.000 | +0.000 |
| P08 | parafrasis | tienen algo pa la piel reseca? | `catalogo-cui-0021` | 1 → 1 | 0.964 | 1.000 | +0.036 |
| X01 | distractor | Devolví un producto porque no me gustó, ¿me reembolsan también lo que pagué de envío? | `guia-reembolso-del-costo-de-envio-1` | 1 → 1 | 0.826 | 0.826 | +0.000 |
| X02 | distractor | ¿Les puedo devolver la caja de cartón en la que me llegó el pedido? | `faq-16` | 1 → 1 | 1.000 | 1.000 | +0.000 |
| X03 | distractor | Me cobraron dos veces la misma compra en la tarjeta, ¿qué hago? | `guia-pagos-rechazados-y-cobros-duplicados-1` | 1 → 1 | 0.826 | 1.000 | +0.174 |
| X04 | distractor | Mi pedido lleva más de una semana de retraso, ¿me dan alguna compensación? | `guia-retrasos-en-la-entrega-1` | 1 → 1 | 1.000 | 1.000 | +0.000 |
| X05 | multidocumento | Si mando a grabar el termo con un nombre, ¿lo puedo devolver después si no me gusta? | `faq-21` | 1 → 1 | 0.673 | 0.987 | +0.314 |
| X06 | multidocumento | Me llegó el desodorante con el sello roto, ¿lo puedo devolver? | `politica-excepciones-que-siempre-aplican-1` | 3 → 4 | 0.605 | 0.676 | +0.071 |

## 4. Balance de cambios

- Consultas en las que el reranking mejora nDCG@4: 10 (D06, P02, P03, P04, P05, P06, P08, X03, X05, X06)
- Consultas en las que el reranking empeora nDCG@4: 1 (D05)
- Consultas sin cambio: 9

**D05** · «¿Qué métodos de pago aceptan?»

- Top-4 sin reranking: `guia-metodos-de-pago-1`, `guia-reembolsos-al-medio-de-pago-1`, `faq-22`, `guia-pagos-a-cuotas-1`
- Top-4 con reranking: `guia-metodos-de-pago-1`, `guia-reembolsos-al-medio-de-pago-1`, `guia-pagos-a-cuotas-1`, `faq-22`

## 5. Umbral de relevancia y consultas fuera de alcance

Puntaje del mejor candidato de cada consulta según cada modelo. Un buen separador asigna puntajes altos a las consultas con respuesta y bajos a las que no la tienen.

| ID | Grupo | Similitud coseno top-1 | Puntaje reranker top-1 | Con umbral 0.005 |
| --- | --- | --- | --- | --- |
| F02 | fuera de alcance | 0.7930 | 0.0000 | abstiene |
| F03 | fuera de alcance | 0.7771 | 0.0000 | abstiene |
| P06 | con respuesta | 0.8113 | 0.0004 | abstiene |
| F04 | fuera de alcance | 0.8074 | 0.0008 | abstiene |
| P04 | con respuesta | 0.8328 | 0.0033 | abstiene |
| P05 | con respuesta | 0.8330 | 0.0100 | responde |
| F01 | fuera de alcance | 0.8255 | 0.0331 | responde |
| P07 | con respuesta | 0.8418 | 0.0680 | responde |
| X06 | con respuesta | 0.8421 | 0.0978 | responde |
| P03 | con respuesta | 0.8372 | 0.1338 | responde |
| P02 | con respuesta | 0.8613 | 0.1426 | responde |
| D01 | con respuesta | 0.8358 | 0.1667 | responde |
| P08 | con respuesta | 0.8470 | 0.1764 | responde |
| X03 | con respuesta | 0.8302 | 0.2387 | responde |
| P01 | con respuesta | 0.8357 | 0.6444 | responde |
| X05 | con respuesta | 0.8497 | 0.6975 | responde |
| X04 | con respuesta | 0.8601 | 0.7879 | responde |
| D05 | con respuesta | 0.8617 | 0.9599 | responde |
| X01 | con respuesta | 0.8781 | 0.9645 | responde |
| D02 | con respuesta | 0.9015 | 0.9974 | responde |
| D06 | con respuesta | 0.8893 | 0.9977 | responde |
| X02 | con respuesta | 0.8807 | 0.9979 | responde |
| D04 | con respuesta | 0.9006 | 0.9995 | responde |
| D03 | con respuesta | 0.9170 | 0.9997 | responde |

- Similitud de coseno: mínimo con respuesta = 0.8113, máximo fuera de alcance = 0.8255 → se solapan
- Puntaje del reranker: mínimo con respuesta = 0.0004, máximo fuera de alcance = 0.0331 → se solapan
- Umbral configurado: 0.005. Se aplica al puntaje del mejor candidato: si no lo alcanza, el modelo no recibe fragmentos y debe abstenerse
- Umbrales que separan todas las consultas fuera de alcance de la mayoría con respuesta: entre 0.0331 y 0.0680
- Abstenciones correctas: 3 de 4 consultas fuera de alcance (la variante A no tiene mecanismo de abstención y siempre entrega fragmentos)
- Abstenciones indebidas: 2 (P04, P06)
- Fragmentos relevantes del top-4 que se pierden por el umbral: 2 aplicándolo al mejor candidato, frente a 5 si se aplicara a cada fragmento por separado

Efecto de distintos umbrales sobre este conjunto:

| Umbral | Abstenciones correctas | Abstenciones indebidas |
| --- | --- | --- |
| 0.001 | 3 de 4 | 1 (P06) |
| 0.005 | 3 de 4 | 2 (P04, P06) |
| 0.01 | 3 de 4 | 2 (P04, P06) |
| 0.05 | 4 de 4 | 3 (P04, P05, P06) |
| 0.1 | 4 de 4 | 5 (P04, P05, P06, P07, X06) |

## 6. Costo en latencia (CPU)

| Etapa | Media por consulta |
| --- | --- |
| Búsqueda vectorial (k candidatos) | 169 ms |
| Reranking de 20 candidatos | 29461 ms |
