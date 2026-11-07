from sqlalchemy.orm import Session
class SqlAlchemyRepository:
    """Repositorio genérico: concentra operaciones de persistencia SQLAlchemy."""
    def __init__(self, db:Session, model): self.db=db; self.model=model
    def get(self, identifier): return self.db.get(self.model,identifier)
    def list(self, offset=0, limit=100): return self.db.query(self.model).offset(offset).limit(limit).all()
    def add(self, entity): self.db.add(entity); self.db.flush(); return entity
    def count(self): return self.db.query(self.model).count()
