-- ReservaCampus · Esquema PostgreSQL generado desde los modelos SQLAlchemy
-- Cada microservicio es dueño de sus tablas (en Render comparten instancia; en Docker
-- Compose cada servicio usa su propia base: auth_db, reservas_db, notificaciones_db).

-- ==================== auth-service ====================
CREATE TABLE usuarios (
	id SERIAL NOT NULL, 
	nombre VARCHAR(80) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	rol VARCHAR(20) NOT NULL, 
	estado VARCHAR(20) NOT NULL, 
	motivo_estado VARCHAR(300), 
	reset_token_hash VARCHAR(128), 
	reset_expira TIMESTAMP WITH TIME ZONE, 
	ultimo_acceso TIMESTAMP WITH TIME ZONE, 
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_usuarios_email ON usuarios (email);

-- ==================== reservas-service ====================
CREATE TABLE espacios (
	id SERIAL NOT NULL, 
	nombre VARCHAR(80) NOT NULL, 
	tipo VARCHAR(30) NOT NULL, 
	capacidad INTEGER NOT NULL, 
	ubicacion VARCHAR(120) NOT NULL, 
	descripcion VARCHAR(300) NOT NULL, 
	actividades VARCHAR(300) NOT NULL, 
	hora_apertura TIME WITHOUT TIME ZONE NOT NULL, 
	hora_cierre TIME WITHOUT TIME ZONE NOT NULL, 
	activo BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (nombre)
);

CREATE TABLE reportes (
	id SERIAL NOT NULL, 
	reserva_id INTEGER NOT NULL, 
	reportante_id INTEGER NOT NULL, 
	reportante_nombre VARCHAR(80) NOT NULL, 
	reserva_reportada_id INTEGER NOT NULL, 
	reportado_id INTEGER NOT NULL, 
	reportado_nombre VARCHAR(80) NOT NULL, 
	reportado_email VARCHAR(120) NOT NULL, 
	espacio VARCHAR(80) NOT NULL, 
	comentario VARCHAR(300) NOT NULL, 
	estado VARCHAR(20) NOT NULL, 
	sancion_id INTEGER, 
	creado_en TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (reserva_id)
);
CREATE INDEX ix_reportes_reportado_id ON reportes (reportado_id);
CREATE INDEX ix_reportes_reportante_id ON reportes (reportante_id);

CREATE TABLE sanciones (
	id SERIAL NOT NULL, 
	usuario_id INTEGER NOT NULL, 
	usuario_email VARCHAR(120) NOT NULL, 
	usuario_nombre VARCHAR(80) NOT NULL, 
	nivel INTEGER NOT NULL, 
	tipo VARCHAR(20) NOT NULL, 
	motivo VARCHAR(300) NOT NULL, 
	reserva_id INTEGER, 
	desde TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	hasta TIMESTAMP WITHOUT TIME ZONE, 
	estado VARCHAR(20) NOT NULL, 
	nota_admin VARCHAR(300), 
	creada_por VARCHAR(80) NOT NULL, 
	creada_en TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_sanciones_usuario_id ON sanciones (usuario_id);

CREATE TABLE horarios_clase (
	id SERIAL NOT NULL, 
	espacio_id INTEGER NOT NULL, 
	dia_semana INTEGER NOT NULL, 
	hora_inicio TIME WITHOUT TIME ZONE NOT NULL, 
	hora_fin TIME WITHOUT TIME ZONE NOT NULL, 
	materia VARCHAR(100) NOT NULL, 
	docente VARCHAR(80) NOT NULL, 
	vigente_desde DATE, 
	vigente_hasta DATE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(espacio_id) REFERENCES espacios (id) ON DELETE CASCADE
);
CREATE INDEX ix_horario_espacio_dia ON horarios_clase (espacio_id, dia_semana);

CREATE TABLE reservas (
	id SERIAL NOT NULL, 
	espacio_id INTEGER NOT NULL, 
	usuario_id INTEGER NOT NULL, 
	usuario_email VARCHAR(120) NOT NULL, 
	usuario_nombre VARCHAR(80) NOT NULL, 
	fecha DATE NOT NULL, 
	hora_inicio TIME WITHOUT TIME ZONE NOT NULL, 
	hora_fin TIME WITHOUT TIME ZONE NOT NULL, 
	asistentes INTEGER NOT NULL, 
	motivo VARCHAR(200) NOT NULL, 
	estado VARCHAR(20) NOT NULL, 
	motivo_revocacion VARCHAR(300), 
	creada_en TIMESTAMP WITH TIME ZONE NOT NULL, 
	llegada_confirmada_en TIMESTAMP WITHOUT TIME ZONE, 
	aviso_previo BOOLEAN NOT NULL, 
	aviso_inicio BOOLEAN NOT NULL, 
	aviso_final BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(espacio_id) REFERENCES espacios (id) ON DELETE CASCADE
);
CREATE INDEX ix_reserva_espacio_fecha ON reservas (espacio_id, fecha);
CREATE INDEX ix_reservas_usuario_id ON reservas (usuario_id);

-- ==================== notificaciones-service ====================
CREATE TABLE notificaciones (
	id SERIAL NOT NULL, 
	usuario_id INTEGER NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	tipo VARCHAR(40) NOT NULL, 
	titulo VARCHAR(120) NOT NULL, 
	mensaje VARCHAR(500) NOT NULL, 
	leida BOOLEAN NOT NULL, 
	correo_enviado BOOLEAN NOT NULL, 
	evento_id VARCHAR(40) NOT NULL, 
	creada_en TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (evento_id)
);
CREATE INDEX ix_notificaciones_usuario_id ON notificaciones (usuario_id);
