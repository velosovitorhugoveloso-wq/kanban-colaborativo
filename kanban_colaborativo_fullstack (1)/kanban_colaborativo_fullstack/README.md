# Kanban Colaborativo — Full Stack

Aplicação acadêmica com front-end HTML/CSS/JavaScript, back-end Python/Flask e banco PostgreSQL. Para executar localmente, usa SQLite automaticamente quando `DATABASE_URL` não está definida.

## Funcionalidades

- Cadastro e login com senhas armazenadas usando hash seguro (Werkzeug).
- Sessões autenticadas e proteção CSRF nas operações de alteração.
- Dados persistidos no banco: contas, quadros, participantes, tarefas, comentários, checklist e histórico.
- Compartilhamento com usuários já cadastrados por e-mail.
- Papéis OWNER, EDITOR e VIEWER, com permissões verificadas no servidor.
- Criar, editar, mover e excluir tarefas; responsável, prazo, prioridade, labels, sprint e story points.
- Comentários com autor/data, checklist e histórico.
- Atualização automática da tela a cada 5 segundos.

## 1. Rodar no Windows

Instale Python 3.11 ou 3.12. Abra o PowerShell na pasta do projeto e execute:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Se o PowerShell bloquear a ativação do ambiente, rode sem ativar:

```powershell
py -m pip install -r requirements.txt
py app.py
```

Abra `http://127.0.0.1:5000`. O banco `kanban.db` será criado automaticamente. Não envie esse arquivo ao GitHub.

## 2. Publicar na internet

GitHub Pages não executa Python/Flask. Use GitHub para armazenar o código, Render para executar o servidor e Neon para PostgreSQL.

### A. Banco Neon
1. Acesse https://neon.tech/ e crie uma conta/projeto PostgreSQL.
2. Copie a URL de conexão (connection string).
3. Guarde-a em segredo; não coloque em código nem publique no GitHub.

### B. GitHub
1. Crie um repositório chamado `kanban-colaborativo`.
2. Envie os arquivos `app.py`, `requirements.txt`, `render.yaml`, `README.md`, `schema.sql` e a pasta `templates`.
3. Confirme que nenhum `.env`, senha ou arquivo `.db` foi enviado.

### C. Render
1. Acesse https://render.com/ e conecte o GitHub.
2. Escolha **New → Web Service** e selecione o repositório.
3. Build command: `pip install -r requirements.txt`.
4. Start command: `gunicorn app:app`.
5. Nas variáveis de ambiente, configure `DATABASE_URL` com a URL do Neon e `COOKIE_SECURE` como `true`. Crie uma `SECRET_KEY` longa e aleatória (o `render.yaml` pode gerar uma automaticamente).
6. Faça o deploy. O Render fornecerá uma URL pública `https://...onrender.com`.

O `render.yaml` contém as configurações básicas; a URL do banco ainda precisa ser informada no painel do Render.

## 3. Demonstração ao professor
1. Abra o endereço publicado e crie a conta do primeiro usuário (será o dono do quadro).
2. Em outro navegador ou janela anônima, crie a conta do segundo usuário.
3. Na primeira conta, clique em **Compartilhar quadro** e informe o e-mail cadastrado da segunda conta.
4. Selecione Editor ou Leitor.
5. Entre na segunda conta e confira o quadro compartilhado.
6. Crie ou mova uma tarefa e aguarde até 5 segundos para a outra tela atualizar.

## Observações

- O convite adiciona contas já cadastradas; este protótipo não envia e-mails.
- A atualização entre navegadores usa consulta ao servidor a cada 5 segundos, não WebSocket.
- Para uso de produção, acrescente recuperação de senha, limitação de tentativas de login, backups e monitoramento. Não compartilhe `SECRET_KEY`, URL do banco ou senhas.
