# Publicar no PythonAnywhere (gratuito)

Resultado: o sistema em `https://SEU-USUARIO.pythonanywhere.com`, com HTTPS, acessível de qualquer lugar (inclusive teletrabalho).

**Plano gratuito:** 1 site, 512 MB de disco (o banco SQLite fica salvo), sem domínio próprio.
O site **expira se não for renovado a cada mês**: entre na aba **Web** e clique em *"Run until 1 month from today"*.
Contas novas não têm tarefas agendadas no plano gratuito, então faça backups pelo script de atualização ou baixando `instance/producao.db` na aba **Files**.

## 1. Criar a conta
Crie uma conta "Beginner" em <https://www.pythonanywhere.com/registration/register/beginner/>. O nome de usuário vira o endereço do site.

## 2. Instalar (uma vez)
Na aba **Consoles**, abra um **Bash** e cole:

```bash
git clone https://github.com/albertjr99/SFX.git ~/SFX && bash ~/SFX/deploy/pythonanywhere_instalar.sh
```

O script cria o ambiente Python, instala as dependências, gera o `.env` com uma chave secreta nova e prepara o banco a partir de `dados_iniciais/` (usuários da equipe e plano de ação 2024–2025).

## 3. Configurar o site (aba **Web**)
O script mostra estes passos no final, já com os caminhos certos:

1. **Add a new web app** → Next → **Manual configuration** → escolha o Python indicado pelo script → Next.
2. **Virtualenv:** `/home/SEU-USUARIO/.virtualenvs/sfx`
3. **Static files:** URL `/static/` → Directory `/home/SEU-USUARIO/SFX/sfx/static`
4. Abra o **WSGI configuration file**, apague tudo e cole o conteúdo de [`deploy/pythonanywhere_wsgi.py`](../deploy/pythonanywhere_wsgi.py).
5. Ative **Force HTTPS** e clique em **Reload**.

## 4. Primeiro acesso da equipe
Todos começam com a senha provisória **`1234`**. Cada pessoa entra com o próprio nome e o sistema obriga a criar uma senha pessoal.
**Peça que todos entrem e troquem a senha logo após publicar** — até lá, quem souber o nome e a senha provisória consegue entrar. O Lucas (administrador) deve ser o primeiro.
Na tela **Usuários**, a etiqueta *Senha provisória* mostra quem ainda não trocou.
Para gerar uma nova senha provisória: tela **Usuários** (perfis de gestão) ou, no console:

```bash
cd ~/SFX && source ~/.virtualenvs/sfx/bin/activate && flask --app wsgi usuarios redefinir-senha NOME
```

## Atualizar para uma nova versão
```bash
bash ~/SFX/deploy/pythonanywhere_atualizar.sh
```
Faz backup do banco em `~/backups/` (guarda os 14 mais recentes), baixa o código novo, aplica migrações e recarrega o site. O banco em uso **nunca** é substituído pelo de `dados_iniciais/`.
