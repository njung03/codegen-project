from sqlalchemy import Column, ForeignKey, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from .database import Base


class InputData(Base):
    __tablename__ = "input_data"

    id = Column(Integer, primary_key=True, index=True)
    prompt = Column(Text)
    github_url = Column(String)


class OutputDiff(Base):
    __tablename__ = "output_diffs"

    id = Column(Integer, primary_key=True, index=True)
    diff = Column(Text)
    input_data_id = Column(Integer, ForeignKey("input_data.id"))
