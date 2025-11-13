from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import date, datetime
from database import OrdemServico, Session, Status
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)


@app.route('/')
def index():
    session = Session()
    hoje = date.today()

    # pega as OS de hoje + faltantes de dias anteriores
    ordens = session.query(OrdemServico).filter(
        (OrdemServico.data_relatorio == hoje) |
        ((OrdemServico.status == Status.faltante) & (OrdemServico.data_relatorio < hoje))
    ).all()
    session.close()

    # separa recebidas e faltantes
    recebidas = [o for o in ordens if o.status == Status.recebida]
    faltantes = [o for o in ordens if o.status == Status.faltante]

    return render_template('index.html', 
                           recebidas=recebidas,
                           faltantes=faltantes,
                           hoje=hoje)



@app.route('/add', methods=['POST'])
def add_ordem():
    session = Session()
    numero = request.form['numero_os']
    cliente = request.form['cliente']
    vendedor = request.form['vendedor']
    status = request.form['status']
    observacao = request.form.get('observacao', '')

    nova_os = OrdemServico(
        numero_os=numero,
        cliente=cliente,
        vendedor=vendedor,
        status=Status[status],
        observacao=observacao,
        data_relatorio=date.today(),
        data_hora_registro=datetime.now()
    )

    session.add(nova_os)
    session.commit()
    session.close()
    return redirect(url_for('index'))

@app.route('/update/<int:os_id>')
def update_os(os_id):
    session = Session()
    os_item = session.query(OrdemServico).get(os_id)
    os_item.status = Status.recebida
    os_item.data_relatorio = date.today()
    session.commit()
    session.close()
    return redirect(url_for('index'))

@app.route('/report')
def gerar_relatorio():
    import csv, os
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    session = Session()
    hoje = date.today()

    # Pega todas as OS do dia atual
    ordens = session.query(OrdemServico).filter(
        OrdemServico.data_relatorio == hoje
    ).all()
    session.close()

    recebidas = [o for o in ordens if o.status == Status.recebida]
    faltantes = [o for o in ordens if o.status == Status.faltante]

    # Cria pasta relatorios se não existir
    relatorio_dir = os.path.join(os.getcwd(), "relatorios")
    os.makedirs(relatorio_dir, exist_ok=True)

    # Caminhos completos
    csv_path = os.path.join(relatorio_dir, f"relatorio_{hoje.strftime('%Y-%m-%d')}.csv")
    pdf_path = os.path.join(relatorio_dir, f"relatorio_{hoje.strftime('%Y-%m-%d')}.pdf")

    # --- CSV ---
    with open(csv_path, "w", newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["=== RECEBIDAS ==="])
        writer.writerow(["Número OS", "Cliente", "Vendedor", "Hora", "Observação"])
        for o in recebidas:
            hora = o.data_hora_registro.strftime("%H:%M")
            writer.writerow([o.numero_os, o.cliente, o.vendedor, hora, o.observacao or ""])
        writer.writerow([])
        writer.writerow(["=== FALTANTES ==="])
        writer.writerow(["Número OS", "Cliente", "Vendedor", "Hora", "Observação"])
        for o in faltantes:
            hora = o.data_hora_registro.strftime("%H:%M")
            writer.writerow([o.numero_os, o.cliente, o.vendedor, hora, o.observacao or ""])

    # --- PDF ---
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    elements = []

    elements.append(Paragraph(f"Relatório de OS - {hoje.strftime('%d/%m/%Y')}", styles['Heading1']))
    elements.append(Spacer(1, 12))

    def add_table(title, ordens):
        elements.append(Paragraph(title, styles['Heading2']))
        data = [["Número OS", "Cliente", "Vendedor", "Hora", "Observação"]]
        for o in ordens:
            data.append([
                o.numero_os,
                o.cliente,
                o.vendedor,
                o.data_hora_registro.strftime("%H:%M"),
                o.observacao or ""
            ])
        if len(data) == 1:
            data.append(["-", "-", "-", "-", "Nenhum registro."])
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 12))

    add_table("🟢 Ordens Recebidas", recebidas)
    add_table("🔴 Ordens Faltantes", faltantes)

    doc.build(elements)

    return render_template('report.html', 
                           hoje=hoje,
                           csv_file=csv_path,
                           pdf_file=pdf_path)

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    session = Session()
    os_item = session.query(OrdemServico).get(id)

    if request.method == 'POST':
        numero_os = request.form['numero_os']
        cliente = request.form['cliente']
        vendedor = request.form['vendedor']
        status_anterior = os_item.status  # Guarda o status antes da edição
        novo_status = request.form['status']
        observacao = request.form.get('observacao', '')

        # Atualiza os campos
        os_item.numero_os = numero_os
        os_item.cliente = cliente
        os_item.vendedor = vendedor
        os_item.status = novo_status
        os_item.observacao = observacao

        # 🔥 Atualiza data/hora se o status mudar de "Faltante" para "Recebida"
        if status_anterior == 'Faltante' and novo_status == 'Recebida':
            os_item.data_hora_registro = datetime.now()

        session.commit()
        session.close()
        return redirect(url_for('index'))

    session.close()
    return render_template('editar.html', os_item=os_item)


@app.route('/remover/<int:os_id>', methods=['POST'])
def remover_os(os_id):
    session = Session()
    os_item = session.query(OrdemServico).get(os_id)
    if os_item:
        session.delete(os_item)
        session.commit()
        flash("Ordem de serviço removida com sucesso.", "success")
    else:
        flash("Ordem não encontrada.", "error")
    session.close()
    return redirect(url_for('index'))


@app.route('/historico', methods=['GET'])
def historico():
    session = Session()
    filtro_data = request.args.get('data')  # formato esperado: YYYY-MM-DD

    if filtro_data:
        try:
            data_filtrada = datetime.strptime(filtro_data, "%Y-%m-%d").date()
            registros = session.query(OrdemServico).filter(
                OrdemServico.data_hora_registro.between(
                    datetime.combine(data_filtrada, datetime.min.time()),
                    datetime.combine(data_filtrada, datetime.max.time())
                )
            ).all()
        except ValueError:
            registros = []
    else:
        registros = session.query(OrdemServico).order_by(OrdemServico.data_hora_registro.desc()).all()

    session.close()
    return render_template("historico.html", registros=registros, filtro_data=filtro_data or "")



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)


