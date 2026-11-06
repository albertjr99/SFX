# Migração da versão 1 para a 2.0

A versão 2.0 aproveita o banco existente (`instance/producao.db`). Nenhum registro de produção é perdido.

## Passo a passo

1. **Faça backup** de `instance/producao.db` e de `data/Pasta2.xlsx`.
2. Baixe o código novo (substituindo `app.py`, `templates/` e os scripts antigos). Mantenha a pasta `instance/`.
3. Recrie o ambiente virtual e instale as dependências:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   copy .env.example .env   # preencha SECRET_KEY
   ```
4. Aplique a migração:
   ```powershell
   flask --app wsgi db upgrade
   ```
5. Importe o plano de ação da planilha antiga (uma vez só):
   ```powershell
   flask --app wsgi plano importar data\Pasta2.xlsx
   ```
6. Suba o sistema (`waitress-serve --listen=0.0.0.0:8000 wsgi:app` no Windows).

## O que a migração `b7e4c2a91d35` faz

| Mudança | Por quê |
| --- | --- |
| `linha_producao.ano` (preenchido a partir de `data_registro`; 2025 quando vazio) | Na v1 o mês era salvo só pelo nome ("Julho"): julho de 2025 e julho de 2026 seriam misturados. |
| `linha_producao.atualizado_em`, `atualizado_por_id` | Saber quem alterou cada linha por último (analista, estagiária ou gestão). |
| Índice `(usuario_id, ano, mes, semana)` | A grade carregava cada linha com uma consulta separada; agora é uma consulta por mês. |
| `usuario.ativo` | Desativar acessos sem apagar o histórico. |
| `usuario.pode_plano_acao` (ligado para quem se chama "Lucas") | Na v1 a permissão estava escrita no código pelo nome. Agora é uma opção no cadastro. |
| Tabelas `plano_acao_ciclo` e `plano_acao_mes` | O plano de ação deixa de reescrever a planilha a cada acesso. |

Para desfazer: `flask --app wsgi db downgrade ecf042e679b9` (os dados do plano de ação no banco são descartados; a planilha original continua intacta).

## Mudanças para os usuários

- **Primeiro acesso**: na v1 qualquer pessoa que soubesse o nome de um colega podia definir a senha dele. Agora o primeiro acesso usa a **senha provisória** (as senhas iniciais da v1 continuam valendo como provisórias) e o sistema obriga a criar uma senha pessoal de pelo menos 8 caracteres com letras e números. A gestão gera novas senhas provisórias em **Usuários**.
- **Login** aceita nome ou e-mail.
- **Todos os meses** do ano ficam disponíveis (a v1 ia só de junho a dezembro), com navegação entre anos.
- **Linhas vazias não são mais gravadas**: a grade continua mostrando 15 linhas por semana, mas só o que tem conteúdo vai para o banco.
- Os endereços antigos (`/registrar-producao`, `/painel-gerente`, `/painel-estagiarias`, `/acompanhamento-pessoal`, `/acompanhamento-anual`) redirecionam para as páginas novas.

## Problemas da v1 corrigidos

- Painel da gestão salvava observações e setor em campos errados e **apagava** as observações e o setor ao salvar; também criava 15 linhas vazias por semana a cada gravação.
- Painel das estagiárias quebrava ao salvar (variável inexistente) e gravava o nome do segurado num campo que não existia.
- `relatorio_geral` apontava para um template inexistente; `editar_producao` e `conferencia_documental` quebravam ao salvar.
- A busca mostrava processos de todos os analistas para qualquer pessoa e inseria o texto sem escapar (XSS).
- `SECRET_KEY` fixa no código, sem proteção CSRF, logout por GET e sem limite de tentativas de login.
- Vários meses com ano fixo (2025) no código.
