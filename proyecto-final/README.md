# Proyecto final · Agente de IA para las devoluciones de EcoMarket

**Maestría en Inteligencia Artificial · Inteligencia Artificial Generativa**

**Autores:** William Alberto Suaza · Anderson Trujillo · Bairon Gutiérrez

---

## El caso

En el Taller 1 construimos a Iris, la asistente de atención al cliente de EcoMarket, y en el Taller 2
le dimos un sistema RAG para responder cualquier consulta con información de la empresa. Iris
respondía, pero no actuaba: si un cliente quería devolver un producto, le explicaba la política y el
trámite quedaba en sus manos.

En este proyecto Iris se convierte en un agente. Consulta la base de conocimiento o el pedido cuando
lo necesita, verifica si la devolución cumple la política, genera la etiqueta de retorno y registra
el caso. Cuando la devolución no procede o requiere una persona, se detiene y lo explica.

## Contenido

| Fase | Documento                                                             | Qué contiene                                                                                                                                                                            |
| ---- | --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | [Diseño de la arquitectura del agente](fase-1-arquitectura.md)        | RAG como herramienta frente a un router, las cinco herramientas con sus entradas y salidas, elección de LangChain frente a LlamaIndex y diagrama del flujo de devolución                |
| 2    | [Implementación y conexión de componentes](fase-2-implementacion.md)  | Qué se conserva del Taller 2, el agente con `create_agent` y middleware, las reglas de negocio, el manejo de éxito y error, y la evaluación con pruebas unitarias y casos contra Gemini |
| 3    | [Análisis crítico y propuestas de mejora](fase-3-analisis-critico.md) | Riesgos de seguridad y ética con sus mitigaciones, monitoreo con métricas y alertas, y nuevas funcionalidades                                                                           |
| 4    | [Despliegue de la aplicación](fase-4-despliegue.md)                   | Elección de Gradio frente a Streamlit, la interfaz y el guion de la demostración de extremo a extremo                                                                                   |

## La solución en una frase

Un agente de LangChain con Gemini decide qué herramienta usar en cada mensaje; el RAG del Taller 2 es
una de ellas, y las reglas que permiten una devolución están en código, de modo que ninguna etiqueta
se emite sin una autorización que solo la verificación puede crear.

## Cómo ejecutar el código

Requiere Python 3.11 o superior, unos 4 GB de espacio libre para los modelos abiertos que se
descargan en la primera ejecución y una clave de la API de Gemini obtenida en
[Google AI Studio](https://aistudio.google.com/apikey). No se necesita GPU.

El entorno virtual, el archivo `.env` y el índice vectorial no forman parte del repositorio: los
pasos 1 a 4 se hacen una sola vez después de clonarlo.

### 1. Entrar a la carpeta del proyecto

```bash
git clone https://github.com/777wills/miaa-genia.git
cd miaa-genia/proyecto-final
```

Todos los comandos siguientes se ejecutan desde `proyecto-final/`.

### 2. Crear el entorno e instalar las dependencias

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

En Windows el entorno se activa con `.venv\Scripts\activate`.

### 3. Configurar la clave de Gemini

```bash
cp .env.example .env
```

En `.env` se escribe la clave. El modelo es el mismo del Taller 2:

```text
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash-lite
```

### 4. Construir el índice de la base de conocimiento

```bash
python src/indexar.py
```

Fragmenta la política de devoluciones, las preguntas frecuentes, el catálogo y la guía de envíos y
pagos (75 fragmentos) y los guarda en ChromaDB, en `src/indice/`. La primera ejecución descarga los
modelos de embeddings y de reranking.

### 5. Abrir la interfaz gráfica

```bash
python src/reset_demo.py
python src/interfaz.py
```

`reset_demo.py` deja en cero las devoluciones simuladas. La interfaz queda disponible en
`http://127.0.0.1:7860`; se abre en el navegador y se detiene con `Ctrl+C` en la terminal. En una
terminal nueva hay que activar otra vez el entorno con `source .venv/bin/activate` antes de
ejecutarla.

Para probarla:

- Los botones de **Ejemplos** cargan un mensaje en el campo de texto; luego se pulsa **Enviar**. El
  panel **Actividad del agente** muestra las herramientas que se ejecutaron y su resultado.
- El guion completo de la demostración, con lo que debe mostrar el panel en cada mensaje, está en la
  [Fase 4](fase-4-despliegue.md#4-demostración-de-extremo-a-extremo).
- **Reiniciar estado de la demo** borra las devoluciones registradas para repetir los casos, y
  **Limpiar conversación** abre una sesión nueva.
- La primera pregunta informativa tarda unos 30 segundos porque carga los modelos; las siguientes
  responden en pocos segundos.

También se puede conversar con Iris por consola con `python src/app.py`.

### Pruebas

Pruebas unitarias, sin llamadas a Gemini:

```bash
python -m unittest discover -s tests -v
```

Casos de extremo a extremo contra Gemini y el índice real (consumen cuota de la API):

```bash
RUN_GEMINI_E2E=1 python -m unittest tests.test_agente_gemini_e2e -v
```

Cada caso queda registrado en `outputs/evidencia-agente-gemini.jsonl`, sin prompts ni argumentos del
cliente. Los resultados se analizan en la [Fase 2](fase-2-implementacion.md#8-evaluación-del-comportamiento).

## Estructura del repositorio

```text
proyecto-final/
├── README.md
├── fase-1-arquitectura.md
├── fase-2-implementacion.md
├── fase-3-analisis-critico.md
├── fase-4-despliegue.md
├── requirements.txt
├── .env.example
├── src/
│   ├── agent.py                    Agente: create_agent, prompt y middleware
│   ├── tools.py                    Las cinco herramientas del agente
│   ├── devoluciones.py             Reglas de negocio y estado simulado
│   ├── rag.py                      Cadena RAG del Taller 2
│   ├── observability.py            Registro de acciones en JSONL
│   ├── interfaz.py                 Aplicación Gradio
│   ├── app.py                      Conversación por consola
│   ├── reset_demo.py               Reinicia el estado de devoluciones
│   ├── indexar.py                  Construye el índice vectorial
│   ├── experimento.py              Comparación con y sin reranking (Taller 2)
│   ├── settings-reranking.toml     Configuración del RAG que usa el agente
│   ├── settings-sin-reranking.toml Variante de comparación del experimento
│   ├── datos/
│   │   ├── politica-devoluciones.md
│   │   ├── faq.json
│   │   ├── catalogo-productos.csv
│   │   ├── guia-envios-y-pagos.pdf
│   │   ├── pedidos.json            Pedidos simulados (fuera del índice vectorial)
│   │   └── evaluacion/             Consultas etiquetadas del experimento
│   └── runtime/                    Autorizaciones, etiquetas y devoluciones simuladas
├── tests/
│   ├── casos_agente.json           Casos A–K para evaluar al agente
│   ├── test_agente_gemini_e2e.py   Casos contra Gemini y prueba de la interfaz
│   ├── test_agent_runtime.py       Ciclo del agente con un modelo falso
│   ├── test_devoluciones.py        Reglas de negocio
│   ├── test_rag_tool.py            Herramienta RAG y esquema de la verificación
│   ├── test_interfaz.py            Panel de actividad
│   ├── test_observability.py       Registro de acciones
│   └── test_estructura_proyecto.py Configuración y componentes
└── outputs/
    ├── evidencia-agente-gemini.jsonl   Resultados de los casos contra Gemini
    └── experimento-taller-2/           Métricas y reporte del experimento de reranking
```

Al ejecutar la aplicación se crean `src/indice/` y `outputs/agent-actions.jsonl`, que no se
versionan.

## Nota sobre los datos

Los pedidos, clientes y productos son ficticios. `pedidos.json` incluye una fecha de corte
(14 de marzo de 2026) que el sistema usa como fecha actual para calcular el plazo de 30 días; así los
casos dan el mismo resultado sin importar cuándo se ejecute el proyecto.
