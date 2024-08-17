from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Date, Time, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from config import SQLALCHEMY_DATABASE_URI

engine = create_engine(SQLALCHEMY_DATABASE_URI, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TestCase(Base):
    __tablename__ = 'test_case'
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey('test_group.id'), nullable=False)
    test_name = Column(String(50), nullable=False)
    test_code = Column(Text, nullable=False)
    creation_date = Column(DateTime, default=datetime.utcnow)
    free_form = Column(Boolean, default=True, nullable=False)
    group = relationship('TestGroup', backref='test_cases')

class TestResult(Base):
    __tablename__ = 'test_result'
    id = Column(Integer, primary_key=True, index=True)
    test_case_id = Column(Integer, ForeignKey('test_case.id'), nullable=False)
    group_id = Column(Integer, ForeignKey('test_group.id'), nullable=False)  # Added group_id
    test_case = relationship('TestCase', backref='results')
    date_run = Column(Date, nullable=False, default=datetime.utcnow().date, index=True)
    time_run = Column(Time, nullable=False, default=datetime.utcnow().time)
    time_taken = Column(Float, nullable=False)
    pass_status = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)

class TestGroup(Base):
    __tablename__ = 'test_group'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    server = Column(String(100), nullable=False)
    port = Column(Integer, nullable=False)
    schedule = Column(String(100), nullable=True)
    tls = Column(Boolean, nullable=False, default=False)

class TestDependency(Base):
    __tablename__ = 'test_dependency'
    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey('test_case.id'), nullable=False)
    dependent_test_id = Column(Integer, ForeignKey('test_case.id'), nullable=False)
    
    test = relationship('TestCase', foreign_keys=[test_id], backref='dependencies')
    dependent_test = relationship('TestCase', foreign_keys=[dependent_test_id], backref='dependents')

# Create all tables
Base.metadata.create_all(bind=engine)
