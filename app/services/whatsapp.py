import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

# Configurações do Twilio
account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
remetente = os.environ.get("TWILIO_PHONE") # Número do Sandbox ou Oficial

client = Client(account_sid, auth_token)

def enviar_mensagem(numero_destino: str, mensagem: str):
    """
    Envia uma mensagem de WhatsApp via Twilio.
    """
    try:
        message = client.messages.create(
            from_=remetente,
            to=numero_destino,
            body=mensagem
        )
        print(f"Mensagem enviada para {numero_destino}. SID: {message.sid}")
        return True
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")
        return False