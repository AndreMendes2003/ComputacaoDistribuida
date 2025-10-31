# printer_server.py
import grpc
from concurrent import futures
import time
import threading
import printing_pb2
import printing_pb2_grpc

class PrintingServiceImpl(printing_pb2_grpc.PrintingServiceServicer):
    """Implementa o serviço de impressão "burro"."""
    
    def __init__(self):
        # Lock para simular que a impressora é um recurso
        # que só pode ser usado por um de cada vez.
        self.print_lock = threading.Lock()
        self.lamport_clock = 0

    def SendToPrinter(self, request, context):
        # O servidor é "burro" sobre exclusão mútua,
        # mas ele atualiza seu próprio relógio de Lamport
        with self.print_lock:
            self.lamport_clock = max(self.lamport_clock, request.lamport_timestamp) + 1
            
            print(f"--- IMPRESSORA (TS: {self.lamport_clock}) ---")
            print(f"[REQUISIÇÃO RECEBIDA] Cliente {request.client_id} (Req N° {request.request_number}, TS: {request.lamport_timestamp})")
            print(f"  > Mensagem: '{request.message_content}'")
            
            # Simula o tempo de impressão
            print("  ...Imprimindo (espera 2s)...")
            time.sleep(2) # Delay de 2 segundos
            
            print("  ...Impressão Concluída.")
            
            response_timestamp = self.lamport_clock + 1
            return printing_pb2.PrintResponse(
                success=True,
                confirmation_message=f"Mensagem {request.request_number} do Cliente {request.client_id} impressa.",
                lamport_timestamp=response_timestamp
            )

def serve():
    port = '50051'
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    printing_pb2_grpc.add_PrintingServiceServicer_to_server(PrintingServiceImpl(), server)
    server.add_insecure_port('[::]:' + port)
    print(f"--- Servidor de Impressão 'Burro' iniciado na porta {port} ---")
    server.start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("Servidor desligando.")
        server.stop(0)

if __name__ == '__main__':
    serve()