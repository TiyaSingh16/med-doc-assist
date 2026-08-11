from pydantic import BaseModel, Field
from typing import Optional


class Diagnosis(BaseModel):
    condition: str = Field(description="Name of the diagnosed medical condition")
    confidence: Optional[str] = Field(
        default=None,
        description="Certainty level if mentioned, e.g. 'confirmed', 'suspected', 'ruled out'"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Any additional context about this diagnosis from the document"
    )


class Medicine(BaseModel):
    name: str = Field(description="Name of the medicine/drug")
    dosage: Optional[str] = Field(default=None, description="e.g. '500mg', '10ml'")
    frequency: Optional[str] = Field(default=None, description="e.g. 'twice daily', 'once at night'")
    duration: Optional[str] = Field(default=None, description="e.g. '7 days', 'ongoing'")


class LabValue(BaseModel):
    test_name: str = Field(description="Name of the lab test, e.g. 'Hemoglobin', 'Fasting Blood Sugar'")
    value: str = Field(description="The measured value, e.g. '13.5', '110'")
    unit: Optional[str] = Field(default=None, description="Unit of measurement, e.g. 'g/dL', 'mg/dL'")
    reference_range: Optional[str] = Field(default=None, description="Normal range if mentioned, e.g. '70-100'")
    flag: Optional[str] = Field(
        default=None,
        description="If the document flags this as high/low/normal/critical, capture it here"
    )


class ExtractionResult(BaseModel):
    diagnoses: list[Diagnosis] = Field(default_factory=list)
    medicines: list[Medicine] = Field(default_factory=list)
    lab_values: list[LabValue] = Field(default_factory=list)
    summary: Optional[str] = Field(
        default=None,
        description="One-line plain-English summary of the document's main finding"
    )