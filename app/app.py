from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import qrcode
import os
import uuid
import time
import io
from datetime import datetime
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image

app = Flask(__name__)
app.secret_key = 'clave_secreta_sistema_qr'

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+pymysql://{os.environ.get('DB_USER', 'root')}:"
    f"{os.environ.get('DB_PASSWORD', 'secret123')}@"
    f"{os.environ.get('DB_HOST', 'localhost')}/"
    f"{os.environ.get('DB_NAME', 'sistema_qr')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = '/app/static/uploads'
app.config['QR_FOLDER'] = '/app/static/qr'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Documento(db.Model):
    __tablename__ = 'documentos'
    id = db.Column(db.Integer, primary_key=True)
    folio = db.Column(db.String(50), unique=True)
    titulo = db.Column(db.String(200))
    tipo_documento = db.Column(db.String(100))
    area_emisora = db.Column(db.String(100))
    estado = db.Column(db.Enum('vigente', 'revocado', 'cancelado'), default='vigente')
    ruta_pdf_original = db.Column(db.String(255))
    ruta_pdf_qr = db.Column(db.String(255))
    ruta_qr = db.Column(db.String(255))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Validacion(db.Model):
    __tablename__ = 'validaciones'
    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey('documentos.id'))
    ip_consulta = db.Column(db.String(50))
    fecha_consulta = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = Usuario.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('panel'))
        flash('Correo o contraseña incorrectos', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/panel')
@login_required
def panel():
    total = Documento.query.count()
    vigentes = Documento.query.filter_by(estado='vigente').count()
    revocados = Documento.query.filter_by(estado='revocado').count()
    cancelados = Documento.query.filter_by(estado='cancelado').count()
    return render_template('panel.html', total=total, vigentes=vigentes,
                           revocados=revocados, cancelados=cancelados)


@app.route('/subir', methods=['GET', 'POST'])
@login_required
def subir():
    if request.method == 'POST':
        archivo = request.files['pdf']
        titulo = request.form['titulo']
        tipo = request.form['tipo']
        area = request.form['area']
        posicion = request.form['posicion']

        if not archivo or not archivo.filename.endswith('.pdf'):
            flash('Solo se permiten archivos PDF', 'error')
            return redirect(url_for('subir'))

        folio = str(uuid.uuid4())[:8].upper()
        nombre_seguro = secure_filename(archivo.filename)
        nombre_original = f"{folio}_original_{nombre_seguro}"
        ruta_original = os.path.join(app.config['UPLOAD_FOLDER'], nombre_original)
        archivo.save(ruta_original)

        url_validacion = f"http://192.168.0.198:8080/validar/{folio}"
        qr = qrcode.make(url_validacion)
        nombre_qr = f"{folio}_qr.png"
        ruta_qr = os.path.join(app.config['QR_FOLDER'], nombre_qr)
        qr.save(ruta_qr)

        nombre_pdf_qr = f"{folio}_con_qr_{nombre_seguro}"
        ruta_pdf_qr = os.path.join(app.config['UPLOAD_FOLDER'], nombre_pdf_qr)
        insertar_qr_en_pdf(ruta_original, ruta_qr, ruta_pdf_qr, posicion)

        doc = Documento(
            folio=folio,
            titulo=titulo,
            tipo_documento=tipo,
            area_emisora=area,
            ruta_pdf_original=nombre_original,
            ruta_pdf_qr=nombre_pdf_qr,
            ruta_qr=nombre_qr,
            usuario_id=current_user.id
        )
        db.session.add(doc)
        db.session.commit()

        flash(f'Documento registrado con folio: {folio}', 'success')
        return redirect(url_for('repositorio'))

    return render_template('subir.html')


def insertar_qr_en_pdf(ruta_pdf, ruta_qr, ruta_salida, posicion):
    reader = PdfReader(ruta_pdf)
    writer = PdfWriter()
    pagina = reader.pages[0]
    ancho = float(pagina.mediabox.width)
    alto = float(pagina.mediabox.height)

    qr_size = 100
    margen = 20

    posiciones = {
        'superior_derecha': (ancho - qr_size - margen, alto - qr_size - margen),
        'superior_izquierda': (margen, alto - qr_size - margen),
        'inferior_derecha': (ancho - qr_size - margen, margen),
        'inferior_izquierda': (margen, margen),
    }
    x, y = posiciones.get(posicion, posiciones['inferior_derecha'])

    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(ancho, alto))
    c.drawImage(ruta_qr, x, y, width=qr_size, height=qr_size)
    c.save()
    packet.seek(0)

    from pypdf import PdfReader as PR
    qr_pdf = PR(packet)

    if posicion == 'ultima_pagina':
        for i, page in enumerate(reader.pages):
            if i == len(reader.pages) - 1:
                page.merge_page(qr_pdf.pages[0])
            writer.add_page(page)
    else:
        for i, page in enumerate(reader.pages):
            if i == 0:
                page.merge_page(qr_pdf.pages[0])
            writer.add_page(page)

    with open(ruta_salida, 'wb') as f:
        writer.write(f)


@app.route('/repositorio')
@login_required
def repositorio():
    documentos = Documento.query.order_by(Documento.created_at.desc()).all()
    return render_template('repositorio.html', documentos=documentos)


@app.route('/descargar-original/<folio>')
@login_required
def descargar_original(folio):
    doc = Documento.query.filter_by(folio=folio).first_or_404()
    ruta = os.path.join(app.config['UPLOAD_FOLDER'], doc.ruta_pdf_original)
    nombre_limpio = doc.ruta_pdf_original.split('_original_')[-1]
    return send_file(ruta, as_attachment=True, download_name=nombre_limpio)


@app.route('/revocar/<folio>', methods=['POST'])
@login_required
def revocar(folio):
    doc = Documento.query.filter_by(folio=folio).first_or_404()
    doc.estado = request.form.get('estado', 'revocado')
    db.session.commit()
    flash(f'Documento {folio} actualizado a: {doc.estado}', 'success')
    return redirect(url_for('repositorio'))


@app.route('/validar/<folio>')
def validar(folio):
    doc = Documento.query.filter_by(folio=folio).first()
    if doc:
        val = Validacion(documento_id=doc.id, ip_consulta=request.remote_addr)
        db.session.add(val)
        db.session.commit()
    return render_template('validar.html', doc=doc, folio=folio)


if __name__ == '__main__':
    with app.app_context():
        intentos = 0
        while intentos < 10:
            try:
                db.create_all()
                if not Usuario.query.filter_by(email='admin@sistema.com').first():
                    admin = Usuario(
                        nombre='Administrador',
                        email='admin@sistema.com',
                        password=generate_password_hash('admin123')
                    )
                    db.session.add(admin)
                    db.session.commit()
                print("✅ Base de datos lista")
                break
            except Exception as e:
                intentos += 1
                print(f"⏳ Esperando base de datos... intento {intentos}")
                time.sleep(5)
    app.run(host='0.0.0.0', port=5000, debug=True)