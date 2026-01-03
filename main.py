import os
import logging
import calendar
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# Importando serviços
from app.services import gemini_agent
from app.services import supabase_client
from app.services import whatsapp

load_dotenv()

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. JOBS DO AGENDADOR ---

def job_cobranca_diaria():
    logger.info("⏰ Iniciando cobrança diária...")
    usuarios = supabase_client.listar_usuarios_ativos()
    for user in usuarios:
        whatsapp.enviar_mensagem(
            user['telefone'], 
            f"🤖 Boa noite, {user.get('nome', 'Campeão')}! Hora do check-in. Quais metas você cumpriu hoje?"
        )

def job_resumo_mensal():
    logger.info("📊 Gerando relatórios mensais...")
    agora = datetime.now()
    # Pega primeiro e último dia do mês atual
    ultimo_dia = calendar.monthrange(agora.year, agora.month)[1]
    data_inicio = f"{agora.year}-{agora.month:02d}-01"
    data_fim = f"{agora.year}-{agora.month:02d}-{ultimo_dia}"

    usuarios = supabase_client.listar_usuarios_ativos()

    for user in usuarios:
        tel = user['telefone']
        
        # ATENÇÃO: Consultas ajustadas para o seu banco (telefone_user)
        metas = supabase_client.client.table("metas").select("*").eq("telefone_user", tel).execute()
        
        # Pega as respostas do mês
        respostas = supabase_client.client.table("respostas_diarias").select("*")\
            .eq("telefone_user", tel)\
            .gte("data", data_inicio).lte("data", data_fim).execute()

        if not respostas.data:
            continue

        prompt = f"""
        ANALISTA DE PERFORMANCE. Mês: {agora.month}/{agora.year}.
        METAS DO USUÁRIO: {metas.data}
        REGISTROS DO MÊS (Histórico): {respostas.data}
        
        Gere um relatório curto para WhatsApp:
        1. Totais realizados vs Planejado.
        2. Frase motivacional.
        """
        
        try:
            resp_ia = gemini_agent.model.generate_content(prompt)
            whatsapp.enviar_mensagem(tel, resp_ia.text)
        except Exception as e:
            logger.error(f"Erro relatório {tel}: {e}")

# --- 2. LIFESPAN (Inicia/Para o servidor) ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    scheduler.add_job(job_cobranca_diaria, 'cron', hour=20, minute=0, timezone='America/Sao_Paulo')
    scheduler.add_job(job_resumo_mensal, CronTrigger(day='last', hour=21, minute=0, timezone='America/Sao_Paulo'))
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

# --- 3. ROTAS ---

@app.get("/")
def home():
    return {"status": "online", "banco": "conectado"}

@app.post("/webhook")
async def receive_whatsapp(request: Request):
    try:
        form = await request.form()
        msg = form.get("Body", "").strip()
        telefone = form.get("From")
        
        logger.info(f"📩 {telefone}: {msg}")

        # 1. Identifica ou Cria
        user = supabase_client.get_user(telefone)
        if not user:
            supabase_client.create_user(telefone)
            whatsapp.enviar_mensagem(telefone, "Olá! Vamos configurar? Envie suas **METAS DIÁRIAS** (ex: Ler, Treinar).")
            return {"status": "novo"}

        fase = user.get('fase', 'SETUP_DIARIA')
        msg_lower = msg.lower()

        # 2. INTELIGÊNCIA DE "OI" vs "RESET"
        
        # Se for só um cumprimento, NÃO reinicia
        cumprimentos = ["oi", "ola", "olá", "bom dia", "boa noite"]
        if msg_lower in cumprimentos:
            if fase == 'ATIVO':
                whatsapp.enviar_mensagem(telefone, "Olá! 👋 Já cumpriu alguma meta hoje? Me conta aí!")
            else:
                whatsapp.enviar_mensagem(telefone, "Oi! Estamos configurando. Veja a pergunta acima 👆")
            return {"status": "cumprimento"}

        # Se for pedido EXPLICITO de reset, aí sim reinicia
        if any(x in msg_lower for x in ["reset", "reiniciar", "configurar", "começar"]):
            supabase_client.atualizar_fase(telefone, 'SETUP_DIARIA')
            whatsapp.enviar_mensagem(telefone, "🔄 Reiniciando! Envie suas **METAS DIÁRIAS**.")
            return {"status": "reset"}

        # --- FLUXOS ---

        if fase == 'SETUP_DIARIA':
            ia = gemini_agent.extrair_novas_metas(msg)
            metas = ia.get('metas', [])
            if not metas:
                whatsapp.enviar_mensagem(telefone, "Não entendi. Liste simples: 'Academia, Ler'.")
                return {"erro": "ia"}
            
            supabase_client.salvar_metas(telefone, metas, tipo="diaria")
            supabase_client.atualizar_fase(telefone, 'SETUP_MENSAL')
            whatsapp.enviar_mensagem(telefone, "✅ Diárias salvas! Agora envie as **METAS MENSAIS** (ou digite 'Pular').")
            return {"ok": "diaria"}

        if fase == 'SETUP_MENSAL':
            if "pular" not in msg_lower:
                ia = gemini_agent.extrair_novas_metas(msg)
                metas = ia.get('metas', [])
                if metas:
                    supabase_client.salvar_metas(telefone, metas, tipo="mensal")
            
            supabase_client.atualizar_fase(telefone, 'ATIVO')
            whatsapp.enviar_mensagem(telefone, "🎉 Tudo pronto! Fase: **ATIVO**. Te chamo às 20h!")
            return {"ok": "mensal"}

        if fase == 'ATIVO':
            # Busca descrições das metas para a IA comparar
            metas_db = supabase_client.get_metas(telefone)
            nomes_metas = [m['descricao'] for m in metas_db]

            analise = gemini_agent.verificar_progresso(msg, nomes_metas)
            itens = analise.get('analise', [])

            if not itens:
                whatsapp.enviar_mensagem(telefone, "Não entendi. Tente: 'Hoje eu corri'.")
                return {"erro": "analise"}

            # Salva na tabela respostas_diarias
            supabase_client.salvar_respostas_diarias(telefone, itens, metas_db)

            feedback = analise.get('comentario_motivacional', 'Boa!')
            texto_final = f"{feedback}\n"
            for i in itens:
                icon = "✅" if i['concluido'] else "❌"
                texto_final += f"\n{icon} {i['meta']}"
            
            whatsapp.enviar_mensagem(telefone, texto_final)
            return {"ok": "registrado"}

    except Exception as e:
        logger.error(f"Erro: {e}")
        return {"status": "erro"}