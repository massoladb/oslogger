from sqlalchemy import create_engine, Column, Integer, String, DateTime, Date, Enum
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, date
import enum
import os

Base = declarative_base()

class Status(enum.Enum):
    recebida = "Recebida"
    faltante = "Faltante"

class OrdemServico(Base):
    __tablename__ = 'ordens_servico'

    id = Column(Integer, primary_key=True)
    numero_os = Column(String, nullable=False)
    cliente = Column(String, nullable=False)
    vendedor = Column(String, nullable=False)
    status = Column(Enum(Status), default=Status.recebida)
    observacao = Column(String)
    data_hora_registro = Column(DateTime, default=datetime.now)
    data_relatorio = Column(Date, default=date.today)

# Caminho do banco (na pasta atual ou em uma pasta compartilhada da rede)
DB_PATH = os.path.join(os.path.dirname(__file__), "os_data.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
