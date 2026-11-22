import socket

from config import HOST, PORT, ENCODING
from protocol import create_message, send_json, receive_json

def identify_client(connection, reader):
    username = input('Informe seu nome: ').strip()
    
    while not username:
        username = input('Informe um nome válido: ').strip()
        
    identification = create_message(
        message_type = 'identification',
        sender = username,
        recipient = 'server',
        content = 'human'
    )
    
    send_json(connection, identification)
    
    response = receive_json(reader)
    
    if response is None:
        raise ConnectionError('Servidor disconectado.')
    
    if response.get('message_type') != 'confirmation':
        raise ValueError('Resposta de identificação inválida.')
    
    if response.get('request_id') != identification['request_id']:
        raise ValueError('ID de identificação inválido')
    
    print(response['content'])
    
    return username

def message_loop(connection, reader, username):
    while True:
        content = input('Informe sua mensagem: ').strip()
        
        if not content:
            continue

        if content.lower() == '@exit':
            disconnection = create_message(
                message_type = 'disconnection',
                sender = username,
                recipient = 'server',
                content = ''
            )
        
            send_json(connection, disconnection)
            break
        
        message = create_message(
            message_type = 'message',
            sender = username,
            recipient = 'server',
            content = content
        )
        
        send_json(connection, message)
        
        response = receive_json(reader)
        
        if response is None:
            print('Servidor desconectado.')
            break
        
        if response.get('request_id') != message['request_id']:
            raise ValueError('Resposta de identificação inválida.')
        
        if response.get('message_type') != 'response':
            raise ValueError('Resposta de mensagem inválida.')
        
        print(f'Resposta: {response['content']}')
        

def start_client():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            
            client.connect((HOST, PORT))
            print(f'Conectado ao {HOST}:{PORT}')
            
            with client.makefile('r', encoding=ENCODING) as reader:
                username = identify_client(client, reader)
                message_loop(client, reader, username)
                
        print('Cliente parou')
        
    except (OSError, ValueError, KeyError, AttributeError) as error:
        print(f'Erro de comunicação: {error}')
        
    
if __name__ == '__main__':
    try:
        start_client()
    except KeyboardInterrupt:
        print('Cliente foi interrompido')