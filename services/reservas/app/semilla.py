"""Datos iniciales: espacios y un horario de clases de ejemplo (ocupación fija semanal)."""
from datetime import time

ESPACIOS_INICIALES = [
    dict(nombre="Sala de Estudio A-101", tipo="sala_estudio", capacidad=6, ubicacion="Biblioteca, piso 1",
         descripcion="Mesa para 6, tablero y TV para presentaciones."),
    dict(nombre="Sala de Estudio A-102", tipo="sala_estudio", capacidad=4, ubicacion="Biblioteca, piso 1",
         descripcion="Sala pequeña y silenciosa."),
    dict(nombre="Sala de Estudio B-201", tipo="sala_estudio", capacidad=10, ubicacion="Biblioteca, piso 2",
         descripcion="Sala grupal con videobeam."),
    dict(nombre="Laboratorio de Cómputo 1", tipo="laboratorio", capacidad=30, ubicacion="Bloque C, piso 3",
         descripcion="30 equipos con Python, Docker y VS Code.", hora_apertura=time(7, 0), hora_cierre=time(20, 0)),
    dict(nombre="Laboratorio de Redes", tipo="laboratorio", capacidad=20, ubicacion="Bloque C, piso 2",
         descripcion="Switches, routers y racks para prácticas.", hora_apertura=time(8, 0), hora_cierre=time(18, 0)),
    dict(nombre="Auditorio Principal", tipo="auditorio", capacidad=200, ubicacion="Bloque A",
         descripcion="Sonido, proyector y tarima.", hora_apertura=time(8, 0), hora_cierre=time(20, 0)),
    dict(nombre="Cancha Múltiple", tipo="cancha", capacidad=24, ubicacion="Zona deportiva",
         descripcion="Fútbol sala, baloncesto y voleibol.", hora_apertura=time(6, 0), hora_cierre=time(22, 0)),
]

# dia: 0 = lunes ... 5 = sábado
HORARIOS_INICIALES = [
    dict(espacio="Laboratorio de Cómputo 1", dia=0, inicio=time(8), fin=time(10), materia="Programación I", docente="Ing. Laura Gómez"),
    dict(espacio="Laboratorio de Cómputo 1", dia=2, inicio=time(8), fin=time(10), materia="Programación I", docente="Ing. Laura Gómez"),
    dict(espacio="Laboratorio de Cómputo 1", dia=1, inicio=time(14), fin=time(16), materia="Bases de Datos", docente="Ing. Carlos Ruiz"),
    dict(espacio="Laboratorio de Cómputo 1", dia=3, inicio=time(14), fin=time(16), materia="Bases de Datos", docente="Ing. Carlos Ruiz"),
    dict(espacio="Laboratorio de Cómputo 1", dia=4, inicio=time(10), fin=time(12), materia="Ingeniería de Software II", docente="Ing. Andrés Mejía"),
    dict(espacio="Laboratorio de Redes", dia=0, inicio=time(10), fin=time(12), materia="Redes de Computadores", docente="Ing. Paula Díaz"),
    dict(espacio="Laboratorio de Redes", dia=2, inicio=time(10), fin=time(12), materia="Redes de Computadores", docente="Ing. Paula Díaz"),
    dict(espacio="Laboratorio de Redes", dia=4, inicio=time(14), fin=time(17), materia="Seguridad Informática", docente="Ing. Jorge León"),
    dict(espacio="Auditorio Principal", dia=4, inicio=time(8), fin=time(10), materia="Cátedra Institucional"),
    dict(espacio="Sala de Estudio B-201", dia=1, inicio=time(10), fin=time(12), materia="Tutoría de Cálculo", docente="Monitoría"),
    dict(espacio="Sala de Estudio B-201", dia=3, inicio=time(10), fin=time(12), materia="Tutoría de Física", docente="Monitoría"),
    dict(espacio="Cancha Múltiple", dia=0, inicio=time(16), fin=time(18), materia="Educación Física"),
    dict(espacio="Cancha Múltiple", dia=2, inicio=time(16), fin=time(18), materia="Educación Física"),
    dict(espacio="Cancha Múltiple", dia=5, inicio=time(8), fin=time(11), materia="Torneo Interfacultades"),
]
