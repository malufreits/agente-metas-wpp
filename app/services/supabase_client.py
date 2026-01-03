import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(url, key)

def normalizar_telefone(telefone: str) -> str:
    """
    Remove caracteres extras e normaliza o formato do telefone.
    Exemplo: +5531994381418 -> 5531994381418
    """
    return telefone.replace("+", "").strip()

def get_user(telefone: str):
    telefone = normalizar_telefone(telefone)
    response = supabase.table("usuarios").select("*").eq("telefone", telefone).execute()
    if response.data:
        return response.data[0]
    return None

def create_user(telefone: str, nome: str = "Usuário"):
    """
    Cria um novo usuário com um valor padrão para o nome caso não seja fornecido.
    """
    telefone = normalizar_telefone(telefone)
    data = {"telefone": telefone, "nome": nome, "fase": "ONBOARDING"}
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
        supabase.table("metas").insert(dados).execute()

def get_metas(telefone: str):
    response = supabase.table("metas").select("id, descricao, tipo").eq("telefone_user", telefone).execute()
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

def salvar_meta(telefone: str, descricao: str, tipo: str):
    telefone = normalizar_telefone(telefone)
    """
    Salva uma meta no banco de dados.
    tipo: "diaria" ou "mensal"
    """
    data = {
        "telefone_user": telefone,
        "descricao": descricao,
        "tipo": tipo
    }
    supabase.table("metas").insert(data).execute()

def listar_metas(telefone: str, tipo: str):
    """
    Lista metas do tipo especificado (diária ou mensal) para um usuário.
    """
    response = supabase.table("metas").select("id, descricao, tipo").eq("telefone_user", telefone).eq("tipo", tipo).execute()
    return response.data

def registrar_historico_meta(meta_id: int, data: str, atingida: bool):
    """
    Registra no histórico se uma meta foi atingida em uma data específica.
    """
    registro = {
        "meta_id": meta_id,
        "data": data,
        "atingida": atingida
    }
    supabase.table("historico_metas").insert(registro).execute()

def listar_historico_meta(meta_id: int):
    """
    Lista o histórico de uma meta específica.
    """
    response = supabase.table("historico_metas").select("data, atingida").eq("meta_id", meta_id).execute()
    return response.data

def cadastrar_metas_anuais(telefone: str, metas: list):
    """
    Cadastra metas diárias para o ano inteiro.
    """
    for meta in metas:
        salvar_meta(telefone, meta, "diaria")

def cadastrar_metas_mensais(telefone: str, metas: list):
    """
    Cadastra metas mensais no início de cada mês.
    """
    for meta in metas:
        salvar_meta(telefone, meta, "mensal")

def gerar_relatorio_mensal(telefone: str):
    """
    Gera um relatório comparativo entre as metas mensais e o que foi atingido.
    """
    metas_mensais = listar_metas(telefone, "mensal")
    relatorio = []

    for meta in metas_mensais:
        historico = listar_historico_meta(meta['id'])
        atingidas = [h for h in historico if h['atingida']]
        nao_atingidas = [h for h in historico if not h['atingida']]

        relatorio.append({
            "meta": meta['descricao'],
            "atingidas": len(atingidas),
            "nao_atingidas": len(nao_atingidas)
        })

    return relatorio

def criar_meta(telefone: str, descricao: str, tipo: str):
    """
    Cria uma nova meta (diária ou mensal) para o usuário.
    """
    data = {
        "telefone_user": telefone,
        "descricao": descricao,
        "tipo": tipo
    }
    supabase.table("metas").insert(data).execute()

def listar_metas_por_tipo(telefone: str, tipo: str):
    """
    Lista metas do tipo especificado (diária ou mensal) para um usuário.
    """
    response = supabase.table("metas").select("id, descricao, tipo").eq("telefone_user", telefone).eq("tipo", tipo).execute()
    return response.data

def registrar_resposta_diaria(telefone: str, meta_id: int, data: str, atingida: bool):
    telefone = normalizar_telefone(telefone)
    """
    Registra a resposta diária do usuário para uma meta específica.
    """
    registro = {
        "telefone_user": telefone,
        "meta_id": meta_id,
        "data": data,
        "atingida": atingida
    }
    supabase.table("respostas_diarias").insert(registro).execute()

def listar_respostas_diarias(telefone: str, data: str):
    """
    Lista todas as respostas diárias de um usuário para uma data específica.
    """
    response = supabase.table("respostas_diarias").select("meta_id, atingida").eq("telefone_user", telefone).eq("data", data).execute()
    return response.data