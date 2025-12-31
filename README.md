# 🤖 Agente de Responsabilidade (Accountability AI Agent)

> Um assistente pessoal no WhatsApp que usa Inteligência Artificial para ajudar você a cumprir suas metas diárias e mensais.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-green.svg)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange.svg)
![Twilio](https://img.shields.io/badge/Twilio-WhatsApp-red.svg)

---

## 📌 Sobre o Projeto

Este projeto é um **Bot de WhatsApp** inteligente que atua como um "parceiro de responsabilidade". Ele não apenas envia lembretes, mas **entende** o que o usuário diz, registra o progresso no banco de dados e gera relatórios de performance.

O sistema utiliza o **Google Gemini (LLM)** para interpretar linguagem natural, permitindo que o usuário converse normalmente com o bot para cadastrar metas ou reportar o dia.

### ✨ Funcionalidades Principais

- **Onboarding Inteligente:** O usuário lista suas metas (ex: "ler, correr e beber água") e a IA extrai e cadastra tudo automaticamente.
- **Cobrança Diária Automática:** O bot envia uma mensagem todo dia às 20h perguntando o que foi feito.
- **Registro de Progresso:** O usuário responde como foi o dia (ex: "hoje só consegui ler"), e a IA identifica qual meta foi cumprida e salva no banco.
- **Relatório Mensal:** No último dia do mês, o bot gera um relatório completo comparando o realizado vs. o planejado.
- **Deploy em Nuvem:** Funciona 24/7 hospedado no Render.com.

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** Python 3
- **API Framework:** FastAPI
- **Inteligência Artificial:** Google Gemini (Generative AI)
- **Mensageria:** Twilio API (WhatsApp)
- **Banco de Dados:** Supabase (PostgreSQL)
- **Agendamento:** APScheduler (Cron Jobs)
- **Hospedagem:** Render

---

## ⚙️ Configuração e Instalação

### Pré-requisitos

- Python 3 instalado.
- Contas ativas: [Twilio](https://www.twilio.com/), [Google AI Studio](https://aistudio.google.com/), [Supabase](https://supabase.com/).

### 1. Clonar o repositório

```bash
git clone https://github.com/seu-usuario/agente-metas-wpp.git
cd agente-metas-wpp
```

### 2. Criar e ativar um ambiente virtual

```bash
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto e adicione as seguintes variáveis:

```env
TWILIO_ACCOUNT_SID=seu_account_sid
TWILIO_AUTH_TOKEN=seu_auth_token
SUPABASE_URL=sua_url_supabase
SUPABASE_KEY=sua_chave_supabase
```

### 5. Executar o projeto

```bash
python main.py
```

---

## 🧪 Testes

Para rodar os testes, utilize o comando:

```bash
pytest
```

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

## 🙌 Contribuições

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues e enviar pull requests.

---

## 📞 Suporte

Se você tiver dúvidas ou problemas, entre em contato pelo e-mail: suporte@exemplo.com.
