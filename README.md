# 🤖 Agente de Responsabilidade (Accountability AI Agent)

> Um assistente pessoal no WhatsApp que usa Inteligência Artificial para ajudar você a cumprir suas metas diárias e mensais.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-green.svg)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange.svg)
![Twilio](https://img.shields.io/badge/Twilio-WhatsApp-red.svg)

## 📌 Sobre o Projeto

Este projeto é um **Bot de WhatsApp** inteligente que atua como um "parceiro de responsabilidade". Ele não apenas envia lembretes, mas **entende** o que o usuário diz, registra o progresso no banco de dados e gera relatórios de performance.

O sistema utiliza o **Google Gemini (LLM)** para interpretar linguagem natural, permitindo que o usuário converse normalmente com o bot para cadastrar metas ou reportar o dia.

### ✨ Funcionalidades Principais

* **Onboarding Inteligente:** O usuário lista suas metas (ex: "ler, correr e beber água") e a IA extrai e cadastra tudo automaticamente.
* **Cobrança Diária Automática:** O bot envia uma mensagem todo dia às 20h perguntando o que foi feito.
* **Registro de Progresso:** O usuário responde como foi o dia (ex: "hoje só consegui ler"), e a IA identifica qual meta foi cumprida e salva no banco.
* **Relatório Mensal:** No último dia do mês, o bot gera um relatório completo comparando o realizado vs. o planejado.
* **Deploy em Nuvem:** Funciona 24/7 hospedado no Render.com.

---

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** Python 3
* **API Framework:** FastAPI
* **Inteligência Artificial:** Google Gemini (Generative AI)
* **Mensageria:** Twilio API (WhatsApp)
* **Banco de Dados:** Supabase (PostgreSQL)
* **Agendamento:** APScheduler (Cron Jobs)
* **Hospedagem:** Render

---

## ⚙️ Configuração e Instalação

### Pré-requisitos
* Python 3 instalado.
* Contas ativas: [Twilio](https://www.twilio.com/), [Google AI Studio](https://aistudio.google.com/), [Supabase](https://supabase.com/).

### 1. Clonar o repositório
```bash
git clone [https://github.com/seu-usuario/agente-metas-wpp.git](https://github.com/seu-usuario/agente-metas-wpp.git)
cd agente-metas-wpp
