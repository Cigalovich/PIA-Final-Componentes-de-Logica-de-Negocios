# AutoFix Pro — Aplicación funcional PIA

API REST para la gestión operativa de un taller automotriz. Implementa persistencia SQLite/SQLAlchemy, catálogo de fixtures, órdenes, cotizaciones, anticipos, trabajos adicionales, control de capacidad, refacciones, cierre, historial, KPIs, eventos de dominio y bitácora append-only a nivel de API.

## Requisitos
- Python 3.12 recomendado (3.10+ compatible con la sintaxis usada)
- PowerShell, terminal o Docker Desktop

## Ejecución local (Windows / PowerShell)
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m uvicorn app.main:app --reload
```
Abrir http://127.0.0.1:8000/docs . La base `autofixpro.db` y los fixtures se inicializan automáticamente al iniciar la API.

## Docker
```bash
docker compose up --build
```
Pruebas dentro de contenedor:
```bash
docker compose --profile test run --build --rm tests
```

## Pruebas locales
```powershell
py -m pytest -q
py -m pytest --cov=app --cov-report=term-missing --cov-fail-under=80
```

## Principales endpoints
- `GET /api/health`, `GET /api/db-health`
- `GET /api/actores`, `/api/catalogo`, `/api/operaciones`, `/api/detalles`, `/api/casos-prueba`, `/api/transiciones-prueba`
- `POST /api/ordenes` recepción (US-01, US-11, US-15, US-16)
- `POST /api/ordenes/{folio}/cotizaciones` y `POST /api/cotizaciones/{id}/decision` (US-04, US-06, US-08)
- `POST /api/ordenes/{folio}/pagos`, `POST /api/ordenes/{folio}/transiciones`, `POST /api/ordenes/{folio}/cerrar` (US-02)
- `POST /api/ordenes/{folio}/trabajos-adicionales` (US-05, US-07)
- `POST /api/ordenes/{folio}/incremento-refaccion` (US-09)
- `POST /api/ordenes/{folio}/refacciones`, `GET /api/refacciones/en-riesgo` (US-10, US-14)
- `POST /api/ordenes/{folio}/retraso` (US-12)
- `POST /api/ordenes/{folio}/llamadas-recoleccion`, `/calcular-almacenaje` (US-13)
- `GET /api/portal/{folio}`, `GET /api/vehiculos/{vin}/historial` (US-12, US-18)
- `GET /api/kpis/diarios` (US-17)
- `GET /api/auditoria`, `GET /api/ordenes/{folio}/auditoria`, `GET /api/eventos` (US-19)

## Reglas implementadas
- Capacidad: 12 bahías y 8 cajones; excepción por flotilla con contrato.
- Anticipo del 50% cuando la cotización supera $5,000 MXN.
- Trabajo adicional de $800 MXN o más requiere aprobación del cliente.
- Desviación acumulada mayor al 30% del presupuesto original se bloquea y escala a Gerencia.
- Incremento de refacción menor al 10% puede autorizar asesor con motivo; 10% o más requiere Gerencia.
- SLA refacciones: local 24 h, nacional 72 h, importación 7 días; agotadas escala tras 48 h.
- Retraso proyectado mayor a 4 h registra notificación.
- Resguardo tras 15 días naturales y 3 llamadas; almacenaje $100 MXN/día posterior al día 15.
- Cierre exige reparación, pago total y firma.
- Auditoría es append-only por contrato de API; no existen endpoints de edición/borrado.

## Límites y adaptaciones explícitas
- Las notificaciones WhatsApp se registran en una tabla `notificaciones`; el envío real requiere credenciales y proveedor externo, no incluidos en los materiales. El sistema implementa el registro de notificación y su evidencia, no una integración externa real.
- Las evidencias fotográficas se reciben como URLs; la recepción exige frente, atrás, lado izquierdo, lado derecho y daños. Para sustituciones existe registro de antes/después. El almacenamiento binario requiere definir proveedor de archivos.
- El historial devuelve órdenes registradas, garantías vigentes y recomendaciones pendientes; hay endpoints para registrar y atender estos elementos.
- Las excepciones de flotilla permiten registrar el ingreso aunque las 12 bahías y los 8 cajones estén simultáneamente ocupados; el sistema no inventa capacidad física adicional. Si solo uno de los dos recursos está lleno, puede utilizar el otro.
- Los CSV de casos y transiciones contienen instrucciones, no oráculos esperados. Se conservan como fixtures y deben contrastarse con el resultado esperado proporcionado por el docente/equipo. No se marcan automáticamente como aprobados.
- El flujo de estados se implementó a partir del glosario/BRD de equipo (RECIBIDA, DIAGNOSTICADA, ESPERANDO_AUTORIZACION, EN_REPARACION, ESPERANDO_REFACCION, LISTA_PARA_ENTREGA, EN_RES_GUARDO, CERRADA, CANCELADA); validar su correspondencia exacta con el BPMN entregado.

## Seguridad antes de producción
Este es un prototipo académico. Antes de producción deben agregarse autenticación/autorización real por roles, gestión segura de firmas, URLs de evidencia firmadas, políticas de retención y migraciones Alembic. La cabecera `usuario`/`rol` sirve para trazabilidad demostrativa y no sustituye autenticación.

## Evaluación de fixtures del alumno
Ejecuta `py scripts/evaluar_casos.py` para calcular con los datos importados las 120 reglas del CSV (60 precondiciones y 60 beneficios) y generar `resultados_casos_prueba.csv`. Los valores `REGLA_CUMPLIDA`/`REGLA_NO_CUMPLIDA` son resultados observados, no pass/fail del examen. El archivo de 20 transiciones se exporta como pendiente de oráculo porque el CSV de alumno no proporciona estado destino ni resultado esperado; no se inventaron.

## Accesos rápidos en Windows
- Doble clic en `INICIAR_AUTOFIX.bat` para crear el entorno, instalar dependencias e iniciar la API.
- Con la API cerrada, ejecuta `EJECUTAR_PRUEBAS.bat` para correr pruebas y validar cobertura global mínima del 80%.
