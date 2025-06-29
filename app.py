import sqlite3
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import locale
import json
import requests
import os

# Define o locale para Português do Brasil para formatar nomes de meses
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    print("Locale pt_BR.UTF-8 não encontrado. Usando o padrão do sistema.")

app = Flask(__name__)
app.secret_key = 'sua-nova-chave-secreta-ainda-mais-segura'
DATABASE = 'financeiro_v2.db'


# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
def get_db():
    conn = sqlite3.connect(DATABASE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        db.execute("PRAGMA foreign_keys = ON")
        # Criação de tabelas
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS categorias (id INTEGER PRIMARY KEY, nome TEXT NOT NULL UNIQUE, tipo TEXT NOT NULL)')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY, tipo TEXT NOT NULL, onde TEXT, oque TEXT, valor REAL NOT NULL, data TEXT NOT NULL, parcelas INTEGER DEFAULT 1, forma_pagamento TEXT, id_conta INTEGER, FOREIGN KEY(id_conta) REFERENCES contas(id))')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS investimentos (id INTEGER PRIMARY KEY, tipo TEXT NOT NULL, destino TEXT NOT NULL, valor REAL NOT NULL, data TEXT NOT NULL)')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS entradas (id INTEGER PRIMARY KEY, descricao TEXT NOT NULL, data TEXT NOT NULL, id_conta INTEGER, FOREIGN KEY(id_conta) REFERENCES contas(id))')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS itens_entrada (id INTEGER PRIMARY KEY, id_entrada INTEGER NOT NULL, tipo TEXT NOT NULL, descricao TEXT NOT NULL, valor REAL NOT NULL, FOREIGN KEY (id_entrada) REFERENCES entradas (id) ON DELETE CASCADE)')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS contas_fixas (id INTEGER PRIMARY KEY, descricao TEXT NOT NULL, valor REAL NOT NULL, dia_vencimento INTEGER NOT NULL, tipo_valor TEXT NOT NULL, categoria_gasto TEXT NOT NULL, ativa BOOLEAN NOT NULL DEFAULT 1)')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS orcamento (id INTEGER PRIMARY KEY, categoria TEXT NOT NULL, valor_planejado REAL NOT NULL, mes INTEGER NOT NULL, ano INTEGER NOT NULL, UNIQUE(categoria, mes, ano))')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS contas (id INTEGER PRIMARY KEY, nome TEXT NOT NULL UNIQUE, saldo REAL NOT NULL DEFAULT 0.0)')

        # Adiciona a coluna 'id_conta' à tabela 'gastos' se ela não existir
        try:
            cursor.execute('ALTER TABLE gastos ADD COLUMN id_conta INTEGER REFERENCES contas(id)')
            cursor.execute('ALTER TABLE entradas ADD COLUMN id_conta INTEGER REFERENCES contas(id)')
        except sqlite3.OperationalError:
            pass  # Coluna já existe

        db.commit()
        cursor.execute("SELECT COUNT(id) FROM categorias")
        if cursor.fetchone()[0] == 0:
            categorias_padrao = [('Moradia', 'gasto'), ('Alimentação', 'gasto'), ('Transporte', 'gasto'),
                                 ('Lazer', 'gasto'), ('Saúde', 'gasto'), ('Educação', 'gasto'), ('Presente', 'gasto'),
                                 ('Outros', 'gasto'), ('Ações', 'investimento'), ('Criptomoedas', 'investimento'),
                                 ('Renda Fixa', 'investimento'), ('Imóveis', 'investimento'), ('Ouro', 'investimento'),
                                 ('Cartão de Crédito', 'pagamento'), ('PIX', 'pagamento'), ('Dinheiro', 'pagamento'),
                                 ('Boleto', 'pagamento')]
            cursor.executemany("INSERT INTO categorias (nome, tipo) VALUES (?, ?)", categorias_padrao)
            db.commit()
            print("Categorias padrão inseridas.")
        print("Banco de dados V2 inicializado.")


# --- FUNÇÃO AUXILIAR ---
def gerar_lancamentos_recorrentes(db, ano, mes):
    contas_recorrentes = db.execute("SELECT * FROM contas_fixas WHERE ativa = 1").fetchall()
    contas_pendentes_do_mes = []
    lancamentos_gerados = 0
    for conta in contas_recorrentes:
        try:
            data_gasto_obj = datetime.date(ano, mes, conta['dia_vencimento'])
        except ValueError:
            ultimo_dia_do_mes = (datetime.date(ano, mes, 1) + datetime.timedelta(days=31)).replace(
                day=1) - datetime.timedelta(days=1); data_gasto_obj = ultimo_dia_do_mes
        data_gasto_str = data_gasto_obj.strftime('%Y-%m-%d');
        identificador_gasto = f"[Conta Fixa] {conta['descricao']}"
        gasto_existente = db.execute("SELECT id FROM gastos WHERE oque = ? AND strftime('%Y-%m', data) = ?",
                                     (identificador_gasto, data_gasto_str[:7])).fetchone()
        if not gasto_existente:
            if conta['tipo_valor'] == 'fixo':
                db.execute(
                    'INSERT INTO gastos (tipo, onde, oque, valor, data, forma_pagamento) VALUES (?, ?, ?, ?, ?, ?)',
                    (conta['categoria_gasto'], 'Lançamento Automático', identificador_gasto, conta['valor'],
                     data_gasto_str, 'Recorrente')); lancamentos_gerados += 1
            else:
                contas_pendentes_do_mes.append(conta)
    if lancamentos_gerados > 0: db.commit(); flash(
        f'{lancamentos_gerados} conta(s) fixa(s) foram geradas para este mês.', 'info')
    return contas_pendentes_do_mes


# --- ROTAS PRINCIPAIS ---
@app.route('/')
def index():
    db = get_db();
    today_string = datetime.datetime.now().strftime('%Y-%m-%d');
    categorias_gasto = [c['nome'] for c in
                        db.execute("SELECT nome FROM categorias WHERE tipo = 'gasto' ORDER BY nome").fetchall()];
    categorias_investimento = [c['nome'] for c in db.execute(
        "SELECT nome FROM categorias WHERE tipo = 'investimento' ORDER BY nome").fetchall()];
    formas_pagamento = [p['nome'] for p in
                        db.execute("SELECT nome FROM categorias WHERE tipo = 'pagamento' ORDER BY nome").fetchall()]
    return render_template('index.html', **locals())


@app.route('/dashboard')
def dashboard():
    db = get_db();
    filtro_mes = request.args.get('mes', default=datetime.datetime.now().month, type=int);
    filtro_ano = request.args.get('ano', default=datetime.datetime.now().year, type=int);
    filtro_categoria = request.args.get('categoria', default='todos')
    contas_pendentes = gerar_lancamentos_recorrentes(db, filtro_ano, filtro_mes)
    data_inicio = datetime.date(filtro_ano, filtro_mes, 1);
    mes_fim = filtro_mes + 1;
    ano_fim = filtro_ano
    if mes_fim > 12: mes_fim = 1; ano_fim += 1
    data_fim_exclusive = datetime.date(ano_fim, mes_fim, 1)
    query = "SELECT * FROM gastos WHERE data >= ? AND data < ?";
    params = [data_inicio.strftime('%Y-%m-%d'), data_fim_exclusive.strftime('%Y-%m-%d')]
    if filtro_categoria != 'todos': query += " AND tipo = ?"; params.append(filtro_categoria)
    query += " ORDER BY data DESC"
    gastos_filtrados_rows = db.execute(query, params).fetchall();
    gastos_filtrados = [dict(row) for row in gastos_filtrados_rows]
    mes_ano_str = f"{filtro_ano}-{str(filtro_mes).zfill(2)}"
    total_receitas_brutas = db.execute(
        "SELECT SUM(valor) as total FROM itens_entrada WHERE tipo = 'receita' AND strftime('%Y-%m', (SELECT data FROM entradas WHERE id = id_entrada)) = ?",
        (mes_ano_str,)).fetchone()['total'] or 0
    total_gastos = sum(g['valor'] for g in gastos_filtrados)
    total_investido = db.execute("SELECT SUM(valor) as total FROM investimentos WHERE strftime('%Y-%m', data) = ?",
                                 (mes_ano_str,)).fetchone()['total'] or 0
    saldo_final = total_receitas_brutas - total_gastos - total_investido
    resumo_mes = {'receitas': total_receitas_brutas, 'gastos': total_gastos, 'investido': total_investido,
                  'saldo': saldo_final}
    gastos_por_categoria_rows = db.execute(
        "SELECT tipo, SUM(valor) as total FROM gastos WHERE data >= ? AND data < ? GROUP BY tipo",
        (data_inicio.strftime('%Y-%m-%d'), data_fim_exclusive.strftime('%Y-%m-%d'))).fetchall()
    gastos_por_categoria = [dict(row) for row in gastos_por_categoria_rows]
    orcamento_mes = db.execute("SELECT categoria, valor_planejado FROM orcamento WHERE ano = ? AND mes = ?",
                               (filtro_ano, filtro_mes)).fetchall()
    gastos_map = {g['tipo']: g['total'] for g in gastos_por_categoria};
    orcamento_map = {o['categoria']: o['valor_planejado'] for o in orcamento_mes}
    dados_orcamento = []
    categorias_orcamentaveis = db.execute("SELECT nome FROM categorias WHERE tipo = 'gasto' ORDER BY nome").fetchall()
    for cat in categorias_orcamentaveis:
        categoria = cat['nome'];
        planejado = orcamento_map.get(categoria, 0);
        gasto_atual = gastos_map.get(categoria, 0);
        restante = planejado - gasto_atual;
        percentual = (gasto_atual / planejado * 100) if planejado > 0 else 0
        dados_orcamento.append(
            {'categoria': categoria, 'planejado': planejado, 'gasto': gasto_atual, 'restante': restante,
             'percentual': min(percentual, 100)})
    categorias_gasto = [c['nome'] for c in categorias_orcamentaveis];
    formas_pagamento = [p['nome'] for p in
                        db.execute("SELECT nome FROM categorias WHERE tipo = 'pagamento' ORDER BY nome").fetchall()]
    nomes_meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro',
                   'Novembro', 'Dezembro'];
    meses_para_filtro = [{'num': i + 1, 'nome': nomes_meses[i]} for i in range(12)]
    return render_template('dashboard.html', gastos=gastos_filtrados, resumo_mes=resumo_mes,
                           categorias_gasto=categorias_gasto, formas_pagamento=formas_pagamento,
                           filtros_ativos={'mes': filtro_mes, 'ano': filtro_ano, 'categoria': filtro_categoria},
                           meses_para_filtro=meses_para_filtro, contas_pendentes=contas_pendentes,
                           dados_orcamento=dados_orcamento)


# --- ROTAS DE PROCESSAMENTO E GERENCIAMENTO ---
@app.route('/adicionar/gasto', methods=['POST'])
def adicionar_gasto():
    try:
        db = get_db();
        cursor = db.cursor()
        tipo, onde, oque, valor, data_str, forma_pagamento, parcelas = (request.form['tipo_gasto'],
                                                                        request.form.get('onde', ''),
                                                                        request.form.get('oque', ''),
                                                                        float(request.form['valor_gasto']),
                                                                        request.form['data_gasto'],
                                                                        request.form.get('forma_pagamento'),
                                                                        int(request.form.get('parcelas', 1)))
        if parcelas > 1:
            valor_parcela = round(valor / parcelas, 2);
            data_obj = datetime.datetime.strptime(data_str, '%Y-%m-%d').date()
            for i in range(parcelas):
                mes_atual = data_obj.month + i;
                ano_atual = data_obj.year + (mes_atual - 1) // 12;
                mes_atual = (mes_atual - 1) % 12 + 1
                try:
                    data_parcela = datetime.date(ano_atual, mes_atual, data_obj.day)
                except ValueError:
                    data_parcela = (datetime.date(ano_atual, mes_atual, 1) + datetime.timedelta(days=31)).replace(
                        day=1) - datetime.timedelta(days=1)
                oque_parcelado = f"{oque} ({i + 1}/{parcelas})"
                cursor.execute(
                    'INSERT INTO gastos (tipo, onde, oque, valor, data, parcelas, forma_pagamento) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (tipo, onde, oque_parcelado, valor_parcela, data_parcela.strftime('%Y-%m-%d'), 1, forma_pagamento))
        else:
            cursor.execute(
                'INSERT INTO gastos (tipo, onde, oque, valor, data, parcelas, forma_pagamento) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (tipo, onde, oque, valor, data_str, 1, forma_pagamento))
        db.commit();
        flash(f'Gasto "{oque}" adicionado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao adicionar gasto: {e}', 'danger'); print(f"ERRO em adicionar_gasto: {e}")
    return redirect(url_for('index'))


@app.route('/adicionar/investimento', methods=['POST'])
def adicionar_investimento():
    try:
        db = get_db(); db.execute('INSERT INTO investimentos (tipo, destino, valor, data) VALUES (?, ?, ?, ?)',
                                  (request.form['tipo_investimento'], request.form['destino'],
                                   float(request.form['valor_investimento']),
                                   request.form['data_investimento'])); db.commit(); flash(
            'Investimento adicionado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao adicionar investimento: {e}', 'danger')
    return redirect(url_for('index'))


@app.route('/adicionar/entrada', methods=['POST'])
def adicionar_entrada():
    try:
        db = get_db();
        cursor = db.cursor()
        cursor.execute('INSERT INTO entradas (descricao, data) VALUES (?, ?)',
                       (request.form['descricao_entrada'], request.form['data_entrada']));
        id_entrada = cursor.lastrowid
        receitas_desc, receitas_valor = request.form.getlist('receita_desc[]'), request.form.getlist('receita_valor[]')
        for desc, valor in zip(receitas_desc, receitas_valor):
            if desc and valor: cursor.execute(
                'INSERT INTO itens_entrada (id_entrada, tipo, descricao, valor) VALUES (?, ?, ?, ?)',
                (id_entrada, 'receita', desc, float(valor)))
        descontos_desc, descontos_valor = request.form.getlist('desconto_desc[]'), request.form.getlist(
            'desconto_valor[]')
        for desc, valor in zip(descontos_desc, descontos_valor):
            if desc and valor: cursor.execute(
                'INSERT INTO itens_entrada (id_entrada, tipo, descricao, valor) VALUES (?, ?, ?, ?)',
                (id_entrada, 'desconto', desc, float(valor)))
        db.commit();
        flash('Entrada adicionada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao adicionar entrada: {e}', 'danger')
    return redirect(url_for('index'))


@app.route('/editar/gasto/<int:id>', methods=['POST'])
def editar_gasto(id):
    try:
        db = get_db();
        tipo = request.form.get('tipo');
        onde = request.form.get('onde');
        oque = request.form.get('oque');
        valor = float(request.form.get('valor'));
        data = request.form.get('data');
        forma_pagamento = request.form.get('forma_pagamento')
        db.execute(
            'UPDATE gastos SET tipo = ?, onde = ?, oque = ?, valor = ?, data = ?, forma_pagamento = ? WHERE id = ?',
            (tipo, onde, oque, valor, data, forma_pagamento, id));
        db.commit();
        flash('Gasto atualizado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar o gasto: {e}', 'danger'); print(f"ERRO em editar_gasto: {e}")
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/excluir/<string:tabela>/<int:id>', methods=['POST'])
def excluir_lancamento(tabela, id):
    if tabela not in ['gastos', 'investimentos', 'entradas']:
        flash('Tipo de lançamento inválido.', 'danger')
    else:
        try:
            db = get_db(); db.execute(f"DELETE FROM {tabela} WHERE id = ?", (id,)); db.commit(); flash(
                'Lançamento excluído com sucesso!', 'success')
        except Exception as e:
            flash(f'Erro ao excluir: {e}', 'danger')
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/lancar_pendencia', methods=['POST'])
def lancar_pendencia():
    try:
        db = get_db();
        valor = float(request.form['valor']);
        descricao = request.form['descricao'];
        categoria = request.form['categoria'];
        data = request.form['data'];
        identificador = f"[Conta Fixa] {descricao}"
        db.execute('INSERT INTO gastos (tipo, onde, oque, valor, data, forma_pagamento) VALUES (?, ?, ?, ?, ?, ?)',
                   (categoria, 'Lançamento de Pendência', identificador, valor, data, 'Recorrente'));
        db.commit()
        flash(f'Conta pendente "{descricao}" lançada!', 'success')
    except Exception as e:
        flash(f'Erro ao lançar pendência: {e}', 'danger')
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/categorias')
def gerenciar_categorias():
    db = get_db();
    cat_gastos = db.execute("SELECT * FROM categorias WHERE tipo = 'gasto' ORDER BY nome").fetchall();
    cat_investimentos = db.execute("SELECT * FROM categorias WHERE tipo = 'investimento' ORDER BY nome").fetchall();
    cat_pagamentos = db.execute("SELECT * FROM categorias WHERE tipo = 'pagamento' ORDER BY nome").fetchall()
    return render_template('gerenciar_categorias.html', gastos=cat_gastos, investimentos=cat_investimentos,
                           pagamentos=cat_pagamentos)


@app.route('/categorias/adicionar', methods=['POST'])
def adicionar_categoria():
    nome, tipo = request.form.get('nome'), request.form.get('tipo')
    if not nome or not tipo:
        flash('Nome e tipo são obrigatórios.', 'danger')
    else:
        try:
            db = get_db(); db.execute("INSERT INTO categorias (nome, tipo) VALUES (?, ?)",
                                      (nome, tipo)); db.commit(); flash(f'Categoria "{nome}" adicionada!', 'success')
        except sqlite3.IntegrityError:
            flash(f'A categoria "{nome}" já existe.', 'warning')
        except Exception as e:
            flash(f'Erro: {e}', 'danger')
    return redirect(url_for('gerenciar_categorias'))


@app.route('/categorias/excluir/<int:id>', methods=['POST'])
def excluir_categoria(id):
    try:
        db = get_db(); db.execute("DELETE FROM categorias WHERE id = ?", (id,)); db.commit(); flash(
            'Categoria excluída.', 'success')
    except Exception as e:
        flash(f'Erro ao excluir: {e}', 'danger')
    return redirect(url_for('gerenciar_categorias'))


@app.route('/contas')
def gerenciar_contas():
    db = get_db();
    contas = db.execute("SELECT * FROM contas ORDER BY nome").fetchall()
    return render_template('gerenciar_contas.html', contas=contas)


@app.route('/contas/adicionar', methods=['POST'])
def adicionar_conta():
    try:
        nome = request.form.get('nome');
        saldo_str = request.form.get('saldo')
        saldo = float(saldo_str) if saldo_str else 0.0
        if not nome:
            flash('O nome da conta é obrigatório.', 'danger')
        else:
            db = get_db(); db.execute("INSERT INTO contas (nome, saldo) VALUES (?, ?)",
                                      (nome, saldo)); db.commit(); flash(f'Conta "{nome}" adicionada com sucesso!',
                                                                         'success')
    except sqlite3.IntegrityError:
        flash(f'Já existe uma conta com o nome "{nome}".', 'warning')
    except Exception as e:
        flash(f'Erro ao adicionar conta: {e}', 'danger')
    return redirect(url_for('gerenciar_contas'))


@app.route('/contas/atualizar_saldo/<int:id>', methods=['POST'])
def atualizar_saldo(id):
    try:
        saldo = float(request.form.get('saldo'));
        db = get_db();
        db.execute("UPDATE contas SET saldo = ? WHERE id = ?", (saldo, id));
        db.commit();
        flash('Saldo atualizado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar saldo: {e}', 'danger')
    return redirect(url_for('gerenciar_contas'))


@app.route('/contas/excluir/<int:id>', methods=['POST'])
def excluir_conta(id):
    try:
        db = get_db(); db.execute("DELETE FROM contas WHERE id = ?", (id,)); db.commit(); flash(
            'Conta excluída com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir conta: {e}', 'danger')
    return redirect(url_for('gerenciar_contas'))


@app.route('/contas_fixas')
def gerenciar_contas_fixas():
    db = get_db();
    contas = db.execute("SELECT * FROM contas_fixas ORDER BY dia_vencimento").fetchall();
    categorias_gasto = [c['nome'] for c in
                        db.execute("SELECT nome FROM categorias WHERE tipo = 'gasto' ORDER BY nome").fetchall()]
    return render_template('contas_fixas.html', contas=contas, categorias_gasto=categorias_gasto)


@app.route('/contas_fixas/adicionar', methods=['POST'])
def adicionar_conta_fixa():
    try:
        valor = float(request.form.get('valor', 0)) if request.form.get('valor') else 0
        if request.form['tipo_valor'] == 'variavel': valor = 0
        db = get_db();
        db.execute(
            'INSERT INTO contas_fixas (descricao, valor, dia_vencimento, tipo_valor, categoria_gasto) VALUES (?, ?, ?, ?, ?)',
            (request.form['descricao'], valor, int(request.form['dia_vencimento']), request.form['tipo_valor'],
             request.form['categoria_gasto']));
        db.commit();
        flash('Conta fixa adicionada!', 'success')
    except Exception as e:
        flash(f'Erro ao adicionar conta: {e}', 'danger')
    return redirect(url_for('gerenciar_contas_fixas'))


@app.route('/contas_fixas/excluir/<int:id>', methods=['POST'])
def excluir_conta_fixa(id):
    try:
        db = get_db(); db.execute("DELETE FROM contas_fixas WHERE id = ?", (id,)); db.commit(); flash(
            'Conta fixa excluída.', 'success')
    except Exception as e:
        flash(f'Erro ao excluir conta: {e}', 'danger')
    return redirect(url_for('gerenciar_contas_fixas'))


@app.route('/entradas')
def listar_entradas():
    db = get_db();
    entradas = db.execute("SELECT * FROM entradas ORDER BY data DESC").fetchall()
    return render_template('listar_entradas.html', entradas=entradas)


@app.route('/editar/entrada/<int:id>', methods=['GET', 'POST'])
def editar_entrada(id):
    db = get_db()
    if request.method == 'POST':
        try:
            descricao_entrada = request.form['descricao_entrada'];
            data_entrada = request.form['data_entrada']
            db.execute('UPDATE entradas SET descricao = ?, data = ? WHERE id = ?',
                       (descricao_entrada, data_entrada, id))
            db.execute('DELETE FROM itens_entrada WHERE id_entrada = ?', (id,))
            receitas_desc, receitas_valor = request.form.getlist('receita_desc[]'), request.form.getlist(
                'receita_valor[]')
            for desc, valor in zip(receitas_desc, receitas_valor):
                if desc and valor: db.execute(
                    'INSERT INTO itens_entrada (id_entrada, tipo, descricao, valor) VALUES (?, ?, ?, ?)',
                    (id, 'receita', desc, float(valor)))
            descontos_desc, descontos_valor = request.form.getlist('desconto_desc[]'), request.form.getlist(
                'desconto_valor[]')
            for desc, valor in zip(descontos_desc, descontos_valor):
                if desc and valor: db.execute(
                    'INSERT INTO itens_entrada (id_entrada, tipo, descricao, valor) VALUES (?, ?, ?, ?)',
                    (id, 'desconto', desc, float(valor)))
            db.commit();
            flash('Entrada atualizada com sucesso!', 'success');
            return redirect(url_for('listar_entradas'))
        except Exception as e:
            flash(f'Erro ao atualizar entrada: {e}', 'danger'); return redirect(url_for('editar_entrada', id=id))
    entrada = db.execute("SELECT * FROM entradas WHERE id = ?", (id,)).fetchone();
    itens = db.execute("SELECT * FROM itens_entrada WHERE id_entrada = ? ORDER BY tipo", (id,)).fetchall()
    receitas = [item for item in itens if item['tipo'] == 'receita'];
    descontos = [item for item in itens if item['tipo'] == 'desconto']
    return render_template('editar_entrada.html', entrada=entrada, receitas=receitas, descontos=descontos)


@app.route('/orcamento', methods=['GET', 'POST'])
def orcamento():
    db = get_db()
    if request.method == 'POST':
        mes = int(request.form['mes']);
        ano = int(request.form['ano'])
        for categoria, valor in request.form.items():
            if categoria not in ['mes', 'ano']:
                valor_planejado = float(valor) if valor else 0
                cursor = db.cursor()
                cursor.execute(
                    'INSERT INTO orcamento (categoria, valor_planejado, mes, ano) VALUES (?, ?, ?, ?) ON CONFLICT(categoria, mes, ano) DO UPDATE SET valor_planejado = excluded.valor_planejado',
                    (categoria, valor_planejado, mes, ano))
        db.commit();
        flash('Orçamento salvo com sucesso!', 'success');
        return redirect(url_for('orcamento', mes=mes, ano=ano))
    filtro_mes = request.args.get('mes', default=datetime.datetime.now().month, type=int);
    filtro_ano = request.args.get('ano', default=datetime.datetime.now().year, type=int)
    categorias_gasto = db.execute("SELECT nome FROM categorias WHERE tipo = 'gasto' ORDER BY nome").fetchall()
    orcamento_atual_rows = db.execute("SELECT categoria, valor_planejado FROM orcamento WHERE ano = ? AND mes = ?",
                                      (filtro_ano, filtro_mes)).fetchall()
    orcamento_atual = {row['categoria']: row['valor_planejado'] for row in orcamento_atual_rows}
    nomes_meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro',
                   'Novembro', 'Dezembro'];
    meses_para_filtro = [{'num': i + 1, 'nome': nomes_meses[i]} for i in range(12)]
    return render_template('orcamento.html', categorias=[c['nome'] for c in categorias_gasto],
                           orcamento_atual=orcamento_atual, filtros_ativos={'mes': filtro_mes, 'ano': filtro_ano},
                           meses_para_filtro=meses_para_filtro)


# --- ROTAS DE INTELIGÊNCIA ARTIFICIAL ---
def chamar_gemini_api(extrato, categorias_gasto, categorias_entrada):
    print("--- CHAMANDO A API REAL DO GEMINI ---")
    API_KEY = os.getenv('GOOGLE_API_KEY')
    if not API_KEY:
        print("ERRO: Variável de ambiente GOOGLE_API_KEY não definida.")
        flash(
            "Erro de Configuração: A chave da API do Google não foi encontrada. Por favor, siga as instruções para configurar a variável de ambiente 'GOOGLE_API_KEY' no seu ambiente de desenvolvimento.",
            "danger")
        return []

    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    prompt = f"""
    Analise o seguinte extrato bancário. Para cada linha, determine se é uma entrada (crédito, valor positivo, PIX recebido) ou um gasto (débito, valor negativo, pagamento, compra).
    Ignore linhas que são apenas informativas, como saldos ou rendimentos automáticos que não sejam transações de utilizador.

    Para cada transação válida, extraia:
    1.  'tipo_transacao': Deve ser 'gasto' ou 'entrada'.
    2.  'data': A data da transação no formato AAAA-MM-DD. Assuma o ano corrente se não for especificado. Se não houver data, use a data de hoje: {datetime.date.today().strftime('%Y-%m-%d')}.
    3.  'descricao': Uma descrição curta e limpa da transação.
    4.  'valor': O valor numérico absoluto (sempre positivo).
    5.  'categoria_sugerida': 
        - Se for um 'gasto', sugira a categoria mais apropriada da lista de gastos: {', '.join(categorias_gasto)}. Use 'Outros' se nenhuma se encaixar.
        - Se for uma 'entrada', sugira a categoria mais apropriada da lista de entradas: {', '.join(categorias_entrada)}. Use 'Outras Receitas' se nenhuma se encaixar.

    O resultado deve ser um array de objetos JSON, seguindo estritamente o schema fornecido.

    Extrato:
    ---
    {extrato}
    ---
    """
    schema = {
        "type": "ARRAY", "items": {
            "type": "OBJECT", "properties": {
                "tipo_transacao": {"type": "STRING", "enum": ["gasto", "entrada"]},
                "data": {"type": "STRING", "description": "Data no formato AAAA-MM-DD"},
                "descricao": {"type": "STRING", "description": "Descrição da transação"},
                "valor": {"type": "NUMBER", "description": "Valor numérico absoluto da transação"},
                "categoria_sugerida": {"type": "STRING", "description": "Categoria sugerida"}
            }, "required": ["tipo_transacao", "data", "descricao", "valor", "categoria_sugerida"]
        }
    }
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"response_mime_type": "application/json", "response_schema": schema}}

    try:
        response = requests.post(API_URL, json=payload, headers={'Content-Type': 'application/json'})
        if response.status_code == 403:
            print("ERRO 403: Acesso Proibido. Verifique a chave da API e as permissões do projeto.")
            flash(
                "Erro de permissão (403): Não foi possível aceder à IA. Verifique se a sua API Key é válida e se a 'Generative Language API' está ativada no seu projeto Google Cloud.",
                "danger")
            return []
        response.raise_for_status()
        response_json = response.json();
        print("Resposta da API recebida:", response_json)
        content_text = response_json['candidates'][0]['content']['parts'][0]['text']
        transacoes = json.loads(content_text)
        return transacoes
    except requests.exceptions.RequestException as e:
        print(f"Erro na chamada da API: {e}"); flash(f"Erro de comunicação com a API: {e}", "danger")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"Erro ao processar a resposta da API: {e}"); flash(
            "A resposta da IA não veio no formato esperado. Tente novamente.", "danger")
    return []


@app.route('/ia/importar', methods=['GET', 'POST'])
def importar_extrato():
    db = get_db()
    if request.method == 'POST':
        extrato_texto = request.form.get('extrato')
        id_conta = request.form.get('id_conta')
        if not extrato_texto or not id_conta:
            flash('É necessário selecionar uma conta e colar o texto do extrato.', 'warning')
            return redirect(url_for('importar_extrato'))

        categorias_gasto = [c['nome'] for c in
                            db.execute("SELECT nome FROM categorias WHERE tipo = 'gasto'").fetchall()]
        categorias_entrada = ['Salário', 'Aluguel Recebido', 'Reembolso', 'Venda', 'Outras Receitas']  # Exemplo

        transacoes_extraidas = chamar_gemini_api(extrato_texto, categorias_gasto, categorias_entrada)

        if not transacoes_extraidas:
            flash(
                'A IA não conseguiu extrair nenhuma transação do texto fornecido. Verifique o extrato e tente novamente.',
                'warning')
            return redirect(url_for('importar_extrato'))

        session['transacoes_para_revisar'] = transacoes_extraidas
        session['id_conta_importacao'] = id_conta

        return redirect(url_for('revisar_importacao'))

    contas = db.execute("SELECT * FROM contas ORDER BY nome").fetchall()
    return render_template('importar_extrato.html', contas=contas)


@app.route('/ia/revisar')
def revisar_importacao():
    transacoes = session.get('transacoes_para_revisar', [])
    if not transacoes: flash('Nenhuma transação para revisar. Por favor, importe um extrato primeiro.',
                             'warning'); return redirect(url_for('importar_extrato'))
    db = get_db();
    categorias_gasto = [c['nome'] for c in
                        db.execute("SELECT nome FROM categorias WHERE tipo = 'gasto' ORDER BY nome").fetchall()];
    categorias_entrada = ['Salário', 'Aluguel Recebido', 'Reembolso', 'Venda', 'Outras Receitas']
    return render_template('revisar_importacao.html', transacoes=transacoes, categorias_gasto=categorias_gasto,
                           categorias_entrada=categorias_entrada)


@app.route('/ia/salvar', methods=['POST'])
def salvar_importacao():
    try:
        db = get_db()
        id_conta = session.get('id_conta_importacao')
        if not id_conta: flash("Sessão expirada ou conta não selecionada. Tente novamente.", "danger"); return redirect(
            url_for('importar_extrato'))

        tipos_transacao = request.form.getlist('tipo_transacao')
        descricoes = request.form.getlist('descricao')
        valores = request.form.getlist('valor')
        datas = request.form.getlist('data')
        categorias = request.form.getlist('categoria')

        lancamentos_salvos = 0
        for i in range(len(descricoes)):
            if f'incluir_{i}' in request.form:
                tipo = tipos_transacao[i]
                if tipo == 'gasto':
                    db.execute(
                        'INSERT INTO gastos (tipo, onde, oque, valor, data, forma_pagamento, parcelas, id_conta) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        (categorias[i], descricoes[i], 'Importado via IA', float(valores[i]), datas[i],
                         'Débito em Conta', 1, id_conta))
                elif tipo == 'entrada':
                    cursor = db.cursor()
                    cursor.execute('INSERT INTO entradas (descricao, data, id_conta) VALUES (?, ?, ?)',
                                   (categorias[i], datas[i], id_conta))
                    id_entrada = cursor.lastrowid
                    cursor.execute('INSERT INTO itens_entrada (id_entrada, tipo, descricao, valor) VALUES (?, ?, ?, ?)',
                                   (id_entrada, 'receita', descricoes[i], float(valores[i])))
                lancamentos_salvos += 1

        db.commit()
        flash(f'{lancamentos_salvos} lançamentos foram salvos com sucesso!', 'success')
    except Exception as e:
        flash(f'Ocorreu um erro ao salvar os lançamentos: {e}', 'danger'); print(f"ERRO em salvar_importacao: {e}")

    session.pop('transacoes_para_revisar', None)
    session.pop('id_conta_importacao', None)

    return redirect(url_for('dashboard'))


# --- ROTAS DE API (GRÁFICOS) ---
@app.route('/api/dados/gastos_por_categoria')
def api_gastos_por_categoria():
    db = get_db();
    filtro_mes = request.args.get('mes', default=datetime.datetime.now().month, type=int);
    filtro_ano = request.args.get('ano', default=datetime.datetime.now().year, type=int)
    data_inicio = datetime.date(filtro_ano, filtro_mes, 1);
    mes_fim = filtro_mes + 1;
    ano_fim = filtro_ano
    if mes_fim > 12: mes_fim = 1; ano_fim += 1
    data_fim_exclusive = datetime.date(ano_fim, mes_fim, 1)
    dados = db.execute(
        "SELECT tipo, SUM(valor) as total FROM gastos WHERE data >= ? AND data < ? GROUP BY tipo ORDER BY total DESC",
        (data_inicio.strftime('%Y-%m-%d'), data_fim_exclusive.strftime('%Y-%m-%d'))).fetchall()
    return jsonify({'labels': [d['tipo'] for d in dados], 'data': [d['total'] for d in dados]})


@app.route('/api/dados/fluxo_mensal')
def api_fluxo_mensal():
    db = get_db();
    ano = request.args.get('ano', default=datetime.datetime.now().year, type=int)
    receitas = db.execute(
        "SELECT strftime('%m', e.data) as mes, SUM(ie.valor) as total FROM entradas e JOIN itens_entrada ie ON e.id = ie.id_entrada WHERE ie.tipo = 'receita' AND strftime('%Y', e.data) = ? GROUP BY mes",
        (str(ano),)).fetchall()
    gastos = db.execute(
        "SELECT strftime('%m', data) as mes, SUM(valor) as total FROM gastos WHERE strftime('%Y', data) = ? GROUP BY mes",
        (str(ano),)).fetchall()
    meses_labels = [datetime.date(ano, i, 1).strftime('%b').capitalize() for i in range(1, 13)];
    dados_receitas = [0] * 12;
    dados_gastos = [0] * 12
    for r in receitas: dados_receitas[int(r['mes']) - 1] = r['total']
    for g in gastos: dados_gastos[int(g['mes']) - 1] = g['total']
    return jsonify({'labels': meses_labels, 'receitas': dados_receitas, 'gastos': dados_gastos})


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0')

