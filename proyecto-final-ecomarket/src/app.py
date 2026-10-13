from agent import IrisAgent

def main():
    try:
        agente = IrisAgent()
    except Exception as error:
        print(f"No fue posible iniciar Iris: {error}")
        return

    historial = []
    print("Iris · EcoMarket")
    print("Escribe 'salir' para terminar.\n")

    while True:
        mensaje = input("Cliente: ").strip()
        if mensaje.lower() in {"salir", "exit", "quit"}:
            break
        if not mensaje:
            continue

        resultado = agente.responder(mensaje, historial)
        print(f"\nIris: {resultado['respuesta']}\n")
        if resultado["eventos"]:
            print("Herramientas ejecutadas:")
            for evento in resultado["eventos"]:
                print(f"- {evento['herramienta']}: {evento['resultado'].get('codigo', 'OK')}")
            print()
        historial.append((mensaje, resultado["respuesta"]))

if __name__ == "__main__":
    main()
