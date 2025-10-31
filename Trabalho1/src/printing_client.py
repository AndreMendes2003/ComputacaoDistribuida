# printing_client.py
import grpc
import threading
import time
import random
import sys
import argparse
from concurrent import futures

# Importa os códigos gerados pelo protoc
import printing_pb2
import printing_pb2_grpc

# --- Estado Global do Cliente ---

# Usamos um Lock e uma Condition Variable para gerenciar o estadode forma segura entre a thread principal (lógica do cliente) e as threads do servidor gRPC (que recebem pedidos de outros).
STATE_LOCK = threading.Lock()
STATE_CONDITION = threading.Condition(STATE_LOCK)

CLIENT_ID = -1
CLIENT_STATE = "RELEASED" # Estados: RELEASED, WANTED, HELD
LAMPORT_CLOCK = 0
MY_REQUEST_TIMESTAMP = -1 # Guarda o timestamp
MY_REQUEST_NUMBER = 0

# --- Funções do Relógio de Lamport (Thread-safe) ---

def tick():
    """Regra 1: Incrementa o relógio antes de um evento local."""
    global LAMPORT_CLOCK
    with STATE_LOCK:
        LAMPORT_CLOCK += 1
        return LAMPORT_CLOCK

def update_clock(received_timestamp):
    """Regra 3: Atualiza o relógio ao receber uma mensagem."""
    global LAMPORT_CLOCK
    with STATE_LOCK:
        LAMPORT_CLOCK = max(LAMPORT_CLOCK, received_timestamp) + 1
        return LAMPORT_CLOCK

# --- Implementação do Servidor gRPC do Cliente ---
# (Roda em uma thread separada para ouvir os outros clientes)

class MutualExclusionImpl(printing_pb2_grpc.MutualExclusionServiceServicer):
    
    def RequestAccess(self, request, context):
        """Handler para quando OUTRO cliente nos pede acesso (RPC)."""
        
        # 1. Atualiza relógio ao receber o pedido
        received_clock = update_clock(request.lamport_timestamp)
        
        print(f"[Cliente {CLIENT_ID} | TS: {received_clock}] Recebeu RequestAccess de {request.client_id} (TS: {request.lamport_timestamp})")

        # 2. Lógica de Decisão de Ricart-Agrawala
        with STATE_LOCK:
            # Verifica se devemos deferir (atrasar) a resposta "OK"
            should_defer = False
            
            if CLIENT_STATE == "HELD":
                # Caso 1: Esta na Seção Crítica (imprimindo).
                should_defer = True
            elif CLIENT_STATE == "WANTED":
                # Caso 2: Também quer entrar. Usa o desempate.
                if (MY_REQUEST_TIMESTAMP, CLIENT_ID) < (request.lamport_timestamp, request.client_id):
                    # Pedido é mais antigo (menor). Ele deve esperar.
                    should_defer = True
                else:
                    # O pedido dele é mais antigo (ou ID menor em caso de empate).
                    # Deve esperar por ele (responde OK).
                    should_defer = False
            # Caso 3: (CLIENT_STATE == "RELEASED")
            # Não estamos na SC e não queremos entrar. Respondemos OK.
            
            # 3. Loop de Espera (Deferindo a resposta)
            #    Usa a Condition Variable para esperar eficientemente.
            while should_defer:
                print(f"  [Cliente {CLIENT_ID}] Deferindo pedido de {request.client_id} (Nosso estado: {CLIENT_STATE}, Nosso TS: {MY_REQUEST_TIMESTAMP})")
                STATE_CONDITION.wait() # Libera o lock e dorme
                
                # Ao acordar (notificado por notify_all()), reavalia a condição
                # (o estado pode ter mudado para RELEASED)
                
                # REAVALIA a condição de deferir
                if CLIENT_STATE == "HELD":
                    should_defer = True
                elif CLIENT_STATE == "WANTED":
                    if (MY_REQUEST_TIMESTAMP, CLIENT_ID) < (request.lamport_timestamp, request.client_id):
                        should_defer = True
                    else:
                        should_defer = False
                else:
                    should_defer = False # Estado agora é RELEASED
            
            # 4. Envia a Resposta "OK"
            reply_ts = tick() # Evento de envio de resposta
            print(f"  [Cliente {CLIENT_ID} | TS: {reply_ts}] Respondendo 'OK' para {request.client_id}")
            
            return printing_pb2.AccessResponse(
                access_granted=True,
                lamport_timestamp=reply_ts
            )

    def ReleaseAccess(self, request, context):
        """Handler para o (opcional) ReleaseAccess do .proto."""
        
        received_clock = update_clock(request.lamport_timestamp)
        print(f"[Cliente {CLIENT_ID} | TS: {received_clock}] Recebeu notificação 'ReleaseAccess' de {request.client_id}")
        
        return printing_pb2.Empty()


def run_grpc_server(port):
    """Inicia o servidor gRPC do cliente (para ouvir os outros)."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    printing_pb2_grpc.add_MutualExclusionServiceServicer_to_server(MutualExclusionImpl(), server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    print(f"[Cliente {CLIENT_ID}] Servidor interno iniciado. Ouvindo na porta {port}")
    server.wait_for_termination()

# --- Lógica Principal do Cliente ---
# (Roda na thread principal)

def run_client_logic(my_id, my_port, client_addresses, printer_address):
    global CLIENT_ID, CLIENT_STATE, MY_REQUEST_TIMESTAMP, MY_REQUEST_NUMBER
    CLIENT_ID = my_id

    # --- Conexões gRPC (Stubs) ---
    print(f"[Cliente {CLIENT_ID}] Conectando aos outros clientes: {client_addresses}")
    client_stubs = {}
    for addr in client_addresses:
        # Pega o ID do cliente a partir da porta (ex: 'localhost:50052' -> 52)
        other_id_str = addr.split(':')[-1]
        other_id = int(other_id_str) % 100 # Assume que IDs são os 2 últimos dígitos da porta
        channel = grpc.insecure_channel(addr)
        client_stubs[other_id] = printing_pb2_grpc.MutualExclusionServiceStub(channel)

    print(f"[Cliente {CLIENT_ID}] Conectando ao servidor de impressão: {printer_address}")
    printer_channel = grpc.insecure_channel(printer_address)
    printer_stub = printing_pb2_grpc.PrintingServiceStub(printer_channel)


    while True:
        # --- 1. Fase RELEASED: Espera para querer imprimir ---
        time.sleep(random.uniform(4, 10)) # Espera um tempo aleatório
        
        # --- 2. Fase WANTED: Tenta obter acesso à SC ---
        
        my_req = None
        with STATE_LOCK:
            CLIENT_STATE = "WANTED"
            MY_REQUEST_NUMBER += 1
            MY_REQUEST_TIMESTAMP = tick() # Evento: Gerou pedido
            my_req = printing_pb2.AccessRequest(
                client_id=CLIENT_ID,
                lamport_timestamp=MY_REQUEST_TIMESTAMP,
                request_number=MY_REQUEST_NUMBER
            )
            print(f"\n[Cliente {CLIENT_ID} | TS: {MY_REQUEST_TIMESTAMP}] --- Estado: WANTED (Req N° {MY_REQUEST_NUMBER}) ---")
        
        # Envia RequestAccess para todos os outros clientes
        # Estas chamadas são bloqueantes. Elas só retornam quando o
        # outro cliente nos envia o AccessResponse("OK").
        reply_count = 0
        for other_id, stub in client_stubs.items():
            print(f"[Cliente {CLIENT_ID}] Enviando RequestAccess para {other_id}...")
            try:
                response = stub.RequestAccess(my_req)
                update_clock(response.lamport_timestamp) # Evento: Recebeu resposta
                reply_count += 1
                print(f"[Cliente {CLIENT_ID}] Recebeu 'OK' de {other_id} ({reply_count}/{len(client_stubs)})")
            except grpc.RpcError as e:
                print(f"[Cliente {CLIENT_ID}] ERRO: Não foi possível contatar cliente {other_id}: {e.details()}")
                # Em um sistema robusto, falhas de nós seriam tratadas aqui.

        print(f"\n[Cliente {CLIENT_ID}] Recebeu 'OK' de todos os {reply_count} clientes.")
        
        # --- 3. Fase HELD: Conseguiu! Entra na Seção Crítica ---
        with STATE_LOCK:
            CLIENT_STATE = "HELD"
        
        print(f"[Cliente {CLIENT_ID}] --- Estado: HELD (Entrando na Seção Crítica) ---")
        
        # Agora podemos falar com o servidor burro
        try:
            print(f"[Cliente {CLIENT_ID}] Enviando para a Impressora...")
            print_ts = tick() # Evento: Envio para impressora
            print_req = printing_pb2.PrintRequest(
                client_id=CLIENT_ID,
                message_content=f"Trabalho de CD do Cliente {CLIENT_ID}",
                lamport_timestamp=print_ts,
                request_number=MY_REQUEST_NUMBER
            )
            print_resp = printer_stub.SendToPrinter(print_req)
            update_clock(print_resp.lamport_timestamp) # Evento: Recebeu da impressora
            print(f"[Cliente {CLIENT_ID}] Impressora confirmou: '{print_resp.confirmation_message}'")
            
        except grpc.RpcError as e:
            print(f"[Cliente {CLIENT_ID}] ERRO: Falha ao contatar impressora: {e.details()}")

        # --- 4. Fase RELEASED: Sai da Seção Crítica ---
        
        release_ts = -1
        with STATE_LOCK:
            CLIENT_STATE = "RELEASED"
            MY_REQUEST_TIMESTAMP = -1 # Limpa nosso pedido
            release_ts = tick() # Evento: Liberação
            
            print(f"\n[Cliente {CLIENT_ID} | TS: {release_ts}] --- Estado: RELEASED (Notificando waiters) ---")
            
            # ACORDA todas as threads (RequestAccess) que estavam dormindo
            # (esperando em 'STATE_CONDITION.wait()')
            STATE_CONDITION.notify_all() 
        
        # Envia a notificação ReleaseAccess (como pedido no .proto)
        release_msg = printing_pb2.AccessRelease(
            client_id=CLIENT_ID,
            lamport_timestamp=release_ts,
            request_number=MY_REQUEST_NUMBER
        )
        for other_id, stub in client_stubs.items():
            try:
                # Esta é uma chamada "fire-and-forget", não espera resposta
                stub.ReleaseAccess(release_msg)
            except grpc.RpcError:
                print(f"[Cliente {CLIENT_ID}] Falha ao notificar Release para {other_id}")
                pass 

# --- Inicialização ---

def main():
    # Configura o parsing de argumentos da linha de comando
    parser = argparse.ArgumentParser(description='Cliente de Impressão Distribuída (R-A)')
    parser.add_argument('--id', type=int, required=True, help='ID deste cliente (ex: 1)')
    parser.add_argument('--port', type=str, required=True, help='Porta para este cliente ouvir (ex: 50052)')
    parser.add_argument('--clients', type=str, required=True, help='Endereços dos outros clientes (ex: localhost:50053,localhost:50054)')
    parser.add_argument('--server', type=str, required=True, help='Endereço do servidor de impressão (ex: localhost:50051)')
    args = parser.parse_args()

    client_addresses = []
    if args.clients:
        client_addresses = args.clients.split(',')

    # 1. Inicia o servidor gRPC do cliente (para ouvir os outros) em uma thread
    server_thread = threading.Thread(target=run_grpc_server, args=(args.port,), daemon=True)
    server_thread.start()

    # 2. Inicia a lógica principal do cliente (para pedir acesso) na thread principal
    try:
        # Espera um pouco para garantir que todos os servidores subiram
        time.sleep(3) 
        run_client_logic(args.id, args.port, client_addresses, args.server)
    except KeyboardInterrupt:
        print(f"\n[Cliente {args.id}] Desligando...")
        sys.exit(0)
    except Exception as e:
        print(f"[Cliente {args.id}] Erro fatal: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
