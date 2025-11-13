from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import date, datetime, timedelta
from database import OrdemServico, Session, Status
import pandas as pd
import os
import io
from PIL import Image as PILImage

app = Flask(__name__)
app.secret_key = os.urandom(24)


@app.route('/')
def index():
    session = Session()
    hoje = date.today()
    ontem = hoje - timedelta(days=1)

    # pega as OS de hoje + faltantes de dias anteriores
    ordens = session.query(OrdemServico).filter(
        (OrdemServico.data_relatorio == hoje) |
        ((OrdemServico.status == Status.faltante) & (OrdemServico.data_relatorio < hoje))
    ).all()

    # <-- Nova consulta para as OS recebidas ontem -->
    recebidas_ontem = session.query(OrdemServico).filter(
        OrdemServico.data_relatorio == ontem,
        OrdemServico.status == Status.recebida
    ).order_by(OrdemServico.data_hora_registro).all()

    session.close()

    # separa recebidas e faltantes
    recebidas = [o for o in ordens if o.status == Status.recebida]
    faltantes = [o for o in ordens if o.status == Status.faltante]

    return render_template('index.html', 
                           recebidas=recebidas,
                           faltantes=faltantes,
                           recebidas_ontem=recebidas_ontem,
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
    import csv, os, io # Garante que 'io' está importado
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    # Imports que você já tem:
    from PIL import Image as PILImage

    session = Session()
    hoje = date.today()

    # ... (Query do banco de dados permanece a mesma) ...
    ordens = session.query(OrdemServico).filter(
        OrdemServico.data_relatorio == hoje
    ).all()
    session.close()

    recebidas = [o for o in ordens if o.status == Status.recebida]
    faltantes = [o for o in ordens if o.status == Status.faltante]

    relatorio_dir = os.path.join(os.getcwd(), "relatorios")
    os.makedirs(relatorio_dir, exist_ok=True)

    csv_path = os.path.join(relatorio_dir, f"relatorio_{hoje.strftime('%Y-%m-%d')}.csv")
    pdf_path = os.path.join(relatorio_dir, f"relatorio_{hoje.strftime('%Y-%m-%d')}.pdf")

    # --- CSV (inalterado) ---
    with open(csv_path, "w", newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["=== RECEBIDAS ==="])
        writer.writerow(["Data", "Hora", "Número OS", "Cliente", "Vendedor", "Observação"])
        for o in recebidas:
            data = o.data_hora_registro.strftime("%d/%m/%Y")
            hora = o.data_hora_registro.strftime("%H:%M")
            writer.writerow([data, hora, o.numero_os, o.cliente, o.vendedor, o.observacao or ""])
        writer.writerow([])
        writer.writerow(["=== FALTANTES ==="])
        writer.writerow(["Data", "Hora", "Número OS", "Cliente", "Vendedor", "Observação"])
        for o in faltantes:
            data = o.data_hora_registro.strftime("%d/%m/%Y")
            hora = o.data_hora_registro.strftime("%H:%M")
            writer.writerow([data, hora, o.numero_os, o.cliente, o.vendedor, o.observacao or ""])


    # --- PDF (Atualizado) ---
    
    # 1. Definição de Cores
    COLOR_APPLE_GREEN = HexColor('#34c759')
    COLOR_APPLE_RED = HexColor('#ff3b30')
    COLOR_APPLE_GRAY_BG = HexColor('#f5f5f7')
    COLOR_APPLE_TEXT_SECONDARY = HexColor('#86868b')
    COLOR_APPLE_LINE = HexColor('#e5e5e5')
    COLOR_APPLE_TEXT_PRIMARY = HexColor('#1d1d1f')

    # 2. Configura Documento e Estilos
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, topMargin=40, bottomMargin=40, leftMargin=40, rightMargin=40)
    elements = []

    # 3. Adiciona Estilos Personalizados
    styles.add(ParagraphStyle(name='MainTitle', fontName='Helvetica-Bold', fontSize=18, alignment=1, spaceAfter=20, textColor=COLOR_APPLE_TEXT_PRIMARY))
    styles.add(ParagraphStyle(name='SectionTitleGreen', fontName='Helvetica-Bold', fontSize=14, textColor=COLOR_APPLE_GREEN, spaceBefore=12, spaceAfter=10))
    styles.add(ParagraphStyle(name='SectionTitleRed', fontName='Helvetica-Bold', fontSize=14, textColor=COLOR_APPLE_RED, spaceBefore=12, spaceAfter=10))
    
    # NOVOS ESTILOS PARA QUEBRA DE TEXTO NA TABELA
    styles.add(ParagraphStyle(name='TableHeader', fontName='Helvetica-Bold', fontSize=9, textColor=COLOR_APPLE_TEXT_SECONDARY, alignment=0)) # 0=LEFT
    styles.add(ParagraphStyle(name='TableBody', fontName='Helvetica', fontSize=9, textColor=COLOR_APPLE_TEXT_PRIMARY, alignment=0))

    # 4. Adiciona Logo (Método Corrigido)
    # 4. Adiciona Logo (Método Corrigido e Manual)
    logo_path = os.path.join(os.getcwd(), "static", "logo.png")
    if os.path.exists(logo_path):
        try:
            # 1. Abre com Pillow
            pil_img = PILImage.open(logo_path)
            
            # 2. CONVERTE para RGB (remove transparência)
            pil_img = pil_img.convert('RGB')
            
            # 3. Pega as dimensões originais
            orig_width, orig_height = pil_img.size
            
            # 4. Define a largura desejada e CALCULA A ALTURA
            new_width = 160
            aspect_ratio = orig_height / orig_width
            new_height = new_width * aspect_ratio
            
            # 5. Cria um buffer de memória
            img_buffer = io.BytesIO()
            
            # 6. Salva a imagem no buffer
            pil_img.save(img_buffer, format='JPEG')
            img_buffer.seek(0)
            
            # 7. PASSA O BUFFER E AS DIMENSÕES EXATAS
            img = Image(img_buffer, width=new_width, height=new_height)
            
            img.hAlign = 'CENTER'
            elements.append(img)
            elements.append(Spacer(1, 30))
            
        except Exception as e:
            # Removemos o 'raise e' para o PDF gerar de qualquer forma
            print(f"Erro CRÍTICO ao processar logo para PDF: {e}")

    # 5. Adiciona Título Principal
    elements.append(Paragraph(f"Relatório de OS - {hoje.strftime('%d/%m/%Y')}", styles['MainTitle']))

    # 6. Função Auxiliar Reestilizada (COM QUEBRA DE TEXTO)
    def add_table(title, title_style_name, ordens):
        elements.append(Paragraph(title, styles[title_style_name]))
        
        # Envolve cabeçalhos em Paragraphs
        header = [
            Paragraph("Data", styles['TableHeader']),
            Paragraph("Hora", styles['TableHeader']),
            Paragraph("Número OS", styles['TableHeader']),
            Paragraph("Cliente", styles['TableHeader']),
            Paragraph("Vendedor", styles['TableHeader']),
            Paragraph("Observação", styles['TableHeader'])
        ]
        data = [header]
        
        # Envolve dados em Paragraphs
        for o in ordens:
            data.append([
                Paragraph(o.data_hora_registro.strftime("%d/%m/%Y"), styles['TableBody']),
                Paragraph(o.data_hora_registro.strftime("%H:%M"), styles['TableBody']),
                Paragraph(o.numero_os, styles['TableBody']),
                Paragraph(o.cliente, styles['TableBody']), # Isto agora vai quebrar linha
                Paragraph(o.vendedor, styles['TableBody']),
                Paragraph(o.observacao or "", styles['TableBody']) # Isto também
            ])
        
        if len(data) == 1:
            # Envolve a linha "Nenhum registro"
            data.append([
                Paragraph("-", styles['TableBody']),
                Paragraph("-", styles['TableBody']),
                Paragraph("-", styles['TableBody']),
                Paragraph("Nenhum registro.", styles['TableBody']),
                Paragraph("-", styles['TableBody']),
                Paragraph("-", styles['TableBody'])
            ])
        
        t = Table(data, repeatRows=1, colWidths=[60, 40, 70, 150, 80, '*'])
        
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_APPLE_GRAY_BG), # Fundo do Cabeçalho
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), # Alinha tudo ao topo
            ('LINEBELOW', (0, 0), (-1, -1), 1, COLOR_APPLE_LINE),
            ('BOX', (0, 0), (-1, -1), 1, COLOR_APPLE_LINE),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 12))

    # 7. Adiciona as tabelas
    add_table("Ordens Recebidas", "SectionTitleGreen", recebidas)
    add_table("Ordens Faltantes", "SectionTitleRed", faltantes)

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
        mostrando_recentes = True
        registros = session.query(OrdemServico).order_by(
            OrdemServico.data_hora_registro.desc()
        ).limit(50).all()

    session.close()
    return render_template("historico.html", 
                           registros=registros, 
                           filtro_data=filtro_data or "",
                           mostrando_recentes=mostrando_recentes)



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)


