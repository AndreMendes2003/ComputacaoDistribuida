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

## Entregáveis para submissão

- Código-fonte: `src/printer_server.py`, `src/printing_client.py`, e stubs gRPC em `src/`.
- Scripts: `requirements.txt`.
- Documentação: este `README.md` (completo).
- Evidências: logs de execução (salve outputs dos 4 terminais em `Trabalho1/logs/`).