from decimal import Decimal
import pytest
from app.domain import *

def test_money_rounding_and_negative():
    assert money('12.345')==Decimal('12.35')
    with pytest.raises(ValueError): money('-1')
def test_specification_and_or_not():
    active=PredicateSpecification(lambda x:x['active'])
    preferred=PredicateSpecification(lambda x:x['preferred'])
    no_promo=PredicateSpecification(lambda x:not x['promo'])
    assert (active & (preferred | no_promo)).is_satisfied_by({'active':True,'preferred':False,'promo':False})
    assert (~preferred).is_satisfied_by({'preferred':False})
    assert not (active & preferred).is_satisfied_by({'active':True,'preferred':False})
def test_closure_triple():
    assert CierreTriple(True,True,True).is_satisfied()
    assert not CierreTriple(True,False,True).is_satisfied()
def test_deposit_threshold():
    assert not deposit_required('5000')
    assert deposit_required('5000.01')
    assert required_deposit('6000')==Decimal('3000.00')
def test_additional_threshold():
    assert not additional_needs_customer('799.99')
    assert additional_needs_customer('800')
def test_deviation_threshold():
    assert not deviation_requires_management('1000','300')
    assert deviation_requires_management('1000','300.01')
def test_state_machine_valid_invalid():
    validate_transition('RECIBIDA','DIAGNOSTICADA')
    with pytest.raises(DomainError): validate_transition('RECIBIDA','CERRADA')
def test_part_sla():
    start=datetime(2026,1,1)
    assert (part_deadline('LOCAL',start)-start).total_seconds()==86400
    assert (part_deadline('NACIONAL',start)-start).total_seconds()==259200
    assert (part_deadline('IMPORTACION',start)-start).days==7


def test_aggregate_order_and_capacity():
    order=OrdenDeServicio('F-1')
    order.transicionar('DIAGNOSTICADA')
    assert order.estado=='DIAGNOSTICADA'
    assert TallerCapacidad(12,8).admite(False) is False
    assert TallerCapacidad(12,8).admite(True) is True

def test_quote_aggregate_and_fixture_specs():
    assert Cotizacion(Decimal('6000'),Decimal('3000')).puede_iniciar_reparacion()
    assert not Cotizacion(Decimal('6000'),Decimal('2999')).puede_iniciar_reparacion()
    assert PuedeProcesarseSpecification().is_satisfied_by({'cliente_activo':True,'detalle_no_vacio':True,'autorizado':True})
    assert BeneficioReferenciaSpecification().is_satisfied_by({'vip':True,'total':'1500','promocion':False})

def test_aggregate_close():
    order=OrdenDeServicio('F-2',estado='LISTA_PARA_ENTREGA',reparado=True,pagado=True,firmado=True)
    order.cerrar()
    assert order.estado=='CERRADA'

def test_repository_and_unit_of_work():
    from app.database import SessionLocal
    from app.models import Actor
    from app.repositories.base import SqlAlchemyRepository
    from app.unit_of_work import UnitOfWork
    with SessionLocal() as db:
        repo=SqlAlchemyRepository(db,Actor)
        assert repo.count()>=40
        assert repo.get('AUT-C001') is not None
        assert len(repo.list(limit=3))==3
    with UnitOfWork() as uow:
        uow.db.add(Actor(actor_id='TEST-UOW',nombre='Prueba UOW',es_preferente=False,activo=True,ciudad='Monterrey'))
        uow.commit()
    with SessionLocal() as db:
        assert db.get(Actor,'TEST-UOW') is not None
        db.delete(db.get(Actor,'TEST-UOW')); db.commit()
