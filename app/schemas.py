from pydantic import BaseModel, Field, ConfigDict, field_validator
from decimal import Decimal
from datetime import datetime
from typing import Optional

class ActorCreate(BaseModel):
    actor_id:str; nombre:str; es_preferente:bool=False; activo:bool=True; ciudad:str
class ReceptionCreate(BaseModel):
    actor_id:str
    nombre_cliente:str=Field(min_length=2,max_length=120)
    telefono:str=Field(min_length=7,max_length=30)
    correo:Optional[str]=None
    placas:str=Field(min_length=4,max_length=20)
    vin:str=Field(min_length=11,max_length=40)
    aseguradora:Optional[str]=None
    poliza:Optional[str]=None
    flotilla_contrato:bool=False
    fecha_estimada_entrega:Optional[datetime]=None
    tecnico:Optional[str]=None
    evidencias:dict[str,str]
    @field_validator('evidencias')
    @classmethod
    def required_photos(cls,v):
        required={'FRENTE','ATRAS','LADO_IZQUIERDO','LADO_DERECHO','DANOS'}
        missing=required-set(v)
        if missing: raise ValueError('Faltan fotografías obligatorias: '+', '.join(sorted(missing)))
        if any(not str(x).strip() for x in v.values()): raise ValueError('Las URLs de evidencias no pueden estar vacías')
        return v
    @field_validator('poliza')
    @classmethod
    def policy_if_insured(cls,v,info):
        return v
class QuoteLine(BaseModel):
    descripcion:str; categoria:str; cantidad:int=Field(gt=0); precio_unitario:Decimal=Field(ge=0)
class QuoteCreate(BaseModel):
    lineas:list[QuoteLine]=Field(min_length=1)
    canal:str='WHATSAPP'
class QuoteDecision(BaseModel):
    aprobado:bool
    firma:str=Field(min_length=3)
    usuario:str=Field(min_length=2)
class PaymentCreate(BaseModel):
    monto:Decimal=Field(gt=0); tipo:str='PAGO'; referencia:Optional[str]=None
class AdditionalCreate(BaseModel):
    descripcion:str; monto:Decimal=Field(gt=0); asesor:str
class AdditionalDecision(BaseModel):
    aprobado:bool; usuario:str
class TransitionRequest(BaseModel):
    estado_destino:str
    usuario:str
    rol:str='ASESOR'
class CloseRequest(BaseModel):
    firma_conformidad:str=Field(min_length=3)
    usuario:str
class PartCreate(BaseModel):
    descripcion:str; proveedor_tipo:str
class PartUpdate(BaseModel):
    estado:str
class DelayRequest(BaseModel):
    horas_retraso:int=Field(gt=0); fecha_estimada_entrega:datetime; usuario:str
class StorageRequest(BaseModel):
    llamadas_recoleccion:int=Field(ge=0,le=3)
class PriceIncreaseRequest(BaseModel):
    precio_original:Decimal=Field(gt=0); precio_nuevo:Decimal=Field(gt=0); motivo:str; usuario:str
class OutModel(BaseModel):
    model_config=ConfigDict(from_attributes=True)
