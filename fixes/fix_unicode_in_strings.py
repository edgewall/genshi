"""Fixer that changes expressions inside strings literals from u"..." to "...".

"""

import re
from lib2to3 import fixer_base

_literal_re = re.compile(r"(.+?)\b[uU]([rR]?[\'\"])")

class FixUnicodeInStrings(fixer_base.BaseFix):

    PATTERN = "STRING"

    def transform(self, node, results):
        new = node.clone()
        new.value = _literal_re.sub(r"\1\2", new.value)
        return new
