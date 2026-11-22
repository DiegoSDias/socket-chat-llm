import socket

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


def message_loop(connection, reader, username):
    while True:
        content = input("Informe sua mensagem: ").strip()

        if not content:
            continue

        if content.lower() == "@exit":
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

        response = receive_json(reader)

        if response is None:
            print("Servidor desconectado.")
            break
        
        if not isinstance(response, dict):
            raise ValueError('Resposta do servidor inválida.')

        if response.get("request_id") != message["request_id"]:
            raise ValueError("Resposta de identificação inválida.")

        response_type = response.get("message_type")
        
        if response_type == 'error':
            print(f'Erro no servidor: {response.get(content)}')
            continue
        
        if message_type == 'list_users':
            if response_type != 'users':
                raise ValueError('Resposta de usuários inválida.')

            users = response.get('content')
            
            if not isinstance(users, list):
                raise ValueError('Lista de usuários inválida.')
            
            print('\nUsuários online: ')
            
            for user in users:
                if not isinstance(user, dict):
                    raise ValueError('Dados do usuário inválido.')
                
                display_name = user.get('display_name')
                user_name = user.get('username')
                
                if not isinstance(display_name, str) or not isinstance(user_name, str):
                    raise ValueError('Informações do usuário inválidas.')
                
                print(f' - {display_name} @{user_name}')
                
            print()
        
        else:
            if response_type != "response":
                raise ValueError("Resposta de mensagem inválida.")

            print(f"Resposta: {response['content']}")


def start_client():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:

            client.connect((HOST, PORT))
            print(f"Conectado ao {HOST}:{PORT}")

            with client.makefile("r", encoding=ENCODING) as reader:
                username = identify_client(client, reader)
                message_loop(client, reader, username)

        print("Cliente parou")

    except (OSError, ValueError, KeyError, AttributeError) as error:
        print(f"Erro de comunicação: {error}")


if __name__ == "__main__":
    try:
        start_client()
    except KeyboardInterrupt:
        print("Cliente foi interrompido")
