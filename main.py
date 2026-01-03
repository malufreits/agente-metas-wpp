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
    """ Roda todo dia às 20h. Cobra as metas diárias. """
    logger.info("⏰ Executando job de cobrança diária...")
    usuarios_ativos = supabase_client.listar_usuarios_ativos()
    
    for user in usuarios_ativos:
        telefone = user['telefone']
        nome = user.get('nome', 'Campeão')
        msg = f"🤖 Boa noite, {nome}! Chegou a hora do check-in. Quais das suas metas diárias você concluiu hoje?"
        whatsapp.enviar_mensagem(telefone, msg)

def job_resumo_mensal():
    """ Roda no último dia do mês às 21h. Gera relatório. """
    logger.info("📊 Gerando relatório mensal...")
    agora = datetime.now()
    ultimo_dia = calendar.monthrange(agora.year, agora.month)[1]
    data_inicio = f"{agora.year}-{agora.month:02d}-01"
    data_fim = f"{agora.year}-{agora.month:02d}-{ultimo_dia}"

    usuarios_ativos = supabase_client.listar_usuarios_ativos()

    for user in usuarios_ativos:
        telefone = user['telefone']
        
        # Busca metas e histórico
        metas = supabase_client.client.table("metas").select("*").eq("telefone", telefone).execute()
        historico = supabase_client.client.table("historico").select("*").eq("telefone", telefone)\
            .gte("data", data_inicio).lte("data", data_fim).execute()

        if not historico.data:
            continue

        prompt_relatorio = f"""
        ATUE COMO UM ANALISTA DE PERFORMANCE. Mês: {agora.month}/{agora.year}.
        DADOS DAS METAS: {metas.data}
        HISTÓRICO DO MÊS: {historico.data}
        Gere um relatório curto e motivacional para o WhatsApp.
        """

        try:
            resposta = gemini_agent.model.generate_content(prompt_relatorio)
            whatsapp.enviar_mensagem(telefone, resposta.text)
            logger.info(f"✅ Relatório enviado para {telefone}")
        except Exception as e:
            logger.error(f"Erro relatório {telefone}: {e}")

# --- 2. CICLO DE VIDA (LIFESPAN) ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    scheduler.add_job(job_cobranca_diaria, 'cron', hour=20, minute=0, timezone='America/Sao_Paulo')
    scheduler.add_job(job_resumo_mensal, CronTrigger(day='last', hour=21, minute=0, timezone='America/Sao_Paulo'))
    scheduler.start()
    logger.info("🚀 Scheduler iniciado!")
    yield
    scheduler.shutdown()
    logger.info("🛑 Scheduler desligado.")

app = FastAPI(lifespan=lifespan)

# --- 3. ROTAS E LÓGICA DO CHAT ---

@app.get("/")
def home():
    return {"status": "online", "bot": "Accountability Agent"}

@app.post("/webhook")
async def receive_whatsapp(request: Request):
    try:
        form = await request.form()
        msg_texto = form.get("Body", "").strip()
        telefone = form.get("From")
        
        logger.info(f"📩 De: {telefone} | Msg: {msg_texto}")

        # 1. Identifica ou Cria Usuário
        user = supabase_client.get_user(telefone)
        if not user:
            supabase_client.create_user(telefone)
            # Define fase inicial explicitamente
            supabase_client.atualizar_fase(telefone, 'SETUP_DIARIA')
            whatsapp.enviar_mensagem(
                telefone, 
                "Olá! Sou seu Agente de Metas. 🎯\n\nVamos começar? Primeiro, me mande uma lista das suas **METAS DIÁRIAS** (ex: Ler, Treinar, Beber agua)."
            )
            return {"status": "novo_usuario"}

        # 2. BOTÃO DE PÂNICO / RESET (Resolve o problema do loop)
        # Se o usuário mandar qualquer uma dessas palavras, reinicia o cadastro.
        palavras_reset = ["oi", "ola", "olá", "reset", "inicio", "começar", "configurar"]
        
        if msg_texto.lower() in palavras_reset:
            supabase_client.atualizar_fase(telefone, 'SETUP_DIARIA')
            whatsapp.enviar_mensagem(
                telefone, 
                "🔄 Vamos reconfigurar suas metas!\n\nPasso 1: Envie suas **METAS DIÁRIAS** (ex: Ler 10 pag, Academia)."
            )
            return {"status": "reset_flow"}

        # Recupera a fase atual
        fase = user.get('fase', 'SETUP_DIARIA')

        # --- FASE 1: CADASTRAR DIÁRIAS ---
        if fase == 'SETUP_DIARIA':
            resultado_ia = gemini_agent.extrair_novas_metas(msg_texto)
            lista_metas = resultado_ia.get('metas', [])

            if not lista_metas:
                whatsapp.enviar_mensagem(telefone, "Não entendi suas metas diárias. Tente listar simples: 'Correr, Ler, Estudar'.")
                return {"status": "erro_ia_diaria"}

            # Salva como DIARIA e avança fase
            # IMPORTANTE: Garanta que seu supabase_client.salvar_metas aceita o parametro 'tipo'
            supabase_client.salvar_metas(telefone, lista_metas, tipo="diaria")
            supabase_client.atualizar_fase(telefone, 'SETUP_MENSAL')
            
            whatsapp.enviar_mensagem(
                telefone, 
                f"✅ {len(lista_metas)} metas diárias salvas!\n\nAgora, Passo 2: Me mande suas **METAS MENSAIS** (ex: Ler 1 livro, Perder 2kg)."
            )
            return {"status": "diarias_ok"}

        # --- FASE 2: CADASTRAR MENSAIS ---
        if fase == 'SETUP_MENSAL':
            resultado_ia = gemini_agent.extrair_novas_metas(msg_texto)
            lista_metas = resultado_ia.get('metas', [])

            if not lista_metas:
                whatsapp.enviar_mensagem(telefone, "Não entendi. Mande suas metas mensais ou digite 'Pular'.")
                return {"status": "erro_ia_mensal"}

            # Salva como MENSAL e finaliza cadastro
            supabase_client.salvar_metas(telefone, lista_metas, tipo="mensal")
            supabase_client.atualizar_fase(telefone, 'ATIVO')
            
            whatsapp.enviar_mensagem(
                telefone, 
                "🎉 Tudo configurado! \n\nVocê está na fase **ATIVO**. Todos os dias às 20h passarei aqui para cobrar suas metas. Pode deixar comigo! 🫡"
            )
            return {"status": "mensais_ok"}

        # --- FASE 3: VIDA NORMAL (ATIVO) ---
        if fase == 'ATIVO':
            metas_db = supabase_client.get_metas(telefone)
            lista_nomes_metas = [m['descricao'] for m in metas_db]

            if not lista_nomes_metas:
                 whatsapp.enviar_mensagem(telefone, "Você não tem metas ativas. Digite 'Reset' para configurar.")
                 return {"status": "sem_metas"}

            analise = gemini_agent.verificar_progresso(msg_texto, lista_nomes_metas)
            itens_analisados = analise.get('analise', [])
            
            if not itens_analisados:
                 whatsapp.enviar_mensagem(telefone, "Não entendi o que você realizou. Tente ser mais específico.")
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