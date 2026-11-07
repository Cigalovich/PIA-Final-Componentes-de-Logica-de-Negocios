"""Evalúa las 120 reglas de los CSV del paquete alumno y exporta resultados observados.
Las 20 transiciones se conservan como pendientes de oráculo porque el CSV no indica
estado destino ni resultado esperado; no se inventa un resultado aprobado/rechazado.
"""
import csv, sys
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database import SessionLocal,Base,engine
from app.models import Actor,CatalogItem,Operation,OperationDetail
from app.seed import seed_fixtures
from app.domain import PuedeProcesarseSpecification,BeneficioReferenciaSpecification
ROOT=Path(__file__).resolve().parents[1]/'datos'

def read(name):
    with open(ROOT/name,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    cases=read('casos_prueba.csv'); transitions=read('transiciones_prueba.csv'); results=[]
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_fixtures(db)
        prices={x.recurso_id:Decimal(str(x.precio_mxn)) for x in db.query(CatalogItem).all()}
        for c in cases:
            op=db.get(Operation,c['operacion_id']); actor=db.get(Actor,op.actor_id) if op else None
            details=db.query(OperationDetail).filter_by(operacion_id=c['operacion_id']).all()
            total=sum((prices.get(x.recurso_id,Decimal('0'))*x.cantidad for x in details),Decimal('0'))
            if c['tipo_prueba']=='validar_operacion':
                ok=PuedeProcesarseSpecification().is_satisfied_by({'cliente_activo':bool(actor and actor.activo),'detalle_no_vacio':bool(details),'autorizado':bool(op and op.autorizado)})
            elif c['tipo_prueba']=='evaluar_beneficio':
                ok=BeneficioReferenciaSpecification().is_satisfied_by({'vip':bool(actor and actor.es_preferente),'total':total,'promocion':bool(op and op.promocion_activa)})
            else:
                results.append({**c,'resultado_ejecucion':'NO_IMPLEMENTADO','detalle':'Tipo de prueba desconocido'});continue
            results.append({**c,'resultado_ejecucion':'REGLA_CUMPLIDA' if ok else 'REGLA_NO_CUMPLIDA','total_calculado_mxn':str(total.quantize(Decimal('0.01'))),'detalle':'Resultado observado de la regla; el CSV alumno no contiene oráculo esperado'})
    out=ROOT.parent/'resultados_casos_prueba.csv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(results[0].keys()));writer.writeheader();writer.writerows(results)
    trans_out=ROOT.parent/'transiciones_pendientes_oraculo.csv'
    with open(trans_out,'w',encoding='utf-8-sig',newline='') as f:
        fields=list(transitions[0].keys())+['resultado_ejecucion','detalle']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for t in transitions:w.writerow({**t,'resultado_ejecucion':'PENDIENTE_ORACULO','detalle':'El CSV no define estado destino ni resultado esperado; validar contra BPMN/oráculo del equipo/docente'})
    print(f'Casos evaluados: {len(cases)}')
    from collections import Counter
    print('Resultados:',dict(Counter(x['resultado_ejecucion'] for x in results)))
    print(f'Transiciones inventariadas: {len(transitions)} (pendientes de oráculo)')
    print('Archivos:',out,trans_out)
if __name__=='__main__':main()
