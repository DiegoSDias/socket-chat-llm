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
            'connection': connection,
            'send_lock': threading.Lock(),
            'ready': False
        }
        
    return True


def mark_client_ready(username, connection):
    with clients_lock:
        client = connected_clients.get(username.casefold())
        
        if client is not None and client['connection'] is connection:
            client['ready'] = True


def unregister_client(username, connection): 
    with clients_lock:
        username_key = username.casefold()
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
            if client['ready']
        ]
        
    return sorted(users, key=lambda user: user['username'].casefold())


def send_to_client(username, message):
    with clients_lock:
        client = connected_clients.get(username.casefold())
        
        if client is None or not client['ready']:
            return False
        
        connection = client['connection']
        send_lock = client['send_lock']
        
    try:
        with send_lock:
            send_json(connection, message)
        
        return True
    
    except OSError as error:
        print(f'Não foi possivel enviar mensagem para @{username}: {error}')
        return False


def send_error(connection, username, description, request_id=None):
    error_message = create_message(
        message_type = 'error',
        sender = 'server',
        recipient = username,
        content = description,
        request_id = request_id
    )
    
    with clients_lock:
        client = (
            connected_clients.get(username.casefold())
            if isinstance(username, str)
            else None
        )
    
    is_ready = (
        client is not None
        and client['connection'] is connection
        and client['ready']
    )
    
    if is_ready:
        send_to_client(username, error_message)
    else:
        send_json(connection, error_message)


def handle_chat_message(connection, username, display_name, message):
    request_id = message['request_id']
    recipient = message['recipient']
    content = message['content']
    
    if not isinstance(recipient, str) or not recipient:
        send_error(connection, username, 'Destinatário inválido.', request_id)
        return
    
    if not isinstance(content, str) or not content.strip():
        send_error(connection, username, 'Mensagem não pode ser vazia.', request_id)
        return
    
    if recipient == 'all':
        with clients_lock:
            recipient = [
                client['username']
                for key, client in connected_clients.items()
                if key != username.casefold() and client['ready']
            ]
        
        delivered = 0
        
        for target in recipient:
            forwarded = create_message(
                message_type = 'message',
                sender = username,
                recipient = 'all',
                content = {
                    'display_name': display_name,
                    'text': content,
                    'scope': 'public'
                },
                request_id = request_id
            )
            
            if send_to_client(target, forwarded):
                delivered += 1
        
        status = f'Mensagens públicas enviadas para {delivered} usuários.'
        
    else:
        forwarded = create_message(
            message_type = 'message',
            sender = username,
            recipient = recipient,
            content = {
                'display_name': display_name,
                'text': content,
                'scope': 'private'
            },
            request_id = request_id
        )
        
        if not send_to_client(recipient, forwarded):
            send_error(
                connection,
                username,
                f'Usuário @{recipient} não está disponível',
                request_id
            )
            return
        
        status = f'Mensagem privada enviada para @{recipient}.'
        
    response = create_message(
        message_type = 'response',
        sender = 'server',
        recipient = username,
        content = status,
        request_id = request_id
    )
        
    send_to_client(username, response)
 

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
                
                confirmation = create_message(
                    message_type = 'confirmation',
                    sender = 'server',
                    recipient = username,
                    content = f'Bem vindo, {display_name} (@{username})!',
                    request_id = request_id,
                )
                
                send_json(connection, confirmation)
                mark_client_ready(username, connection)
                
                print(f'Usuário conectado: {display_name} (@{username})')
                
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
                        send_error(
                            connection, 
                            username, 
                            'Mensagem inválida', 
                            request_id
                        )
                        continue
                    
                    handle_chat_message(
                        connection,
                        username,
                        display_name,
                        message
                    )
                      
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