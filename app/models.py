from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Boolean, Integer, Date, DateTime, Numeric, ForeignKey, Text, JSON, UniqueConstraint, DDL, event as sa_event
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class Actor(Base):
    __tablename__='actores'
    actor_id: Mapped[str]=mapped_column(String(20), primary_key=True)
    nombre: Mapped[str]=mapped_column(String(100))
    es_preferente: Mapped[bool]=mapped_column(Boolean, default=False)
    activo: Mapped[bool]=mapped_column(Boolean, default=True)
    ciudad: Mapped[str]=mapped_column(String(100))

class CatalogItem(Base):
    __tablename__='catalogo_recursos'
    recurso_id: Mapped[str]=mapped_column(String(20), primary_key=True)
    descripcion: Mapped[str]=mapped_column(String(200))
    precio_mxn: Mapped[Decimal]=mapped_column(Numeric(12,2))
    capacidad_o_stock: Mapped[int]=mapped_column(Integer, default=0)
    habilitado: Mapped[bool]=mapped_column(Boolean, default=True)

class Operation(Base):
    __tablename__='operaciones'
    operacion_id: Mapped[str]=mapped_column(String(20), primary_key=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('actores.actor_id'))
    estado_inicial: Mapped[str]=mapped_column(String(40), default='RECIBIDA')
    fecha_solicitud: Mapped[date]=mapped_column(Date)
    promocion_activa: Mapped[bool]=mapped_column(Boolean, default=False)
    autorizado: Mapped[bool]=mapped_column(Boolean, default=False)
    referencia: Mapped[str]=mapped_column(String(100))
    detalles: Mapped[list['OperationDetail']]=relationship(cascade='all, delete-orphan')

class OperationDetail(Base):
    __tablename__='detalle_operaciones'
    id: Mapped[int]=mapped_column(Integer, primary_key=True, autoincrement=True)
    operacion_id: Mapped[str]=mapped_column(ForeignKey('operaciones.operacion_id'))
    recurso_id: Mapped[str]=mapped_column(ForeignKey('catalogo_recursos.recurso_id'))
    cantidad: Mapped[int]=mapped_column(Integer)

class TestCase(Base):
    __tablename__='casos_prueba'
    caso_id: Mapped[str]=mapped_column(String(20), primary_key=True)
    operacion_id: Mapped[str]=mapped_column(String(20))
    tipo_prueba: Mapped[str]=mapped_column(String(80))
    regla_a_verificar: Mapped[str]=mapped_column(Text)
    resultado_alumno: Mapped[str]=mapped_column(String(40))
    instrucciones: Mapped[str]=mapped_column(Text)

class TransitionFixture(Base):
    __tablename__='transiciones_prueba'
    caso_id: Mapped[str]=mapped_column(String(20), primary_key=True)
    operacion_id: Mapped[str]=mapped_column(String(20))
    accion_sugerida: Mapped[str]=mapped_column(String(80))
    estado_inicial: Mapped[str]=mapped_column(String(40))
    resultado_alumno: Mapped[str]=mapped_column(String(40))
    instrucciones: Mapped[str]=mapped_column(Text)

class ServiceOrder(Base):
    __tablename__='ordenes_servicio'
    folio: Mapped[str]=mapped_column(String(30), primary_key=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('actores.actor_id'))
    nombre_cliente: Mapped[str]=mapped_column(String(120))
    telefono: Mapped[str]=mapped_column(String(30))
    correo: Mapped[str|None]=mapped_column(String(150), nullable=True)
    placas: Mapped[str]=mapped_column(String(20), index=True)
    vin: Mapped[str]=mapped_column(String(40), index=True)
    aseguradora: Mapped[str|None]=mapped_column(String(120), nullable=True)
    poliza: Mapped[str|None]=mapped_column(String(80), nullable=True)
    estado: Mapped[str]=mapped_column(String(40), default='RECIBIDA', index=True)
    fecha_apertura: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)
    fecha_estimada_entrega: Mapped[datetime|None]=mapped_column(DateTime, nullable=True)
    bahia: Mapped[bool]=mapped_column(Boolean, default=False)
    cajon: Mapped[bool]=mapped_column(Boolean, default=True)
    flotilla_contrato: Mapped[bool]=mapped_column(Boolean, default=False)
    tecnico: Mapped[str|None]=mapped_column(String(120), nullable=True)
    tecnico_acepto: Mapped[bool]=mapped_column(Boolean, default=False)
    vehiculo_reparado: Mapped[bool]=mapped_column(Boolean, default=False)
    pago_total: Mapped[bool]=mapped_column(Boolean, default=False)
    firma_conformidad: Mapped[str|None]=mapped_column(Text, nullable=True)
    fecha_listo: Mapped[datetime|None]=mapped_column(DateTime, nullable=True)
    llamadas_recoleccion: Mapped[int]=mapped_column(Integer, default=0)
    fecha_resguardo: Mapped[datetime|None]=mapped_column(DateTime, nullable=True)
    monto_pagado: Mapped[Decimal]=mapped_column(Numeric(12,2), default=Decimal('0'))
    lines: Mapped[list['OrderLine']]=relationship(cascade='all, delete-orphan')

class OrderLine(Base):
    __tablename__='lineas_servicio'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    folio: Mapped[str]=mapped_column(ForeignKey('ordenes_servicio.folio'))
    descripcion: Mapped[str]=mapped_column(String(200))
    categoria: Mapped[str]=mapped_column(String(30))
    cantidad: Mapped[int]=mapped_column(Integer, default=1)
    precio_unitario: Mapped[Decimal]=mapped_column(Numeric(12,2))

class PhotoEvidence(Base):
    __tablename__='evidencias_fotograficas'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    folio: Mapped[str]=mapped_column(ForeignKey('ordenes_servicio.folio'))
    tipo: Mapped[str]=mapped_column(String(40))
    url: Mapped[str]=mapped_column(Text)
    etapa: Mapped[str]=mapped_column(String(30), default='RECEPCION')
    created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)

class Quote(Base):
    __tablename__='cotizaciones'
    folio_cotizacion: Mapped[str]=mapped_column(String(30), primary_key=True)
    folio: Mapped[str]=mapped_column(ForeignKey('ordenes_servicio.folio'))
    total: Mapped[Decimal]=mapped_column(Numeric(12,2))
    estado: Mapped[str]=mapped_column(String(30), default='PENDIENTE')
    canal: Mapped[str]=mapped_column(String(30), default='WHATSAPP')
    enviado_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)
    autorizado_por: Mapped[str|None]=mapped_column(String(120), nullable=True)
    firma: Mapped[str|None]=mapped_column(Text, nullable=True)
    anticipo_requerido: Mapped[Decimal]=mapped_column(Numeric(12,2), default=Decimal('0'))
    anticipo_pagado: Mapped[Decimal]=mapped_column(Numeric(12,2), default=Decimal('0'))

class AdditionalWork(Base):
    __tablename__='trabajos_adicionales'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    folio: Mapped[str]=mapped_column(ForeignKey('ordenes_servicio.folio'))
    descripcion: Mapped[str]=mapped_column(String(200))
    monto: Mapped[Decimal]=mapped_column(Numeric(12,2))
    autorizado_por: Mapped[str|None]=mapped_column(String(120), nullable=True)
    estado: Mapped[str]=mapped_column(String(40), default='PENDIENTE')
    requiere_cliente: Mapped[bool]=mapped_column(Boolean, default=False)
    requiere_gerencia: Mapped[bool]=mapped_column(Boolean, default=False)
    cliente_aprobado: Mapped[bool]=mapped_column(Boolean, default=False)
    gerencia_aprobada: Mapped[bool]=mapped_column(Boolean, default=False)
    created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)

class PartOrder(Base):
    __tablename__='pedidos_refacciones'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    folio: Mapped[str]=mapped_column(ForeignKey('ordenes_servicio.folio'))
    descripcion: Mapped[str]=mapped_column(String(200))
    proveedor_tipo: Mapped[str]=mapped_column(String(20))
    pedido_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)
    estado: Mapped[str]=mapped_column(String(30), default='SOLICITADA')
    fecha_limite: Mapped[datetime]=mapped_column(DateTime)
    agotada_desde: Mapped[datetime|None]=mapped_column(DateTime, nullable=True)
    aportada_cliente: Mapped[bool]=mapped_column(Boolean, default=False)
    sin_garantia: Mapped[bool]=mapped_column(Boolean, default=False)

class Payment(Base):
    __tablename__='pagos'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    folio: Mapped[str]=mapped_column(ForeignKey('ordenes_servicio.folio'))
    monto: Mapped[Decimal]=mapped_column(Numeric(12,2))
    tipo: Mapped[str]=mapped_column(String(30))
    referencia: Mapped[str|None]=mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__='bitacora_auditoria'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    folio: Mapped[str|None]=mapped_column(String(30), nullable=True, index=True)
    usuario: Mapped[str]=mapped_column(String(120))
    rol: Mapped[str]=mapped_column(String(40))
    accion: Mapped[str]=mapped_column(String(100))
    entidad: Mapped[str]=mapped_column(String(80))
    detalle: Mapped[dict]=mapped_column(JSON, default=dict)
    fecha: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)

class DomainEventRecord(Base):
    __tablename__='domain_events'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    folio: Mapped[str|None]=mapped_column(String(30), nullable=True)
    nombre: Mapped[str]=mapped_column(String(100))
    payload: Mapped[dict]=mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)

class Notification(Base):
    __tablename__='notificaciones'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    folio: Mapped[str]=mapped_column(ForeignKey('ordenes_servicio.folio'))
    canal: Mapped[str]=mapped_column(String(30))
    mensaje: Mapped[str]=mapped_column(Text)
    estado: Mapped[str]=mapped_column(String(30), default='REGISTRADA')
    created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)

# Protección adicional de inmutabilidad en SQLite y motores compatibles con triggers.
sa_event.listen(AuditLog.__table__, 'after_create', DDL("CREATE TRIGGER IF NOT EXISTS trg_audit_no_update BEFORE UPDATE ON bitacora_auditoria BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END"))
sa_event.listen(AuditLog.__table__, 'after_create', DDL("CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete BEFORE DELETE ON bitacora_auditoria BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END"))

class PriceAdjustment(Base):
    __tablename__='ajustes_precio_refaccion'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    folio: Mapped[str]=mapped_column(ForeignKey('ordenes_servicio.folio'))
    precio_original: Mapped[Decimal]=mapped_column(Numeric(12,2))
    precio_nuevo: Mapped[Decimal]=mapped_column(Numeric(12,2))
    porcentaje: Mapped[Decimal]=mapped_column(Numeric(8,2))
    motivo: Mapped[str]=mapped_column(Text)
    estado: Mapped[str]=mapped_column(String(30), default='PENDIENTE_GERENCIA')
    solicitado_por: Mapped[str]=mapped_column(String(120))
    autorizado_por: Mapped[str|None]=mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)

class Warranty(Base):
    __tablename__='garantias'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    vin: Mapped[str]=mapped_column(String(40), index=True)
    descripcion: Mapped[str]=mapped_column(String(200))
    vigente_hasta: Mapped[date]=mapped_column(Date)

class Recommendation(Base):
    __tablename__='recomendaciones_pendientes'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    vin: Mapped[str]=mapped_column(String(40), index=True)
    descripcion: Mapped[str]=mapped_column(String(200))
    atendida: Mapped[bool]=mapped_column(Boolean, default=False)
