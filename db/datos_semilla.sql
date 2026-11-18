-- ReservaCampus · Datos iniciales (los servicios también los siembran solos al arrancar si la tabla está vacía)

INSERT INTO espacios (nombre, tipo, capacidad, ubicacion, descripcion, actividades, hora_apertura, hora_cierre, activo) VALUES
  ('Sala de Estudio A-101', 'sala_estudio', 6, 'Biblioteca, piso 1', 'Mesa para 6, tablero y TV para presentaciones.', 'estudiar, trabajos en grupo, reuniones', '07:00:00', '21:00:00', TRUE),
  ('Sala de Estudio A-102', 'sala_estudio', 4, 'Biblioteca, piso 1', 'Sala pequeña y silenciosa.', 'estudiar, lectura', '07:00:00', '21:00:00', TRUE),
  ('Sala de Estudio B-201', 'sala_estudio', 10, 'Biblioteca, piso 2', 'Sala grupal con videobeam.', 'estudiar, trabajos en grupo, exposiciones, reuniones', '07:00:00', '21:00:00', TRUE),
  ('Laboratorio de Cómputo 1', 'laboratorio', 30, 'Bloque C, piso 3', '30 equipos con Python, Docker y VS Code.', 'programación, prácticas de computación', '07:00:00', '20:00:00', TRUE),
  ('Laboratorio de Redes', 'laboratorio', 20, 'Bloque C, piso 2', 'Switches, routers y racks para prácticas.', 'prácticas de redes', '08:00:00', '18:00:00', TRUE),
  ('Auditorio Principal', 'auditorio', 200, 'Bloque A', 'Sonido, proyector y tarima.', 'eventos, conferencias, seminarios', '08:00:00', '20:00:00', TRUE),
  ('Cancha Múltiple', 'cancha', 24, 'Zona deportiva', 'Fútbol sala, baloncesto y voleibol.', 'fútbol, baloncesto, voleibol', '06:00:00', '22:00:00', TRUE);

INSERT INTO horarios_clase (espacio_id, dia_semana, hora_inicio, hora_fin, materia, docente) VALUES
  ((SELECT id FROM espacios WHERE nombre = 'Laboratorio de Cómputo 1'), 0, '08:00:00', '10:00:00', 'Programación I', 'Ing. Laura Gómez'),
  ((SELECT id FROM espacios WHERE nombre = 'Laboratorio de Cómputo 1'), 2, '08:00:00', '10:00:00', 'Programación I', 'Ing. Laura Gómez'),
  ((SELECT id FROM espacios WHERE nombre = 'Laboratorio de Cómputo 1'), 1, '14:00:00', '16:00:00', 'Bases de Datos', 'Ing. Carlos Ruiz'),
  ((SELECT id FROM espacios WHERE nombre = 'Laboratorio de Cómputo 1'), 3, '14:00:00', '16:00:00', 'Bases de Datos', 'Ing. Carlos Ruiz'),
  ((SELECT id FROM espacios WHERE nombre = 'Laboratorio de Cómputo 1'), 4, '10:00:00', '12:00:00', 'Ingeniería de Software II', 'Ing. Andrés Mejía'),
  ((SELECT id FROM espacios WHERE nombre = 'Laboratorio de Redes'), 0, '10:00:00', '12:00:00', 'Redes de Computadores', 'Ing. Paula Díaz'),
  ((SELECT id FROM espacios WHERE nombre = 'Laboratorio de Redes'), 2, '10:00:00', '12:00:00', 'Redes de Computadores', 'Ing. Paula Díaz'),
  ((SELECT id FROM espacios WHERE nombre = 'Laboratorio de Redes'), 4, '14:00:00', '17:00:00', 'Seguridad Informática', 'Ing. Jorge León'),
  ((SELECT id FROM espacios WHERE nombre = 'Auditorio Principal'), 4, '08:00:00', '10:00:00', 'Cátedra Institucional', ''),
  ((SELECT id FROM espacios WHERE nombre = 'Sala de Estudio B-201'), 1, '10:00:00', '12:00:00', 'Tutoría de Cálculo', 'Monitoría'),
  ((SELECT id FROM espacios WHERE nombre = 'Sala de Estudio B-201'), 3, '10:00:00', '12:00:00', 'Tutoría de Física', 'Monitoría'),
  ((SELECT id FROM espacios WHERE nombre = 'Cancha Múltiple'), 0, '16:00:00', '18:00:00', 'Educación Física', ''),
  ((SELECT id FROM espacios WHERE nombre = 'Cancha Múltiple'), 2, '16:00:00', '18:00:00', 'Educación Física', ''),
  ((SELECT id FROM espacios WHERE nombre = 'Cancha Múltiple'), 5, '08:00:00', '11:00:00', 'Torneo Interfacultades', '');

-- Administrador: lo crea auth-service al arrancar con ADMIN_EMAIL / ADMIN_PASSWORD (la contraseña se guarda
-- con PBKDF2-SHA256, por eso no se inserta aquí en texto plano).