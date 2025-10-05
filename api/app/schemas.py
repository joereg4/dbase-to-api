from pydantic import BaseModel


class Customer(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class Vendor(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class Invoice(BaseModel):
    id: int
    number: str

    class Config:
        from_attributes = True

