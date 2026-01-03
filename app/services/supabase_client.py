import os
from supabase import create_client, Client

# Configuração do Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
client: Client = create_client(url, key)

def get_user(telefone):
    """Busca o usuário pelo telefone."""
    response = client.table("usuarios").select("*").eq("telefone", telefone).execute()
    if response.data:
        return response.data[0]
    return None

def create_user(telefone):
    """Cria um novo usuário."""
    return client.table("usuarios").insert({
        "telefone": telefone,
        "fase": "SETUP_DIARIA",
        "nome": "Novo Usuário"
    }).execute()

def atualizar_fase(telefone, nova_fase):
    """Muda a fase do usuário (SETUP_DIARIA, SETUP_MENSAL, ATIVO)."""
    return client.table("usuarios").update({"fase": nova_fase}).eq("telefone", telefone).execute()

def salvar_metas(telefone, lista_metas, tipo="diaria"):
    """
    Salva as metas no banco.
    IMPORTANTE: Usa 'telefone_user' e salva o 'tipo'.
    """
    for meta in lista_metas:
        client.table("metas").insert({
            "telefone_user": telefone,  # <--- Corrigido conforme seu diagrama
            "descricao": meta,
            "tipo": tipo,               # <--- Salva se é diaria ou mensal
            "data_criacao": "now()"
        }).execute()

def get_metas(telefone):
    """Busca todas as metas do usuário."""
    return client.table("metas").select("*").eq("telefone_user", telefone).execute().data

def listar_usuarios_ativos():
    """Lista usuários que já terminaram o cadastro."""
    return client.table("usuarios").select("*").eq("fase", "ATIVO").execute().data

def salvar_respostas_diarias(telefone, itens_analisados, metas_db):
    """
    Salva o progresso na tabela respostas_diarias.
    Tenta cruzar o texto da IA com o ID da meta no banco.
    """
    from datetime import datetime
    hoje = datetime.now().strftime("%Y-%m-%d")

    for item in itens_analisados:
        # Tenta achar o ID da meta correspondente
        meta_id = None
        texto_meta = item['meta'].lower()
        
        for m in metas_db:
            # Compara descrições de forma simples
            if m['descricao'].lower() in texto_meta or texto_meta in m['descricao'].lower():
                meta_id = m['id']
                break
        
        if meta_id:
            client.table("respostas_diarias").insert({
                "telefone_user": telefone,
                "meta_id": meta_id,
                "data": hoje,
                "atingida": item['concluido']
            }).execute()