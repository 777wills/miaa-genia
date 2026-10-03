# Fase 2. Implementación y conexión de componentes

## Cómo se extendió el Taller 2

El proyecto mantiene tres ideas del taller anterior:

- la información transaccional de pedidos no se vectoriza;
- las consultas informativas se responden desde una base de conocimiento;
- Gemini se utiliza como modelo generativo.

Sobre esa base se agregó `agent.py`, que coordina las herramientas. El archivo `devoluciones.py` contiene las reglas de negocio y se mantuvo separado del modelo para poder probarlas sin depender de una respuesta generativa.

## Archivos principales

### `src/agent.py`

Contiene el ciclo del agente. Se construye un `ChatGoogleGenerativeAI`, se registran las herramientas con `bind_tools` y se ejecutan hasta que el modelo produce una respuesta final.

Se impuso un máximo de pasos para impedir ciclos indefinidos.

### `src/tools.py`

Expone al agente las cinco herramientas:

- RAG;
- consulta exacta del pedido;
- verificación de elegibilidad;
- generación de etiqueta;
- registro de devolución.

### `src/devoluciones.py`

Contiene la lógica determinística. Esta separación es importante porque un LLM puede redactar una explicación, pero no debería decidir de manera libre si se cumplen reglas como el plazo o el estado del pedido.

### `src/rag.py`

Conserva la recuperación semántica con ChromaDB y embeddings multilingües. Si por algún motivo el índice vectorial no puede cargarse, existe un fallback léxico para que la demostración no se bloquee por una falla de infraestructura. El método usado queda registrado en la respuesta de la herramienta.

### `src/observability.py`

Registra cada ejecución de herramienta en JSONL. El log guarda:

- hora;
- sesión;
- nombre de la herramienta;
- estado;
- argumentos no sensibles;
- resumen del resultado.

### `src/interfaz.py`

Mantiene Gradio como en el Taller 2. La diferencia es que el panel derecho ahora muestra la actividad del agente, no solamente los fragmentos recuperados.

## Manejo de respuestas y errores

Se contemplaron los siguientes casos:

| Situación | Comportamiento |
|---|---|
| Pedido inexistente | Se informa y no se ejecuta otra acción |
| SKU no pertenece al pedido | Se detiene la devolución |
| Pedido no entregado | No se genera etiqueta |
| Pedido con devolución previa | Se evita el duplicado |
| Más de 30 días | Se deriva a revisión humana |
| Categoría no retornable | Se explica la regla |
| Excepción atribuible a EcoMarket | Se solicita revisión/evidencia y no se genera retorno físico automático |
| Autorización inexistente | `generar_etiqueta_devolucion` rechaza la llamada |
| Etiqueta inexistente | `registrar_devolucion` rechaza la llamada |
| Registro duplicado | No se crea un segundo caso |
| Error del modelo o API | La interfaz muestra un mensaje controlado |
| Demasiadas llamadas a herramientas | El agente se detiene por límite de pasos |

## Pruebas incluidas

Las pruebas unitarias se concentran en la parte que no debe depender del comportamiento del LLM:

```bash
python -m unittest discover -s tests -v
```

Se prueban, entre otros:

- devolución ordinaria válida;
- pedido no entregado;
- producto no retornable;
- excepción por producto averiado;
- devolución duplicada;
- bloqueo de una etiqueta sin autorización;
- registro de una devolución autorizada.

## Evaluación del comportamiento del agente

Además de las pruebas unitarias, `PROMPTS_DEMO.md` incluye prompts para comprobar cuándo el agente debe usar herramientas y cuándo debe limitarse a responder con RAG.

La demostración cubre tres tipos de comportamiento:

1. **Responder directamente:** un saludo o conversación que no necesita datos de EcoMarket.
2. **Responder con RAG:** una pregunta sobre políticas.
3. **Ejecutar un flujo completo:** una devolución válida.
4. **Saber detenerse:** devolución no elegible, duplicada o caso que requiere persona.

Esta distinción es importante porque un agente útil no es el que llama más herramientas, sino el que llama únicamente las necesarias.
