from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_migrate import Migrate
from datetime import datetime, timedelta
import calendar

# --- Configuração da aplicação ---
app = Flask(__name__)
app.secret_key = 'chave-secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///producao.db'

db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Meses em Português para filtro
MESES_PT = [
    'Janeiro','Fevereiro','Março','Abril','Maio','Junho',
    'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'
]
class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # analista, estagiaria, gerente
    modalidade = db.Column(db.String(20))           # presencial ou teletrabalho
    primeiro_acesso_realizado = db.Column(db.Boolean, default=False)

class LinhaProducao(db.Model):
    __tablename__ = 'linha_producao'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    mes = db.Column(db.String(20), nullable=False)
    semana = db.Column(db.String(50), nullable=False)
    indice_linha = db.Column(db.Integer, nullable=False)
    numero_processo = db.Column(db.String(50))
    requerente = db.Column(db.String(100))
    fase = db.Column(db.String(50))
    observacao = db.Column(db.Text)
    data_registro = db.Column(db.DateTime, default=datetime.utcnow)
    averbacao = db.Column(db.Boolean, default=False)
    desaverbacao = db.Column(db.Boolean, default=False)
    conf_av_desav = db.Column(db.Boolean, default=False)
    ctc = db.Column(db.Boolean, default=False)
    conf_ctc = db.Column(db.Boolean, default=False)
    dtc = db.Column(db.Boolean, default=False)
    conf_dtc = db.Column(db.Boolean, default=False)
    in_68 = db.Column(db.Boolean, default=False)
    dpor = db.Column(db.Boolean, default=False)
    registro_atos = db.Column(db.Boolean, default=False)
    ag_completar = db.Column(db.Boolean, default=False)
    outros = db.Column(db.Boolean, default=False)

    usuario = db.relationship('Usuario', backref='linhas')

# Gera as semanas úteis de um mês e ano
def gerar_semanas(mes_num, ano):
    semanas = []
    primeiro_dia = datetime(ano, mes_num, 1)
    ultimo_dia = datetime(ano, mes_num, calendar.monthrange(ano, mes_num)[1])
    semana = []
    dia = primeiro_dia
    while dia <= ultimo_dia:
        if dia.weekday() < 5:
            semana.append(dia.strftime('%d/%m'))
        if dia.weekday() == 4 or dia == ultimo_dia:
            if semana:
                semanas.append(f"{semana[0]} a {semana[-1]}")
                semana = []
        dia += timedelta(days=1)
    return semanas

# Alias para compatibilidade
obter_semanas_do_mes = gerar_semanas

# --- Flask-Login user loader ---
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# --- Rotas de autenticação ---
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    nome = request.form['nome']
    senha = request.form['senha']
    usuario = Usuario.query.filter(func.lower(Usuario.nome)==nome.lower()).first()
    if usuario and check_password_hash(usuario.senha, senha):
        login_user(usuario)
        session['usuario_id'] = usuario.id
        session['usuario_tipo'] = usuario.tipo
        if usuario.tipo == 'analista':
            return redirect(url_for('registrar_producao'))
        elif usuario.tipo == 'estagiaria':
            return redirect(url_for('painel_estagiarias'))
        else:
            return redirect(url_for('painel_gerente'))
    return 'Login inválido'

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))

@app.route('/primeiro-acesso', methods=['POST'])
def primeiro_acesso():
    nome = request.form.get('nome')
    nova_senha = request.form.get('nova_senha')
    # busca usuario pelo nome, ignorando maiúsculas/minúsculas
    usuario = Usuario.query.filter(func.lower(Usuario.nome) == nome.lower()).first()
    if not usuario:
        flash('Usuário não encontrado.')
    elif usuario.primeiro_acesso_realizado:
        flash('Senha já definida anteriormente.')
    else:
        usuario.senha = generate_password_hash(nova_senha)
        usuario.primeiro_acesso_realizado = True
        db.session.commit()
        flash('Senha definida com sucesso. Agora faça login.')
    return redirect(url_for('login'))
    
# ... (seu setup do app, db, Usuario, LinhaProducao, gerar_semanas, etc.) ...


@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route('/acompanhamento-anual')
@login_required
def acompanhamento_anual():
    campos = [ 'averbacao','desaverbacao','conf_av_desav','ctc','conf_ctc',
               'dtc','conf_dtc','in_68','dpor','registro_atos','ag_completar','outros' ]
    meses = ['Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

    totais_anuais = { m: {c:0 for c in campos} for m in meses }
    for p in LinhaProducao.query.filter(LinhaProducao.mes.in_(meses)).all():
        for c in campos:
            if getattr(p, c):
                totais_anuais[p.mes][c] += 1

    grafico_anos = { c: sum(m[c] for m in totais_anuais.values()) for c in campos }

    return render_template(
        'acompanhamento_anual.html',
        totais_anuais = totais_anuais,
        grafico_anos   = grafico_anos,
        meses          = meses,
        campos         = campos
    )

@app.route('/acompanhamento-analista')
@login_required
def acompanhamento_analista():
    # só gestores
    if current_user.tipo == 'analista':
        flash('Acesso não autorizado.')
        return redirect(url_for('index'))

    analista_id      = request.args.get('analista_id', type=int)
    # lista fixa de meses (meses que você usa no sistema)
    meses            = ['Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
    # define mês padrão: parâmetro ou mês corrente (se estiver na lista) ou 'Junho'
    hoje_nome        = datetime.now().strftime('%B').capitalize()
    mes_param        = request.args.get('mes')
    if mes_param in meses:
        mes = mes_param
    elif hoje_nome in meses:
        mes = hoje_nome
    else:
        mes = 'Junho'

    # gerar semanas do mês
    ano              = datetime.now().year
    mes_idx          = meses.index(mes)
    semanas          = gerar_semanas(mes_idx + 6, ano)

    # parâmetros de filtro do gráfico
    view             = request.args.get('view', 'mes')   # 'semana','mes','ano'
    selected_semana  = request.args.get('semana', semanas[0] if semanas else '')

    # campos de contagem
    campos = [
        'averbacao','desaverbacao','conf_av_desav','ctc','conf_ctc',
        'dtc','conf_dtc','in_68','dpor','registro_atos','ag_completar','outros'
    ]

    # busca o analista
    analista = Usuario.query.get(analista_id) if analista_id else None

    # inicializa contadores
    counts = {c: 0 for c in campos}

    if analista:
        if view == 'semana':
            # só aquela semana
            for p in LinhaProducao.query.filter_by(
                    usuario_id=analista.id, mes=mes, semana=selected_semana):
                for c in campos:
                    if getattr(p, c):
                        counts[c] += 1

        elif view == 'mes':
            # soma todas as semanas do mês
            for s in semanas:
                for p in LinhaProducao.query.filter_by(
                        usuario_id=analista.id, mes=mes, semana=s):
                    for c in campos:
                        if getattr(p, c):
                            counts[c] += 1

        else:  # view == 'ano'
            # soma todos os meses
            for m in meses:
                for p in LinhaProducao.query.filter_by(
                        usuario_id=analista.id, mes=m):
                    for c in campos:
                        if getattr(p, c):
                            counts[c] += 1

    return render_template(
        'acompanhamento_analista.html',
        analista=analista,
        meses=meses,
        mes=mes,
        semanas=semanas,
        view=view,
        selected_semana=selected_semana,
        campos=campos,
        counts=counts
    )

from datetime import datetime

@app.route('/painel-gerente', methods=['GET', 'POST'])
@login_required
def painel_gerente():
    # 1) só gestores acessam
    if current_user.tipo == 'analista':
        flash('Acesso não autorizado.')
        return redirect(url_for('index'))

    # 2) listas de analistas
    analistas_presencial   = Usuario.query.filter_by(tipo='analista', modalidade='presencial').all()
    analistas_teletrabalho = Usuario.query.filter_by(tipo='analista', modalidade='teletrabalho').all()

    # 3) leitura dos filtros
    analista_id     = request.values.get('analista_id', type=int)
    mes_param       = request.values.get('mes')               # tenta ler ?mes=
    selected_semana = request.values.get('semana', 'Mês inteiro')

    # meses que trabalhamos
    meses = ['Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

    # se veio mes_param válido, usa-o; senão, define pelo mês atual
    if mes_param in meses:
        mes = mes_param
    else:
        m_atual = datetime.now().month
        if 6 <= m_atual <= 12:
            mes = meses[m_atual - 6]
        else:
            mes = meses[0]

    usuario_sel = Usuario.query.get(analista_id) if analista_id else None

    # gera semanas e linhas
    ano     = datetime.now().year
    idx     = meses.index(mes)
    semanas = gerar_semanas(idx + 6, ano)
    linhas  = 33 if usuario_sel and usuario_sel.modalidade=='teletrabalho' else 28

    campos = [
        'averbacao','desaverbacao','conf_av_desav','ctc','conf_ctc',
        'dtc','conf_dtc','in_68','dpor','registro_atos','ag_completar','outros'
    ]

    # inicialização
    processos_info  = {}
    totais_semanais = {s: {c:0 for c in campos} for s in semanas}
    total_feito     = 0
    meta            = 100
    percentual_meta = 0
    alertas         = {}

    if usuario_sel:
        # meta variável
        meta = 112 if usuario_sel.modalidade=='teletrabalho' else 100

        # se veio POST, salva as edições
        if request.method == 'POST':
            for s in semanas:
                for i in range(linhas):
                    p = (LinhaProducao.query
                            .filter_by(usuario_id=usuario_sel.id, mes=mes, semana=s)
                            .offset(i).first())
                    if not p:
                        p = LinhaProducao(
                            usuario_id=usuario_sel.id,
                            mes=mes,
                            semana=s,
                            indice_linha=i,
                            data_registro=datetime.utcnow()
                        )
                        db.session.add(p)
                    p.numero_processo = request.form.get(f'{s}_{i}_numero_processo','')
                    p.requerente      = request.form.get(f'{s}_{i}_requerente','')
                    p.fase            = request.form.get(f'{s}_{i}_fase','')
                    p.observacao      = request.form.get(f'{s}_{i}_obs','')
                    for c in campos:
                        setattr(p, c, bool(request.form.get(f'{s}_{i}_{c}')))
            db.session.commit()
            flash('Produção atualizada com sucesso.')
            return redirect(url_for('painel_gerente',
                                    analista_id=usuario_sel.id,
                                    mes=mes,
                                    semana=selected_semana))

        # monta informações e totais semanais
        processos_info = {
            s: [
                (LinhaProducao.query
                    .filter_by(usuario_id=usuario_sel.id, mes=mes, semana=s)
                    .offset(i).first())
                for i in range(linhas)
            ]
            for s in semanas
        }
        for s in semanas:
            for p in LinhaProducao.query.filter_by(usuario_id=usuario_sel.id, mes=mes, semana=s):
                for c in campos:
                    if getattr(p, c):
                        totais_semanais[s][c] += 1

        # total do mês e progresso
        total_feito     = sum(sum(vals.values()) for vals in totais_semanais.values())
        percentual_meta = min(int((total_feito / meta) * 100), 100)

        # alertas semanais
        for s in semanas:
            feito    = sum(totais_semanais[s].values())
            esperado = 25 if usuario_sel.modalidade=='presencial' else 28
            if feito < esperado:
                alertas[s] = f"Faltam {esperado - feito} tarefas"

    # totais anuais p/ comparativo
    totais_anuais = {m: {c:0 for c in campos} for m in meses}
    for m in meses:
        for p in LinhaProducao.query.filter_by(mes=m):
            for c in campos:
                if getattr(p, c):
                    totais_anuais[m][c] += 1

    # total do mês p/ mini‐relatório
    total_mes = {c: sum(totaiss[c] for totaiss in totais_semanais.values())
                 for c in campos}

    return render_template(
        'painel_gerente.html',
        analistas_presencial   = analistas_presencial,
        analistas_teletrabalho = analistas_teletrabalho,
        usuario_selecionado    = usuario_sel,
        meses                  = meses,
        mes                    = mes,
        semanas                = semanas,
        linhas                 = linhas,
        campos                 = campos,
        processos_info         = processos_info,
        totais                 = totais_semanais,
        total_mes              = total_mes,
        total_feito            = total_feito,
        meta                   = meta,
        percentual_meta        = percentual_meta,
        selected_semana        = selected_semana,
        alertas                = alertas,
        totais_anuais          = totais_anuais
    )
# --- Acompanhamento Pessoal com filtro de mês e semana ---
@app.route('/acompanhamento-pessoal')
@login_required
def acompanhamento_pessoal():
    # acesso apenas para analistas
    if current_user.tipo != 'analista':
        flash('Acesso não autorizado.')
        return redirect(url_for('login'))

    # lista de meses para filtro
    meses = MESES_PT

    # parâmetros GET opcionais
    selected_mes = request.args.get('mes') or MESES_PT[datetime.now().month - 1]
    selected_semana = request.args.get('semana') or 'Mês inteiro'

    # converte mes para número
    mes_num = MESES_PT.index(selected_mes) + 1
    ano = datetime.now().year

    # gera semanas do mês selecionado
    semanas = gerar_semanas(mes_num, ano)

    campos = ['averbacao','desaverbacao','conf_av_desav','ctc','conf_ctc',
              'dtc','conf_dtc','in_68','dpor','registro_atos','ag_completar','outros']

    totais = {}
    total_mes = {c: 0 for c in campos}
    total_feito = 0

    # conta por semana e total do mês
    for s in semanas:
        cont = {c: 0 for c in campos}
        prods = LinhaProducao.query.filter_by(
            usuario_id=current_user.id,
            mes=selected_mes,
            semana=s
        ).all()
        for p in prods:
            for c in campos:
                if getattr(p, c, False):
                    cont[c] += 1
                    total_mes[c] += 1
                    total_feito += 1
        totais[s] = cont

    meta = 112 if current_user.modalidade == 'teletrabalho' else 100
    percentual_meta = round((total_feito / meta) * 100, 1) if meta else 0

    return render_template('acompanhamento_pessoal.html',
        usuario=current_user,
        meses=meses,
        semanas=semanas,
        selected_mes=selected_mes,
        selected_semana=selected_semana,
        campos=campos,
        totais=totais,
        total_mes=total_mes,
        total_feito=total_feito,
        meta=meta,
        percentual_meta=percentual_meta
    )

@app.route('/editar-producao/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_producao(id):
    producao = LinhaProducao.query.get_or_404(id)
    if request.method == 'POST':
        producao.numero_processo = request.form['numero_processo']
        producao.requerente = request.form['requerente']
        producao.fase = request.form['fase']
        db.session.commit()
        return redirect(url_for('painel_gerente'))
    return render_template('editar_producao.html', producao=producao)

# Continuação será feita na próxima etapa

@app.route('/registrar-producao', methods=['GET', 'POST'])
@login_required
def registrar_producao():
    if current_user.tipo != 'analista':
        flash('Acesso não autorizado.')
        return redirect(url_for('login'))

    usuario = Usuario.query.get(session['usuario_id'])
    meses = ['Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    ano = 2025

    # Pega o parâmetro ?mes=... se houver
    mes_param = request.args.get('mes')

    # Se o parâmetro for válido, usa-o; caso contrário, abre no mês atual
    if mes_param in meses:
        mes_atual = mes_param
    else:
        # Mapeia o mês numérico para nosso array de meses (Junho=6 → índice 0)
        mes_numero_atual = datetime.now().month
        if 6 <= mes_numero_atual <= 12:
            mes_atual = meses[mes_numero_atual - 6]
        else:
            mes_atual = meses[0]  # fallback para Junho

    mes_index = meses.index(mes_atual)
    mes_anterior = meses[mes_index - 1] if mes_index > 0 else meses[-1]
    mes_posterior = meses[mes_index + 1] if mes_index < len(meses) - 1 else meses[0]
    mes_num = mes_index + 6

    semanas = gerar_semanas(mes_num, ano)
    linhas = 33 if usuario.modalidade == 'teletrabalho' else 28
    campos = [
        'averbacao', 'desaverbacao', 'conf_av_desav', 'ctc',
        'conf_ctc', 'dtc', 'conf_dtc', 'in_68', 'dpor',
        'registro_atos', 'ag_completar', 'outros'
    ]

    if request.method == 'POST':
        for semana in semanas:
            for i in range(linhas):
                indice_linha = i + 1

                producao = LinhaProducao.query.filter_by(
                    usuario_id=usuario.id,
                    mes=mes_atual,
                    semana=semana,
                    indice_linha=indice_linha
                ).first()

                if not producao:
                    producao = LinhaProducao(
                        usuario_id=usuario.id,
                        mes=mes_atual,
                        semana=semana,
                        indice_linha=indice_linha,
                        data_registro=datetime.utcnow()
                    )
                    db.session.add(producao)

                for campo in campos:
                    valor = request.form.get(f'{semana}_{i}_{campo}')
                    setattr(producao, campo, bool(valor))

                producao.observacao = request.form.get(f'{semana}_{i}_obs') or ""

        db.session.commit()
        flash('Produção salva com sucesso!')
        return redirect(url_for('registrar_producao', mes=mes_atual))

    processos_info = {
        semana: [
            LinhaProducao.query.filter_by(
                usuario_id=usuario.id,
                mes=mes_atual,
                semana=semana,
                indice_linha=i + 1
            ).first()
            for i in range(linhas)
        ]
        for semana in semanas
    }

    totais = {semana: {campo: 0 for campo in campos} for semana in semanas}
    for semana in semanas:
        producoes = LinhaProducao.query.filter_by(
            usuario_id=usuario.id,
            semana=semana,
            mes=mes_atual
        ).all()
        for p in producoes:
            for campo in campos:
                if getattr(p, campo):
                    totais[semana][campo] += 1

    total_feito = sum(sum(vals.values()) for vals in totais.values())
    meta = 112 if usuario.modalidade == 'teletrabalho' else 100
    percentual_meta = min(int((total_feito / meta) * 100), 100)

    return render_template(
        'registrar_producao.html',
        usuario=usuario,
        semanas=semanas,
        linhas=linhas,
        campos=campos,
        processos_info=processos_info,
        totais=totais,
        total_feito=total_feito,
        percentual_meta=percentual_meta,
        meta=meta,
        mes_atual=mes_atual,
        mes_anterior=mes_anterior,
        mes_posterior=mes_posterior
    )

@app.template_filter('get_attr')
def get_attr(obj, name):
    return getattr(obj, name, None)


@app.route('/painel-estagiarias', methods=['GET', 'POST'])
@login_required
def painel_estagiarias():
    if current_user.tipo != 'estagiaria':
        flash('Acesso não autorizado.')
        return redirect(url_for('index'))

    analistas_presencial = Usuario.query.filter_by(tipo='analista', modalidade='presencial').all()
    analistas_teletrabalho = Usuario.query.filter_by(tipo='analista', modalidade='teletrabalho').all()

    analista_id = request.args.get('analista_id') or request.form.get('analista_id')
    usuario_selecionado = Usuario.query.get(analista_id) if analista_id else None

    mes = request.args.get('mes') or request.form.get('mes') or 'Junho'
    ano = 2025
    meses = ['Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    mes_index = meses.index(mes)
    semanas = gerar_semanas(mes_index + 6, ano)
    linhas = 33 if usuario_selecionado and usuario_selecionado.modalidade == 'teletrabalho' else 28

    campos = ['numero_processo', 'requerente', 'fase']
    campos_checkbox = [
        'averbacao', 'desaverbacao', 'conf_av_desav', 'ctc',
        'conf_ctc', 'dtc', 'conf_dtc', 'in_68', 'dpor',
        'registro_atos', 'ag_completar', 'outros'
    ]

    if request.method == 'POST' and usuario_selecionado:
        for semana in semanas:
            for i in range(linhas):
                producao = LinhaProducao.query.filter_by(usuario_id=usuario_selecionado.id, semana=semana, mes=mes).offset(i).first()
                if not producao:
                    producao = LinhaProducao(
                        usuario_id=usuario_selecionado.id,
                        mes=mes,
                        semana=semana,
                        data_registro=datetime.utcnow()
                    )
                    db.session.add(producao)

                producao.numero_processo = request.form.get(f'{semana}_{i}_numero_processo') or ""
                producao.requerente = request.form.get(f'{semana}_{i}_requerente') or ""
                producao.fase = request.form.get(f'{semana}_{i}_fase') or ""
                producao.observacao = request.form.get(f'{semana}_{i}_obs') or ""

                for campo in campos_checkbox:
                    producao_valor = request.form.get(f'{semana}_{i}_{campo}')
                    setattr(producao, campo, producao_valor is not None)

        db.session.commit()
        flash('Edições salvas com sucesso!')

    processos_info = {}
    if usuario_selecionado:
        processos_info = {
            semana: [
                LinhaProducao.query.filter_by(usuario_id=usuario_selecionado.id, semana=semana, mes=mes).offset(i).first()
                for i in range(linhas)
            ]
            for semana in semanas
        }

    return render_template(
        'painel_estagiarias.html',
        analistas_presencial=analistas_presencial,
        analistas_teletrabalho=analistas_teletrabalho,
        processos_info=processos_info,
        semanas=semanas,
        linhas=linhas,
        campos=campos,
        usuario_selecionado=usuario_selecionado,
        mes=mes
    )

@app.route('/relatorio-geral')
@login_required
def relatorio_geral():
    if 'usuario_id' not in session or session['usuario_tipo'] == 'analista':
        flash('Acesso não autorizado.')
        return redirect(url_for('index'))

    ano = 2025
    meses = ['Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    campos = [
        'averbacao', 'desaverbacao', 'conf_av_desav', 'ctc',
        'conf_ctc', 'dtc', 'conf_dtc', 'in_68', 'dpor',
        'registro_atos', 'ag_completar', 'outros'
    ]

    totais_gerais = {mes: {campo: 0 for campo in campos} for mes in meses}

    for mes in meses:
        producoes = LinhaProducao.query.filter_by(mes=mes).all()
        for producao in producoes:
            for campo in campos:
                if getattr(producao, campo):
                    totais_gerais[mes][campo] += 1

    return render_template(
        'relatorio_geral.html',
        totais_gerais=totais_gerais,
        campos=campos,
        meses=meses
    )


@app.route('/editar-producao-lote/<int:analista_id>', methods=['POST'])
@login_required
def editar_producao_lote(analista_id):
    if 'usuario_id' not in session or session['usuario_tipo'] != 'estagiaria':
        flash('Acesso não autorizado.')
        return redirect(url_for('index'))

    usuario = Usuario.query.get_or_404(analista_id)
    mes = request.args.get('mes') or 'Junho'
    ano = 2025
    meses = ['Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    mes_index = meses.index(mes)
    semanas = gerar_semanas(mes_index + 6, ano)
    linhas = 33 if usuario.modalidade == 'teletrabalho' else 28

    for semana in semanas:
        for i in range(linhas):
            processo = LinhaProducao.query.filter_by(
                usuario_id=analista_id, semana=semana, mes=mes
            ).offset(i).first()

            if not processo:
                processo = LinhaProducao(
                    usuario_id=analista_id,
                    mes=mes,
                    semana=semana,
                    data_registro=datetime.utcnow()
                )
                db.session.add(processo)

            processo.numero_processo = request.form.get(f'{semana}_{i}_numero_processo') or ""
            processo.requerente = request.form.get(f'{semana}_{i}_requerente') or ""
            processo.fase = request.form.get(f'{semana}_{i}_fase') or ""

    db.session.commit()
    flash('Edições salvas com sucesso.')
    return redirect(url_for('painel_estagiarias', analista_id=analista_id, mes=mes))

if __name__ == '__main__':
    app.run(debug=True)
