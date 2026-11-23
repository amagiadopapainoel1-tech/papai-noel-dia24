import os
from flask import Flask, render_template, request, redirect, jsonify
from datetime import datetime, timedelta
import sqlite3
import smtplib
from email.message import EmailMessage

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "segredo123")

EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
NOME_REMETENTE = "Recanto do Papai Noel - Curitiba 🎅"
QR_CODE_PATH = "static/KrCode pix Paulo.jpg"
NOEL_FOTO_PATH = "static/capa_2026.jpg"

VALOR_SESSAO = 50.00
WHATSAPP_NOEL = "5541997565882"
PIX_COPIA_COLA = "00020126360014br.gov.bcb.pix0114+5541997565882520400005303986540550.005802BR5912PAULO_DUARTE6008Curitiba610981550-31062140510PapaiNoel6304"

def criar_tabela():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            horario TEXT,
            responsavel TEXT,
            numero_criancas INTEGER,
            email TEXT,
            telefone TEXT,
            valor_total REAL,
            status_pagamento TEXT,
            observacoes TEXT,
            endereco TEXT,
            bairro TEXT,
            cidade TEXT
        )
    """)
    conn.commit()
    conn.close()

criar_tabela()

DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

def gerar_datas_2026():
    datas = []
    inicio = datetime(2026, 12, 1)
    fim = datetime(2026, 12, 23)
    atual = inicio
    while atual <= fim:
        valor_iso = atual.strftime("%Y-%m-%d")
        texto_br = f"{atual.strftime('%d/%m/%Y')} ({DIAS_SEMANA[atual.weekday()]})"
        datas.append({"valor": valor_iso, "texto": texto_br})
        atual += timedelta(days=1)
    return datas

def gerar_horarios(data_str):
    try:
        dt = datetime.strptime(data_str, "%Y-%m-%d")
    except ValueError:
        return []

    if not (datetime(2026, 12, 1) <= dt <= datetime(2026, 12, 23)):
        return []

    inicio = dt.replace(hour=17, minute=0)
    fim = dt.replace(hour=23, minute=45)

    horarios = []
    atual = inicio
    while atual <= fim:
        horarios.append(atual.strftime("%H:%M"))
        atual += timedelta(minutes=15)

    return horarios

def horarios_ocupados(data_str):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT horario FROM agendamentos WHERE data = ?", (data_str,))
    dados = cursor.fetchall()
    conn.close()
    return {linha[0] for linha in dados}

@app.route("/horarios_indisponiveis", methods=["POST"])
def horarios_indisponiveis():
    data = request.form.get("data")
    if not data:
        return jsonify({"erro": "data não enviada"})

    todos = gerar_horarios(data)
    ocupados = horarios_ocupados(data)

    return jsonify({
        "horarios_disponiveis": todos,
        "ocupados": list(ocupados)
    })

def enviar_email(destinatario, responsavel, data_br, horario, valor_total):
    if not destinatario or not EMAIL_REMETENTE or not EMAIL_PASSWORD:
        return

    try:
        msg = EmailMessage()
        msg["Subject"] = "Pré-Reserva - Recanto do Papai Noel 2026 🎅"
        msg["From"] = f"{NOME_REMETENTE} <{EMAIL_REMETENTE}>"
        msg["To"] = destinatario

        corpo = f"""
Olá {responsavel}!

Sua pré-reserva no Recanto do Papai Noel (Bairro Uberaba - Curitiba) foi registrada! 🎅✨

📅 Data: {data_br}
⏰ Horário: {horario} (Sessão exclusiva de 14 minutos)
💰 Valor por família: R$ {valor_total:.2f}

Para confirmar definitivamente sua vaga, realize o pagamento via PIX (R$ 50,00) e envie o comprovante no nosso WhatsApp: (41) 99756-5882.

PIX Copia e Cola:
{PIX_COPIA_COLA}

Esperamos sua família com muito carinho! 🎄
        """
        msg.set_content(corpo)

        for caminho in [QR_CODE_PATH, NOEL_FOTO_PATH]:
            if os.path.exists(caminho):
                with open(caminho, "rb") as f:
                    msg.add_attachment(
                        f.read(),
                        maintype="image",
                        subtype="jpeg" if caminho.lower().endswith((".jpg", ".jpeg")) else "png",
                        filename=os.path.basename(caminho)
                    )

        with smtplib.SMTP_SSL("smtpgmail.com", 465, timeout=10) as smtp:
            smtp.login(EMAIL_REMETENTE, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print(f"Aviso: não foi possível enviar e-mail automático: {e}")

@app.route("/")
def index():
    return render_template(
        "index.html",
        datas=gerar_datas_2026(),
        reserva=None,
        pix_copia_cola=PIX_COPIA_COLA,
        whatsapp_noel=WHATSAPP_NOEL
    )

@app.route("/enviar", methods=["POST"])
def enviar():
    data = request.form.get("data", "").strip()
    horario = request.form.get("horario", "").strip()
    responsavel = request.form.get("responsavel", "").strip()
    numero_criancas = int(request.form.get("numero_criancas", 1))
    numero_adultos = request.form.get("numero_adultos", "1 adulto")
    email = request.form.get("email", "").strip()
    telefone = request.form.get("telefone", "").strip()
    autoriza_imagem = request.form.get("autoriza_imagem", "Não informado")
    obs_cliente = request.form.get("observacoes", "").strip()
    bairro = request.form.get("bairro", "").strip()
    cidade = request.form.get("cidade", "Curitiba").strip()

    if horario in horarios_ocupados(data):
        return render_template(
            "index.html",
            datas=gerar_datas_2026(),
            erro="Ops! Esse horário acabou de ser reservado por outra família. Escolha outro horário disponível.",
            reserva=None,
            pix_copia_cola=PIX_COPIA_COLA,
            whatsapp_noel=WHATSAPP_NOEL
        )

    observacoes = f"Adultos: {numero_adultos} | Uso de imagem: {autoriza_imagem}"
    if obs_cliente:
        observacoes += f" | Obs: {obs_cliente}"

    status_pagamento = "Aguardando Comprovante PIX"
    valor_total = VALOR_SESSAO

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO agendamentos
        (data, horario, responsavel, numero_criancas, email, telefone, valor_total,
         status_pagamento, observacoes, endereco, bairro, cidade)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data, horario, responsavel, numero_criancas, email, telefone,
        valor_total, status_pagamento, observacoes, "", bairro, cidade
    ))
    conn.commit()
    conn.close()

    try:
        data_br = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        data_br = data

    enviar_email(email, responsavel, data_br, horario, valor_total)

    reserva = {
        "data_br": data_br,
        "horario": horario,
        "responsavel": responsavel,
        "criancas": numero_criancas,
        "adultos": numero_adultos
    }

    return render_template(
        "index.html",
        datas=gerar_datas_2026(),
        reserva=reserva,
        pix_copia_cola=PIX_COPIA_COLA,
        whatsapp_noel=WHATSAPP_NOEL
    )

@app.route("/agenda")
def agenda():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, data, horario, responsavel, numero_criancas, telefone, status_pagamento, observacoes, bairro
        FROM agendamentos
        ORDER BY data ASC, horario ASC
    """)
    registros = cursor.fetchall()
    conn.close()

    lista_formatada = []
    for r in registros:
        try:
            d_br = datetime.strptime(r[1], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            d_br = r[1]
        lista_formatada.append({
            "id": r[0],
            "data": d_br,
            "horario": r[2],
            "responsavel": r[3],
            "criancas": r[4],
            "telefone": r[5],
            "status": r[6],
            "obs": r[7],
            "bairro": r[8]
        })

    return render_template("agenda.html", agendamentos=lista_formatada)

@app.route("/excluir/<int:id_reserva>", methods=["POST"])
def excluir(id_reserva):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM agendamentos WHERE id = ?", (id_reserva,))
    conn.commit()
    conn.close()
    return redirect("/agenda")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
