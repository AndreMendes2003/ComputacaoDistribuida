# Trabalho 1 - Sistema de Impressão Distribuída (Ricart-Agrawala + Lamport)

Este repositório contém a implementação em Python pedida no trabalho prático:
um servidor de impressão "burro" e clientes inteligentes que coordenam o acesso
à impressora via o algoritmo de Ricart-Agrawala, usando relógios lógicos de
Lamport para ordenar eventos.

Este README reúne: manual de execução, especificação do sistema, casos de teste,
mapa para a rubrica de avaliação e instruções para empacotamento/submissão.

## Conteúdo relevante
- `src/printer_server.py` - Servidor de impressão "burro" (porta padrão 50051).
- `src/printing_client.py` - Cliente inteligente que implementa Ricart-Agrawala e Lamport.
- `protos/printing.proto` - Definição do protocolo gRPC usado.
- `requirements.txt` - Dependências Python (grpcio, grpcio-tools).
- `start_all.ps1` - (Windows) inicia servidor + 3 clientes em janelas separadas.

## Pré-requisitos
- Python 3.7+

Instalar dependências:

```powershell
python -m pip install -r .\requirements.txt
```

Gerar código gRPC (quando alterar `.proto`):

```powershell
python -m grpc_tools.protoc -I. --python_out=./src --grpc_python_out=./src protos/printing.proto
```

## Estrutura e arquitetura
O sistema divide responsabilidades:

- Servidor de Impressão "burro":
  - Implementa `PrintingService` com RPC `SendToPrinter(PrintRequest) -> PrintResponse`.
  - Ao receber uma requisição, atualiza seu relógio de Lamport local, imprime a
    mensagem no console no formato pedido e simula 2s de tempo de impressão.
  - Não participa do algoritmo de exclusão mútua.

- Clientes Inteligentes:
  - Implementam `MutualExclusionService` com RPCs `RequestAccess` e `ReleaseAccess`.
  - Mantêm estados Ricart-Agrawala (`RELEASED`, `WANTED`, `HELD`) e relógio de Lamport.
  - Enviam `RequestAccess` para os peers, aguardam `AccessResponse` (OK) e, quando
    recebem OKs de todos, chamam `SendToPrinter` no servidor burro.

## Implementação técnica — principais pontos

- **Relógio de Lamport**
  - `tick()`: incrementa o relógio antes de eventos locais.
  - `update_clock(t)`: ao receber timestamp `t`, faz `LAMPORT_CLOCK = max(LAMPORT_CLOCK, t) + 1`.
  - Ambas funções são protegidas por `threading.RLock()` para evitar deadlocks.

- **Ricart-Agrawala**
  - Ao entrar em `WANTED`: o cliente gera `MY_REQUEST_TIMESTAMP = tick()`, aumenta
    `MY_REQUEST_NUMBER`, e envia `AccessRequest` para todos os peers.
  - Espera receber `AccessResponse(access_granted=True)` de todos antes de entrar em `HELD`.
  - Ao liberar, envia `AccessRelease` para os peers e faz `STATE_CONDITION.notify_all()`.
  - Tie-break: tupla `(timestamp, client_id)`; menor vence.

## Como executar (exemplo com 3 clientes)
Abra 4 terminais (um para o servidor e um para cada cliente). Exemplos para PowerShell:

```powershell
# Terminal 1: servidor de impressão
python .\src\printer_server.py

# Terminal 2: Cliente 1
python .\src\printing_client.py --id 1 --port 50052 --clients localhost:50053,localhost:50054 --server localhost:50051

# Terminal 3: Cliente 2
python .\src\printing_client.py --id 2 --port 50053 --clients localhost:50052,localhost:50054 --server localhost:50051

# Terminal 4: Cliente 3
python .\src\printing_client.py --id 3 --port 50054 --clients localhost:50052,localhost:50053 --server localhost:50051
```

Ou use `start_all.ps1` no Windows para abrir janelas automaticamente.

## Casos de Teste (passo a passo)

### Cenário 1 — Funcionamento Básico sem concorrência
1. Inicie servidor, em seguida inicie dois clientes (B e C) que aguardam.
2. Inicie Cliente A; ele deverá:
   - Entrar em `WANTED`, enviar `RequestAccess` e receber OKs dos peers.
   - Entrar em `HELD` e enviar `SendToPrinter` ao servidor burro.
   - Após impressão, entrar em `RELEASED` e notificar peers com `ReleaseAccess`.

**Verificações (logs)**:
- Mensagens "WANTED" e envios/recebimentos de `RequestAccess`/`AccessResponse`.
- Impressora imprimindo a requisição: `[REQUISIÇÃO RECEBIDA] Cliente {id}...`.

### Cenário 2 — Concorrência
1. Inicie servidor.
2. Inicie Cliente C e faça com que ele entre em `HELD` (imprimindo).
3. Inicie Cliente A e B quase simultaneamente.

**Verificações**:
- Enquanto C estiver em `HELD`, A e B só recebem OKs após `Release` de C.
- Entre A e B, o menor Lamport timestamp (ou menor client_id em empate) vence.

## Exemplos de logs observados

Trechos reais de execução mostram deferimento enquanto há cliente em HELD, notificações
de liberação e ordem por timestamps. Exemplo:

```
--- IMPRESSORA (TS: 3) ---
[REQUISIÇÃO RECEBIDA] Cliente 1 (Req N° 1, TS: 2)
  > Mensagem: 'Trabalho de CD do Cliente 1'
  ...Imprimindo (espera 2s)...
  ...Impressão Concluída.
```

## Mapeamento para a Rubrica de Avaliação

- **Corretude do algoritmo (30% / 3 pts)**: Ricart-Agrawala com deferimento e tie-break `(timestamp, client_id)`.
- **Sincronização de relógios (20% / 2 pts)**: `tick()`/`update_clock()` aplicados corretamente.
- **Comunicação cliente-servidor (10% / 1 pt)**: `PrintingService` usado pelo cliente em `HELD`.
- **Comunicação cliente-cliente (10% / 1 pt)**: `MutualExclusionService` implementado entre clientes.
- **Funcionamento em múltiplos terminais (10% / 1 pt)**: testado com processos separados.
- **Código fonte e documentação (20% / 2 pts)**: código comentado e documentação (README).

## Entregáveis para submissão

- Código-fonte: `src/printer_server.py`, `src/printing_client.py`, e stubs gRPC em `src/`.
- Scripts: `start_all.ps1` e `requirements.txt`.
- Documentação: este `README.md` (completo).
- Evidências: logs de execução (salve outputs dos 4 terminais em `Trabalho1/logs/`).

## Checklist final antes da submissão

- [ ] Incluir o diretório `src/` com `printing_pb2.py` e `printing_pb2_grpc.py` (ou gerar).
- [ ] Incluir `requirements.txt`.
- [ ] Incluir `start_all.ps1` e este `README.md`.
- [ ] Anexar `logs/` com as execuções dos dois cenários.

## Próximos passos (opcionais)

- Implementar testes automatizados de integração (subprocessos) para comprovar
  exclusão mútua de forma reprodutível.
- Melhorar tolerância a falhas (retries, detectação de nós mortos).

## Contato e submissão

Coloque todos os arquivos e a pasta `logs/` em um único ZIP e submeta conforme as
instruções da disciplina. Se quiser, eu posso preparar o ZIP automaticamente com os
logs atuais e os arquivos essenciais.
# Trabalho 1 - Sistema de Impressão Distribuída (Ricart-Agrawala + Lamport)

Este diretório contém uma implementação em Python de um sistema de impressão distribuída
usando gRPC, o algoritmo de Ricart-Agrawala para exclusão mútua distribuída e relógios
lógicos de Lamport.

Conteúdo relevante:
- `src/printer_server.py` - Servidor de impressão "burro" (porta padrão 50051).
- `src/printing_client.py` - Cliente inteligente que implementa Ricart-Agrawala e Lamport.
- `protos/printing.proto` - Definição do protocolo gRPC usado.
- `requirements.txt` - Dependências Python (grpcio, grpcio-tools).

Pré-requisitos
- Python 3.7+
- Instalar dependências:

```powershell
python -m pip install -r .\requirements.txt
```

Gerar código gRPC (se necessário):

```powershell
python -m grpc_tools.protoc -I. --python_out=./src --grpc_python_out=./src protos/printing.proto
```

Como executar (exemplo usando 3 clientes)

1. Inicie o servidor de impressão (terminal 1):

```powershell
python .\src\printer_server.py
```

2. Inicie o Cliente 1 (terminal 2):

```powershell
python .\src\printing_client.py --id 1 --port 50052 --clients localhost:50053,localhost:50054 --server localhost:50051
```

3. Inicie o Cliente 2 (terminal 3):

```powershell
python .\src\printing_client.py --id 2 --port 50053 --clients localhost:50052,localhost:50054 --server localhost:50051
```

4. Inicie o Cliente 3 (terminal 4):

```powershell
python .\src\printing_client.py --id 3 --port 50054 --clients localhost:50052,localhost:50053 --server localhost:50051
```

Observações
- O servidor de impressão é "burro" e não participa do algoritmo de exclusão mútua.
- Os clientes executam o algoritmo de Ricart-Agrawala e usam relógios de Lamport.
- Para testes automatizados rápidos, veja `start_all.ps1` que abre janelas separadas.
# Trabalho 1 Computação Distribuída

Este projeto implementa um sistema de exclusão mútua distribuída usando o algoritmo de Ricart-Agrawala.

## 1. Estrutura de Pastas

- `/protos` - Contém a definição do serviço `.proto`.
- `/src` - Contém todo o código-fonte Python (scripts e gRPC gerado).
- `requirements.txt` - Dependências do Python.
- `generate_grpc.sh` - Script para gerar o código gRPC.

## 2. Instruções

1. Instalar as dependências gRPC:
    ```bash
    pip install -r requirements.txt

2. Geração do Código gRPC:

    -Linux:
   
        bash generate_grpc.sh

    -Windows:
   
        python -m grpc_tools.protoc -I=protos/ --python_out=src/ --grpc_python_out=src/ protos/printing.proto

3. Execução:
   
    Necessários 4 terminais (um para o servidor e um para cada cliente).

     Terminal 1 (Servidor de Impressão "Burro")
 
        python3 src/printer_server.py

    Terminal 2 (Cliente 1)

        python3 src/printing_client.py --id 1 --port 50052 --clients localhost:50053,localhost:50054 --server localhost:50051

    Terminal 3 (Cliente 2)

        python3 src/printing_client.py --id 2 --port 50053 --clients localhost:50052,localhost:50054 --server localhost:50051

    Terminal 4 (Cliente 3)

        python3 src/printing_client.py --id 3 --port 50054 --clients localhost:50052,localhost:50053 --server localhost:50051

