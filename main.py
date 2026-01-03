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
            supabase_client.atualizar_fase(telefone, 'SETUP_DIARIA')
            whatsapp.enviar_mensagem(
                telefone, 
                "Olá! Sou seu Agente de Metas. 🎯\n\nVamos começar? Primeiro, me mande uma lista das suas **METAS DIÁRIAS** (ex: Ler, Treinar, Beber agua)."
            )
            return {"status": "novo_usuario"}

        # Recupera a fase atual
        fase = user.get('fase', 'SETUP_DIARIA')

        # --- 2. COMANDOS ESPECIAIS ---
        msg_lower = msg_texto.lower()

        # A) RESET REAL (Só se você pedir explicitamente)
        comandos_reset = ["reset", "reiniciar", "configurar", "mudar metas", "começar do zero"]
        if any(cmd in msg_lower for cmd in comandos_reset):
            supabase_client.atualizar_fase(telefone, 'SETUP_DIARIA')
            whatsapp.enviar_mensagem(
                telefone, 
                "🔄 Entendido! Vamos reconfigurar suas metas do zero.\n\nPasso 1: Envie suas novas **METAS DIÁRIAS**."
            )
            return {"status": "reset_flow"}

        # B) CUMPRIMENTOS (Educação)
        cumprimentos = ["oi", "ola", "olá", "bom dia", "boa tarde", "boa noite"]
        if msg_lower in cumprimentos:
            if fase == 'ATIVO':
                whatsapp.enviar_mensagem(telefone, "Opa! 👋 Estou por aqui. Se já fez alguma meta hoje, é só me contar!")
                return {"status": "cumprimento_ativo"}
            else:
                # Se ainda não terminou de configurar, o "Oi" serve para lembrar
                whatsapp.enviar_mensagem(telefone, "Olá! Ainda estamos configurando. Veja a mensagem acima e me responda. 👆")
                return {"status": "cumprimento_setup"}

        # --- 3. FLUXOS DE FASE ---

        # FASE 1: CADASTRAR DIÁRIAS
        if fase == 'SETUP_DIARIA':
            resultado_ia = gemini_agent.extrair_novas_metas(msg_texto)
            lista_metas = resultado_ia.get('metas', [])

            if not lista_metas:
                whatsapp.enviar_mensagem(telefone, "Não entendi suas metas diárias. Tente listar simples: 'Correr, Ler, Estudar'.")
                return {"status": "erro_ia_diaria"}

            # Importante: Sua função salvar_metas deve aceitar o parametro tipo="diaria"
            supabase_client.salvar_metas(telefone, lista_metas, tipo="diaria")
            supabase_client.atualizar_fase(telefone, 'SETUP_MENSAL')
            
            whatsapp.enviar_mensagem(
                telefone, 
                f"✅ {len(lista_metas)} metas diárias salvas!\n\nAgora, Passo 2: Me mande suas **METAS MENSAIS** (ex: Ler 1 livro, Perder 2kg)."
            )
            return {"status": "diarias_ok"}

        # FASE 2: CADASTRAR MENSAIS
        if fase == 'SETUP_MENSAL':
            if "pular" in msg_lower:
                 lista_metas = [] # Lista vazia se pular
            else:
                resultado_ia = gemini_agent.extrair_novas_metas(msg_texto)
                lista_metas = resultado_ia.get('metas', [])
                if not lista_metas:
                    whatsapp.enviar_mensagem(telefone, "Não entendi. Mande suas metas mensais ou digite 'Pular'.")
                    return {"status": "erro_ia_mensal"}

            # Salva (se tiver) e finaliza
            if lista_metas:
                supabase_client.salvar_metas(telefone, lista_metas, tipo="mensal")
            
            supabase_client.atualizar_fase(telefone, 'ATIVO')
            
            whatsapp.enviar_mensagem(
                telefone, 
                "🎉 Tudo pronto! \n\nAgora você está na fase **ATIVO**. Pode viver sua vida que às 20h eu passo para cobrar. Se quiser registrar algo antes, é só mandar aqui! 🫡"
            )
            return {"status": "mensais_ok"}

        # FASE 3: VIDA NORMAL (ATIVO)
        if fase == 'ATIVO':
            metas_db = supabase_client.get_metas(telefone)
            # Garante que pega descrição correta independente do nome da coluna
            lista_nomes_metas = [m.get('descricao') or m.get('descricao_meta') for m in metas_db]

            if not lista_nomes_metas:
                 whatsapp.enviar_mensagem(telefone, "Ops, não achei metas ativas. Digite 'Reset' para configurar.")
                 return {"status": "sem_metas"}

            analise = gemini_agent.verificar_progresso(msg_texto, lista_nomes_metas)
            itens_analisados = analise.get('analise', [])
            
            if not itens_analisados:
                 # Se falou algo nada a ver e não é "Oi", o bot avisa
                 whatsapp.enviar_mensagem(telefone, "Não entendi se você cumpriu alguma meta. Tente: 'Hoje eu corri e li'.")
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