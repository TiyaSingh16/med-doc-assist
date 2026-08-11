from pydantic import BaseModel, Field
from typing import Optional


class LabValueChange(BaseModel):
    test_name: str = Field(description="Name of the lab test")
    old_value: Optional[str] = Field(default=None, description="Value in the earlier document, if present")
    new_value: Optional[str] = Field(default=None, description="Value in the later document, if present")
    trend: str = Field(description="One of: 'improved', 'worsened', 'unchanged', 'new', 'resolved'")
    unit: Optional[str] = Field(default=None, description="Unit of measurement")


class MedicationChange(BaseModel):
    name: str = Field(description="Name of the medicine")
    change_type: str = Field(description="One of: 'added', 'removed', 'dosage_changed', 'unchanged'")
    old_dosage: Optional[str] = Field(default=None)
    new_dosage: Optional[str] = Field(default=None)


class DiagnosisChange(BaseModel):
    condition: str = Field(description="Name of the diagnosis")
    change_type: str = Field(description="One of: 'new', 'resolved', 'ongoing'")


class ComparisonResult(BaseModel):
    lab_value_changes: list[LabValueChange] = Field(default_factory=list)
    medication_changes: list[MedicationChange] = Field(default_factory=list)
    diagnosis_changes: list[DiagnosisChange] = Field(default_factory=list)
    summary: str = Field(description="Plain-English summary of the overall change between the two documents")