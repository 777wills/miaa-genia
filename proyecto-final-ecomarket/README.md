# Proyecto final · Agente de IA para EcoMarket

**Maestría en Inteligencia Artificial · Inteligencia Artificial Generativa**

**Autores:** William Alberto Suaza · Anderson Trujillo · Bairon Gutiérrez

## Qué se construyó

En el Taller 2, Iris respondía consultas usando RAG y una búsqueda exacta de pedidos. Para el proyecto final se mantuvo esa idea y se agregó una capa de agente capaz de ejecutar acciones sobre el proceso de devoluciones.

El agente puede:

- consultar la base de conocimiento de EcoMarket;
- consultar un pedido por número de seguimiento;
- verificar si un producto cumple las reglas de devolución;
- generar una etiqueta simulada cuando la devolución es válida;
- registrar la devolución;
- detener el flujo cuando el caso requiere revisión humana;
- evitar devoluciones duplicadas;
- dejar un registro de las herramientas ejecutadas.

La solución usa **LangChain** para el modelo, los mensajes y las herramientas. El RAG del Taller 2 se conserva como una herramienta del agente. La interfaz se mantiene en **Gradio**, porque ya era la tecnología usada en el taller anterior y permite mostrar en la misma pantalla la conversación y la actividad del agente.

## Estructura

```text
proyecto-final-ecomarket/
├── README.md
├── fase-1-arquitectura.md
├── fase-2-implementacion.md
├── fase-3-analisis-critico.md
├── fase-4-despliegue.md
├── VALIDACION_RUBRICA.md
├── GUIA_VIDEO.md
├── PROMPTS_DEMO.md
├── requirements.txt
├── .env.example
├── src/
│   ├── agent.py
│   ├── app.py
│   ├── interfaz.py
│   ├── tools.py
│   ├── devoluciones.py
│   ├── rag.py
│   ├── indexar.py
│   ├── observability.py
│   ├── reset_demo.py
│   ├── datos/
│   │   ├── pedidos.json
│   │   └── conocimiento/
│   │       ├── politica-devoluciones.md
│   │       ├── faq.json
│   │       └── envios-y-pagos.md
│   └── runtime/
├── tests/
│   └── test_devoluciones.py
└── outputs/
```

## Instalación

Se recomienda Python 3.11 o superior.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

En `.env` se debe configurar:

```text
GEMINI_API_KEY=...
```

La configuración conserva el modelo usado en el Taller 2:

```text
gemini-3.5-flash-lite
```

## Construir el índice RAG

```bash
python src/indexar.py
```

La primera ejecución descarga el modelo de embeddings. Si el índice todavía no existe, el sistema también puede crearlo cuando se hace la primera consulta.

## Ejecutar pruebas

Las reglas críticas de devolución están separadas del LLM y se prueban sin hacer llamadas a Gemini:

```bash
python -m unittest discover -s tests -v
```

## Ejecutar por consola

```bash
python src/app.py
```

## Ejecutar la interfaz

```bash
python src/interfaz.py
```

Gradio queda disponible localmente, normalmente en:

```text
http://127.0.0.1:7860
```

## Prompts recomendados para la demostración

### 1. Consulta que debe usar RAG

```text
¿Cuánto tiempo tengo para solicitar una devolución?
```

### 2. Devolución válida

```text
Quiero devolver la camiseta de algodón orgánico del pedido ECO-2026-1042.
El SKU es TEX-0031, está sin uso, conserva las etiquetas y fue un cambio de talla.
```

Resultado esperado: verificar elegibilidad → generar etiqueta → registrar devolución.

Antes de repetir esta prueba:

```bash
python src/reset_demo.py
```

### 3. Pedido que no está entregado

```text
Quiero devolver el producto HOG-0204 del pedido ECO-2026-1087 porque cambié de opinión.
```

Resultado esperado: la verificación rechaza el flujo porque el pedido todavía no está entregado.

### 4. Producto normalmente no retornable

```text
Quiero devolver el café ALI-0455 del pedido ECO-2026-1372 porque ya no lo quiero.
```

Resultado esperado: no se genera etiqueta porque pertenece a alimentos perecederos.

### 5. Excepción que necesita revisión

```text
El café ALI-0455 del pedido ECO-2026-1372 llegó con el empaque roto. Quiero una solución.
```

Resultado esperado: el agente identifica una excepción atribuible a EcoMarket y no genera una devolución física automática. El caso se deriva para validación de evidencia.

### 6. Devolución ya existente

```text
Genera otra devolución para TEX-0145 del pedido ECO-2026-1268.
```

Resultado esperado: el agente detecta que ya existe una devolución y evita duplicarla.

## Nota sobre los datos

Los datos son ficticios y se usan únicamente para el caso académico de EcoMarket. La fecha de corte incluida en `pedidos.json` se utiliza como fecha de referencia para las reglas de plazo. Esto permite reproducir los mismos casos de prueba aunque el proyecto se ejecute posteriormente.
