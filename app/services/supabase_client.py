import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(url, key)

def get_user(telefone: str):
    response = supabase.table("usuarios").select("*").eq("telefone", telefone).execute()
    if response.data:
        return response.data[0]
    return None

def create_user(telefone: str):
    data = {"telefone": telefone, "fase": "ONBOARDING"}
    supabase.table("usuarios").insert(data).execute()

def listar_usuarios_ativos():
    # Retorna todos usuários que já saíram do onboarding
    response = supabase.table("usuarios").select("telefone, nome").eq("fase", "ATIVO").execute()
    return response.data

def atualizar_fase(telefone: str, nova_fase: str):
    supabase.table("usuarios").update({"fase": nova_fase}).eq("telefone", telefone).execute()

def salvar_metas(telefone: str, lista_metas: list):
    # Primeiro limpamos metas antigas se houver, para evitar duplicidade na reconfiguração
    # (Opcional, depende da lógica que você quer)
    
    dados = []
    for meta in lista_metas:
        dados.append({"telefone_user": telefone, "descricao_meta": meta})
    
    if dados:
        supabase.table("metas_config").insert(dados).execute()

def get_metas(telefone: str):
    response = supabase.table("metas_config").select("id, descricao_meta").eq("telefone_user", telefone).execute()
    return response.data

def salvar_historico_diario(telefone: str, analise_ia: list, metas_db: list):
    """
    analise_ia: Lista vinda do Gemini [{'meta': 'Correr', 'concluido': True}]
    metas_db: Lista vinda do Banco [{'id': 1, 'descricao_meta': 'Correr'}]
    """
    registros = []
    
    # Cruzamos o nome da meta vinda da IA com o ID da meta no banco
    for item in analise_ia:
        nome_meta_ia = item['meta'] # A IA tenta acertar o nome
        concluido = item['concluido']
        
        # Tentativa simples de match (pode ser melhorada com fuzzy match se precisar)
        for m_db in metas_db:
            # Verifica se o nome da meta está contido na string do banco ou vice-versa
            if m_db['descricao_meta'].lower() in nome_meta_ia.lower() or nome_meta_ia.lower() in m_db['descricao_meta'].lower():
                registros.append({
                    "telefone_user": telefone,
                    "meta_id": m_db['id'],
                    "concluido": concluido
                })
                break
    
    if registros:
        supabase.table("registros_diarios").insert(registros).execute()