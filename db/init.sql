CREATE DATABASE IF NOT EXISTS sistema_qr;
USE sistema_qr;

CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    folio VARCHAR(50) UNIQUE NOT NULL,
    titulo VARCHAR(200) NOT NULL,
    tipo_documento VARCHAR(100) NOT NULL,
    area_emisora VARCHAR(100) NOT NULL,
    estado ENUM('vigente', 'revocado', 'cancelado') DEFAULT 'vigente',
    ruta_pdf_original VARCHAR(255),
    ruta_pdf_qr VARCHAR(255),
    ruta_qr VARCHAR(255),
    usuario_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

CREATE TABLE validaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    documento_id INT,
    ip_consulta VARCHAR(50),
    fecha_consulta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (documento_id) REFERENCES documentos(id)
);

-- Usuario de prueba (contraseña: admin123)
INSERT INTO usuarios (nombre, email, password) VALUES (
    'Administrador',
    'admin@sistema.com',
    'scrypt:32768:8:1$salt$hash'
);