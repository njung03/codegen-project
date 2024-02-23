from pydantic import BaseModel

class InputDataBase(BaseModel):
    prompt: str
    github_url: str

class InputDataCreate(InputDataBase):
    pass

class InputData(InputDataBase):
    id: int
    class Config:
        orm_mode = True

class OutputDiffBase(BaseModel):
    diff: str

class OutputDiffCreate(OutputDiffBase):
    pass

class OutputDiff(OutputDiffBase):
    id: int
    input_data_id: int

    class Config:
        orm_mode = True
