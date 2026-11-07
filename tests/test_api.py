from datetime import datetime, timedelta

def reception(client,actor='AUT-C001'):
    return client.post('/api/ordenes',json={
      'actor_id':actor,'nombre_cliente':'Cliente Prueba','telefono':'8112345678','placas':'ABC123','vin':'1HGCM82633A004352',
      'evidencias':{'FRENTE':'https://example.test/f.jpg','ATRAS':'https://example.test/a.jpg','LADO_IZQUIERDO':'https://example.test/i.jpg','LADO_DERECHO':'https://example.test/d.jpg','DANOS':'https://example.test/danos.jpg'}
    })
def test_health_and_fixture_counts(client):
    assert client.get('/api/health').status_code==200
    assert client.get('/api/actores?limite=100').json()['total']==40
    assert len(client.get('/api/catalogo').json())==20
    assert client.get('/api/operaciones?limite=100').json()['total']==60
    assert len(client.get('/api/detalles').json())==117
    assert len(client.get('/api/casos-prueba').json())==120
    assert len(client.get('/api/transiciones-prueba').json())==20
def test_reception_requires_four_photos(client):
    payload={'actor_id':'AUT-C001','nombre_cliente':'Cliente','telefono':'8112345678','placas':'ABC123','vin':'1HGCM82633A004352','evidencias':{'FRENTE':'x'}}
    assert client.post('/api/ordenes',json=payload).status_code==422
def test_reception_and_customer_portal(client):
    r=reception(client); assert r.status_code==201, r.text
    folio=r.json()['folio']; assert client.get('/api/portal/'+folio).json()['estado']=='RECIBIDA'
    assert len(client.get(f'/api/ordenes/{folio}/evidencias').json())==5
def test_quote_deposit_approval_and_transition(client):
    folio=reception(client).json()['folio']
    client.post(f'/api/ordenes/{folio}/diagnostico',params={'diagnostico':'Revisión general','tecnico':'Técnico 1'})
    q=client.post(f'/api/ordenes/{folio}/cotizaciones',json={'lineas':[{'descripcion':'Reparación','categoria':'MANO_OBRA','cantidad':1,'precio_unitario':'6000'}]})
    assert q.status_code==201, q.text
    qid=q.json()['cotizacion_id']; assert q.json()['anticipo_requerido']==3000.0
    assert client.post(f'/api/cotizaciones/{qid}/decision',json={'aprobado':True,'firma':'firma-cliente','usuario':'cliente'}).status_code==200
    assert client.post(f'/api/ordenes/{folio}/transiciones',json={'estado_destino':'EN_REPARACION','usuario':'asesor'}).status_code==409
    p=client.post(f'/api/ordenes/{folio}/pagos',json={'monto':'3000','tipo':'ANTICIPO'})
    assert p.status_code==201, p.text
    assert client.post(f'/api/ordenes/{folio}/transiciones',json={'estado_destino':'EN_REPARACION','usuario':'asesor'}).status_code==200
def test_invalid_transition_and_missing_order(client):
    assert client.get('/api/ordenes/NO-EXISTE').status_code==404
    folio=reception(client).json()['folio']
    r=client.post(f'/api/ordenes/{folio}/transiciones',json={'estado_destino':'CERRADA','usuario':'x'})
    assert r.status_code==409
def test_close_requires_triple_condition(client):
    folio=reception(client).json()['folio']
    r=client.post(f'/api/ordenes/{folio}/cerrar',json={'firma_conformidad':'firma','usuario':'caja'})
    assert r.status_code==409
def test_additional_work_threshold(client):
    folio=reception(client).json()['folio']
    client.post(f'/api/ordenes/{folio}/diagnostico',params={'diagnostico':'Revisión','tecnico':'Técnico 1'})
    client.post(f'/api/ordenes/{folio}/cotizaciones',json={'lineas':[{'descripcion':'Base','categoria':'SERVICIO','cantidad':1,'precio_unitario':'10000'}]})
    a=client.post(f'/api/ordenes/{folio}/trabajos-adicionales',json={'descripcion':'Ajuste','monto':'799.99','asesor':'asesor'})
    assert a.status_code==201 and a.json()['estado']=='AUTORIZADO_ASESOR'
    b=client.post(f'/api/ordenes/{folio}/trabajos-adicionales',json={'descripcion':'Extra','monto':'800','asesor':'asesor'})
    assert b.status_code==201 and b.json()['requiere_aprobacion_cliente'] is True
def test_parts_sla_and_delay_notification(client):
    folio=reception(client).json()['folio']
    p=client.post(f'/api/ordenes/{folio}/refacciones',json={'descripcion':'Filtro','proveedor_tipo':'LOCAL'})
    assert p.status_code==201
    assert client.post(f'/api/ordenes/{folio}/retraso',json={'horas_retraso':5,'fecha_estimada_entrega':(datetime.utcnow()+timedelta(days=1)).isoformat(),'usuario':'asesor'}).json()['notificacion_requerida'] is True
def test_audit_is_read_only(client):
    folio=reception(client).json()['folio']
    assert len(client.get(f'/api/ordenes/{folio}/auditoria').json())>=1
    assert client.delete('/api/auditoria/1').status_code==405
def test_history_and_kpis(client):
    r=reception(client); folio=r.json()['folio']
    assert client.get('/api/vehiculos/1HGCM82633A004352/historial').status_code==200
    assert client.get('/api/kpis/diarios').status_code==200

def test_additional_requires_both_client_and_manager_if_both_rules_apply(client):
    folio=reception(client).json()['folio']
    client.post(f'/api/ordenes/{folio}/diagnostico',params={'diagnostico':'Revisión','tecnico':'Técnico 1'})
    client.post(f'/api/ordenes/{folio}/cotizaciones',json={'lineas':[{'descripcion':'Base','categoria':'SERVICIO','cantidad':1,'precio_unitario':'2000'}]})
    # Acumulado mayor al 30% del presupuesto original y trabajo >= $800.
    r=client.post(f'/api/ordenes/{folio}/trabajos-adicionales',json={'descripcion':'Trabajo especial','monto':'900','asesor':'asesor'})
    assert r.status_code==201 and r.json()['requiere_aprobacion_cliente'] and r.json()['requiere_autorizacion_gerencia']
    wid=r.json()['id']
    assert client.post(f'/api/trabajos-adicionales/{wid}/decision',json={'aprobado':True,'usuario':'cliente'}).json()['estado']=='PENDIENTE_APROBACIONES'
    assert client.post(f'/api/trabajos-adicionales/{wid}/autorizacion-gerencia',params={'aprobado':True,'gerente':'gerente'}).json()['estado']=='APROBADO'

def test_safety_disclaimer_and_part_evidence(client):
    folio=reception(client).json()['folio']
    r=client.post(f'/api/ordenes/{folio}/deslinde-seguridad',params={'riesgo':'Frenos','cliente':'cliente','firma':'firma-digital'})
    assert r.status_code==200 and r.json()['deslinde_registrado']
    r=client.post(f'/api/ordenes/{folio}/evidencias-pieza',params={'antes_url':'https://x.test/before','despues_url':'https://x.test/after','usuario':'tecnico'})
    assert r.status_code==201 and r.json()['evidencias_registradas']==2
