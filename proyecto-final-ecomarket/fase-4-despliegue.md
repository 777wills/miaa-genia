# Fase 4. Despliegue de la aplicación

## Herramienta escogida

Se mantiene **Gradio** porque ya se utilizó en el Taller 2 y permite reutilizar la interfaz existente sin agregar otro framework al proyecto.

Para este caso ofrece lo que necesitamos:

- campo de texto para el mensaje;
- historial de conversación;
- ejemplos de prueba;
- panel para mostrar la actividad del agente;
- ejecución local sencilla.

Cambiar a Streamlit también sería posible, pero no aportaría una ventaja suficiente para justificar rehacer la interfaz.

## Interfaz

La aplicación tiene dos zonas:

1. **Conversación con Iris**
   - mensaje del cliente;
   - respuesta del agente;
   - botón para limpiar la conversación.

2. **Actividad del agente**
   - herramienta utilizada;
   - resultado de cada llamada;
   - errores controlados;
   - identificación de la sesión.

El panel de actividad facilita la demostración porque permite comprobar que una devolución válida realmente pasó por las herramientas y que una consulta informativa no dispara acciones innecesarias.

## Ejecución

```bash
python src/indexar.py
python src/interfaz.py
```

La aplicación se abre localmente en el navegador.

## Demostración extremo a extremo

Para la demostración principal se recomienda este prompt:

```text
Quiero devolver la camiseta de algodón orgánico del pedido ECO-2026-1042.
El SKU es TEX-0031, está sin uso, conserva las etiquetas y fue un cambio de talla.
```

El panel debería mostrar, en orden:

1. `verificar_elegibilidad_devolucion`;
2. `generar_etiqueta_devolucion`;
3. `registrar_devolucion`.

Luego se puede mostrar un caso que no debe ejecutar acciones:

```text
¿Cuánto tiempo tengo para solicitar una devolución?
```

En ese caso se espera una consulta al RAG y una respuesta informativa.

Finalmente se recomienda mostrar un fallo controlado:

```text
Genera otra devolución para TEX-0145 del pedido ECO-2026-1268.
```

El agente debe reconocer que ya existe una devolución y no debe crear otra.
