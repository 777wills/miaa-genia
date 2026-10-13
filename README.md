# Inteligencia Artificial Generativa

Repositorio de talleres de la asignatura **Inteligencia Artificial Generativa**, de la **Maestría en
Inteligencia Artificial Aplicada** de la **Universidad ICESI**.

**Autores:** William Alberto Suaza · Anderson Trujillo · Bairon Gutiérrez

---

## Propósito

Reunimos aquí el desarrollo de los talleres y el proyecto final de la asignatura. Cada entrega vive
en su propia carpeta, es autocontenida y aporta tanto los documentos de análisis como el código
ejecutable que sustenta las decisiones tomadas.

## Entregas

| Entrega        | Carpeta                                              | Tema                                                                          | Contenido                                                                                                                                                              |
| -------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Taller 1       | [taller-1](taller-1)                                 | Optimización de la atención al cliente en una empresa de comercio electrónico | Selección y justificación de un modelo de IA generativa, evaluación de fortalezas, limitaciones y riesgos éticos, e implementación de una cadena de prompts ejecutable |
| Taller 2       | [taller-2](taller-2)                                 | Implementación de un sistema RAG para la atención al cliente de EcoMarket     | Selección de embeddings, reranker y base vectorial, construcción de la base de conocimiento e integración de un RAG con reranking, con experimento comparativo         |
| Proyecto final | [proyecto-final](proyecto-final)                   | Agente de IA para la atención al cliente de EcoMarket                         | RAG del Taller 2 con reranking, tool calling con LangChain, validación determinística de devoluciones e interfaz Gradio                                                 |

## Organización

Cada entrega sigue una estructura equivalente:

```
taller-N/
├── README.md          Portada del taller, con el caso y las instrucciones de ejecución
├── fase-*.md          Documentos de análisis, uno por fase del enunciado
├── requirements.txt   Dependencias con versiones fijadas
├── outputs/           Resultados reales obtenidos al ejecutar el código
└── src/               Código fuente, configuración y datos de prueba
```

## Convenciones

- Los documentos de análisis se escriben en Markdown, para que se lean directamente en el navegador.
- Las credenciales nunca se versionan: cada entrega incluye un archivo `.env.example` como plantilla y
  excluye el `.env` real mediante `.gitignore`.
- Las dependencias se declaran con versiones fijadas, de modo que el código siga siendo ejecutable
  más adelante.
- Los resultados de cada ejecución se conservan en `outputs/` como evidencia verificable.

## Cómo empezar

Cada taller se ejecuta de forma independiente. Consulta el README de la carpeta correspondiente para
conocer los requisitos, la configuración de credenciales y los comandos de ejecución.
