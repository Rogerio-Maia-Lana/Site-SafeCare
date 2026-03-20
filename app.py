from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2 import IntegrityError
from database import get_db, init_db
from auth import login_required, cuidador_required, familiar_required

app = Flask(__name__)
app.secret_key = __import__("os").getenv("SECRET_KEY", "safecare_secret")

DEFAULT_USERS = [
    {"nome": "cuidador", "email": "cuidador@gmail.com", "senha": "123456", "tipo": "cuidador"},
    {"nome": "familiar", "email": "familiar@gmail.com", "senha": "123456", "tipo": "familiar"},
]


def ensure_default_users():
    try:
        db = get_db()
        cursor = db.cursor()
        for usuario in DEFAULT_USERS:
            cursor.execute("SELECT id FROM usuarios WHERE email = %s", (usuario["email"],))
            existente = cursor.fetchone()
            if existente:
                continue
            cursor.execute(
                "INSERT INTO usuarios (nome, email, senha, tipo) VALUES (%s, %s, %s, %s)",
                (
                    usuario["nome"],
                    usuario["email"],
                    generate_password_hash(usuario["senha"]),
                    usuario["tipo"],
                ),
            )
        db.commit()
        cursor.close()
        db.close()
    except Exception:
        pass


@app.before_request
def bootstrap_defaults():
    if not app.config.get("DB_READY"):
        init_db()
        ensure_default_users()
        app.config["DB_READY"] = True



def saudacao_por_horario():
    hora = __import__("datetime").datetime.now().hour
    if hora < 12:
        return "Bom dia"
    if hora < 18:
        return "Boa tarde"
    return "Boa noite"


def montar_resumo_pacientes(pacientes, tarefas, ocorrencias, autorizacoes=None):
    autorizacoes = autorizacoes or []
    tarefas_por_paciente = {}
    for tarefa in tarefas:
        pid = tarefa.get("paciente_id")
        tarefas_por_paciente.setdefault(pid, []).append(tarefa)

    ocorrencias_por_paciente = {}
    for ocorrencia in ocorrencias:
        pid = ocorrencia.get("paciente_id")
        if pid not in ocorrencias_por_paciente:
            ocorrencias_por_paciente[pid] = ocorrencia

    autorizacoes_por_paciente = {}
    for autorizacao in autorizacoes:
        pid = autorizacao.get("paciente_id")
        autorizacoes_por_paciente[pid] = autorizacoes_por_paciente.get(pid, 0) + 1

    cards = []
    hoje = date.today().isoformat()
    for paciente in pacientes:
        pid = paciente["id"]
        lista_tarefas = tarefas_por_paciente.get(pid, [])
        tarefas_hoje = [t for t in lista_tarefas if t.get("data") == hoje]
        concluidas = sum(1 for t in lista_tarefas if t.get("concluida") or t.get("status") == "concluida")
        pendentes = len(lista_tarefas) - concluidas
        progresso = int((concluidas / len(lista_tarefas)) * 100) if lista_tarefas else 0
        cards.append({
            **paciente,
            "total_tarefas": len(lista_tarefas),
            "tarefas_hoje": len(tarefas_hoje),
            "progresso": progresso,
            "pendentes": pendentes,
            "concluidas": concluidas,
            "ultima_ocorrencia": ocorrencias_por_paciente.get(pid),
            "familiares_total": autorizacoes_por_paciente.get(pid, 0),
        })
    return cards


def montar_metricas_dashboard(tarefas, notificacoes, solicitacoes=None):
    solicitacoes = solicitacoes or []
    total = len(tarefas)
    concluidas = sum(1 for t in tarefas if t.get("concluida") or t.get("status") == "concluida")
    pendentes = total - concluidas
    progresso = int((concluidas / total) * 100) if total else 0
    hoje = date.today().isoformat()
    hoje_total = sum(1 for t in tarefas if t.get("data") == hoje)
    hoje_concluidas = sum(1 for t in tarefas if t.get("data") == hoje and (t.get("concluida") or t.get("status") == "concluida"))
    pendentes_convites = sum(1 for s in solicitacoes if s.get("status") == "pendente")
    nao_lidas = sum(1 for n in notificacoes if not n.get("lida"))
    return {
        "total_tarefas": total,
        "concluidas": concluidas,
        "pendentes": pendentes,
        "progresso": progresso,
        "hoje_total": hoje_total,
        "hoje_concluidas": hoje_concluidas,
        "hoje_pendentes": max(hoje_total - hoje_concluidas, 0),
        "pendentes_convites": pendentes_convites,
        "nao_lidas": nao_lidas,
    }


def fetch_all_dict(query, params=()):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    db.close()
    return rows


def criar_notificacao(cursor, usuario_id, titulo, mensagem, tipo):
    cursor.execute(
        """
        INSERT INTO notificacoes (usuario_id, titulo, mensagem, tipo)
        VALUES (%s, %s, %s, %s)
        """,
        (usuario_id, titulo, mensagem, tipo),
    )


@app.context_processor
def inject_user_context():
    return {
        "usuario_logado": "usuario_id" in session,
        "perfil_logado": session.get("perfil"),
        "usuario_id": session.get("usuario_id"),
    }


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "")

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user["senha"], senha):
            session["usuario_id"] = user["id"]
            session["perfil"] = user["tipo"]
            session["usuario_nome"] = user["nome"]

            if user["tipo"] == "cuidador":
                return redirect(url_for("dashboard_cuidador"))
            return redirect(url_for("dashboard_familiar"))

        flash("Credenciais inválidas.", "error")

    return render_template("login.html")


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha_raw = request.form.get("senha", "")
        perfil = request.form.get("perfil", "").strip()

        if not nome or not email or not senha_raw or perfil not in ["cuidador", "familiar"]:
            flash("Preencha todos os campos corretamente.", "error")
            return redirect(url_for("cadastro"))

        if len(senha_raw) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "error")
            return redirect(url_for("cadastro"))

        senha = generate_password_hash(senha_raw)
        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute(
                "INSERT INTO usuarios (nome, email, senha, tipo) VALUES (%s, %s, %s, %s)",
                (nome, email, senha, perfil),
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            flash("Este e-mail já está cadastrado.", "error")
            return redirect(url_for("cadastro"))
        finally:
            cursor.close()
            db.close()

        flash("Conta criada com sucesso.", "success")
        return redirect(url_for("login"))

    return render_template("cadastro.html")


@app.route("/cuidador")
@cuidador_required
def dashboard_cuidador():
    cuidador_id = session["usuario_id"]
    data_filtro = request.args.get("data", "").strip()
    tipo_filtro = request.args.get("tipo", "").strip()
    status_filtro = request.args.get("status", "").strip()
    paciente_filtro = request.args.get("paciente_id", "").strip()

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT id, nome, idade, observacoes, criado_em
        FROM pacientes
        WHERE cuidador_id = %s
        ORDER BY criado_em DESC
        """,
        (cuidador_id,),
    )
    pacientes = cursor.fetchall()

    query_tarefas = """
        SELECT
            t.id,
            t.descricao AS titulo,
            t.tipo,
            TO_CHAR(t.data, 'YYYY-MM-DD') AS data,
            t.concluida,
            p.nome AS paciente_nome,
            p.id AS paciente_id
        FROM tarefas t
        JOIN pacientes p ON p.id = t.paciente_id
        WHERE p.cuidador_id = %s
    """
    params_tarefas = [cuidador_id]

    if paciente_filtro:
        query_tarefas += " AND p.id = %s"
        params_tarefas.append(paciente_filtro)
    if data_filtro:
        query_tarefas += " AND t.data = %s"
        params_tarefas.append(data_filtro)
    if tipo_filtro:
        query_tarefas += " AND t.tipo = %s"
        params_tarefas.append(tipo_filtro)
    if status_filtro == "pendente":
        query_tarefas += " AND t.concluida = 0"
    elif status_filtro == "realizada":
        query_tarefas += " AND t.concluida = 1"

    query_tarefas += " ORDER BY t.data DESC, t.id DESC"
    cursor.execute(query_tarefas, tuple(params_tarefas))
    tarefas = cursor.fetchall()
    tarefas_pendentes = sorted([t for t in tarefas if not t["concluida"]], key=lambda t: (t.get("data") or "", t.get("id") or 0), reverse=True)[:10]

    cursor.execute(
        """
        SELECT
            o.id,
            TO_CHAR(o.criado_em, 'YYYY-MM-DD HH24:MI') AS data,
            p.nome AS paciente_nome,
            o.descricao,
            p.id AS paciente_id
        FROM ocorrencias o
        JOIN pacientes p ON p.id = o.paciente_id
        WHERE p.cuidador_id = %s
        ORDER BY o.criado_em DESC
        LIMIT 50
        """,
        (cuidador_id,),
    )
    ocorrencias = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            a.id,
            a.paciente_id,
            a.familiar_id,
            p.nome AS paciente_nome,
            u.nome AS familiar_nome,
            u.email AS familiar_email,
            TO_CHAR(a.criado_em, 'YYYY-MM-DD HH24:MI') AS criado_em
        FROM autorizacoes a
        JOIN pacientes p ON p.id = a.paciente_id
        JOIN usuarios u ON u.id = a.familiar_id
        WHERE p.cuidador_id = %s
        ORDER BY a.criado_em DESC
        """,
        (cuidador_id,),
    )
    autorizacoes = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            s.id,
            s.paciente_id,
            s.destinatario_id,
            s.mensagem,
            s.status,
            p.nome AS paciente_nome,
            u.nome AS familiar_nome,
            u.email AS familiar_email,
            TO_CHAR(s.criado_em, 'YYYY-MM-DD HH24:MI') AS criado_em,
            TO_CHAR(s.respondido_em, 'YYYY-MM-DD HH24:MI') AS respondido_em
        FROM solicitacoes_autorizacao s
        JOIN pacientes p ON p.id = s.paciente_id
        JOIN usuarios u ON u.id = s.destinatario_id
        WHERE s.remetente_id = %s
        ORDER BY s.criado_em DESC
        LIMIT 50
        """,
        (cuidador_id,),
    )
    solicitacoes_enviadas = cursor.fetchall()

    cursor.execute(
        """
        SELECT id, titulo, mensagem, tipo, lida,
               TO_CHAR(criado_em, 'YYYY-MM-DD HH24:MI') AS criado_em
        FROM notificacoes
        WHERE usuario_id = %s
        ORDER BY criado_em DESC
        LIMIT 20
        """,
        (cuidador_id,),
    )
    notificacoes = cursor.fetchall()

    cursor.execute(
        """
        SELECT 'diario' AS periodo,
               COUNT(*) AS total_tarefas,
               SUM(CASE WHEN concluida = 1 THEN 1 ELSE 0 END) AS concluidas
        FROM tarefas t
        JOIN pacientes p ON p.id = t.paciente_id
        WHERE p.cuidador_id = %s AND t.data = CURRENT_DATE
        UNION ALL
        SELECT 'semanal' AS periodo,
               COUNT(*) AS total_tarefas,
               SUM(CASE WHEN concluida = 1 THEN 1 ELSE 0 END) AS concluidas
        FROM tarefas t
        JOIN pacientes p ON p.id = t.paciente_id
        WHERE p.cuidador_id = %s AND t.data >= CURRENT_DATE - INTERVAL '7 days'
        UNION ALL
        SELECT 'mensal' AS periodo,
               COUNT(*) AS total_tarefas,
               SUM(CASE WHEN concluida = 1 THEN 1 ELSE 0 END) AS concluidas
        FROM tarefas t
        JOIN pacientes p ON p.id = t.paciente_id
        WHERE p.cuidador_id = %s
          AND DATE_TRUNC('month', t.data) = DATE_TRUNC('month', CURRENT_DATE)
        """,
        (cuidador_id, cuidador_id, cuidador_id),
    )
    relatorios_tarefas = cursor.fetchall()

    cursor.execute(
        """
        SELECT COUNT(*) AS total_pacientes FROM pacientes WHERE cuidador_id = %s
        """,
        (cuidador_id,),
    )
    total_pacientes = cursor.fetchone()["total_pacientes"]

    cursor.close()
    db.close()

    metricas = montar_metricas_dashboard(tarefas, notificacoes, solicitacoes_enviadas)
    pacientes_cards = montar_resumo_pacientes(pacientes, tarefas, ocorrencias, autorizacoes)

    return render_template(
        "cuidador.html",
        pacientes=pacientes,
        pacientes_cards=pacientes_cards,
        tarefas=tarefas,
        tarefas_pendentes=tarefas_pendentes,
        ocorrencias=ocorrencias,
        autorizacoes=autorizacoes,
        solicitacoes_enviadas=solicitacoes_enviadas,
        notificacoes=notificacoes,
        relatorios_tarefas=relatorios_tarefas,
        total_pacientes=total_pacientes,
        metricas=metricas,
        saudacao=saudacao_por_horario(),
        filtros={
            "data": data_filtro,
            "tipo": tipo_filtro,
            "status": status_filtro,
            "paciente_id": paciente_filtro,
        },
    )


@app.route("/cuidador/pacientes/novo", methods=["POST"])
@cuidador_required
def criar_paciente():
    nome = request.form.get("nome", "").strip()
    idade = request.form.get("idade", "").strip()
    observacoes = request.form.get("observacoes", "").strip()

    if not nome:
        flash("Informe o nome do paciente.", "error")
        return redirect(url_for("dashboard_cuidador"))

    idade_int = None
    if idade:
        try:
            idade_int = int(idade)
        except ValueError:
            flash("Idade inválida.", "error")
            return redirect(url_for("dashboard_cuidador"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        INSERT INTO pacientes (nome, idade, observacoes, cuidador_id)
        VALUES (%s, %s, %s, %s)
        """,
        (nome, idade_int, observacoes, session["usuario_id"]),
    )
    db.commit()
    cursor.close()
    db.close()

    flash("Paciente cadastrado com sucesso.", "success")
    return redirect(url_for("dashboard_cuidador"))


@app.route("/cuidador/pacientes/<int:paciente_id>/editar", methods=["POST"])
@cuidador_required
def editar_paciente(paciente_id):
    nome = request.form.get("nome", "").strip()
    idade = request.form.get("idade", "").strip()
    observacoes = request.form.get("observacoes", "").strip()

    if not nome:
        flash("Nome do paciente é obrigatório.", "error")
        return redirect(url_for("dashboard_cuidador"))

    idade_int = None
    if idade:
        try:
            idade_int = int(idade)
        except ValueError:
            flash("Idade inválida.", "error")
            return redirect(url_for("dashboard_cuidador"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        UPDATE pacientes
        SET nome = %s, idade = %s, observacoes = %s
        WHERE id = %s AND cuidador_id = %s
        """,
        (nome, idade_int, observacoes, paciente_id, session["usuario_id"]),
    )
    db.commit()
    cursor.close()
    db.close()

    flash("Paciente atualizado com sucesso.", "success")
    return redirect(url_for("dashboard_cuidador"))


@app.route("/cuidador/pacientes/<int:paciente_id>/excluir", methods=["POST"])
@cuidador_required
def excluir_paciente(paciente_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM pacientes WHERE id = %s AND cuidador_id = %s",
        (paciente_id, session["usuario_id"]),
    )
    db.commit()
    cursor.close()
    db.close()

    flash("Paciente excluído com sucesso.", "success")
    return redirect(url_for("dashboard_cuidador"))


@app.route("/cuidador/tarefas/nova", methods=["POST"])
@cuidador_required
def criar_tarefa():
    paciente_id = request.form.get("paciente_id", "").strip()
    descricao = request.form.get("descricao", "").strip()
    tipo = request.form.get("tipo", "").strip() or "rotina"
    data = request.form.get("data", "").strip()

    if not paciente_id or not descricao or not data:
        flash("Preencha paciente, descrição e data da tarefa.", "error")
        return redirect(url_for("dashboard_cuidador"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, nome FROM pacientes WHERE id = %s AND cuidador_id = %s",
        (paciente_id, session["usuario_id"]),
    )
    paciente = cursor.fetchone()
    if not paciente:
        cursor.close()
        db.close()
        flash("Paciente inválido ou não pertence ao seu perfil.", "error")
        return redirect(url_for("dashboard_cuidador"))

    cursor = db.cursor()
    cursor.execute(
        """
        INSERT INTO tarefas (paciente_id, descricao, tipo, data, concluida)
        VALUES (%s, %s, %s, %s, 0)
        """,
        (paciente_id, descricao, tipo, data),
    )
    db.commit()
    cursor.close()
    db.close()

    flash("Tarefa criada com sucesso.", "success")
    return redirect(url_for("dashboard_cuidador"))


@app.route("/cuidador/tarefas/<int:tarefa_id>/editar", methods=["POST"])
@cuidador_required
def editar_tarefa(tarefa_id):
    descricao = request.form.get("descricao", "").strip()
    tipo = request.form.get("tipo", "").strip() or "rotina"
    data = request.form.get("data", "").strip()

    if not descricao or not data:
        flash("Preencha descrição e data da tarefa.", "error")
        return redirect(url_for("dashboard_cuidador"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        UPDATE tarefas t
        JOIN pacientes p ON p.id = t.paciente_id
        SET t.descricao = %s, t.tipo = %s, t.data = %s
        WHERE t.id = %s AND p.cuidador_id = %s
        """,
        (descricao, tipo, data, tarefa_id, session["usuario_id"]),
    )
    db.commit()
    cursor.close()
    db.close()

    flash("Tarefa atualizada com sucesso.", "success")
    return redirect(url_for("dashboard_cuidador"))


@app.route("/cuidador/tarefas/<int:tarefa_id>/status", methods=["POST"])
@cuidador_required
def atualizar_status_tarefa(tarefa_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT t.id, t.concluida, p.nome AS paciente_nome, p.id AS paciente_id, p.cuidador_id
        FROM tarefas t
        JOIN pacientes p ON p.id = t.paciente_id
        WHERE t.id = %s AND p.cuidador_id = %s
        """,
        (tarefa_id, session["usuario_id"]),
    )
    tarefa = cursor.fetchone()
    if not tarefa:
        cursor.close()
        db.close()
        flash("Tarefa não encontrada.", "error")
        return redirect(url_for("dashboard_cuidador"))

    novo_status = 0 if tarefa["concluida"] else 1
    cursor = db.cursor()
    cursor.execute(
        """
        UPDATE tarefas t
        JOIN pacientes p ON p.id = t.paciente_id
        SET t.concluida = %s
        WHERE t.id = %s AND p.cuidador_id = %s
        """,
        (novo_status, tarefa_id, session["usuario_id"]),
    )

    if novo_status == 1:
        db_dict = db.cursor(dictionary=True)
        db_dict.execute(
            """
            SELECT a.familiar_id, p.nome AS paciente_nome
            FROM autorizacoes a
            JOIN pacientes p ON p.id = a.paciente_id
            WHERE a.paciente_id = %s
            """,
            (tarefa["paciente_id"],),
        )
        familiares = db_dict.fetchall()
        db_dict.close()
        for fam in familiares:
            criar_notificacao(
                cursor,
                fam["familiar_id"],
                "Tarefa realizada",
                f"Uma tarefa do paciente {fam['paciente_nome']} foi marcada como realizada.",
                "tarefa_realizada",
            )

    db.commit()
    cursor.close()
    db.close()

    flash("Status da tarefa atualizado.", "success")
    return redirect(url_for("dashboard_cuidador"))


@app.route("/cuidador/tarefas/<int:tarefa_id>/excluir", methods=["POST"])
@cuidador_required
def excluir_tarefa(tarefa_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        DELETE t FROM tarefas t
        JOIN pacientes p ON p.id = t.paciente_id
        WHERE t.id = %s AND p.cuidador_id = %s
        """,
        (tarefa_id, session["usuario_id"]),
    )
    db.commit()
    cursor.close()
    db.close()

    flash("Tarefa excluída com sucesso.", "success")
    return redirect(url_for("dashboard_cuidador"))


@app.route("/cuidador/ocorrencias/nova", methods=["POST"])
@cuidador_required
def criar_ocorrencia():
    paciente_id = request.form.get("paciente_id", "").strip()
    descricao = request.form.get("descricao", "").strip()

    if not paciente_id or not descricao:
        flash("Selecione o paciente e descreva a ocorrência.", "error")
        return redirect(url_for("dashboard_cuidador"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, nome FROM pacientes WHERE id = %s AND cuidador_id = %s",
        (paciente_id, session["usuario_id"]),
    )
    paciente = cursor.fetchone()
    if not paciente:
        cursor.close()
        db.close()
        flash("Paciente inválido ou não pertence ao seu perfil.", "error")
        return redirect(url_for("dashboard_cuidador"))

    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO ocorrencias (paciente_id, descricao) VALUES (%s, %s)",
        (paciente_id, descricao),
    )

    db_dict = db.cursor(dictionary=True)
    db_dict.execute(
        "SELECT familiar_id FROM autorizacoes WHERE paciente_id = %s",
        (paciente_id,),
    )
    familiares = db_dict.fetchall()
    db_dict.close()

    for fam in familiares:
        criar_notificacao(
            cursor,
            fam["familiar_id"],
            "Nova ocorrência registrada",
            f"Foi registrada uma nova ocorrência para o paciente {paciente['nome']}.",
            "ocorrencia",
        )

    db.commit()
    cursor.close()
    db.close()

    flash("Ocorrência registrada com sucesso.", "success")
    return redirect(url_for("dashboard_cuidador"))


@app.route("/cuidador/autorizacoes/enviar", methods=["POST"])
@cuidador_required
def enviar_solicitacao_autorizacao():
    paciente_id = request.form.get("paciente_id", "").strip()
    email_familiar = request.form.get("email_familiar", "").strip().lower()
    mensagem = request.form.get("mensagem", "").strip()

    if not paciente_id or not email_familiar:
        flash("Selecione um paciente e informe o e-mail do familiar.", "error")
        return redirect(url_for("dashboard_cuidador"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, nome FROM pacientes WHERE id = %s AND cuidador_id = %s",
        (paciente_id, session["usuario_id"]),
    )
    paciente = cursor.fetchone()
    if not paciente:
        cursor.close()
        db.close()
        flash("Paciente inválido.", "error")
        return redirect(url_for("dashboard_cuidador"))

    cursor.execute(
        "SELECT id, nome, email FROM usuarios WHERE email = %s AND tipo = 'familiar'",
        (email_familiar,),
    )
    familiar = cursor.fetchone()
    if not familiar:
        cursor.close()
        db.close()
        flash("Familiar não encontrado com esse e-mail.", "error")
        return redirect(url_for("dashboard_cuidador"))

    cursor.execute(
        """
        SELECT id FROM solicitacoes_autorizacao
        WHERE paciente_id = %s AND destinatario_id = %s AND status = 'pendente'
        """,
        (paciente_id, familiar["id"]),
    )
    duplicada = cursor.fetchone()
    if duplicada:
        cursor.close()
        db.close()
        flash("Já existe uma solicitação pendente para esse familiar e paciente.", "error")
        return redirect(url_for("dashboard_cuidador"))

    cursor2 = db.cursor()
    cursor2.execute(
        """
        INSERT INTO solicitacoes_autorizacao
        (paciente_id, remetente_id, destinatario_id, mensagem, status)
        VALUES (%s, %s, %s, %s, 'pendente')
        """,
        (paciente_id, session["usuario_id"], familiar["id"], mensagem),
    )
    criar_notificacao(
        cursor2,
        familiar["id"],
        "Nova solicitação de autorização",
        f"Você recebeu uma solicitação para acompanhar o paciente {paciente['nome']}.",
        "autorizacao_recebida",
    )
    db.commit()
    cursor2.close()
    cursor.close()
    db.close()

    flash("Solicitação enviada com sucesso.", "success")
    return redirect(url_for("dashboard_cuidador"))


@app.route("/familiar")
@familiar_required
def dashboard_familiar():
    familiar_id = session["usuario_id"]
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT p.id, p.nome, p.idade, p.observacoes, u.nome AS cuidador_nome
        FROM pacientes p
        JOIN autorizacoes a ON a.paciente_id = p.id
        JOIN usuarios u ON u.id = p.cuidador_id
        WHERE a.familiar_id = %s
        ORDER BY p.criado_em DESC
        """,
        (familiar_id,),
    )
    pacientes_autorizados = cursor.fetchall()

    cursor.execute(
        """
        SELECT t.id,
               t.descricao AS titulo,
               t.tipo,
               TO_CHAR(t.data, 'YYYY-MM-DD') AS data,
               CASE WHEN t.concluida = 1 THEN 'concluida' ELSE 'pendente' END AS status,
               p.nome AS paciente_nome,
               p.id AS paciente_id
        FROM tarefas t
        JOIN pacientes p ON p.id = t.paciente_id
        JOIN autorizacoes a ON a.paciente_id = p.id
        WHERE a.familiar_id = %s
        ORDER BY t.data DESC, t.id DESC
        """,
        (familiar_id,),
    )
    tarefas = cursor.fetchall()

    cursor.execute(
        """
        SELECT o.id,
               TO_CHAR(o.criado_em, 'YYYY-MM-DD HH24:MI') AS data,
               p.nome AS paciente_nome,
               o.descricao,
               p.id AS paciente_id,
               'Ocorrência' AS tipo
        FROM ocorrencias o
        JOIN pacientes p ON p.id = o.paciente_id
        JOIN autorizacoes a ON a.paciente_id = p.id
        WHERE a.familiar_id = %s
        ORDER BY o.criado_em DESC
        LIMIT 50
        """,
        (familiar_id,),
    )
    ocorrencias = cursor.fetchall()

    cursor.execute(
        """
        SELECT s.id, s.mensagem, s.status,
               TO_CHAR(s.criado_em, 'YYYY-MM-DD HH24:MI') AS criado_em,
               TO_CHAR(s.respondido_em, 'YYYY-MM-DD HH24:MI') AS respondido_em,
               p.nome AS paciente_nome,
               u.nome AS cuidador_nome
        FROM solicitacoes_autorizacao s
        JOIN pacientes p ON p.id = s.paciente_id
        JOIN usuarios u ON u.id = s.remetente_id
        WHERE s.destinatario_id = %s
        ORDER BY s.criado_em DESC
        LIMIT 50
        """,
        (familiar_id,),
    )
    solicitacoes = cursor.fetchall()

    cursor.execute(
        """
        SELECT id, titulo, mensagem, tipo, lida,
               TO_CHAR(criado_em, 'YYYY-MM-DD HH24:MI') AS criado_em
        FROM notificacoes
        WHERE usuario_id = %s
        ORDER BY criado_em DESC
        LIMIT 20
        """,
        (familiar_id,),
    )
    notificacoes = cursor.fetchall()

    cursor.execute(
        """
        SELECT 'diario' AS periodo,
               COUNT(*) AS total_tarefas,
               SUM(CASE WHEN concluida = 1 THEN 1 ELSE 0 END) AS concluidas
        FROM tarefas t
        JOIN autorizacoes a ON a.paciente_id = t.paciente_id
        WHERE a.familiar_id = %s AND t.data = CURRENT_DATE
        UNION ALL
        SELECT 'semanal' AS periodo,
               COUNT(*) AS total_tarefas,
               SUM(CASE WHEN concluida = 1 THEN 1 ELSE 0 END) AS concluidas
        FROM tarefas t
        JOIN autorizacoes a ON a.paciente_id = t.paciente_id
        WHERE a.familiar_id = %s AND t.data >= CURRENT_DATE - INTERVAL '7 days'
        UNION ALL
        SELECT 'mensal' AS periodo,
               COUNT(*) AS total_tarefas,
               SUM(CASE WHEN concluida = 1 THEN 1 ELSE 0 END) AS concluidas
        FROM tarefas t
        JOIN autorizacoes a ON a.paciente_id = t.paciente_id
        WHERE a.familiar_id = %s
          AND DATE_TRUNC('month', t.data) = DATE_TRUNC('month', CURRENT_DATE)
        """,
        (familiar_id, familiar_id, familiar_id),
    )
    relatorios_tarefas = cursor.fetchall()

    cursor.close()
    db.close()

    metricas = montar_metricas_dashboard(tarefas, notificacoes, solicitacoes)
    pacientes_cards = montar_resumo_pacientes(pacientes_autorizados, tarefas, ocorrencias)

    return render_template(
        "familiar.html",
        pacientes_autorizados=pacientes_autorizados,
        pacientes_cards=pacientes_cards,
        tarefas=tarefas,
        ocorrencias=ocorrencias,
        solicitacoes=solicitacoes,
        notificacoes=notificacoes,
        relatorios_tarefas=relatorios_tarefas,
        metricas=metricas,
        saudacao=saudacao_por_horario(),
    )


@app.route("/familiar/autorizacoes/<int:solicitacao_id>/aceitar", methods=["POST"])
@familiar_required
def aceitar_autorizacao(solicitacao_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT s.*, p.nome AS paciente_nome, u.id AS cuidador_id
        FROM solicitacoes_autorizacao s
        JOIN pacientes p ON p.id = s.paciente_id
        JOIN usuarios u ON u.id = s.remetente_id
        WHERE s.id = %s AND s.destinatario_id = %s AND s.status = 'pendente'
        """,
        (solicitacao_id, session["usuario_id"]),
    )
    solicitacao = cursor.fetchone()
    if not solicitacao:
        cursor.close()
        db.close()
        flash("Solicitação inválida.", "error")
        return redirect(url_for("dashboard_familiar"))

    cursor2 = db.cursor()
    cursor2.execute(
        """
        UPDATE solicitacoes_autorizacao
        SET status = 'aceita', respondido_em = NOW()
        WHERE id = %s
        """,
        (solicitacao_id,),
    )
    cursor2.execute(
        "INSERT INTO autorizacoes (paciente_id, familiar_id) VALUES (%s, %s) ON CONFLICT (paciente_id, familiar_id) DO NOTHING",
        (solicitacao["paciente_id"], session["usuario_id"]),
    )
    criar_notificacao(
        cursor2,
        solicitacao["remetente_id"],
        "Autorização aceita",
        f"O familiar aceitou acompanhar o paciente {solicitacao['paciente_nome']}.",
        "autorizacao_aceita",
    )
    db.commit()
    cursor2.close()
    cursor.close()
    db.close()

    flash("Autorização aceita com sucesso.", "success")
    return redirect(url_for("dashboard_familiar"))


@app.route("/familiar/autorizacoes/<int:solicitacao_id>/recusar", methods=["POST"])
@familiar_required
def recusar_autorizacao(solicitacao_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT s.*, p.nome AS paciente_nome
        FROM solicitacoes_autorizacao s
        JOIN pacientes p ON p.id = s.paciente_id
        WHERE s.id = %s AND s.destinatario_id = %s AND s.status = 'pendente'
        """,
        (solicitacao_id, session["usuario_id"]),
    )
    solicitacao = cursor.fetchone()
    if not solicitacao:
        cursor.close()
        db.close()
        flash("Solicitação inválida.", "error")
        return redirect(url_for("dashboard_familiar"))

    cursor2 = db.cursor()
    cursor2.execute(
        """
        UPDATE solicitacoes_autorizacao
        SET status = 'recusada', respondido_em = NOW()
        WHERE id = %s
        """,
        (solicitacao_id,),
    )
    criar_notificacao(
        cursor2,
        solicitacao["remetente_id"],
        "Autorização recusada",
        f"O familiar recusou o convite para acompanhar o paciente {solicitacao['paciente_nome']}.",
        "autorizacao_recusada",
    )
    db.commit()
    cursor2.close()
    cursor.close()
    db.close()

    flash("Solicitação recusada.", "success")
    return redirect(url_for("dashboard_familiar"))


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logout realizado com sucesso.", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    ensure_default_users()
    app.run(debug=False)
