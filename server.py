import socket
import threading

from config import HOST, PORT, ENCODING
from protocol import create_message, send_json, receive_json

def handle_client(connection, address):
    try:
        with connection:
            thread_name = threading.current_thread().name
            
            print(f'Cliente conectado: {address} - ({thread_name})')
            
            with connection.makefile('r', encoding=ENCODING) as reader:
                identification = receive_json(reader)
                
                if identification is None:
                    print('Cliente desconectou antes da identificação.')
                    return
                
                if identification.get('message_type') != 'identification':
                    print('Identificação inválida.')
                    return
                
                username = identification.get('sender', '')
                
                if not isinstance(username, str) or not username.strip():
                    print('Nome de usuário inválido')
                    return
                
                username = username.strip()
                
                print(f'Usuário identificado: {username}')
                
                confirmation = create_message(
                    message_type = 'confirmation',
                    sender = 'server',
                    recipient = username,
                    content = f'Bem vindo, {username}!',
                    request_id = identification['request_id'],
                )
                
                send_json(connection, confirmation)
                
                while True:
                    message = receive_json(reader)
                    
                    if not message:
                        print(f'{username} disconectou')
                        break
                    
                    if message.get('message_type') == 'disconnection':
                        print(f'{username} disconectou')
                        break
                    
                    if message.get('message_type') != 'message':
                        print('Mensagem inválida')
                        continue
                    
                    content = message.get('content', '')
                    
                    if not isinstance(content, str):
                        print('Conteúdo da mensagem inválido')
                        continue
                    
                    print(f'{username}: {content}')
                    
                    response = create_message(
                        message_type = 'response',
                        sender = 'server',
                        recipient = username,
                        content = content.upper(),
                        request_id = message['request_id']
                    )
                    
                    send_json(connection, response)
                    
        
    except (OSError, ValueError, KeyError, AttributeError) as error:
        print(f'Erro de comunicação com {address}: {error}')
        
    finally:
        print(f'Conexão com {address} finalizada!')
        
def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        
        server.bind((HOST, PORT))
        server.listen()
        
        print(f'Servidor iniciou em {HOST}:{PORT}')
        
        while True:
            print('Aguardando conexão...')
            
            connection, address = server.accept()
            
            client_thread = threading.Thread(
                target = handle_client,
                args = (connection, address),
                name = f'client-{address[1]}',
                daemon = True
            )

            client_thread.start()
            
if __name__ == '__main__':
    try:
        start_server()
    except KeyboardInterrupt:
        print('\nServidor foi interrompido.')