from fastapi import FastAPI, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import uuid4
from .database import Base, engine, get_db, SessionLocal
from . import models as m
from .schemas import *
from .domain import *
from .seed import seed_fixtures

Base.metadata.create_all(bind=engine)
if engine.dialect.name == 'sqlite':
    from sqlalchemy import text
    with engine.begin() as _conn:
        _conn.execute(text("CREATE TRIGGER IF NOT EXISTS trg_audit_no_update BEFORE UPDATE ON bitacora_auditoria BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END"))
        _conn.execute(text("CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete BEFORE DELETE ON bitacora_auditoria BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END"))
with SessionLocal() as _db: seed_fixtures(_db)
app=FastAPI(title='AutoFix Pro API',version='1.0.0',description='API de gestión de órdenes de servicio, cotizaciones, capacidad, pagos y auditoría de AutoFix Pro.')

def audit(db,folio,user,role,action,entity,detail=None):
    db.add(m.AuditLog(folio=folio,usuario=user,rol=role,accion=action,entidad=entity,detalle=detail or {}))
def event(db,folio,name,payload=None): db.add(m.DomainEventRecord(folio=folio,nombre=name,payload=payload or {}))
def order_or_404(db,folio):
    o=db.get(m.ServiceOrder,folio)
    if not o: raise HTTPException(404,'Orden no encontrada')
    return o
def order_total(db,folio):
    return money(sum((Decimal(str(x.precio_unitario))*x.cantidad for x in db.query(m.OrderLine).filter_by(folio=folio).all()),Decimal('0')))
def total_due(db,folio):
    quote=db.query(m.Quote).filter_by(folio=folio,estado='APROBADA').order_by(m.Quote.enviado_at.desc()).first()
    base=Decimal(str(quote.total)) if quote else Decimal('0')
    extras = sum(
        (
            Decimal(str(x.monto))
            for x in db.query(m.AdditionalWork).filter(
                m.AdditionalWork.folio == folio,
                m.AdditionalWork.estado.in_(['APROBADO', 'AUTORIZADO_ASESOR'])
            ).all()
        ),
        Decimal('0')
    )
    order=db.get(m.ServiceOrder,folio)
    storage=Decimal('0')
    if order and order.fecha_listo and order.fecha_resguardo:
        days=max(0,(datetime.utcnow()-order.fecha_listo).days-15); storage=Decimal(days)*Decimal('100')
    return money(base+extras+storage)
def quote_total(q): return money(sum((Decimal(str(x.precio_unitario))*x.cantidad for x in q.lineas),Decimal('0')))
def actor_dict(a): return {'actor_id':a.actor_id,'nombre':a.nombre,'es_preferente':a.es_preferente,'activo':a.activo,'ciudad':a.ciudad}
def operation_dict(o): return {'operacion_id':o.operacion_id,'actor_id':o.actor_id,'estado_inicial':o.estado_inicial,'fecha_solicitud':o.fecha_solicitud,'promocion_activa':o.promocion_activa,'autorizado':o.autorizado,'referencia':o.referencia}

@app.get('/')
def home(): return {'mensaje':'Bienvenido a AutoFix Pro','estado':'API funcionando'}
@app.get('/api/health')
def health(): return {'sistema':'AutoFix Pro','estado':'activo','base_de_datos':'configurada'}
@app.get('/api/db-health')
def db_health(db:Session=Depends(get_db)):
    try: db.execute(func.count().select() if False else __import__('sqlalchemy').text('SELECT 1'))
    except Exception as e: raise HTTPException(503,str(e))
    return {'base_de_datos':'SQLite' if engine.dialect.name=='sqlite' else engine.dialect.name,'estado':'conectada','mensaje':'Conexión exitosa con AutoFix Pro'}

# Legacy fixture read API and repositories
@app.get('/api/actores')
def actors(ciudad:str|None=None,activo:bool|None=None,es_preferente:bool|None=None,pagina:int=Query(1,ge=1),limite:int=Query(10,ge=1,le=100),db:Session=Depends(get_db)):
    q=db.query(m.Actor)
    if ciudad:q=q.filter(m.Actor.ciudad==ciudad)
    if activo is not None:q=q.filter(m.Actor.activo==activo)
    if es_preferente is not None:q=q.filter(m.Actor.es_preferente==es_preferente)
    total=q.count(); rows=q.order_by(m.Actor.actor_id).offset((pagina-1)*limite).limit(limite).all()
    return {'total':total,'pagina':pagina,'limite':limite,'resultados':[actor_dict(x) for x in rows]}
@app.get('/api/actores/{actor_id}')
def actor(actor_id:str,db:Session=Depends(get_db)):
    x=db.get(m.Actor,actor_id)
    if not x: raise HTTPException(404,'Actor no encontrado')
    return actor_dict(x)
@app.get('/api/catalogo')
def catalog(db:Session=Depends(get_db)):
    return [{'recurso_id':x.recurso_id,'descripcion':x.descripcion,'precio_mxn':x.precio_mxn,'capacidad_o_stock':x.capacidad_o_stock,'habilitado':x.habilitado} for x in db.query(m.CatalogItem).order_by(m.CatalogItem.recurso_id)]
@app.get('/api/operaciones')
def operations(actor_id:str|None=None,estado:str|None=None,pagina:int=Query(1,ge=1),limite:int=Query(10,ge=1,le=100),db:Session=Depends(get_db)):
    q=db.query(m.Operation)
    if actor_id:q=q.filter_by(actor_id=actor_id)
    if estado:q=q.filter(m.Operation.estado_inicial==estado)
    total=q.count(); rows=q.order_by(m.Operation.operacion_id).offset((pagina-1)*limite).limit(limite).all()
    return {'total':total,'pagina':pagina,'limite':limite,'resultados':[operation_dict(x) for x in rows]}
@app.get('/api/operaciones/{operacion_id}')
def operation(operacion_id:str,db:Session=Depends(get_db)):
    x=db.get(m.Operation,operacion_id)
    if not x: raise HTTPException(404,'Operación no encontrada')
    return operation_dict(x)
@app.get('/api/detalles')
def details(operacion_id:str|None=None,db:Session=Depends(get_db)):
    q=db.query(m.OperationDetail)
    if operacion_id:q=q.filter_by(operacion_id=operacion_id)
    return [{'operacion_id':x.operacion_id,'recurso_id':x.recurso_id,'cantidad':x.cantidad} for x in q.all()]
@app.get('/api/casos-prueba')
def cases(operacion_id:str|None=None,db:Session=Depends(get_db)):
    q=db.query(m.TestCase)
    if operacion_id:q=q.filter_by(operacion_id=operacion_id)
    return [{'caso_id':x.caso_id,'operacion_id':x.operacion_id,'tipo_prueba':x.tipo_prueba,'regla_a_verificar':x.regla_a_verificar,'resultado_alumno':x.resultado_alumno,'instrucciones':x.instrucciones} for x in q.all()]
@app.get('/api/transiciones-prueba')
def transitions_fixture(operacion_id:str|None=None,db:Session=Depends(get_db)):
    q=db.query(m.TransitionFixture)
    if operacion_id:q=q.filter_by(operacion_id=operacion_id)
    return [{'caso_id':x.caso_id,'operacion_id':x.operacion_id,'accion_sugerida':x.accion_sugerida,'estado_inicial':x.estado_inicial,'resultado_alumno':x.resultado_alumno,'instrucciones':x.instrucciones} for x in q.all()]

# US-01, US-11, US-15, US-16: reception and physical capacity
@app.post('/api/ordenes',status_code=201)
def create_order(data:ReceptionCreate,usuario:str=Header('sistema'),rol:str=Header('ASESOR'),db:Session=Depends(get_db)):
    a=db.get(m.Actor,data.actor_id)
    if not a or not a.activo: raise HTTPException(422,'El propietario debe existir y estar activo')
    if bool(data.aseguradora) != bool(data.poliza): raise HTTPException(422,'Si se captura aseguradora, también se requiere póliza; si no aplica, ambos campos deben omitirse')
    occupied_bays=db.query(m.ServiceOrder).filter(m.ServiceOrder.bahia==True,m.ServiceOrder.estado.notin_(['CERRADA','CANCELADA'])).count()
    occupied_slots=db.query(m.ServiceOrder).filter(m.ServiceOrder.cajon==True,m.ServiceOrder.estado.notin_(['CERRADA','CANCELADA'])).count()
    if (occupied_bays>=12 and occupied_slots>=8) and not data.flotilla_contrato:
        event(db,None,'CapacidadSaturada',{'bahias':occupied_bays,'cajones':occupied_slots}); db.commit()
        raise HTTPException(409,'Capacidad saturada: máximo 12 bahías y 8 cajones. Solo flotillas con contrato tienen excepción.')
    folio='AF-'+datetime.utcnow().strftime('%Y%m%d')+'-'+uuid4().hex[:6].upper()
    o=m.ServiceOrder(folio=folio,actor_id=data.actor_id,nombre_cliente=data.nombre_cliente,telefono=data.telefono,correo=data.correo,placas=data.placas.upper(),vin=data.vin.upper(),aseguradora=data.aseguradora,poliza=data.poliza,flotilla_contrato=data.flotilla_contrato,fecha_estimada_entrega=data.fecha_estimada_entrega,tecnico=data.tecnico,bahia=occupied_bays<12,cajon=occupied_slots<8)
    db.add(o); db.flush()
    for typ,url in data.evidencias.items(): db.add(m.PhotoEvidence(folio=folio,tipo=typ,url=url,etapa='RECEPCION'))
    audit(db,folio,usuario,rol,'ORDEN_CREADA','OrdenDeServicio',{'placas':o.placas,'vin':o.vin}); event(db,folio,'OrdenCreada',{'folio':folio})
    db.commit(); return {'folio':folio,'estado':o.estado,'fecha_apertura':o.fecha_apertura,'bahia_asignada':o.bahia,'cajon_asignado':o.cajon}
@app.get('/api/ordenes/{folio}')
def get_order(folio:str,db:Session=Depends(get_db)):
    o=order_or_404(db,folio)
    return {'folio':o.folio,'actor_id':o.actor_id,'cliente':o.nombre_cliente,'telefono':o.telefono,'placas':o.placas,'vin':o.vin,'estado':o.estado,'fecha_apertura':o.fecha_apertura,'tecnico':o.tecnico,'total':order_total(db,folio)}
@app.get('/api/ordenes/{folio}/evidencias')
def evidence(folio:str,db:Session=Depends(get_db)):
    order_or_404(db,folio)
    return [{'tipo':x.tipo,'url':x.url,'etapa':x.etapa,'created_at':x.created_at} for x in db.query(m.PhotoEvidence).filter_by(folio=folio).all()]
@app.post('/api/ordenes/{folio}/evidencias',status_code=201)
def add_evidence(folio:str,tipo:str,url:str,etapa:str='REPARACION',usuario:str=Header('sistema'),db:Session=Depends(get_db)):
    order_or_404(db,folio); x=m.PhotoEvidence(folio=folio,tipo=tipo,url=url,etapa=etapa); db.add(x); audit(db,folio,usuario,'TECNICO','EVIDENCIA_AGREGADA','PhotoEvidence',{'tipo':tipo,'etapa':etapa}); db.commit(); return {'id':x.id,'registrada':True}
# Diagnosis, quotations and customer authorization
@app.post('/api/ordenes/{folio}/cotizaciones',status_code=201)
def create_quote(folio:str,data:QuoteCreate,usuario:str=Header('asesor'),db:Session=Depends(get_db)):
    o=order_or_404(db,folio)
    if o.estado not in {'DIAGNOSTICADA','ESPERANDO_AUTORIZACION'}:
        raise HTTPException(409,'Primero debe registrarse el diagnóstico de la unidad')
    total=quote_total(data)
    qid='COT-'+uuid4().hex[:8].upper()
    dep=required_deposit(total) if deposit_required(total) else Decimal('0.00')
    q=m.Quote(folio_cotizacion=qid,folio=folio,total=total,canal=data.canal.upper(),anticipo_requerido=dep)
    db.add(q)
    for line in data.lineas:
        db.add(m.OrderLine(folio=folio,descripcion=line.descripcion,categoria=line.categoria.upper(),cantidad=line.cantidad,precio_unitario=money(line.precio_unitario)))
    if o.estado=='DIAGNOSTICADA':
        validate_transition(o.estado,'ESPERANDO_AUTORIZACION')
    o.estado='ESPERANDO_AUTORIZACION'
    audit(db,folio,usuario,'ASESOR','COTIZACION_ENVIADA','Cotizacion',{'cotizacion':qid,'total':str(total)})
    event(db,folio,'CotizacionEnviada',{'cotizacion':qid,'canal':data.canal})
    db.add(m.Notification(folio=folio,canal=data.canal.upper(),mensaje=f'Cotización {qid} por ${total} MXN enviada (registro simulado; requiere integración externa para envío real).'))
    db.commit()
    return {'cotizacion_id':qid,'folio':folio,'total_mxn':total,'anticipo_requerido':dep,'estado':q.estado,'notificacion':'registrada; envío externo no configurado'}

@app.get('/api/ordenes/{folio}/cotizaciones')
def list_quotes(folio:str,db:Session=Depends(get_db)):
    order_or_404(db,folio)
    return [{'cotizacion_id':q.folio_cotizacion,'total':q.total,'estado':q.estado,'anticipo_requerido':q.anticipo_requerido,'anticipo_pagado':q.anticipo_pagado,'canal':q.canal} for q in db.query(m.Quote).filter_by(folio=folio).all()]

@app.post('/api/cotizaciones/{cotizacion_id}/decision')
def quote_decision(cotizacion_id:str,data:QuoteDecision,db:Session=Depends(get_db)):
    q=db.get(m.Quote,cotizacion_id)
    if not q:
        raise HTTPException(404,'Cotización no encontrada')
    if q.estado!='PENDIENTE':
        raise HTTPException(409,'La cotización ya fue resuelta')
    o=order_or_404(db,q.folio)
    q.estado='APROBADA' if data.aprobado else 'RECHAZADA'
    q.autorizado_por=data.usuario
    q.firma=data.firma
    audit(db,q.folio,data.usuario,'CLIENTE','COTIZACION_'+q.estado,'Cotizacion',{'cotizacion':cotizacion_id,'firma':data.firma})
    event(db,q.folio,'CotizacionAutorizada' if data.aprobado else 'CotizacionRechazada',{'cotizacion':cotizacion_id})
    if not data.aprobado:
        o.estado='CANCELADA'
    db.commit()
    return {'cotizacion_id':cotizacion_id,'estado':q.estado,'anticipo_requerido':q.anticipo_requerido}

@app.post('/api/ordenes/{folio}/pagos',status_code=201)
def add_payment(folio:str,data:PaymentCreate,usuario:str=Header('caja'),db:Session=Depends(get_db)):
    o=order_or_404(db,folio)
    amount=money(data.monto)
    approved=db.query(m.Quote).filter_by(folio=folio,estado='APROBADA').order_by(m.Quote.enviado_at.desc()).first()
    if not approved:
        raise HTTPException(409,'No hay cotización aprobada')
    due=total_due(db,folio)
    if Decimal(str(o.monto_pagado))+amount>due:
        raise HTTPException(422,f'El pago excede el saldo pendiente. Total a pagar: {due}')
    p=m.Payment(folio=folio,monto=amount,tipo=data.tipo.upper(),referencia=data.referencia)
    db.add(p)
    o.monto_pagado=money(Decimal(str(o.monto_pagado))+amount)
    if data.tipo.upper()=='ANTICIPO':
        approved.anticipo_pagado=money(Decimal(str(approved.anticipo_pagado))+amount)
    if o.monto_pagado>=total_due(db,folio):
        o.pago_total=True
    audit(db,folio,usuario,'CAJERO','PAGO_REGISTRADO','Pago',{'monto':str(amount),'tipo':data.tipo})
    db.commit()
    return {'pago_id':p.id,'monto_pagado':o.monto_pagado,'pago_total':o.pago_total}

# State machine, technician assignment and closing
@app.post('/api/ordenes/{folio}/transiciones')
def transition(folio:str,data:TransitionRequest,db:Session=Depends(get_db)):
    o=order_or_404(db,folio)
    target=data.estado_destino.upper()
    try:
        validate_transition(o.estado,target)
    except DomainError as e:
        event(db,folio,'TransicionRechazada',{'actual':o.estado,'destino':target})
        audit(db,folio,data.usuario,data.rol,'TRANSICION_RECHAZADA','OrdenDeServicio',{'destino':target})
        db.commit()
        raise HTTPException(409,str(e))
    if target=='EN_REPARACION':
        q=db.query(m.Quote).filter_by(folio=folio,estado='APROBADA').order_by(m.Quote.enviado_at.desc()).first()
        if not q:
            raise HTTPException(409,'Se requiere cotización aprobada')
        if q.anticipo_requerido>0 and q.anticipo_pagado<q.anticipo_requerido:
            raise HTTPException(409,'Anticipo del 50% pendiente')
    previous_state=o.estado
    o.estado=target
    if target=='LISTA_PARA_ENTREGA':
        o.vehiculo_reparado=True
        o.fecha_listo=datetime.utcnow()
        event(db,folio,'OrdenListaParaEntrega')
    audit(db,folio,data.usuario,data.rol,'ESTADO_CAMBIADO','OrdenDeServicio',{'estado_anterior':previous_state,'estado_nuevo':target})
    event(db,folio,'EstadoOrdenActualizado',{'estado':target})
    db.commit()
    return {'folio':folio,'estado':target}

@app.post('/api/ordenes/{folio}/aceptacion-tecnico')
def technician_accept(folio:str,tecnico:str,usuario:str=Header('tecnico'),db:Session=Depends(get_db)):
    o=order_or_404(db,folio)
    o.tecnico=tecnico
    o.tecnico_acepto=True
    audit(db,folio,usuario,'TECNICO','ASIGNACION_ACEPTADA','OrdenDeServicio',{'tecnico':tecnico})
    db.commit()
    return {'folio':folio,'tecnico':tecnico,'aceptada':True}

@app.post('/api/ordenes/{folio}/cerrar')
def close_order(folio:str,data:CloseRequest,db:Session=Depends(get_db)):
    o=order_or_404(db,folio)
    if o.estado not in {'LISTA_PARA_ENTREGA','EN_RES_GUARDO'}:
        raise HTTPException(409,'El vehículo debe estar listo para entrega')
    o.pago_total=Decimal(str(o.monto_pagado))>=total_due(db,folio)
    cond=CierreTriple(o.vehiculo_reparado,o.pago_total,bool(data.firma_conformidad.strip()))
    if not cond.is_satisfied():
        raise HTTPException(409,'No se cumple la condición triple: vehículo reparado, pago total y firma de conformidad')
    o.firma_conformidad=data.firma_conformidad
    o.estado='CERRADA'
    o.bahia=False
    o.cajon=False
    audit(db,folio,data.usuario,'CAJERO','ORDEN_CERRADA','OrdenDeServicio',{'pago_total':True,'firma':True})
    event(db,folio,'OrdenCerrada')
    event(db,None,'EspacioLiberado',{'folio':folio})
    db.commit()
    return {'folio':folio,'estado':o.estado,'cerrada':True}

# CU-03 additional work and deviations
@app.post('/api/ordenes/{folio}/trabajos-adicionales',status_code=201)
def additional(folio:str,data:AdditionalCreate,db:Session=Depends(get_db)):
    o=order_or_404(db,folio)
    amount=money(data.monto)
    original=db.query(m.Quote).filter_by(folio=folio).order_by(m.Quote.enviado_at.asc()).first()
    if not original:
        raise HTTPException(409,'Primero debe existir una cotización original')

    acumulados = db.query(m.AdditionalWork).filter(
        m.AdditionalWork.folio == folio,
        m.AdditionalWork.estado.in_(['APROBADO', 'AUTORIZADO_ASESOR'])
    ).all()

    accumulated = money(
        sum((Decimal(str(x.monto)) for x in acumulados), Decimal('0')) + amount
    )

    exceeds=deviation_requires_management(original.total,accumulated)
    needs_client=additional_needs_customer(amount)
    status='PENDIENTE_APROBACIONES' if (exceeds or needs_client) else 'AUTORIZADO_ASESOR'

    x=m.AdditionalWork(
        folio=folio,
        descripcion=data.descripcion,
        monto=amount,
        autorizado_por=data.asesor if status=='AUTORIZADO_ASESOR' else None,
        estado=status,
        requiere_cliente=needs_client,
        requiere_gerencia=exceeds,
        cliente_aprobado=not needs_client,
        gerencia_aprobada=not exceeds
    )
    db.add(x)
    audit(db,folio,data.asesor,'ASESOR','TRABAJO_ADICIONAL_REGISTRADO','TrabajoAdicional',{'monto':str(amount),'estado':status,'requiere_cliente':needs_client,'requiere_gerencia':exceeds})
    event(db,folio,'TrabajoAdicionalDetectado',{'monto':str(amount)})
    db.commit()
    return {'id':x.id,'estado':status,'requiere_aprobacion_cliente':needs_client,'requiere_autorizacion_gerencia':exceeds}

@app.post('/api/trabajos-adicionales/{work_id}/decision')
def additional_decision(work_id:int,data:AdditionalDecision,db:Session=Depends(get_db)):
    x=db.get(m.AdditionalWork,work_id)
    if not x:
        raise HTTPException(404,'Trabajo adicional no encontrado')
    if not x.requiere_cliente or x.cliente_aprobado:
        raise HTTPException(409,'El trabajo no está pendiente de aprobación del cliente')
    if not data.aprobado:
        x.estado='RECHAZADO'
    else:
        x.cliente_aprobado=True
        x.estado='APROBADO' if x.gerencia_aprobada else 'PENDIENTE_APROBACIONES'
    audit(db,x.folio,data.usuario,'CLIENTE','TRABAJO_ADICIONAL_'+x.estado,'TrabajoAdicional',{'id':work_id})
    db.commit()
    return {'id':work_id,'estado':x.estado}

@app.post('/api/ordenes/{folio}/incremento-refaccion')
def price_increase(folio:str,data:PriceIncreaseRequest,db:Session=Depends(get_db)):
    order_or_404(db,folio)
    old=money(data.precio_original)
    new=money(data.precio_nuevo)
    pct=(new-old)/old*100
    if pct>=10:
        x=m.PriceAdjustment(folio=folio,precio_original=old,precio_nuevo=new,porcentaje=pct,motivo=data.motivo,solicitado_por=data.usuario)
        db.add(x)
        audit(db,folio,data.usuario,'ASESOR','INCREMENTO_PRECIO_PENDIENTE','Refaccion',{'porcentaje':str(pct),'motivo':data.motivo})
        db.commit()
        return {'id':x.id,'requiere_autorizacion_gerencia':True,'incremento_porcentaje':pct,'estado':x.estado}
    audit(db,folio,data.usuario,'ASESOR','INCREMENTO_PRECIO_AUTORIZADO','Refaccion',{'porcentaje':str(pct),'motivo':data.motivo})
    db.commit()
    return {'requiere_autorizacion_gerencia':False,'incremento_porcentaje':pct,'estado':'AUTORIZADO_ASESOR'}

@app.post('/api/trabajos-adicionales/{work_id}/autorizacion-gerencia')
def manager_additional_decision(work_id:int,aprobado:bool,gerente:str,db:Session=Depends(get_db)):
    x=db.get(m.AdditionalWork,work_id)
    if not x:
        raise HTTPException(404,'Trabajo adicional no encontrado')
    if not x.requiere_gerencia or x.gerencia_aprobada:
        raise HTTPException(409,'No requiere autorización pendiente de Gerencia')
    if not aprobado:
        x.estado='RECHAZADO'
    else:
        x.gerencia_aprobada=True
        x.estado='APROBADO' if x.cliente_aprobado else 'PENDIENTE_APROBACIONES'
    x.autorizado_por=gerente
    audit(db,x.folio,gerente,'GERENCIA','DESVIACION_'+x.estado,'TrabajoAdicional',{'id':work_id})
    db.commit()
    return {'id':work_id,'estado':x.estado}

@app.post('/api/ajustes-precio/{adjustment_id}/decision')
def price_adjustment_decision(adjustment_id:int,aprobado:bool,gerente:str,db:Session=Depends(get_db)):
    x=db.get(m.PriceAdjustment,adjustment_id)
    if not x:
        raise HTTPException(404,'Ajuste de precio no encontrado')
    if x.estado!='PENDIENTE_GERENCIA':
        raise HTTPException(409,'El ajuste ya fue resuelto')
    x.estado='APROBADO' if aprobado else 'RECHAZADO'
    x.autorizado_por=gerente
    audit(db,x.folio,gerente,'GERENCIA','AJUSTE_PRECIO_'+x.estado,'Refaccion',{'id':adjustment_id,'porcentaje':str(x.porcentaje)})
    db.commit()
    return {'id':adjustment_id,'estado':x.estado}

@app.post('/api/ordenes/{folio}/evidencias-pieza',status_code=201)
def add_part_replacement_evidence(folio:str,antes_url:str,despues_url:str,usuario:str,db:Session=Depends(get_db)):
    order_or_404(db,folio)
    if not antes_url.strip() or not despues_url.strip():
        raise HTTPException(422,'Se requieren evidencias antes y después de sustituir la pieza')
    before=m.PhotoEvidence(folio=folio,tipo='ANTES_SUSTITUCION',url=antes_url,etapa='SUSTITUCION')
    after=m.PhotoEvidence(folio=folio,tipo='DESPUES_SUSTITUCION',url=despues_url,etapa='SUSTITUCION')
    db.add_all([before,after])
    audit(db,folio,usuario,'TECNICO','EVIDENCIA_SUSTITUCION_REGISTRADA','PhotoEvidence',{'antes':antes_url,'despues':despues_url})
    db.commit()
    return {'folio':folio,'evidencias_registradas':2}

@app.post('/api/ordenes/{folio}/diagnostico')
def register_diagnosis(folio:str,diagnostico:str,tecnico:str,db:Session=Depends(get_db)):
    o=order_or_404(db,folio)
    try:
        validate_transition(o.estado,'DIAGNOSTICADA')
    except DomainError as e:
        raise HTTPException(409,str(e))
    old=o.estado
    o.estado='DIAGNOSTICADA'
    audit(db,folio,tecnico,'TECNICO','DIAGNOSTICO_REGISTRADO','OrdenDeServicio',{'diagnostico':diagnostico,'estado_anterior':old})
    event(db,folio,'OrdenDiagnosticada',{'diagnostico':diagnostico})
    db.commit()
    return {'folio':folio,'estado':o.estado,'diagnostico':diagnostico}

@app.post('/api/ordenes/{folio}/deslinde-seguridad')
def safety_disclaimer(folio:str,riesgo:str,cliente:str,firma:str,db:Session=Depends(get_db)):
    order_or_404(db,folio)
    if not firma.strip():
        raise HTTPException(422,'Se requiere firma digital de deslinde')
    audit(db,folio,cliente,'CLIENTE','DESLINDE_SEGURIDAD_FIRMADO','OrdenDeServicio',{'riesgo_rechazado':riesgo,'firma':firma})
    event(db,folio,'DeslindeFirmado',{'riesgo':riesgo})
    db.commit()
    return {'folio':folio,'deslinde_registrado':True,'garantia_afectada':True}
# Parts supply SLA and out-of-stock flow
@app.post('/api/ordenes/{folio}/refacciones',status_code=201)
def create_part(folio:str,data:PartCreate,db:Session=Depends(get_db)):
    order_or_404(db,folio)
    try:
        deadline=part_deadline(data.proveedor_tipo.upper())
    except DomainError as e:
        raise HTTPException(422,str(e))
    x=m.PartOrder(folio=folio,descripcion=data.descripcion,proveedor_tipo=data.proveedor_tipo.upper(),fecha_limite=deadline)
    db.add(x)
    audit(db,folio,'compras','COMPRAS','REFACCION_SOLICITADA','Refaccion',{'proveedor':data.proveedor_tipo,'fecha_limite':deadline.isoformat()})
    db.commit()
    return {'id':x.id,'fecha_limite':deadline,'estado':x.estado}

@app.patch('/api/refacciones/{part_id}')
def update_part(part_id:int,data:PartUpdate,db:Session=Depends(get_db)):
    x=db.get(m.PartOrder,part_id)
    if not x:
        raise HTTPException(404,'Pedido de refacción no encontrado')
    x.estado=data.estado.upper()
    if x.estado=='AGOTADA':
        x.agotada_desde=datetime.utcnow()
    audit(db,x.folio,'compras','COMPRAS','ESTADO_REFACCION_CAMBIADO','Refaccion',{'estado':x.estado})
    db.commit()
    return {'id':x.id,'estado':x.estado}

@app.post('/api/refacciones/{part_id}/buscar-alternos')
def search_alternatives(part_id:int,alternativas:list[str],usuario:str,db:Session=Depends(get_db)):
    x=db.get(m.PartOrder,part_id)
    if not x:
        raise HTTPException(404,'Pedido de refacción no encontrado')
    if not alternativas:
        raise HTTPException(422,'Registra al menos una alternativa consultada')
    x.estado='ALTERNOS_BUSCADOS'
    audit(db,x.folio,usuario,'COMPRAS','ALTERNOS_BUSCADOS','Refaccion',{'part_id':part_id,'alternativas':alternativas})
    db.commit()
    return {'id':part_id,'estado':x.estado,'alternativas_consultadas':len(alternativas)}

@app.post('/api/refacciones/{part_id}/pieza-cliente')
def customer_part(part_id:int,acepta_sin_garantia:bool,usuario:str,db:Session=Depends(get_db)):
    x=db.get(m.PartOrder,part_id)
    if not x:
        raise HTTPException(404,'Pedido no encontrado')
    if not acepta_sin_garantia:
        raise HTTPException(409,'Debe aceptarse explícitamente que la pieza aportada por cliente no tiene garantía de componente')
    x.aportada_cliente=True
    x.sin_garantia=True
    x.estado='APORTADA_CLIENTE'
    audit(db,x.folio,usuario,'CLIENTE','PIEZA_CLIENTE_SIN_GARANTIA','Refaccion',{'part_id':part_id})
    db.commit()
    return {'id':part_id,'aportada_cliente':True,'sin_garantia':True}

@app.get('/api/refacciones/en-riesgo')
def parts_at_risk(db:Session=Depends(get_db)):
    now=datetime.utcnow()
    rows=db.query(m.PartOrder).filter(m.PartOrder.estado.notin_(['RECIBIDA','CANCELADA'])).all()
    return [{'id':x.id,'folio':x.folio,'descripcion':x.descripcion,'estado':'EN_RIESGO' if now>x.fecha_limite else x.estado,'fecha_limite':x.fecha_limite,'escalamiento_gerencia':now>x.fecha_limite or (x.agotada_desde and now>x.agotada_desde+timedelta(hours=48))} for x in rows]

# Delay notifications, storage and customer portal/history
@app.post('/api/ordenes/{folio}/retraso')
def delay(folio:str,data:DelayRequest,db:Session=Depends(get_db)):
    o=order_or_404(db,folio)
    o.fecha_estimada_entrega=data.fecha_estimada_entrega
    if data.horas_retraso>4:
        msg=f'Retraso proyectado de {data.horas_retraso} horas. Nueva fecha estimada: {data.fecha_estimada_entrega.isoformat()}'
        db.add(m.Notification(folio=folio,canal='WHATSAPP',mensaje=msg))
        audit(db,folio,data.usuario,'ASESOR','RETRASO_NOTIFICADO','OrdenDeServicio',{'horas':data.horas_retraso})
    db.commit()
    return {'notificacion_requerida':data.horas_retraso>4,'registro':'creado' if data.horas_retraso>4 else 'no requerido'}

@app.post('/api/ordenes/{folio}/llamadas-recoleccion')
def storage_calls(folio:str,data:StorageRequest,db:Session=Depends(get_db)):
    o=order_or_404(db,folio)
    o.llamadas_recoleccion=data.llamadas_recoleccion
    days=(datetime.utcnow()-o.fecha_listo).days if o.fecha_listo else 0
    if days>=15 and data.llamadas_recoleccion>=3 and o.estado=='LISTA_PARA_ENTREGA':
        o.estado='EN_RES_GUARDO'
        o.fecha_resguardo=datetime.utcnow()
        event(db,folio,'OrdenEnResguardo')
        audit(db,folio,'sistema','CAJA','ORDEN_EN_RESGUARDO','OrdenDeServicio',{'dias':days,'llamadas':data.llamadas_recoleccion})
    db.commit()
    return {'folio':folio,'estado':o.estado,'dias_desde_listo':days}

@app.post('/api/ordenes/{folio}/calcular-almacenaje')
def storage_fee(folio:str,fecha:datetime|None=None,db:Session=Depends(get_db)):
    o=order_or_404(db,folio)
    asof=fecha or datetime.utcnow()
    if not o.fecha_listo:
        return {'dias_cobrables':0,'cargo_mxn':Decimal('0.00')}
    days=max(0,(asof-o.fecha_listo).days-15)
    fee=money(Decimal(days)*Decimal('100'))
    return {'dias_cobrables':days,'cargo_mxn':fee,'moneda':'MXN'}

@app.get('/api/portal/{folio}')
def customer_portal(folio:str,db:Session=Depends(get_db)):
    o=order_or_404(db,folio)
    return {'folio':o.folio,'placas':o.placas,'estado':o.estado,'fecha_apertura':o.fecha_apertura,'fecha_estimada_entrega':o.fecha_estimada_entrega}

@app.get('/api/vehiculos/{vin}/historial')
def vehicle_history(vin:str,db:Session=Depends(get_db)):
    orders=db.query(m.ServiceOrder).filter_by(vin=vin.upper()).order_by(m.ServiceOrder.fecha_apertura.desc()).all()
    return [{'folio':o.folio,'estado':o.estado,'fecha_apertura':o.fecha_apertura,'lineas':[{'descripcion':l.descripcion,'categoria':l.categoria,'cantidad':l.cantidad,'precio_unitario':l.precio_unitario} for l in o.lines],'garantias':[{'descripcion':w.descripcion,'vigente_hasta':w.vigente_hasta} for w in db.query(m.Warranty).filter(m.Warranty.vin==vin.upper(),m.Warranty.vigente_hasta>=date.today()).all()],'recomendaciones_pendientes':[{'id':r.id,'descripcion':r.descripcion} for r in db.query(m.Recommendation).filter_by(vin=vin.upper(),atendida=False).all()]} for o in orders]

@app.post('/api/vehiculos/{vin}/garantias',status_code=201)
def add_warranty(vin:str,descripcion:str,vigente_hasta:date,usuario:str,db:Session=Depends(get_db)):
    x=m.Warranty(vin=vin.upper(),descripcion=descripcion,vigente_hasta=vigente_hasta)
    db.add(x)
    audit(db,None,usuario,'ASESOR','GARANTIA_REGISTRADA','Garantia',{'vin':vin,'descripcion':descripcion})
    db.commit()
    return {'id':x.id,'vigente_hasta':x.vigente_hasta}

@app.post('/api/vehiculos/{vin}/recomendaciones',status_code=201)
def add_recommendation(vin:str,descripcion:str,usuario:str,db:Session=Depends(get_db)):
    x=m.Recommendation(vin=vin.upper(),descripcion=descripcion)
    db.add(x)
    audit(db,None,usuario,'TECNICO','RECOMENDACION_REGISTRADA','Recomendacion',{'vin':vin,'descripcion':descripcion})
    db.commit()
    return {'id':x.id,'registrada':True}

@app.patch('/api/recomendaciones/{recommendation_id}/atender')
def resolve_recommendation(recommendation_id:int,usuario:str,db:Session=Depends(get_db)):
    x=db.get(m.Recommendation,recommendation_id)
    if not x:
        raise HTTPException(404,'Recomendación no encontrada')
    x.atendida=True
    audit(db,None,usuario,'TECNICO','RECOMENDACION_ATENDIDA','Recomendacion',{'id':recommendation_id})
    db.commit()
    return {'id':x.id,'atendida':True}

@app.get('/api/ordenes/{folio}/auditoria')
def audit_for_order(folio:str,db:Session=Depends(get_db)):
    order_or_404(db,folio)
    return [{'id':x.id,'usuario':x.usuario,'rol':x.rol,'accion':x.accion,'entidad':x.entidad,'detalle':x.detalle,'fecha':x.fecha} for x in db.query(m.AuditLog).filter_by(folio=folio).order_by(m.AuditLog.fecha).all()]

@app.get('/api/auditoria')
def audit_all(db:Session=Depends(get_db)):
    return [{'id':x.id,'folio':x.folio,'usuario':x.usuario,'rol':x.rol,'accion':x.accion,'entidad':x.entidad,'detalle':x.detalle,'fecha':x.fecha} for x in db.query(m.AuditLog).order_by(m.AuditLog.fecha.desc()).limit(500).all()]

@app.get('/api/eventos')
def events(db:Session=Depends(get_db)):
    return [{'id':x.id,'folio':x.folio,'nombre':x.nombre,'payload':x.payload,'occurred_at':x.occurred_at} for x in db.query(m.DomainEventRecord).order_by(m.DomainEventRecord.id.desc()).limit(500).all()]

@app.get('/api/kpis/diarios')
def daily_kpis(fecha:date|None=None,db:Session=Depends(get_db)):
    day=fecha or date.today()
    orders=db.query(m.ServiceOrder).filter(func.date(m.ServiceOrder.fecha_apertura)==day.isoformat()).all()
    closed=[o for o in orders if o.estado=='CERRADA']
    open_orders=[o for o in orders if o.estado not in {'CERRADA','CANCELADA'}]
    revenue=db.query(func.coalesce(func.sum(m.Payment.monto),0)).filter(func.date(m.Payment.created_at)==day.isoformat()).scalar()
    avg_hours=None
    durations=[(o.fecha_listo-o.fecha_apertura).total_seconds()/3600 for o in closed if o.fecha_listo]
    if durations:
        avg_hours=round(sum(durations)/len(durations),2)
    bay_count=db.query(m.ServiceOrder).filter(m.ServiceOrder.bahia==True,m.ServiceOrder.estado.notin_(['CERRADA','CANCELADA'])).count()
    slot_count=db.query(m.ServiceOrder).filter(m.ServiceOrder.cajon==True,m.ServiceOrder.estado.notin_(['CERRADA','CANCELADA'])).count()
    delayed=[o for o in orders if o.fecha_estimada_entrega and o.fecha_estimada_entrega.date()<day and o.estado not in {'CERRADA','CANCELADA'}]
    delay_pct=round((len(delayed)/len(orders))*100,2) if orders else 0.0
    by_tech={}
    for o in closed:
        if o.tecnico:
            by_tech[o.tecnico]=by_tech.get(o.tecnico,0)+1
    category_revenue={}
    for o in orders:
        for line in o.lines:
            category_revenue[line.categoria]=category_revenue.get(line.categoria,Decimal('0'))+Decimal(str(line.precio_unitario))*line.cantidad
    return {'fecha':day,'ordenes_abiertas':len(open_orders),'ordenes_cerradas':len(closed),'ingresos_mxn':money(revenue),'ingresos_por_categoria_mxn':{k:money(v) for k,v in category_revenue.items()},'tiempo_promedio_reparacion_horas':avg_hours,'ocupacion_bahias':f'{bay_count}/12','ocupacion_cajones':f'{slot_count}/8','porcentaje_retrasos':delay_pct,'productividad_por_tecnico':by_tech}

# Audit log is append-only at API level; deny destructive methods explicitly.
@app.put('/api/auditoria/{entry_id}',include_in_schema=False)
def immutable_audit_put(entry_id:int):
    raise HTTPException(405,'La bitácora de auditoría es inmutable (US-19)')

@app.patch('/api/auditoria/{entry_id}',include_in_schema=False)
def immutable_audit_patch(entry_id:int):
    raise HTTPException(405,'La bitácora de auditoría es inmutable (US-19)')

@app.delete('/api/auditoria/{entry_id}',include_in_schema=False)
def immutable_audit_delete(entry_id:int):
    raise HTTPException(405,'La bitácora de auditoría es inmutable (US-19)')