# Guía del video de demostración

Duración objetivo: entre 8:30 y 9:30 minutos.

## 0:00 – 2:30 · Fase 1

Mostrar `fase-1-arquitectura.md`.

Explicar:

- Iris venía del Taller 2 con RAG.
- En el proyecto final el RAG pasa a ser una herramienta.
- LangChain se mantiene para no cambiar el stack.
- Mostrar las herramientas:
  - consultar pedido;
  - verificar elegibilidad;
  - generar etiqueta;
  - registrar devolución.
- Aclarar que la verificación está en código y no depende de que el LLM "decida" las reglas.

Mostrar brevemente el diagrama Mermaid.

## 2:30 – 5:30 · Fase 2

Mostrar `src/agent.py` y explicar el ciclo de tool calling.

Luego mostrar `src/devoluciones.py`:

- validación del pedido;
- plazo;
- categoría;
- excepción;
- autorización;
- protección contra duplicados.

Mostrar `tests/test_devoluciones.py` y, si hay tiempo, ejecutar:

```bash
python -m unittest discover -s tests -v
```

## 5:30 – 9:00 · Fase 4

Ejecutar:

```bash
python src/interfaz.py
```

### Caso A: solo RAG

```text
¿Cuánto tiempo tengo para solicitar una devolución?
```

Enseñar que no se genera etiqueta.

### Caso B: acción completa

Antes del caso:

```bash
python src/reset_demo.py
```

Prompt:

```text
Quiero devolver la camiseta de algodón orgánico del pedido ECO-2026-1042.
El SKU es TEX-0031, está sin uso, conserva las etiquetas y fue un cambio de talla.
```

Mostrar en el panel:

1. verificación;
2. etiqueta;
3. registro.

### Caso C: fallo controlado

```text
Genera otra devolución para TEX-0145 del pedido ECO-2026-1268.
```

Mostrar que la herramienta detecta una devolución existente y bloquea la acción.

## Cierre

En una frase:

> El cambio principal frente al Taller 2 es que Iris ya no se limita a recuperar información y responder; ahora puede ejecutar acciones, pero las acciones críticas están protegidas por reglas determinísticas, trazabilidad y manejo de errores.
