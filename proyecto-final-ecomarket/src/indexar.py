from rag import construir_indice

if __name__ == "__main__":
    resultado = construir_indice()
    print(f"Índice construido. Documentos: {resultado['documentos_indexados']}")
    print(f"Ruta: {resultado['indice']}")
