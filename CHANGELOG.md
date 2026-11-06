# Changelog

## 2.0.0 — 2026-11-06

Reescrita completa sobre a mesma base de dados.

### Novo
- Interface redesenhada (layout com navegação lateral, responsiva, impressão em A4 paisagem), fontes e Chart.js servidos localmente.
- Grade única de produção para analistas, estagiárias e gestão, com contagens ao vivo, adicionar/remover linhas, `Ctrl+S`, aviso de alterações não salvas e impressão por semana.
- Busca de processos com link direto para a linha.
- Painel da equipe, visão anual do setor e estatísticas por semana/mês/ano.
- Plano de ação no banco de dados, com ciclos anuais e importação da planilha antiga.
- Cadastro de usuários com senha provisória, troca obrigatória, desativação e permissão de plano de ação.
- Comandos `flask usuarios`, `flask plano`, `flask demo`.
- Testes automatizados (pytest), lint (ruff), CI no GitHub Actions, Dockerfile e docker-compose.

### Segurança
- `SECRET_KEY` por variável de ambiente, CSRF, CSP, cookies seguros, `Cache-Control: no-store`, limite de tentativas de login, logout por POST, proteção contra redirecionamento aberto, autorização por perfil em todas as rotas.

### Corrigido
- Ver lista completa em [docs/MIGRACAO.md](docs/MIGRACAO.md#problemas-da-v1-corrigidos).
