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
    return client.table("usuarios").update({"fase": nova_fase}).eq("telefone", telefone).execute()

def salvar_metas(telefone, lista_metas, tipo="diaria"):
    """Salva uma lista de metas."""
    for meta in lista_metas:
        client.table("metas").insert({
            "telefone_user": telefone,
            "descricao": meta,
            "tipo": tipo,
            "data_criacao": "now()"
        }).execute()

# --- NOVAS FUNÇÕES (Para substituir o agendamento.py) ---

def adicionar_meta_individual(telefone, descricao, tipo="diaria"):
    """Adiciona apenas uma meta extra."""
    return client.table("metas").insert({
        "telefone_user": telefone,
        "descricao": descricao,
        "tipo": tipo,
        "data_criacao": "now()"
    }).execute()

def excluir_meta_por_texto(telefone, texto_meta):
    """
    Tenta excluir uma meta buscando por parte do texto.
    Ex: Se o usuário diz 'Excluir correr', apaga a meta 'Correr 5km'.
    """
    # 1. Busca todas as metas do usuário
    metas = get_metas(telefone)
    meta_para_apagar = None
    
    # 2. Procura qual meta contém o texto informado
    for m in metas:
        if texto_meta.lower() in m['descricao'].lower():
            meta_para_apagar = m
            break
            
    # 3. Se achou, deleta pelo ID
    if meta_para_apagar:
        client.table("metas").delete().eq("id", meta_para_apagar['id']).execute()
        return meta_para_apagar['descricao'] # Retorna o nome do que apagou
    return None

# --------------------------------------------------------

def get_metas(telefone):
    return client.table("metas").select("*").eq("telefone_user", telefone).execute().data

def listar_usuarios_ativos():
    return client.table("usuarios").select("*").eq("fase", "ATIVO").execute().data

def salvar_respostas_diarias(telefone, itens_analisados, metas_db):
    from datetime import datetime
    hoje = datetime.now().strftime("%Y-%m-%d")

    for item in itens_analisados:
        meta_id = None
        texto_meta = item['meta'].lower()
        
        for m in metas_db:
            if m['descricao'].lower() in texto_meta or texto_meta in m['descricao'].lower():
                meta_id = m['id']
                break
        
        if meta_id:
            # Verifica se já não salvou hoje para não duplicar
            ja_existe = client.table("respostas_diarias").select("*")\
                .eq("meta_id", meta_id).eq("data", hoje).execute()
            
            if not ja_existe.data:
                client.table("respostas_diarias").insert({
                    "telefone_user": telefone,
                    "meta_id": meta_id,
                    "data": hoje,
                    "atingida": item['concluido']
                }).execute()