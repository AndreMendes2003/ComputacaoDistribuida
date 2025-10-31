#!/bin/bash
echo "Gerando código Python a partir de protos/printing.proto..."

python3 -m grpc_tools.protoc \
    -I=protos/ \
    --python_out=src/ \
    --grpc_python_out=src/ \
    protos/printing.proto

echo "Arquivos 'printing_pb2.py' e 'printing_pb2_grpc.py' gerados em 'src/'."