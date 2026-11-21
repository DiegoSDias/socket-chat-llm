import json
import uuid

from config import ENCODING

def create_message(message_type, sender, recipient, content, request_id=None):
    return {
        'request_id': str(uuid.uuid4() if request_id is None else request_id),
        'message_type': message_type,
        'sender': sender,
        'recipient': recipient,
        'content': content
    }
    
def send_json(connection, data):
    message = json.dumps(data, ensure_ascii=False) + '\n'
    connection.sendall(message.encode(ENCODING))

def receive_json(reader):
    line = reader.readline()
    
    if not line:
        return None
    
    if line.endswith('\n'):
        raise ValueError('Mensagem Incompleta.')
    
    data = json.loads(line)
    
    return data