"""Vocabulário de domínio da Subgerência de Fixação (SFX).

Tudo que é "lista fixa" no sistema mora aqui: atividades contabilizadas,
documentos da conferência, status de acompanhamento, perfis e meses.
Templates, serviços e relatórios leem destas estruturas — nunca de listas
copiadas em vários lugares.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Campo:
    chave: str
    rotulo: str
    curto: str


# Atividades que contam como produção (checkboxes da grade).
ATIVIDADES: tuple[Campo, ...] = (
    Campo("homologacao", "Homologação", "Homolog."),
    Campo("fixacao_civil", "Fixação civil", "Fix. civil"),
    Campo("in_68", "IN 68", "IN 68"),
    Campo("conf_civil", "Conferência civil", "Conf. civil"),
    Campo("registro_civil", "Registro civil", "Reg. civil"),
    Campo("fixacao_pensao", "Fixação pensão", "Fix. pensão"),
    Campo("conf_pensao", "Conferência pensão", "Conf. pensão"),
    Campo("diligencia", "Diligência", "Diligência"),
    Campo("outros", "Outros", "Outros"),
)
CHAVES_ATIVIDADES: tuple[str, ...] = tuple(c.chave for c in ATIVIDADES)
ROTULO_ATIVIDADE = {c.chave: c.rotulo for c in ATIVIDADES}

# Checklist da conferência documental (sub-linha de cada processo).
DOCUMENTOS: tuple[Campo, ...] = (
    Campo("rg_cpf_doc", "RG / CPF", "RG/CPF"),
    Campo("comp_residencia_doc", "Comprovante de residência", "Comp. resid."),
    Campo("cert_nasc_casamento_doc", "Certidão de nascimento / casamento", "Cert. nasc./cas."),
    Campo("requerimento_doc", "Requerimento", "Requerimento"),
    Campo("dtc_doc", "DTC", "DTC"),
    Campo("negativa_pad_doc", "Negativa de PAD", "Neg. PAD"),
    Campo("contracheque_doc", "Contracheque", "Contracheque"),
    Campo("declaracao_chefia_doc", "Declaração da chefia", "Decl. chefia"),
    Campo("termo_subsidio_doc", "Termo de subsídio", "Termo subsídio"),
    Campo("declaracao_bens_doc", "Declaração de bens", "Decl. bens"),
    Campo("extrato_doc", "Extrato", "Extrato"),
    Campo("qd_elevacao_doc", "QD de elevação", "QD elevação"),
    Campo("lotacao_doc", "Lotação", "Lotação"),
    Campo("tempo_contribuicao_doc", "Tempo de contribuição", "Tempo contrib."),
    Campo("anexos_tce_doc", "Anexos TCE", "Anexos TCE"),
    Campo("portaria_doc", "Portaria", "Portaria"),
    Campo("fixacao_o_doc", "Fixação O", "Fixação O"),
    Campo("siarhes_doc", "SIARHES", "SIARHES"),
)
CHAVES_DOCUMENTOS: tuple[str, ...] = tuple(c.chave for c in DOCUMENTOS)

CAMPOS_TEXTO: tuple[str, ...] = ("numero_processo", "nome_do_segurado", "setor", "observacoes")


@dataclass(frozen=True)
class Status:
    chave: str
    rotulo: str
    simbolo: str
    curto: str


STATUS: tuple[Status, ...] = (
    Status("finalizado", "Finalizado", "X", "Finalizado"),
    Status("tramitado", "Tramitado – aguardando", "»»", "Tramitado"),
    Status("aguardando", "Aguardando orientação da chefia", "?", "Aguardando"),
    Status("acompanhar", "Acompanhar mesmo após envio", "!", "Acompanhar"),
    Status("conferido", "Conferido e encaminhado", "✓", "Conferido"),
)
STATUS_POR_CHAVE = {s.chave: s for s in STATUS}
# Status que mantêm o processo na lista de pendências do analista.
STATUS_PENDENTES: tuple[str, ...] = ("tramitado", "aguardando", "acompanhar")


# Perfis de acesso -----------------------------------------------------------
PERFIL_ANALISTA = "analista"
PERFIL_ESTAGIARIA = "estagiaria"
PERFIL_SUBGERENTE = "subgerente"
PERFIL_GERENTE = "gerente"
PERFIL_DIRETORA = "diretora"
PERFIL_ADMIN = "admin"

PERFIS = {
    PERFIL_ANALISTA: "Analista",
    PERFIL_ESTAGIARIA: "Estagiária",
    PERFIL_SUBGERENTE: "Subgerente",
    PERFIL_GERENTE: "Gerente",
    PERFIL_DIRETORA: "Diretora",
    PERFIL_ADMIN: "Administrador",
}
PERFIS_GESTAO: frozenset[str] = frozenset({PERFIL_SUBGERENTE, PERFIL_GERENTE, PERFIL_DIRETORA, PERFIL_ADMIN})
# Quem pode editar a produção de outra pessoa.
PERFIS_EDICAO_EQUIPE: frozenset[str] = PERFIS_GESTAO | {PERFIL_ESTAGIARIA}

MODALIDADES = {"presencial": "Presencial", "teletrabalho": "Teletrabalho"}

MESES: tuple[str, ...] = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)

# Linhas em branco exibidas por semana na grade de produção.
LINHAS_PADRAO_POR_SEMANA = 15
