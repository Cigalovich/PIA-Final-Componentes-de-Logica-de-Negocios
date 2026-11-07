import csv
from pathlib import Path
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from .models import Actor,CatalogItem,Operation,OperationDetail,TestCase,TransitionFixture

DATA=Path(__file__).resolve().parent.parent/'datos'
def _rows(name):
    with open(DATA/name,encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def seed_fixtures(db:Session):
    if db.query(Actor).count()==0:
        for r in _rows('actores.csv'): db.add(Actor(actor_id=r['actor_id'],nombre=r['nombre'],es_preferente=r['es_preferente']=='1',activo=r['activo']=='1',ciudad=r['ciudad']))
    if db.query(CatalogItem).count()==0:
        for r in _rows('catalogo.csv'): db.add(CatalogItem(recurso_id=r['recurso_id'],descripcion=r['descripcion'],precio_mxn=Decimal(r['precio_mxn']),capacidad_o_stock=int(r['capacidad_o_stock']),habilitado=r['habilitado']=='1'))
    db.flush()
    if db.query(Operation).count()==0:
        for r in _rows('operaciones.csv'):
            db.add(Operation(operacion_id=r['operacion_id'],actor_id=r['actor_id'],estado_inicial=r['estado_inicial'],fecha_solicitud=date.fromisoformat(r['fecha_solicitud']),promocion_activa=r['promocion_activa']=='1',autorizado=r['autorizado']=='1',referencia=r['referencia']))
    db.flush()
    if db.query(OperationDetail).count()==0:
        for r in _rows('detalle_operaciones.csv'): db.add(OperationDetail(operacion_id=r['operacion_id'],recurso_id=r['recurso_id'],cantidad=int(r['cantidad'])))
    if db.query(TestCase).count()==0:
        for r in _rows('casos_prueba.csv'): db.add(TestCase(**r))
    if db.query(TransitionFixture).count()==0:
        for r in _rows('transiciones_prueba.csv'): db.add(TransitionFixture(**r))
    db.commit()
