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
- [ ] No se ejecutó el RAG completo con Chroma y los modelos reales en este entorno.
- [ ] No se ejecutaron decisiones reales de Gemini; la evaluación de los ocho prompts sigue pendiente.

**Estado:** implementación y controles unitarios cubiertos; validación E2E pendiente.

## 3. Análisis crítico y monitoreo

- [x] `fase-3-analisis-critico.md` cubre acciones incorrectas, prompt injection, privacidad, alucinaciones, sesgo e impacto laboral.
- [x] Propone supervisión humana, métricas, alertas y extensiones futuras.
- [x] `outputs/agent-actions.jsonl` registra timestamp, session_id, tool, argumentos sanitizados, resultado, status, error y duración.
- [x] Una prueba verifica los campos y el enmascaramiento de datos del log.

**Estado:** cubierto en documentación y código; requiere revisión operativa antes de producción.

## 4. Despliegue

- [x] Gradio incluye chat, ejemplos, limpieza y panel de actividad.
- [x] La interfaz maneja excepciones normales del agente sin perder la conversación.
- [ ] No se levantó la interfaz ni se completó una demostración de extremo a extremo en este entorno.
- [ ] La prueba E2E con Gemini requiere dependencias instaladas, índice construido y `GEMINI_API_KEY`.

**Estado:** interfaz implementada; funcionamiento E2E pendiente de verificación.

## Validación local disponible

La suite offline cubre reglas de negocio, orquestación simulada, contrato del adaptador RAG y observabilidad. Los dobles de prueba no demuestran la calidad de selección de herramientas de Gemini ni sustituyen una consulta real al índice.

Para repetir las pruebas:

```bash
python -m compileall -q src tests
python -m unittest discover -s tests -v
```

Antes de entregar, ejecutar los prompts de `PROMPTS_DEMO.md` con la credencial configurada y confirmar los casos A–H, el RAG y la interfaz. No afirmar una calificación de 5/5 sin esa verificación.
