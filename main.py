import os
import logging
import calendar
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# Importando seus serviços
from app.services import gemini_agent
from app.services import supabase_client
from app.services import whatsapp

# Carrega variáveis de ambiente
load_dotenv()

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. JOBS DO AGENDADOR (SCHEDULER) ---

def job_cobranca_diaria():
    """
    Roda todo dia às 20h. Cobra as metas diárias.
    """
    logger.info("⏰ Executando job de cobrança diária...")
    
    usuarios_ativos = supabase_client.listar_usuarios_ativos()
    
    for user in usuarios_ativos:
        telefone = user['telefone']
        nome = user.get('nome', 'Campeão')
        msg = f"🤖 Boa noite, {nome}! Chegou a hora do check-in. Quais das suas metas diárias você concluiu hoje?"
        
        whatsapp.enviar_mensagem(telefone, msg)

def job_resumo_mensal():
    """
    Roda no último dia do mês às 21h. Gera relatório de performance.
    """
    logger.info("📊 Gerando relatório mensal para todos os usuários...")
    
    # 1. Definir datas
    agora = datetime.now()
    ultimo_dia = calendar.monthrange(agora.year, agora.month)[1]
    data_inicio = f"{agora.year}-{agora.month:02d}-01"
    data_fim = f"{agora.year}-{agora.month:02d}-{ultimo_dia}"

    # 2. Buscar usuários ativos para enviar o relatório
    usuarios_ativos = supabase_client.listar_usuarios_ativos()

    for user in usuarios_ativos:
        telefone = user['telefone']
        
        # Busca as metas e o histórico DESSE usuário específico
        # Nota: Estamos acessando o cliente raw (supabase_client.client)
        metas = supabase_client.client.table("metas").select("*").eq("telefone", telefone).execute()
        historico = supabase_client.client.table("historico").select("*").eq("telefone", telefone)\
            .gte("data", data_inicio).lte("data", data_fim).execute()

        if not historico.data:
            continue # Pula para o próximo usuário se não tiver histórico

        # 3. Montar Prompt
        prompt_relatorio = f"""
        ATUE COMO UM ANALISTA DE PERFORMANCE PESSOAL.
        Estamos no final do mês {agora.month}/{agora.year}. O mês teve {ultimo_dia} dias.
        
        Abaixo estão as METAS do usuário e o HISTÓRICO deste mês.
        
        SUA MISSÃO:
        1. Para cada meta, calcule o total realizado.
        2. Calcule o objetivo total (Ex: meta diária x dias do mês).
        3. Gere um relatório comparativo e motivacional.
        
        DADOS DAS METAS:
        {metas.data}
        
        HISTÓRICO DO MÊS:
        {historico.data}
        
        FORMATO DA RESPOSTA (Whatsapp):
        📅 *RESUMO DE {agora.month}/{agora.year}*
        
        (Liste cada meta com: Realizado vs Meta Ideal e um emoji de status)
        
        📝 *Conclusão:* (Frase motivacional curta)
        """

        try:
            # 4. Gerar texto com IA (Usando o modelo do seu service)
            resposta = gemini_agent.model.generate_content(prompt_relatorio)
            texto_relatorio = resposta.text

            # 5. Enviar
            whatsapp.enviar_mensagem(telefone, texto_relatorio)
            logger.info(f"✅ Relatório mensal enviado para {telefone}")
        except Exception as e:
            logger.error(f"Erro ao gerar relatório para {telefone}: {e}")

# --- 2. CICLO DE VIDA (LIFESPAN) ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Inicia e para o agendador junto com o servidor.
    """
    scheduler = BackgroundScheduler()
    
    # Job 1: Cobrança Diária (20:00)
    scheduler.add_job(job_cobranca_diaria, 'cron', hour=20, minute=0, timezone='America/Sao_Paulo')
    
    # Job 2: Relatório Mensal (Último dia do mês às 21:00)
    scheduler.add_job(
        job_resumo_mensal, 
        CronTrigger(day='last', hour=21, minute=0, timezone='America/Sao_Paulo')
    )
    
    scheduler.start()
    logger.info("🚀 Scheduler iniciado! Cobranças(20h) e Relatório(Fim do mês 21h).")
    
    yield
    
    scheduler.shutdown()
    logger.info("🛑 Scheduler desligado.")

# Inicializa o App
app = FastAPI(lifespan=lifespan)

# --- 3. ROTAS ---

@app.get("/")
def home():
    return {"status": "online", "bot": "Accountability Agent"}

@app.post("/webhook")
async def receive_whatsapp(request: Request):
    try:
        form = await request.form()
        msg_texto = form.get("Body", "").strip()
        telefone = form.get("From")
        
        logger.info(f"📩 Mensagem recebida de {telefone}: {msg_texto}")

        # Identifica usuário
        user = supabase_client.get_user(telefone)

        # FLUXO 1: NOVO USUÁRIO
        if not user:
            supabase_client.create_user(telefone)
            whatsapp.enviar_mensagem(
                telefone, 
                "Olá! Sou seu Agent de Metas Pessoais. 🎯\n\nVamos configurar seu ano? Responda com uma lista das metas DIÁRIAS (ex: ler 10 paginas, ir na academia)."
            )
            return {"status": "novo_usuario"}

        fase = user.get('fase', 'ONBOARDING')

        # FLUXO 2: CADASTRO DE METAS
        if fase == 'ONBOARDING':
            resultado_ia = gemini_agent.extrair_novas_metas(msg_texto)
            lista_metas = resultado_ia.get('metas', [])

            if not lista_metas:
                whatsapp.enviar_mensagem(telefone, "Não entendi. Tente listar simples: 'Correr, Ler, Estudar'.")
                return {"status": "erro_ia"}

            supabase_client.salvar_metas(telefone, lista_metas)
            supabase_client.atualizar_fase(telefone, 'ATIVO')
            
            whatsapp.enviar_mensagem(
                telefone, 
                f"Perfeito! Cadastrei: {', '.join(lista_metas)}.\n\nAmanhã começo a te cobrar! 🫡"
            )
            return {"status": "metas_salvas"}

        # FLUXO 3: REGISTRO DIÁRIO
        if fase == 'ATIVO':
            metas_db = supabase_client.get_metas(telefone)
            lista_nomes_metas = [m['descricao_meta'] for m in metas_db]

            analise = gemini_agent.verificar_progresso(msg_texto, lista_nomes_metas)
            itens_analisados = analise.get('analise', [])
            
            if not itens_analisados:
                 whatsapp.enviar_mensagem(telefone, "Não entendi o que você fez. Pode explicar melhor?")
                 return {"status": "erro_analise"}

            supabase_client.salvar_historico_diario(telefone, itens_analisados, metas_db)

            feedback = analise.get('comentario_motivacional', 'Registrado!')
            resumo_msg = f"{feedback}\n\n"
            for item in itens_analisados:
                icon = "✅" if item['concluido'] else "❌"
                resumo_msg += f"{icon} {item['meta']}\n"

            whatsapp.enviar_mensagem(telefone, resumo_msg)
            return {"status": "ok"}

    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        return {"status": "erro"}