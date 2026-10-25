import logging

from agent import IrisAgent

LOGGER = logging.getLogger("iris.consola")

def main():
    logging.basicConfig(level=logging.WARNING)
    try:
        agente = IrisAgent()
    except Exception as error:
        print(f"No fue posible iniciar Iris: {error}")
        return

    print("Iris · EcoMarket")
    print("Escribe 'salir' para terminar.\n")

    while True:
        mensaje = input("Cliente: ").strip()
        if mensaje.lower() in {"salir", "exit", "quit"}:
            break
        if not mensaje:
            continue

        try:
            resultado = agente.responder(mensaje)
        except Exception:
            LOGGER.exception("Falló la ejecución del agente")
            print("\nIris: No fue posible procesar tu mensaje en este momento. Intenta de nuevo.\n")
            continue
        print(f"\nIris: {resultado['respuesta']}\n")
        if resultado["eventos"]:
            print("Herramientas ejecutadas:")
            for evento in resultado["eventos"]:
                print(f"- {evento['herramienta']}: {evento['status']}")
            print()

if __name__ == "__main__":
    main()
