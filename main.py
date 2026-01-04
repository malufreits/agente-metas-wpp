import os
import logging
import calendar
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from app.services import gemini_agent
from app.services import supabase_client
from app.services import whatsapp

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. JOBS (Mantido igual) ---
def job_cobranca_diaria():
    logger.info("⏰ Cobrança diária...")
    usuarios = supabase_client.listar_usuarios_ativos()
    for user in usuarios:
        whatsapp.enviar_mensagem(user['telefone'], f"🤖 Boa noite {user.get('nome','')}! Check-in: O que você cumpriu hoje?")

def job_resumo_mensal():
    # (Sua lógica de relatório mensal aqui - igual ao anterior)
    pass 

# --- 2. LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    scheduler.add_job(job_cobranca_diaria, 'cron', hour=20, minute=0, timezone='America/Sao_Paulo')
    # scheduler.add_job(job_resumo_mensal...) # Pode descomentar se quiser
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

# --- 3. WEBHOOK INTELIGENTE ---
@app.post("/webhook")
async def receive_whatsapp(request: Request):
    try:
        form = await request.form()
        msg = form.get("Body", "").strip()
        telefone = form.get("From")
        logger.info(f"📩 {telefone}: {msg}")

        user = supabase_client.get_user(telefone)
        if not user:
            supabase_client.create_user(telefone)
            whatsapp.enviar_mensagem(telefone, "Olá! Vamos configurar? Envie suas **METAS DIÁRIAS**.")
            return {"status": "novo"}

        fase = user.get('fase', 'SETUP_DIARIA')
        msg_lower = msg.lower()

        # --- COMANDOS ESPECIAIS (Migrados do agendamento.py) ---
        
        # 1. RESET
        if any(x in msg_lower for x in ["reset", "reiniciar", "configurar"]):
            supabase_client.atualizar_fase(telefone, 'SETUP_DIARIA')
            whatsapp.enviar_mensagem(telefone, "🔄 Reiniciando! Envie suas **METAS DIÁRIAS**.")
            return {"status": "reset"}

        # 2. ADICIONAR META (Nova funcionalidade)
        # Exemplo: "Adicionar meta: Ler biblia"
        if msg_lower.startswith("adicionar meta") or msg_lower.startswith("nova meta"):
            nova_meta = msg.split(":", 1)[-1].strip() # Pega o texto depois dos dois pontos
            if len(nova_meta) > 3:
                supabase_client.adicionar_meta_individual(telefone, nova_meta, "diaria")
                whatsapp.enviar_mensagem(telefone, f"✅ Meta adicionada: '{nova_meta}'")
                return {"status": "meta_add"}
            else:
                whatsapp.enviar_mensagem(telefone, "Para adicionar, use: 'Nova meta: [descrição]'")
                return {"status": "erro_formato"}

        # 3. EXCLUIR META (Nova funcionalidade)
        # Exemplo: "Excluir meta ler"
        if msg_lower.startswith("excluir meta") or msg_lower.startswith("remover meta"):
            texto_busca = msg.replace("excluir meta", "").replace("remover meta", "").strip()
            removido = supabase_client.excluir_meta_por_texto(telefone, texto_busca)
            
            if removido:
                whatsapp.enviar_mensagem(telefone, f"🗑️ Meta '{removido}' foi excluída!")
            else:
                whatsapp.enviar_mensagem(telefone, f"Não achei nenhuma meta com '{texto_busca}'.")
            return {"status": "meta_del"}

        # --- FLUXO NORMAL ---

        if fase == 'SETUP_DIARIA':
            ia = gemini_agent.extrair_novas_metas(msg)
            metas = ia.get('metas', [])
            if not metas:
                whatsapp.enviar_mensagem(telefone, "Não entendi. Liste: 'Academia, Ler'.")
                return {"erro": "ia"}
            supabase_client.salvar_metas(telefone, metas, "diaria")
            supabase_client.atualizar_fase(telefone, 'SETUP_MENSAL')
            whatsapp.enviar_mensagem(telefone, "✅ Diárias salvas! Agora envie as **METAS MENSAIS**.")
            return {"ok": "diaria"}

        if fase == 'SETUP_MENSAL':
            if "pular" not in msg_lower:
                ia = gemini_agent.extrair_novas_metas(msg)
                metas = ia.get('metas', [])
                if metas: supabase_client.salvar_metas(telefone, metas, "mensal")
            supabase_client.atualizar_fase(telefone, 'ATIVO')
            whatsapp.enviar_mensagem(telefone, "🎉 Tudo pronto! Fase: **ATIVO**.")
            return {"ok": "mensal"}

        if fase == 'ATIVO':
            # Verifica cumprimento de meta OU só conversa
            cumprimentos = ["oi", "ola", "bom dia", "boa tarde"]
            if msg_lower in cumprimentos:
                whatsapp.enviar_mensagem(telefone, "Olá! 👋 Já cumpriu suas metas hoje?")
                return {"ok": "cumprimento"}

            metas_db = supabase_client.get_metas(telefone)
            nomes_metas = [m['descricao'] for m in metas_db]
            analise = gemini_agent.verificar_progresso(msg, nomes_metas)
            itens = analise.get('analise', [])

            if not itens:
                whatsapp.enviar_mensagem(telefone, "Não entendi se você cumpriu algo. Tente ser mais específico.")
                return {"erro": "analise"}

            supabase_client.salvar_respostas_diarias(telefone, itens, metas_db)
            
            # Monta resposta bonitinha
            texto = f"{analise.get('comentario_motivacional', 'Boa!')}\n"
            for i in itens:
                texto += f"\n{'✅' if i['concluido'] else '❌'} {i['meta']}"
            
            whatsapp.enviar_mensagem(telefone, texto)
            return {"ok": "registrado"}

    except Exception as e:
        logger.error(f"Erro: {e}")
        return {"status": "erro"}