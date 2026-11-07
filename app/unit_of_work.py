from .database import SessionLocal
class UnitOfWork:
    """Unidad de trabajo: confirma todo el caso de uso o revierte todos sus cambios."""
    def __enter__(self): self.db=SessionLocal(); return self
    def commit(self): self.db.commit()
    def rollback(self): self.db.rollback()
    def __exit__(self, exc_type, exc, tb):
        if exc_type: self.db.rollback()
        self.db.close()
        return False
