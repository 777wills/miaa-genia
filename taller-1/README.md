# Taller práctico 1 · Optimización de la atención al cliente en EcoMarket

**Maestría en Inteligencia Artificial · Inteligencia Artificial Generativa**

**Autores:** William Alberto Suaza · Anderson Trujillo · Bairon Gutiérrez

---

## El caso

EcoMarket es una tienda en línea de productos sostenibles en rápido crecimiento. Su área de soporte
recibe miles de consultas diarias por chat, correo y redes sociales; el 80% son repetitivas —estado
del pedido, devoluciones, características del producto— y el 20% restante exige empatía y criterio
humano. El tiempo de respuesta promedio es de veinticuatro horas y está deteriorando la
satisfacción del cliente.

Diseñamos una solución de IA generativa para ese problema y la desarrollamos en tres fases.

## Contenido de la entrega

| Fase | Documento                                                                                       | Qué contiene                                                                                                                                                                          |
| ---- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | [Selección y justificación del modelo](fase-1-seleccion-y-justificacion-del-modelo.md)          | Requisitos derivados del caso, criterios ponderados, comparación de alternativas, arquitectura propuesta con diagrama y justificación por costo, escalabilidad, integración y calidad |
| 2    | [Fortalezas, limitaciones y riesgos éticos](fase-2-fortalezas-limitaciones-y-riesgos-eticos.md) | Análisis crítico de la solución, riesgos de alucinación, sesgo, privacidad e impacto laboral, matriz de riesgos con mitigaciones, indicadores y gobernanza del despliegue             |
| 3    | [Aplicación de la ingeniería de prompts](fase-3-ingenieria-de-prompts.md)                       | Implementación ejecutable, técnicas de prompting aplicadas, los dos ejercicios exigidos y la comparación entre el prompt básico y el prompt final                                     |

## La solución en una frase

Una arquitectura híbrida en la que el modelo generativo aporta el lenguaje y los sistemas de
EcoMarket aportan el dato: la consulta se clasifica, el contexto se recupera del registro de pedidos
y de la política vigente, la respuesta se valida antes de enviarse y todo caso sensible se deriva a
un agente humano.

## Cómo ejecutar el código

Requiere Python 3.11 o superior y una clave de la API de Gemini obtenida en
[Google AI Studio](https://aistudio.google.com/apikey).

```bash
cd taller-1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configura la credencial copiando la plantilla y escribiendo la clave dentro del archivo `.env`, que
está excluido del control de versiones:

```bash
cp .env.example .env
```

Genera una respuesta para una consulta concreta:

```bash
python src/app.py src/datos/consultas/01-estado-pedido-retrasado.txt \
  --configuracion src/settings-final.toml
```

Ejecuta las cinco consultas con las dos configuraciones de prompts y guarda las respuestas en
`outputs/`:

```bash
./generar_salidas.sh
```

## Estructura del repositorio

```
taller-1/
├── README.md
├── fase-1-seleccion-y-justificacion-del-modelo.md
├── fase-2-fortalezas-limitaciones-y-riesgos-eticos.md
├── fase-3-ingenieria-de-prompts.md
├── generar_salidas.sh
├── requirements.txt
├── .env.example
├── outputs/
│   ├── basico/
│   └── mejorado/
└── src/
    ├── app.py
    ├── settings.toml
    ├── settings-final.toml
    └── datos/
        ├── pedidos.json
        ├── politica-devoluciones.md
        └── consultas/
```
