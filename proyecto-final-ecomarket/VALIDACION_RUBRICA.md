# Validación contra la rúbrica

Esta revisión se hizo punto por punto antes de empaquetar la entrega.

## 1. Diseño de Arquitectura y Herramientas — 1 punto

**Rúbrica:** definir claramente las herramientas, seleccionar un marco apropiado, justificar la elección y presentar un flujo lógico.

**Cumplimiento**

- [x] RAG incorporado como herramienta del agente.
- [x] Se documentan cuatro herramientas adicionales al RAG.
- [x] Cada herramienta tiene entradas y salidas definidas.
- [x] Se selecciona LangChain y se explica por qué se mantiene frente a LlamaIndex.
- [x] Existe un diagrama de flujo en Mermaid.
- [x] Se explica el orden de ejecución y los bloqueos entre herramientas.

**Evidencia:** `fase-1-arquitectura.md`, `src/tools.py`, `src/devoluciones.py`.

## 2. Implementación de Agentes y Conexión de Componentes — 2 puntos

**Rúbrica:** integrar el agente, demostrar comprensión de la conexión de piezas, tomar decisiones, usar herramientas apropiadas y manejar éxito y fallo de forma robusta.

**Cumplimiento**

- [x] El agente utiliza tool calling de LangChain.
- [x] El modelo puede consultar RAG.
- [x] El modelo puede consultar pedidos.
- [x] La devolución se valida con reglas determinísticas.
- [x] Una etiqueta solo se genera con autorización válida.
- [x] El registro solo se crea desde una etiqueta válida.
- [x] Se evita duplicar devoluciones.
- [x] Existe límite de pasos del agente.
- [x] Se manejan excepciones de herramientas y de API.
- [x] Hay pruebas unitarias de la lógica crítica.
- [x] Hay prompts de evaluación para comportamiento correcto e incorrecto.

**Evidencia:** `fase-2-implementacion.md`, `src/agent.py`, `src/tools.py`, `tests/test_devoluciones.py`, `PROMPTS_DEMO.md`.

## 3. Análisis Crítico y Propuestas de Mejora — 1 punto

**Rúbrica:** análisis crítico de riesgos éticos y de seguridad, propuestas de monitoreo y mejoras pertinentes.

**Cumplimiento**

- [x] Riesgo de acciones incorrectas.
- [x] Prompt injection.
- [x] Privacidad.
- [x] Alucinaciones.
- [x] Sesgo.
- [x] Impacto laboral.
- [x] Registro de acciones.
- [x] Propuesta de métricas y alertas.
- [x] Human in the loop como mejora.
- [x] CRM, reemplazos y evidencias como extensiones futuras.

**Evidencia:** `fase-3-analisis-critico.md`, `src/observability.py`.

## 4. Despliegue Funcional — 1 punto

**Rúbrica:** interfaz funcional con Streamlit o Gradio, intuitiva y usable de extremo a extremo.

**Cumplimiento**

- [x] Gradio.
- [x] Campo de texto.
- [x] Conversación.
- [x] Panel de actividad.
- [x] Botón de limpieza.
- [x] Ejemplos de uso.
- [x] Integración directa con el agente.
- [x] Instrucciones de ejecución.

**Evidencia:** `fase-4-despliegue.md`, `src/interfaz.py`.

## Entrega

- [x] Las cuatro fases están documentadas.
- [x] El código está incluido.
- [x] Se incluye `.env.example`, no una clave real.
- [x] Se incluye guía para el video de máximo 10 minutos.
- [x] Se incluyen prompts específicos para la demostración.
- [x] Se incluye comando de pruebas.

**Puntaje cubierto por la estructura de la entrega: 5/5.**

La calificación final depende de que el repositorio se ejecute en el ambiente del evaluador y de la valoración académica del profesor.
