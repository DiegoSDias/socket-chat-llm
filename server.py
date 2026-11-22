import re
import socket
import threading

from config import HOST, PORT, ENCODING
from protocol import create_message, send_json, receive_json


connected_clients = {}
clients_lock = threading.Lock()

RESERVED_USERNAMES = {'server', 'bot'}
USERNAME_PATTERN = r'[A-Za-z][A-Za-z0-9_]{2,19}'


def register_client(username, display_name, connection):
    username_key = username.casefold()
    
    with clients_lock:
        if username_key in connected_clients:
            return False
        
        connected_clients[username_key] = {
            'username': username,
            'display_name': display_name,
            'connection': connection
        }
        
    return True


def unregister_client(username, connection):
    username_key = username.casefold()
    
    with clients_lock:
        client_data = connected_clients.get(username_key)
        
        if client_data is not None and client_data['connection'] is connection:
            del connected_clients[username_key]
            return True
        
    return False


def list_connected_clients():
    with clients_lock:
        users = [
            {
                'username': client['username'],
                'display_name': client['display_name']
            }
            for client in connected_clients.values()
        ]
        
    return sorted(users, key=lambda user: user['username'].casefold())


def send_error(connection, recipient, description, request_id=None):
    error_message = create_message(
        message_type = 'error',
        sender = 'server',
        recipient = recipient,
        content = description,
        request_id = request_id
    )
    
    send_json(connection, error_message)
    

def handle_client(connection, address):
    username = None
    
    try:
        with connection:
            thread_name = threading.current_thread().name
            
            print(f'Cliente conectado: {address} - ({thread_name})')
            
            with connection.makefile('r', encoding=ENCODING) as reader:
                identification = receive_json(reader)
                
                if identification is None:
                    print('Cliente desconectou antes da identificação.')
                    return
                
                if not isinstance(identification, dict):
                    send_error(connection, 'unknown', 'Formato de identificação inválido.')
                    print('Formato de identificação inválido')
                    return
                
                request_id = identification.get('request_id')
                if not isinstance(request_id, str) or not request_id:
                    print('ID da identificação inválido.')
                    return
                
                if identification.get('message_type') != 'identification':
                    send_error(connection, 'unknown', 'Identificação é obrigatória.', request_id)
                    print('Identificação é obrigatória.')
                    return
                
                username = identification.get('sender', '')
                content = identification.get('content', '')
                
                if not isinstance(username, str):
                    send_error(connection, username, 'Nome de usuário inválido', request_id)
                    print('Nome de usuário inválido')
                    return
                
                username = username.strip()
                
                if not re.fullmatch(USERNAME_PATTERN, username):
                    send_error(connection, username, 'Formato do nome de usuário inválido.')
                    print('Formato do nome de usuário inválido')
                    return
                
                if username.casefold() in RESERVED_USERNAMES:
                    send_error(connection, username, 'Nome de usuário reservado.', request_id)
                    print('Nome de usuário reservado')
                    return
                
                if not isinstance(content, dict):
                    send_error(connection, username, 'Conteúdo de identificação inválido.', request_id)
                    print('Conteúdo de identificação inválido')
                    return
                
                display_name = content.get('display_name')
                role = content.get('role')
                
                if not isinstance(display_name, str):
                    send_error(connection, username, 'Nome inválido.', request_id)
                    print('Nome inválido')
                    return
                
                display_name = display_name.strip()
                
                if not display_name or len(display_name) > 60:
                    send_error(connection, username, 'Tamanho do nome inválido.', request_id)
                    print('Tamanho do nome inválido')
                    return
                
                if role != 'human':
                    send_error(connection, username, 'Função do participante inválida.', request_id)
                    print('Função do participante inválida')
                    return
                
                if not register_client(username, display_name, connection):
                    send_error(connection, username, 'Nome de usuário está em uso.', request_id)
                    print('Nome de usuário está em uso')
                    return
                
                print(f'Usuário conectado: {display_name} @{username}')
                
                confirmation = create_message(
                    message_type = 'confirmation',
                    sender = 'server',
                    recipient = username,
                    content = f'Bem vindo, {display_name} @{username}!',
                    request_id = request_id,
                )
                
                send_json(connection, confirmation)
                
                while True:
                    message = receive_json(reader)
                    
                    if message is None:
                        print(f'{username} disconectou')
                        break
                    
                    if not isinstance(message, dict):
                        send_error(connection, username, 'Formato da mensagem inválida.')
                        continue
                    
                    request_id = message.get('request_id')
                    
                    if not isinstance(request_id, str) or not request_id:
                        send_error(connection, username, 'ID da requisição inválida.')
                        continue
                    
                    if message.get('sender') != username:
                        send_error(connection, username, 'Invalid sender.', request_id)
                        continue
                    
                    message_type = message.get('message_type')
                    
                    if message_type == 'disconnection':
                        print(f'{username} disconectou')
                        break
                    
                    if message_type == 'list_users':
                        response = create_message(
                            message_type = 'users',
                            sender = 'server',
                            recipient = username,
                            content = list_connected_clients(),
                            request_id = request_id
                        )
                        
                        send_json(connection, response)
                        continue
                    
                    if message_type != 'message':
                        send_error(connection, username, 'Mensagem inválida', request_id)
                        continue
                    
                    content = message.get('content', '')
                    
                    if not isinstance(content, str):
                        send_error(connection, username, 'Conteúdo da mensagem inválido', request_id)
                        continue
                    
                    print(f'{display_name} @{username}: {content}')
                    
                    response = create_message(
                        message_type = 'response',
                        sender = 'server',
                        recipient = username,
                        content = content.upper(),
                        request_id = request_id
                    )
                    
                    send_json(connection, response)
                      
    except (OSError, ValueError, KeyError, AttributeError) as error:
        print(f'Erro de comunicação com {address}: {error}')
        
    finally:
        if username is not None:
            if unregister_client(username, connection):
                print(f'Cliente removido: @{username}')
        
def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
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