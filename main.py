import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Importando seus serviços (que definimos nas etapas anteriores)
from app.services import gemini_agent
from app.services import supabase_client
from app.services import whatsapp

# Carrega variáveis de ambiente
load_dotenv()

# Configuração de Logs (para você ver o que está acontecendo no terminal)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. CONFIGURAÇÃO DO AGENDADOR (SCHEDULER) ---
def job_cobranca_diaria():
    """
    Esta função roda automaticamente todo dia às 20h.
    Ela busca todos os usuários ATIVOS e manda mensagem.
    """
    logger.info("⏰ Executando job de cobrança diária...")
    
    # Busca usuários que já configuraram as metas
    usuarios_ativos = supabase_client.listar_usuarios_ativos()
    
    for user in usuarios_ativos:
        telefone = user['telefone']
        nome = user.get('nome', 'Campeão')
        msg = f"🤖 Boa noite, {nome}! Chegou a hora do check-in. Quais das suas metas diárias você concluiu hoje?"
        
        whatsapp.enviar_mensagem(telefone, msg)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.
    Inicia o agendador quando o servidor liga e desliga quando ele para.
    """
    scheduler = BackgroundScheduler()
    # Configurado para rodar às 20:00 (Ajuste o timezone conforme necessário)
    scheduler.add_job(job_cobranca_diaria, 'cron', hour=20, minute=0)
    scheduler.start()
    logger.info("🚀 Scheduler iniciado! Cobranças agendadas para 20h.")
    
    yield # A aplicação roda aqui
    
    scheduler.shutdown()
    logger.info("🛑 Scheduler desligado.")

# Inicializa o App FastAPI
app = FastAPI(lifespan=lifespan)

# --- 2. ROTAS ---

@app.get("/")
def home():
    return {"status": "online", "bot": "Accountability Agent"}

@app.post("/webhook")
async def receive_whatsapp(request: Request):
    """
    Recebe todas as mensagens do WhatsApp (Twilio)
    """
    try:
        # Pega os dados enviados pelo Twilio
        form = await request.form()
        msg_texto = form.get("Body", "").strip()
        telefone = form.get("From")
        
        logger.info(f"📩 Mensagem recebida de {telefone}: {msg_texto}")

        # 1. Identifica o usuário no Banco
        user = supabase_client.get_user(telefone)

        # --- FLUXO 1: USUÁRIO NOVO (Cria conta) ---
        if not user:
            supabase_client.create_user(telefone)
            whatsapp.enviar_mensagem(
                telefone, 
                "Olá! Sou seu Agent de Metas Pessoais. 🎯\n\nVamos configurar seu ano? Responda com uma lista das metas DIÁRIAS que você quer acompanhar (ex: ler 10 paginas, ir na academia, beber 2L agua)."
            )
            return {"status": "novo_usuario_criado"}

        # Recupera a fase atual do usuário
        fase = user.get('fase', 'ONBOARDING')

        # --- FLUXO 2: CONFIGURAÇÃO DE METAS (ONBOARDING) ---
        if fase == 'ONBOARDING':
            # Gemini extrai as metas do texto
            resultado_ia = gemini_agent.extrair_novas_metas(msg_texto)
            lista_metas = resultado_ia.get('metas', [])

            if not lista_metas:
                whatsapp.enviar_mensagem(telefone, "Não entendi suas metas. Tente listar de forma simples, ex: 'Correr, Ler, Estudar'.")
                return {"status": "erro_ia_metas"}

            # Salva no Supabase
            supabase_client.salvar_metas(telefone, lista_metas)
            
            # Atualiza usuário para ATIVO
            supabase_client.atualizar_fase(telefone, 'ATIVO')
            
            whatsapp.enviar_mensagem(
                telefone, 
                f"Perfeito! Cadastrei {len(lista_metas)} metas: {', '.join(lista_metas)}.\n\nA partir de amanhã à noite eu passo aqui para perguntar quais você cumpriu! 🫡"
            )
            return {"status": "metas_cadastradas"}

        # --- FLUXO 3: ROTINA DIÁRIA (ATIVO) ---
        if fase == 'ATIVO':
            # Busca as metas cadastradas desse usuário
            metas_db = supabase_client.get_metas(telefone)
            lista_nomes_metas = [m['descricao_meta'] for m in metas_db]

            # Gemini analisa o que foi feito
            analise = gemini_agent.verificar_progresso(msg_texto, lista_nomes_metas)
            
            # Salva o histórico (Loop nas metas analisadas)
            itens_analisados = analise.get('analise', [])
            
            if not itens_analisados:
                 whatsapp.enviar_mensagem(telefone, "Não consegui entender quais metas você fez. Pode responder de novo?")
                 return {"status": "erro_ia_analise"}

            # Salva no banco
            supabase_client.salvar_historico_diario(telefone, itens_analisados, metas_db)

            # Resposta final com feedback motivacional
            feedback = analise.get('comentario_motivacional', 'Registrado!')
            resumo_msg = f"{feedback}\n\n"
            
            for item in itens_analisados:
                icon = "✅" if item['concluido'] else "❌"
                resumo_msg += f"{icon} {item['meta']}\n"

            whatsapp.enviar_mensagem(telefone, resumo_msg)
            return {"status": "registro_salvo"}

    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        return {"status": "erro"}