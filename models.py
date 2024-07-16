from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class TestCase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('test_group.id'), nullable=False)
    test_name = db.Column(db.String(50), nullable=False)
    test_code = db.Column(db.Text, nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    free_form = db.Column(db.Boolean, default=True, nullable=False)  # New column
    group = db.relationship('TestGroup', backref=db.backref('test_cases', lazy=True))

class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_case_id = db.Column(db.Integer, db.ForeignKey('test_case.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('test_group.id'), nullable=False)  # Added group_id
    test_case = db.relationship('TestCase', backref=db.backref('results', lazy=True))
    date_run = db.Column(db.Date, nullable=False, default=datetime.utcnow, index=True)
    time_taken = db.Column(db.Float, nullable=False)
    pass_status = db.Column(db.Boolean, nullable=False)
    error_message = db.Column(db.Text, nullable=True)

class TestGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    server = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    schedule = db.Column(db.String(100), nullable=True)

class TestDependency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test_case.id'), nullable=False)
    dependent_test_id = db.Column(db.Integer, db.ForeignKey('test_case.id'), nullable=False)
    
    test = db.relationship('TestCase', foreign_keys=[test_id], backref=db.backref('dependencies', lazy='dynamic'))
    dependent_test = db.relationship('TestCase', foreign_keys=[dependent_test_id], backref=db.backref('dependents', lazy='dynamic'))
