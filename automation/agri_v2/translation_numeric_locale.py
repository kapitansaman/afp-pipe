"""Locale-aware token comparison only. Never edits text, units or numeric values."""
import re
from .pipeline import numbers
VERSION='translation-decimal-comma-ru-tg-v1'
def tokens(text,lang=None):
 # Russian/Tajik decimal punctuation is comma. Grouping separators, exponents,
 # signs, units, operators and digit precision are NOT guessed or rewritten.
 # Non-Cyrillic/unspecified locales retain the exact legacy comparator.
 if lang in ('ru-RU','tg-TJ'):
  text=re.sub(r'(?<![\d.,])([0-9]+),([0-9]+)(?![\d.,])',lambda m:m[1]+'.'+m[2],text)
 return numbers(text)
def same(source,target,lang=None):return numbers(source)==tokens(target,lang)
