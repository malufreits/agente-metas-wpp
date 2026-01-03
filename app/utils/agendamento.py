import schedule
import time
from datetime import datetime
from app.services.supabase_client import (
    listar_metas,
    registrar_historico_meta,
    cadastrar_metas_anuais,
    cadastrar_metas_mensais,
    gerar_relatorio_mensal,
)
from app.services.whatsapp import enviar_mensagem, receber_resposta

def perguntar_metas():
    usuarios = ["+5531994381418"]  # Substituir pela lógica de listar usuários
    for telefone in usuarios:
        metas_diarias = listar_metas(telefone, "diaria")
        metas_mensais = listar_metas(telefone, "mensal")

        # Perguntar sobre metas diárias
        for meta in metas_diarias:
            enviar_mensagem(telefone, f"Você atingiu a meta diária '{meta['descricao']}'? (Sim/Não)")

        # Perguntar sobre metas mensais
        for meta in metas_mensais:
            enviar_mensagem(telefone, f"Você atingiu a meta mensal '{meta['descricao']}'? (Sim/Não)")

def processar_resposta(telefone: str, mensagem: str):
    """
    Processa a resposta do usuário e registra no banco de dados.
    """
    mensagem = mensagem.strip().lower()

    if mensagem.startswith("metas diarias:"):
        # Processar metas diárias
        metas = mensagem.replace("metas diarias:", "").split(";")
        for meta in metas:
            criar_meta(telefone, meta.strip(), "diaria")
        enviar_mensagem(telefone, "Suas metas diárias foram registradas com sucesso!")
        return

    if mensagem.startswith("metas mensais:"):
        # Processar metas mensais
        metas = mensagem.replace("metas mensais:", "").split(";")
        for meta in metas:
            criar_meta(telefone, meta.strip(), "mensal")
        enviar_mensagem(telefone, "Suas metas mensais foram registradas com sucesso!")
        return

    # Processar respostas sobre metas atingidas
    metas_diarias = listar_metas(telefone, "diaria")
    metas_mensais = listar_metas(telefone, "mensal")

    for meta in metas_diarias + metas_mensais:
        if meta['descricao'].lower() in mensagem:
            atingida = "sim" in mensagem
            registrar_resposta_diaria(telefone, meta['id'], datetime.now().strftime("%Y-%m-%d"), atingida)
            enviar_mensagem(telefone, f"Resposta registrada para a meta: {meta['descricao']}")
            break

def solicitar_metas_anuais():
    usuarios = ["+5531994381418"]  # Substituir pela lógica de listar usuários
    for telefone in usuarios:
        enviar_mensagem(telefone, "Por favor, envie suas metas diárias para o ano.")
        resposta = receber_resposta(telefone)  # Captura a resposta do usuário
        metas = resposta.split(";")  # Supondo que o usuário separa as metas por ponto e vírgula
        cadastrar_metas_anuais(telefone, metas)

def solicitar_metas_mensais():
    usuarios = ["+5531994381418"]  # Substituir pela lógica de listar usuários
    for telefone in usuarios:
        enviar_mensagem(telefone, "Por favor, envie suas metas mensais para este mês.")
        resposta = receber_resposta(telefone)  # Captura a resposta do usuário
        metas = resposta.split(";")  # Supondo que o usuário separa as metas por ponto e vírgula
        cadastrar_metas_mensais(telefone, metas)

def gerar_relatorio_fim_mes():
    usuarios = ["+5531994381418"]  # Substituir pela lógica de listar usuários
    for telefone in usuarios:
        relatorio = gerar_relatorio_mensal(telefone)
        print(f"Relatório para {telefone}: {relatorio}")  # Substituir por envio via WhatsApp

# Agendar tarefas
schedule.every().year.at("00:00").do(solicitar_metas_anuais)
schedule.every().month.at("00:00").do(solicitar_metas_mensais)
schedule.every().month.at("23:59").do(gerar_relatorio_fim_mes)
# Agendar a tarefa para rodar toda noite às 21:00
schedule.every().day.at("21:00").do(perguntar_metas)

if __name__ == "__main__":
    print("Agendamento iniciado. Pressione Ctrl+C para sair.")
    while True:
        schedule.run_pending()
        time.sleep(1)