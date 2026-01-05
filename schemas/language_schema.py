#schemas/language_schema.py

from pydantic import BaseModel
from core.utils.core_enums import LanguageEnum

class ChangeLanguageRequest(BaseModel):
    language: LanguageEnum
