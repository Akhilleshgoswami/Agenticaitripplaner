from typing import List

from pydantic import BaseModel, Field, model_validator


class Analyst(BaseModel):
    affiliation: str = Field(default="", description="Primary affiliation of the analyst")
    name: str = Field(default="", description="Name of the analyst")
    role: str = Field(default="", description="Role of the analyst")
    description: str = Field(
        default="",
        description="Description of the analyst focus, concerns, and other information",
    )

    @model_validator(mode="before")
    @classmethod
    def handle_discription_alias(cls, values):
        if isinstance(values, dict):
            if "discription" in values and "description" not in values:
                values["description"] = values["discription"]
            elif "description" in values and "discription" not in values:
                values["discription"] = values["description"]
        return values

    @property
    def discription(self) -> str:
        return self.description

    @property
    def persona(self) -> str:
        return f"""
        .  {self.name} is a {self.role} at {self.affiliation}.
        """


class Perspectives(BaseModel):
    analyst: List[Analyst] = Field(description="List of analysts")


class SearchQuery(BaseModel):
    search_query: str = Field(description="Search hquery for the reterival")
