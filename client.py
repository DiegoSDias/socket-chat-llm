import socket
import threading

from config import HOST, PORT, ENCODING
from protocol import create_message, send_json, receive_json


def identify_client(connection, reader):
    display_name = input("Informe seu nome de exibição: ").strip()

    while not display_name:
        display_name = input("Informe um nome de exibição válido: ").strip()
    
    username = input("Informe seu node de usuário: ").strip()

    while not username:
        username = input("Informe um nome de usuário válido: ").strip()


    identification = create_message(
        message_type="identification",
        sender=username,
        recipient="server",
        content={
            'display_name': display_name,
            'role': 'human'
        },
    )

    send_json(connection, identification)

    response = receive_json(reader)

    if response is None:
        raise ConnectionError("Servidor disconectado.")

    if not isinstance(response, dict):
        raise ValueError('Resposta do servidor inválida.')
    
    if response.get("request_id") != identification["request_id"]:
        raise ValueError("ID de identificação inválido")
    
    message_type = response.get("message_type")
    
    if message_type == "error":
        raise ValueError(response.get('content', "Identificação rejeitada."))
    
    if message_type != "confirmation":
        raise ValueError("Resposta de identificação inválida.")

    print(response["content"])

    return username


def receive_messages(reader, stop_event):
    try:
        while not stop_event.is_set():
            message = receive_json(reader)
            
            if message is None:
                if not stop_event.is_set():
                    print('Servidor disconectou.')
                break
            
            if not isinstance(message, dict):
                print('Mensagem recebida inválida.')
                continue
            
            message_type = message.get('message_type')
            content = message.get('content', '')
            
            if message_type == 'response':
                print(f'\nResposta: {content}')
                
            elif message_type == 'users':
                
                if not isinstance(content, list):
                    raise ValueError('Lista de usuários inválida.')
                        
                print('\nUsuários online: ')
                        
                for user in content:
                    if not isinstance(user, dict):
                        raise ValueError('Dados do usuário inválido.')
                            
                    display_name = user.get('display_name')
                    user_name = user.get('username')
                            
                    if not isinstance(display_name, str) or not isinstance(user_name, str):
                        raise ValueError('Informações do usuário inválidas.')
                                
                    print(f' - {display_name} @{user_name}')
                    
            elif message_type == 'error':
                print(f'\nErro no servidor: {content}')
                
            elif message_type == 'message':
                sender = message.get('sender', 'unknown')
                print(f'\n{sender}: {content}')
                
            else:
                print(f'Tipo de mensagem não suportada: {message_type}')
    
    except(OSError, ValueError, UnicodeError) as error:
        if not stop_event.is_set():
            print(f'Erro no recebimento: {error}')
            
    finally:
        stop_event.set()


def send_message(connection, username, stop_event):
    while not stop_event.is_set():
        try:
            content = input('Informe sua mensagem: ').strip()
        except EOFError:
            break
        
        if stop_event.is_set():
            break
        
        if not content:
            break
        
        if content.lower() == '@exit':
            disconnection = create_message(
                message_type="disconnection",
                sender=username,
                recipient="server",
                content="",
            )
            
            send_json(connection, disconnection)
            break
        
        message_type = 'list_users' if content.lower() == '@users' else 'message'
        
        message = create_message(
            message_type=message_type, 
            sender=username, 
            recipient="server", 
            content='' if message_type == 'list_users' else content
        )
        
        send_json(connection, message)
    

def start_client():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:

            client.connect((HOST, PORT))
            print(f"Conectado ao {HOST}:{PORT}")

            with client.makefile("r", encoding=ENCODING) as reader:
                username = identify_client(client, reader)
                
                stop_event = threading.Event()
                
                receiver_thread = threading.Thread(
                    target = receive_messages,
                    args = (reader, stop_event),
                    name = 'message_receiver',
                    daemon = True
                )
                
                receiver_thread.start()
                
                try:
                    send_message(client, username, stop_event)
                finally:
                    stop_event.set()
                    
                    try:
                        client.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    
                    receiver_thread.join(timeout=2)

        print("Cliente parou")

    except (OSError, ValueError, KeyError, AttributeError) as error:
        print(f"Erro de comunicação: {error}")


if __name__ == "__main__":
    try:
        start_client()
    except KeyboardInterrupt:
        print("Cliente foi interrompido")
