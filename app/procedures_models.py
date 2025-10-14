from datetime import datetime
from app.models import db

class Cid(db.Model):
    __tablename__ = 'cids'
    __bind_key__ = 'procedures'
    
    code = db.Column(db.String(10), primary_key=True)
    description = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        return {
            'code': self.code,
            'description': self.description,
            'is_active': self.is_active
        }
    
    def __repr__(self):
        return f'<Cid {self.code}>'


class ProcedureCid(db.Model):
    __tablename__ = 'procedure_cids'
    __bind_key__ = 'procedures'
    
    id = db.Column(db.Integer, primary_key=True)
    procedure_code = db.Column(db.String(20), db.ForeignKey('procedures.code'), nullable=False, index=True)
    cid_code = db.Column(db.String(10), db.ForeignKey('cids.code'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    procedure = db.relationship('Procedure', backref='procedure_cids')
    cid = db.relationship('Cid', backref='procedure_cids')
    
    __table_args__ = (
        db.UniqueConstraint('procedure_code', 'cid_code', name='uq_procedure_cid'),
    )
    
    def __repr__(self):
        return f'<ProcedureCid {self.procedure_code}-{self.cid_code}>'


class Procedure(db.Model):
    __tablename__ = 'procedures'
    __bind_key__ = 'procedures'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, unique=True, index=True)
    description = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    complexity_type = db.Column(db.String(1))
    gender_type = db.Column(db.String(1))  
    max_execution_qty = db.Column(db.Integer) 
    permanence_days = db.Column(db.Integer)  
    points = db.Column(db.Integer) 
    min_age = db.Column(db.Integer)  
    max_age = db.Column(db.Integer) 
    value_sh = db.Column(db.Numeric(12, 2)) 
    value_sa = db.Column(db.Numeric(12, 2))  
    value_sp = db.Column(db.Numeric(12, 2))  
    financing_code = db.Column(db.String(2))  
    rubric_code = db.Column(db.String(6)) 
    permanence_time = db.Column(db.Integer)  
    competence_date = db.Column(db.String(6))  
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'description': self.description,
            'is_active': self.is_active,
            'complexity_type': self.complexity_type,
            'gender_type': self.gender_type,
            'max_execution_qty': self.max_execution_qty,
            'permanence_days': self.permanence_days,
            'points': self.points,
            'min_age': self.min_age,
            'max_age': self.max_age,
            'value_sh': float(self.value_sh) if self.value_sh else None,
            'value_sa': float(self.value_sa) if self.value_sa else None,
            'value_sp': float(self.value_sp) if self.value_sp else None,
            'financing_code': self.financing_code,
            'rubric_code': self.rubric_code,
            'permanence_time': self.permanence_time,
            'competence_date': self.competence_date,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Procedure {self.code}>'



