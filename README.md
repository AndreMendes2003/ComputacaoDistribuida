# Trabalho 1 Computação Distribuída

Este projeto implementa um sistema de exclusão mútua distribuída usando o algoritmo de Ricart-Agrawala.

## 1. Estrutura de Pastas

- `/protos` - Contém a definição do serviço `.proto`.
- `/src` - Contém todo o código-fonte Python (scripts e gRPC gerado).
- `/docs` - Contém o relatório técnico.
- `requirements.txt` - Dependências do Python.
- `generate_grpc.sh` - Script para gerar o código gRPC.

## 2. Instruções

```bash
1. Instalar as dependências gRPC:
    pip install -r requirements.txt

2. Geração do Código gRPC:
    -Linux: 
    bash generate_grpc.sh

    -Windows:
    python -m grpc_tools.protoc -I=protos/ --python_out=src/ --grpc_python_out=src/ protos/printing.proto

3. Execução:
    Necessários 4 terminais (um para o servidor e um para cada cliente).

    -Terminal 1 (Servidor de Impressão "Burro")
    python3 src/printer_server.py

    -Terminal 2 (Cliente 1)
    python3 src/printing_client.py --id 1 --port 50052 --clients localhost:50053,localhost:50054 --server localhost:50051
    // python src/printing_client.py --id 1 --port 50052 --clients localhost:50053,localhost:50054 --server localhost:50051

    -Terminal 3 (Cliente 2)
    python3 src/printing_client.py --id 2 --port 50053 --clients localhost:50052,localhost:50054 --server localhost:50051
    // python src/printing_client.py --id 2 --port 50053 --clients localhost:50052,localhost:50054 --server localhost:50051

    -Terminal 4 (Cliente 3)
    python3 src/printing_client.py --id 3 --port 50054 --clients localhost:50052,localhost:50053 --server localhost:50051
    // python src/printing_client.py --id 3 --port 50054 --clients localhost:50052,localhost:50053 --server localhost:50051

