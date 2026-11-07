from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Generic, TypeVar
from datetime import datetime, timedelta

CENT = Decimal('0.01')
def money(value) -> Decimal:
    result = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    if result < 0: raise ValueError('El importe no puede ser negativo')
    return result

T=TypeVar('T')
class Specification(Generic[T]):
    def is_satisfied_by(self, candidate:T)->bool: raise NotImplementedError
    def __and__(self, other): return AndSpecification(self,other)
    def __or__(self, other): return OrSpecification(self,other)
    def __invert__(self): return NotSpecification(self)
@dataclass
class PredicateSpecification(Specification[T]):
    predicate: Callable[[T],bool]
    def is_satisfied_by(self,candidate): return bool(self.predicate(candidate))
@dataclass
class AndSpecification(Specification[T]):
    left: Specification[T]; right: Specification[T]
    def is_satisfied_by(self,candidate): return self.left.is_satisfied_by(candidate) and self.right.is_satisfied_by(candidate)
@dataclass
class OrSpecification(Specification[T]):
    left: Specification[T]; right: Specification[T]
    def is_satisfied_by(self,candidate): return self.left.is_satisfied_by(candidate) or self.right.is_satisfied_by(candidate)
@dataclass
class NotSpecification(Specification[T]):
    spec: Specification[T]
    def is_satisfied_by(self,candidate): return not self.spec.is_satisfied_by(candidate)

@dataclass
class CierreTriple:
    reparado: bool; pagado: bool; firmado: bool
    def is_satisfied(self): return (PredicateSpecification(lambda x:x.reparado) & PredicateSpecification(lambda x:x.pagado) & PredicateSpecification(lambda x:x.firmado)).is_satisfied_by(self)

class DomainError(Exception): pass
TRANSITIONS={
 'RECIBIDA': {'DIAGNOSTICADA','CANCELADA'},
 'DIAGNOSTICADA': {'ESPERANDO_AUTORIZACION','EN_REPARACION','CANCELADA'},
 'ESPERANDO_AUTORIZACION': {'EN_REPARACION','CANCELADA'},
 'EN_REPARACION': {'ESPERANDO_REFACCION','LISTA_PARA_ENTREGA','CANCELADA'},
 'ESPERANDO_REFACCION': {'EN_REPARACION','CANCELADA'},
 'LISTA_PARA_ENTREGA': {'EN_RES_GUARDO','CERRADA'},
 'EN_RES_GUARDO': {'CERRADA'},
 'CANCELADA': set(), 'CERRADA': set()
}

def validate_transition(current, target):
    if target not in TRANSITIONS.get(current,set()):
        raise DomainError(f'Transición no permitida: {current} -> {target}')

def deposit_required(total): return money(total) > Decimal('5000.00')
def required_deposit(total): return (money(total)*Decimal('0.50')).quantize(CENT, rounding=ROUND_HALF_UP)
def additional_needs_customer(amount): return money(amount) >= Decimal('800.00')
def deviation_requires_management(original, accumulated):
    original=money(original)
    return original > 0 and money(accumulated) > original*Decimal('0.30')
def part_deadline(provider, start=None):
    hours={'LOCAL':24,'NACIONAL':72,'IMPORTACION':168}
    if provider not in hours: raise DomainError('Proveedor debe ser LOCAL, NACIONAL o IMPORTACION')
    return (start or datetime.utcnow())+timedelta(hours=hours[provider])

@dataclass
class OrdenDeServicio:
    """Aggregate root simplificado: protege estado y condición triple de cierre."""
    folio: str
    estado: str = 'RECIBIDA'
    reparado: bool = False
    pagado: bool = False
    firmado: bool = False
    eventos: list = None
    def __post_init__(self):
        if self.eventos is None: self.eventos=[]
    def transicionar(self, destino):
        validate_transition(self.estado,destino)
        anterior=self.estado; self.estado=destino
        self.eventos.append({'nombre':'EstadoOrdenActualizado','payload':{'anterior':anterior,'nuevo':destino}})
        if destino=='LISTA_PARA_ENTREGA': self.reparado=True; self.eventos.append({'nombre':'OrdenListaParaEntrega','payload':{'folio':self.folio}})
    def cerrar(self):
        if not CierreTriple(self.reparado,self.pagado,self.firmado).is_satisfied():
            raise DomainError('El cierre requiere reparación, pago total y firma de conformidad')
        self.transicionar('CERRADA'); self.eventos.append({'nombre':'OrdenCerrada','payload':{'folio':self.folio}})

@dataclass
class TallerCapacidad:
    bahias_ocupadas:int=0
    cajones_ocupados:int=0
    max_bahias:int=12
    max_cajones:int=8
    def admite(self, flotilla_contrato=False):
        disponible=self.bahias_ocupadas<self.max_bahias and self.cajones_ocupados<self.max_cajones
        return (PredicateSpecification(lambda x:x) | PredicateSpecification(lambda x:flotilla_contrato)).is_satisfied_by(disponible)

@dataclass
class Cotizacion:
    total:Decimal
    anticipo_pagado:Decimal=Decimal('0.00')
    def requiere_anticipo(self): return deposit_required(self.total)
    def puede_iniciar_reparacion(self):
        return not self.requiere_anticipo() or money(self.anticipo_pagado)>=required_deposit(self.total)

@dataclass
class PuedeProcesarseSpecification(Specification):
    def is_satisfied_by(self, candidate):
        return bool(candidate.get('cliente_activo') and candidate.get('detalle_no_vacio') and candidate.get('autorizado'))
@dataclass
class BeneficioReferenciaSpecification(Specification):
    def is_satisfied_by(self, candidate):
        return bool(candidate.get('vip') and money(candidate.get('total',0))>=Decimal('1500.00') and not candidate.get('promocion'))
