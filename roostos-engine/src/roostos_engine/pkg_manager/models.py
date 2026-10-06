"""Pydantic models and DTOs for OS package and dependency management."""

from typing import List, Optional
from pydantic import BaseModel, Field


class PackageStatus(BaseModel):
    """Status descriptor for a single OS package."""
    name: str
    installed: bool
    version: Optional[str] = None


class DependencyReport(BaseModel):
    """Dependency evaluation for a specific RoostOS feature or role."""
    feature: str
    satisfied: bool
    packages: List[PackageStatus] = Field(default_factory=list)


class InstallResult(BaseModel):
    """Result of attempting to install one or more system packages."""
    success: bool
    installed: List[str] = Field(default_factory=list)
    failed: List[str] = Field(default_factory=list)
    message: str = ""


class SystemDependenciesSummary(BaseModel):
    """System-wide summary of all feature dependencies."""
    os_family: str
    manager_name: str
    reports: List[DependencyReport] = Field(default_factory=list)
    all_satisfied: bool
