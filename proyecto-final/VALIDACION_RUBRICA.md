# Validación técnica de la rúbrica

Checklist interno. Distingue lo que está implementado de lo que se ejecutó localmente; no asigna una calificación anticipada.

## 1. Diseño de arquitectura y herramientas

- [x] Documenta el flujo y las entradas/salidas de las tools en `fase-1-arquitectura.md`.
- [x] LangChain se justifica frente a LlamaIndex.
- [x] Hay cuatro herramientas adicionales al RAG.
- [x] El flujo exige verificación antes de etiqueta y registro.
- [x] El agente usa `bind_tools` y procesa `tool_calls` en `src/agent.py`.

**Estado:** cubierto en diseño e implementación visible.

## 2. Implementación y conexión

- [x] Reglas críticas de devolución implementadas fuera del LLM.
- [x] Autorización de un solo uso, etiqueta válida y bloqueo de duplicados.
- [x] Límite de pasos, herramienta desconocida y excepciones de ejecución contemplados.
- [x] Hay pruebas unitarias para reglas y pruebas controladas del ciclo de tool calling.
- [x] El adaptador conecta la tool con la cadena LCEL y devuelve evidencia de recuperación.
- [x] Ocho casos especifican el comportamiento esperado en `tests/casos_agente.json`.
- [x] El caso informativo ejecutó Chroma y el reranker reales: 20 candidatos y cuatro fragmentos finales.
- [x] Los casos A–H se ejecutaron con Gemini real; la última corrida aprobó los ocho casos.
- [x] La devolución válida completó verificación, etiqueta y registro; el prompt injection no saltó las herramientas de seguridad.
- [x] La evidencia resumida está en `outputs/evidencia-rubrica-gemini.jsonl`; no contiene prompts, claves ni argumentos.

**Estado:** implementación y flujos E2E comprobados en la última ejecución local.

## 3. Análisis crítico y monitoreo

- [x] `fase-3-analisis-critico.md` cubre acciones incorrectas, prompt injection, privacidad, alucinaciones, sesgo e impacto laboral.
- [x] Propone supervisión humana, métricas, alertas y extensiones futuras.
- [x] `outputs/agent-actions.jsonl` registra timestamp, session_id, tool, argumentos sanitizados, resultado, status, error y duración.
- [x] Una prueba verifica los campos y el enmascaramiento de datos del log.

**Estado:** cubierto en documentación y código; requiere revisión operativa antes de producción.

## 4. Despliegue

- [x] Gradio incluye chat, ejemplos, limpieza y panel de actividad.
- [x] La interfaz maneja excepciones normales del agente sin perder la conversación.
- [x] Gradio respondió HTTP 200 y se probó desde navegador con una consulta RAG real.
- [x] El panel mostró candidatos, similitud, puntajes de reranking, fragmentos finales y clasificación.
- [x] La respuesta visible fue texto limpio, sin metadatos internos de Gemini.

**Estado:** recorrido desde navegador hasta Gemini, RAG y panel de actividad comprobado.

## Validación local disponible

La suite offline cubre reglas de negocio, orquestación simulada, adaptador RAG, panel, estructura documental y observabilidad. Las ocho pruebas E2E están separadas para evitar consumo accidental de API y se habilitan de forma explícita.

Para repetir las pruebas:

```bash
python -m compileall -q src tests
python -m unittest discover -s tests -v
```

La validación de esta copia terminó con 30 pruebas offline aprobadas; las ocho pruebas E2E aprobadas se ejecutaron por separado con `RUN_GEMINI_E2E=1`. La calificación académica final depende del criterio del docente y no puede garantizarse únicamente mediante tests.
