# Fase 2 · Fortalezas, limitaciones y riesgos éticos

**Caso:** optimización de la atención al cliente en EcoMarket
**Autores:** William Alberto Suaza · Anderson Trujillo · Bairon Gutiérrez

---

Evaluamos aquí la solución que propusimos en la
[Fase 1](fase-1-seleccion-y-justificacion-del-modelo.md): una arquitectura híbrida que combina un
modelo generativo, recuperación de datos de EcoMarket y derivación a agentes humanos.

## 1. Fortalezas

| Fortaleza                                      | Mecanismo que la produce                                                                | Efecto esperado en EcoMarket                                                    |
| ---------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Reducción drástica del tiempo de respuesta     | El tramo repetitivo se resuelve en una sola llamada al modelo con el dato ya recuperado | El promedio de 24 horas baja a segundos para cerca del 80% del volumen          |
| Disponibilidad permanente                      | El servicio no depende de turnos ni de jornada laboral                                  | Las consultas de la noche y del fin de semana dejan de acumularse para el lunes |
| Absorción de los picos de demanda              | La capacidad del servicio gestionado se ajusta a la carga sin aprovisionamiento previo  | Las temporadas de descuentos dejan de degradar el servicio                      |
| Consistencia en la aplicación de las políticas | La política de devoluciones es un documento único inyectado como contexto               | Desaparecen las respuestas contradictorias entre agentes distintos              |
| Trazabilidad de cada respuesta                 | Se registra la consulta, el contexto recuperado y la respuesta entregada                | Se puede auditar por qué el sistema respondió lo que respondió                  |
| Liberación de tiempo especializado             | Los agentes dejan de transcribir estados de pedido                                      | El equipo se concentra en los casos que exigen criterio y empatía               |
| Adaptación sin reentrenamiento                 | Cambiar una política significa editar un documento versionado                           | El negocio ajusta reglas en horas, no en ciclos de entrenamiento                |
| Homogeneidad entre canales                     | Un mismo núcleo atiende chat, correo y redes sociales                                   | La experiencia deja de depender del canal por el que escriba el cliente         |

## 2. Limitaciones

Somos conscientes de que la solución tiene fronteras claras y de que reconocerlas es parte del
diseño responsable.

| Limitación                                                 | Por qué ocurre                                                                                                                                       | Cómo la acotamos                                                                                                                              |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| No resuelve el 20% complejo                                | Las quejas y los problemas técnicos exigen negociación, criterio y contacto humano                                                                   | El clasificador deriva esos casos y el modelo solo prepara un borrador para el agente                                                         |
| La calidad depende de la calidad del dato                  | Si el sistema logístico registra mal una fecha, la respuesta será falsa                                                                              | Alertas de consistencia sobre los datos de origen y un mensaje de estado cuando el registro está incompleto                                   |
| No percibe el estado emocional con fiabilidad              | La detección de frustración a partir de texto es aproximada y el sarcasmo escapa al análisis                                                         | Umbral deliberadamente sensible: ante la duda, deriva a una persona                                                                           |
| No entiende el contexto no verbal ni el histórico completo | El asistente ve la consulta y el contexto recuperado, no la relación del cliente con la marca                                                        | Se inyecta un resumen del historial reciente y los casos reincidentes se escalan                                                              |
| El comportamiento cambia sin que nosotros cambiemos nada   | El proveedor actualiza o retira la versión del modelo detrás del mismo identificador, y las respuestas se degradan sin producir ningún error visible | Batería fija de consultas de prueba con el resultado esperado de cada una, que se ejecuta y se compara ante cada cambio de modelo o de prompt |
| Dependencia de un proveedor externo                        | Una caída o un cambio de precios del proveedor afecta la operación                                                                                   | Los prompts viven en archivos de configuración independientes del proveedor y existe un plan de reemplazo                                     |
| Cobertura lingüística desigual                             | El desempeño es menor en mensajes con jerga regional, errores ortográficos densos o mezcla de idiomas                                                | Monitoreo de tasa de escalamiento por tipo de mensaje y derivación cuando la confianza es baja                                                |
| No puede ejecutar acciones críticas por sí solo            | Reembolsar, cancelar o modificar un pedido tiene consecuencias económicas                                                                            | El asistente informa y prepara; la ejecución requiere confirmación humana o reglas estrictas                                                  |

## 3. Riesgos éticos

### 3.1 Alucinaciones

**El riesgo.** El modelo puede afirmar con total seguridad que un pedido llega mañana, que existe un
número de seguimiento inventado o que un producto de higiene admite devolución. En atención al
cliente esto no es un error cosmético: genera expectativas falsas, reclamaciones y pérdida de
confianza, y puede derivar en responsabilidad legal si se promete algo que la empresa no cumplirá.

**Por qué es especialmente grave aquí.** El cliente no tiene forma de distinguir una respuesta
correcta de una inventada, porque ambas están redactadas con la misma fluidez y cortesía.

**Cómo lo contenemos.**

1. El dato nunca proviene de la memoria del modelo: se recupera del sistema transaccional y se
   inyecta en el prompt.
2. Cuando el número de seguimiento no existe, el contexto lo declara de forma explícita y la
   instrucción prohíbe describir cualquier pedido.
3. Una validación automática verifica que los números, fechas y montos citados en la respuesta
   aparezcan en el contexto recuperado; si no aparecen, la respuesta no se envía y el caso pasa a un
   agente.
4. La temperatura se fija en cero para reducir la variabilidad entre ejecuciones.
5. El prompt de rol establece que reconocer el desconocimiento es una respuesta aceptable.

Sometemos esta mitigación a prueba con una consulta sobre un número de seguimiento inexistente, y
contrastamos el comportamiento del prompt inicial frente al prompt final.

### 3.2 Sesgo

**El riesgo.** Los modelos heredan sesgos de sus datos de entrenamiento y la solución puede
introducir otros propios. Identificamos cuatro formas concretas en las que el sesgo afectaría a
EcoMarket:

| Forma de sesgo                     | Manifestación concreta                                                                        | Consecuencia                                                                     |
| ---------------------------------- | --------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Sesgo lingüístico y socioeconómico | Peor comprensión de mensajes con errores ortográficos, jerga regional o escritura informal    | Los clientes con menor alfabetización digital reciben peor servicio              |
| Sesgo de trato según el nombre     | Variación del tono o del nivel de diligencia según el nombre, el género percibido o la ciudad | Discriminación difícil de detectar porque cada respuesta aislada parece correcta |
| Sesgo en la priorización           | El clasificador aprende a escalar más rápido a quien escribe de forma asertiva o formal       | Quien no sabe reclamar queda relegado                                            |
| Sesgo de complacencia              | El modelo tiende a dar la razón y a prometer para evitar el conflicto                         | Se generan compromisos que la empresa no puede sostener                          |

**Cómo lo contenemos.**

1. El prompt de rol prohíbe modular el trato según atributos del cliente y fija un tono uniforme.
2. La anonimización previa retira el nombre completo y otros atributos personales antes de enviar el
   mensaje al modelo, de modo que no puedan influir en la respuesta.
3. Auditoría periódica con pares de mensajes idénticos que solo difieren en nombre, género percibido
   o ciudad, comparando extensión, tono y resultado.
4. Seguimiento de métricas de servicio desagregadas por canal y por región, para detectar
   diferencias sistemáticas de desempeño.
5. Revisión humana de una muestra aleatoria de conversaciones, no solo de las que generan queja.

### 3.3 Privacidad de los datos

**El riesgo.** Las conversaciones contienen nombres, direcciones, correos, teléfonos, historial de
compras y a veces datos de pago. Enviar esa información a un modelo externo, conservarla sin
propósito o usarla para afinar un modelo implica tres problemas distintos: exposición ante
terceros, uso incompatible con la finalidad para la que el cliente entregó el dato, y persistencia
irreversible si los datos quedan incrustados en los pesos de un modelo.

**Por qué el fine-tuning agrava el problema.** Un dato usado para entrenar no se puede borrar
después: no existe un mecanismo práctico para retirar un registro específico de los pesos de un
modelo ya entrenado. Esto choca de frente con el derecho de supresión que la normativa colombiana de
protección de datos personales reconoce al titular. Es una razón ética, no solo técnica, para haber
preferido la recuperación de contexto sobre el afinamiento del modelo.

**Cómo lo contenemos.**

| Medida                                 | Descripción                                                                                                                                        |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Minimización                           | Se envía al modelo únicamente el pedido consultado y el fragmento de política pertinente, nunca la base completa ni el historial íntegro           |
| Anonimización previa                   | Se enmascaran nombres completos, correos, teléfonos y direcciones antes de construir el prompt; el asistente trabaja con identificadores de pedido |
| Prohibición de datos sensibles         | El prompt de rol impide solicitar contraseñas, números completos de tarjeta o códigos de verificación                                              |
| Aislamiento entre clientes             | La recuperación filtra por el pedido del solicitante, de modo que es imposible que la respuesta mencione el pedido de otra persona                 |
| No entrenamiento con datos de clientes | Se contrata el servicio bajo condiciones que excluyan el uso de los datos para entrenar modelos del proveedor                                      |
| Retención limitada                     | Los registros de conversación se conservan por un plazo definido y verificable, y luego se eliminan o se anonimizan de forma irreversible          |
| Transparencia y consentimiento         | Se informa al cliente que interactúa con un asistente automatizado y cómo se tratan sus datos                                                      |
| Control de acceso y cifrado            | Cifrado en tránsito y en reposo, y acceso a los registros restringido por rol                                                                      |
| Gestión de derechos del titular        | Procedimiento explícito para atender solicitudes de acceso, rectificación y supresión                                                              |

### 3.4 Impacto laboral

**El riesgo.** La lectura inmediata de una solución como esta es la reducción de personal. Nuestra
posición es distinta y la sostenemos con el propio análisis del caso: el cuello de botella de
EcoMarket no es el exceso de agentes, es el exceso de consultas repetitivas que consumen el tiempo
de esos agentes. Automatizar la transcripción de estados de pedido no vuelve prescindible al equipo;
lo libera para el 20% que hoy se atiende tarde y mal.

**El objetivo es empoderar, no reemplazar.** En concreto:

| Dimensión            | Cómo la abordamos                                                                                                                                                                                    |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Rol del agente       | Pasa de transcribir datos a resolver casos complejos, con el asistente entregándole el contexto ya reunido y un borrador de respuesta                                                                |
| Nuevas funciones     | Se abren roles de curador de la base de conocimiento, revisor de calidad de las respuestas y responsable del ajuste de prompts, ocupados por quienes conocen el negocio                              |
| Formación            | Plan de capacitación en supervisión del asistente, detección de errores y manejo de casos sensibles, antes del despliegue                                                                            |
| Participación        | El equipo de soporte interviene en el diseño y la revisión de los prompts; son quienes conocen las objeciones reales de los clientes                                                                 |
| Compromiso explícito | Declarar desde el inicio que el proyecto no tiene como objetivo la reducción de la planta, y medir su éxito por satisfacción del cliente y tiempo de resolución, no por número de agentes suprimidos |
| Carga emocional      | Vigilar que el rediseño no concentre en los agentes únicamente las interacciones conflictivas, lo que aumentaría el desgaste; se equilibra la asignación y se monitorea la carga                     |

**Riesgo de deshumanización.** Existe también el riesgo inverso: que el cliente quede atrapado en un
circuito automático sin poder llegar a una persona. Por eso el sistema incluye una salida humana
siempre disponible y explícita, y nunca oculta que el cliente está hablando con un asistente.

### 3.5 Riesgos adicionales que identificamos

| Riesgo                                           | Descripción                                                                                                   | Mitigación                                                                                                                                                         |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Manipulación del asistente por el propio cliente | Un usuario puede intentar que el asistente ignore sus instrucciones y conceda reembolsos o revele información | Los datos del cliente llegan siempre delimitados y marcados como contenido, no como instrucciones; las acciones con efecto económico requieren confirmación humana |
| Falsa sensación de resolución                    | El cliente cree que su caso quedó resuelto porque la respuesta suena segura                                   | Se comunica con claridad el estado real del caso y el siguiente paso                                                                                               |
| Opacidad ante el cliente                         | Interactuar con una máquina creyendo que es una persona vulnera la confianza                                  | Identificación explícita del asistente al inicio de cada conversación                                                                                              |
| Accesibilidad                                    | Respuestas largas o con estructura compleja excluyen a algunos usuarios                                       | Límite de extensión, lenguaje sencillo y estructura predecible, fijados en el prompt                                                                               |
| Huella ambiental                                 | La inferencia consume energía, lo que interpela a una marca de productos sostenibles                          | Enrutamiento que reserva el modelo grande para el 20% complejo, caché de respuestas frecuentes y recuperación selectiva para reducir tokens procesados             |
| Concentración en un proveedor                    | La dependencia técnica y comercial de un solo proveedor reduce el margen de negociación                       | Prompts y lógica desacoplados del proveedor, de modo que el modelo se sustituye sin reescribir la solución                                                         |

## 4. Matriz de riesgos

Valoramos probabilidad e impacto en una escala de tres niveles (bajo, medio, alto) sobre la solución
tal como la diseñamos, antes de aplicar mitigaciones.

| #   | Riesgo                                                        | Probabilidad | Impacto | Criticidad  | Mitigación principal                                                           | Indicador de control                                              |
| --- | ------------------------------------------------------------- | ------------ | ------- | ----------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| 1   | Alucinación sobre datos de pedidos                            | Alta         | Alto    | **Crítica** | Recuperación del dato y validación automática de la respuesta                  | Porcentaje de respuestas con datos no verificables en el contexto |
| 2   | Fuga de datos personales hacia el proveedor                   | Media        | Alto    | **Crítica** | Minimización y anonimización previa al envío                                   | Número de campos personales detectados en los prompts auditados   |
| 3   | Trato desigual por sesgo del modelo                           | Media        | Alto    | **Alta**    | Auditoría de pares contrafactuales y tono uniforme por prompt de rol           | Diferencia de satisfacción entre segmentos de clientes            |
| 4   | Caso sensible no derivado a tiempo                            | Media        | Alto    | **Alta**    | Umbral de escalamiento sensible y palabras clave de riesgo                     | Tasa de escalamientos tardíos detectados en revisión              |
| 5   | Deterioro del clima laboral por temor a la sustitución        | Media        | Medio   | **Media**   | Compromiso explícito, participación del equipo y plan de formación             | Rotación y clima del área de soporte                              |
| 6   | Respuesta correcta a partir de un dato erróneo del sistema    | Media        | Medio   | **Media**   | Alertas de consistencia sobre los datos de origen                              | Casos reabiertos por información incorrecta                       |
| 7   | Manipulación del asistente mediante instrucciones del cliente | Media        | Medio   | **Media**   | Delimitación estricta del contenido y confirmación humana de acciones críticas | Intentos detectados por consulta auditada                         |
| 8   | Degradación silenciosa tras un cambio de versión del modelo   | Media        | Medio   | **Media**   | Conjunto de consultas de regresión ejecutado ante cada cambio                  | Variación de resultados en el conjunto de regresión               |
| 9   | Cliente atrapado en el circuito automático                    | Baja         | Alto    | **Media**   | Salida humana siempre disponible y visible                                     | Solicitudes de agente humano no atendidas                         |
| 10  | Interrupción del servicio del proveedor                       | Baja         | Alto    | **Media**   | Plan de continuidad con respuesta diferida y atención humana                   | Tiempo de indisponibilidad acumulado                              |

## 5. Indicadores de seguimiento

No basta con desplegar: la solución debe medirse de forma continua.

| Indicador                                          | Qué vigila                                | Señal de alarma                                        |
| -------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------ |
| Tiempo de primera respuesta                        | Cumplimiento del objetivo del proyecto    | Supera los umbrales acordados por canal                |
| Tasa de resolución sin intervención humana         | Eficacia real del tramo automatizado      | Cae de forma sostenida                                 |
| Tasa de escalamiento                               | Funcionamiento del clasificador           | Demasiado baja indica casos sensibles mal enrutados    |
| Tasa de respuestas rechazadas por la validación    | Frecuencia de alucinaciones contenidas    | Aumento repentino tras un cambio de modelo o de prompt |
| Satisfacción del cliente, desagregada por segmento | Detección de sesgo y de calidad percibida | Brechas persistentes entre segmentos                   |
| Casos reabiertos                                   | Calidad real de las resoluciones          | Crecimiento frente al periodo previo                   |
| Proporción de conversaciones auditadas             | Cumplimiento del control de calidad       | Cae por debajo del mínimo definido                     |

## 6. Gobernanza y despliegue responsable

Proponemos un despliegue progresivo que permita corregir antes de exponer a todos los clientes:

1. **Modo sombra.** El asistente genera respuestas que solo ve el equipo interno; se comparan con lo
   que respondieron los agentes humanos.
2. **Copiloto.** El asistente redacta y el agente revisa y envía. El equipo gana confianza y aporta
   correcciones a los prompts.
3. **Autonomía acotada.** Respuesta automática únicamente para intenciones de bajo riesgo, como
   estado de pedido, con validación previa al envío.
4. **Ampliación gradual.** Se incorporan nuevas intenciones solo cuando los indicadores del tramo
   anterior se sostienen.

Sobre este proceso definimos responsables claros: un propietario de producto que responde por los
resultados, el equipo de soporte como revisor de calidad y una revisión periódica de privacidad y
sesgo con capacidad de detener el despliegue.

### Límites que no cruzamos

- El asistente no ejecuta reembolsos, cancelaciones ni cambios de pedido sin confirmación humana.
- El asistente no niega un derecho del consumidor ni cierra una reclamación formal.
- El asistente no oculta su naturaleza automatizada.
- El asistente no retiene ni solicita datos sensibles de pago.
- El cliente siempre puede pedir hablar con una persona y esa solicitud se atiende.

## 7. Conclusión del análisis crítico

La solución aporta valor real y medible sobre el problema declarado, pero solo es defendible si se
acepta que traslada el riesgo desde la lentitud hacia la exactitud, la equidad y la privacidad. Por
eso la arquitectura no consiste únicamente en llamar a un modelo: la recuperación del dato, la
validación de la respuesta, la anonimización previa y la derivación humana son parte constitutiva
del diseño, no añadidos opcionales. Cada uno de estos compromisos debe quedar inscrito en la
construcción concreta de los prompts y verificarse con respuestas reales antes de exponer la
solución a los clientes.
