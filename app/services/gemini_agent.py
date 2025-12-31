import os
import google.generativeai as genai
import json
from dotenv import load_dotenv

load_dotenv()

# Configuração da API do Google
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Configuração do Modelo (Gemini 1.5 Flash é rápido e barato/grátis)
generation_config = {
    "temperature": 0.2,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json", # FORÇA O FORMATO JSON
}

# Adicionando função para listar modelos disponíveis

def listar_modelos_disponiveis():
    """
    Lista os modelos disponíveis na API do Google Gemini.
    """
    modelos = genai.list_models()
    print("Modelos disponíveis:")
    for modelo in modelos:
        print(f"- {modelo.name}: {modelo.description}")

# Atualizando o modelo para ser configurável dinamicamente
model_name = os.environ.get("GEMINI_MODEL_NAME", "models/gemini-2.5-flash")

model = genai.GenerativeModel(
    model_name=model_name,
    generation_config=generation_config,
)

def extrair_novas_metas(texto_usuario: str):
    """
    Lê o texto do usuário e extrai uma lista de metas.
    """
    prompt = f"""
    O usuário está listando metas que deseja cumprir diariamente.
    Analise o texto: "{texto_usuario}"
    
    Retorne um JSON com uma lista de strings contendo as metas identificadas.
    Exemplo de formato esperado:
    {{ "metas": ["Ler 10 páginas", "Ir na academia"] }}
    """
    
    response = model.generate_content(prompt)
    return json.loads(response.text)

def verificar_progresso(texto_usuario: str, lista_metas: list):
    """
    Compara o relato do usuário com a lista de metas cadastradas.
    """
    prompt = f"""
    Você é um assistente de responsabilidade (accountability).
    
    Lista de Metas esperadas do usuário: {json.dumps(lista_metas)}
    Relato do dia do usuário: "{texto_usuario}"
    
    Analise o relato e determine para CADA meta se ela foi concluída (true) ou não (false).
    
    Retorne um JSON com o seguinte formato exato:
    {{
        "analise": [
            {{ "meta": "Nome da Meta", "concluido": true }},
            {{ "meta": "Nome da Outra Meta", "concluido": false }}
        ],
        "comentario_motivacional": "Uma frase curta e humana comentando o desempenho."
    }}
    """
    
    response = model.generate_content(prompt)
    return json.loads(response.text)

if __name__ == "__main__":
    # Teste para verificar a chave da API
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Erro: GOOGLE_API_KEY não está configurada.")
    else:
        print(f"GOOGLE_API_KEY configurada: {api_key}")

    listar_modelos_disponiveis()