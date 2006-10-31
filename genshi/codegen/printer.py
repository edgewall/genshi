# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Edgewall Software and Michael Bayer <mike_mp@zzzcomputing.com>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

import re

PYTHON_LINE = "line"
PYTHON_COMMENT = "comment"
PYTHON_BLOCK = "block"

class PythonPrinter(object):
    """prints Python code, keeping track of indentation level.
    
    Adapted from PythonPrinter in Myghty; also uses stream-based operation.  The Myghty version of this is 
    more complicated; among other things, it includes a 'block' version useful 
    for properly indenting user-included blocks of Python.  When Genshi gets the 
    <?python?> tag we will want to revisit this output mode."""  
    def __init__(self, stream):
        # the indentation counter
        self.indent = 0
        
        # a stack storing information about why we incremented 
        # the indentation counter, to help us determine if we
        # should decrement it
        self.indent_detail = []
        
        # the string of whitespace multiplied by the indent
        # counter to produce a line
        self.indentstring = "    "
        
        # a stack of whitespace we pulled from "normalized" 
        # Python lines to track when the indentation counter should
        # be incremented or decremented
        self.spacestack = []
        
        # read stream
        self.stream = stream
        
        self._reset_multi_line_flags()

    def generate(self):
        for linetype, line in self.stream:
            if linetype is PYTHON_LINE:
                yield self._process_line(line)
            elif linetype is PYTHON_COMMENT:
                yield self._process_comment(line)
            elif linetype is PYTHON_BLOCK:
                raise "PYTHON_BLOCK not supported yet"
            else:
                raise "unknown block type %s" % linetype
        
    def _process_line(self, line, is_comment=False):
        """prints a line to the output buffer, preceded by a blank indentation
        string of proportional size to the current indent counter.  
        
        If the line ends with a colon, the indentation counter is incremented after
        printing.  If the line is blank, the indentation counter is decremented.
        
        if normalize_indent is set to true, the line is printed
        with its existing whitespace "normalized" to the current indentation 
        counter; additionally, its existing whitespace is measured and
        compared against a stack of whitespace strings grabbed from other
        normalize_indent calls, which is used to adjust the current indentation 
        counter.
        """
        decreased_indent = False
    
        if (
            re.match(r"^\s*#",line) or
            re.match(r"^\s*$", line)
            ):
            hastext = False
        else:
            hastext = True
        
        # see if this line should decrease the indentation level
        if (not decreased_indent and 
            not is_comment and 
            (not hastext or self._is_unindentor(line))
            ):
            
            if self.indent > 0: 
                self.indent -=1
                # if the indent_detail stack is empty, the user
                # probably put extra closures - the resulting
                # module wont compile.  
                if len(self.indent_detail) == 0:  
                    raise "Too many whitespace closures"
                self.indent_detail.pop()
            
        # see if this line should increase the indentation level.
        # note that a line can both decrase (before printing) and 
        # then increase (after printing) the indentation level.
        result = self._indent_line(line) + "\n"

        if re.search(r":[ \t]*(?:#.*)?$", line):
            # increment indentation count, and also
            # keep track of what the keyword was that indented us,
            # if it is a python compound statement keyword
            # where we might have to look for an "unindent" keyword
            match = re.match(r"^\s*(if|try|elif|while|for)", line)
            if match:
                # its a "compound" keyword, so we will check for "unindentors"
                indentor = match.group(1)
                self.indent +=1
                self.indent_detail.append(indentor)
            else:
                indentor = None
                # its not a "compound" keyword.  but lets also
                # test for valid Python keywords that might be indenting us,
                # else assume its a non-indenting line
                m2 = re.match(r"^\s*(def|class|else|elif|except|finally)", line)
                if m2:
                    self.indent += 1
                    self.indent_detail.append(indentor)

        return result
        
    def _process_comment(self, comment):
        return self._process_line("# " + comment, is_comment=True)
        
    def _is_unindentor(self, line):
        """return True if the given line unindents the most recent indent-increasing line."""
                
        # no indentation detail has been pushed on; return False
        if len(self.indent_detail) == 0: return False

        indentor = self.indent_detail[-1]
        
        # the last indent keyword we grabbed is not a 
        # compound statement keyword; return False
        if indentor is None: return False
        
        # if the current line doesnt have one of the "unindentor" keywords,
        # return False
        match = re.match(r"^\s*(else|elif|except|finally)", line)
        if not match: return False
        
        # whitespace matches up, we have a compound indentor,
        # and this line has an unindentor, this
        # is probably good enough
        return True
        
        # should we decide that its not good enough, heres
        # more stuff to check.
        #keyword = match.group(1)
        
        # match the original indent keyword 
        #for crit in [
        #   (r'if|elif', r'else|elif'),
        #   (r'try', r'except|finally|else'),
        #   (r'while|for', r'else'),
        #]:
        #   if re.match(crit[0], indentor) and re.match(crit[1], keyword): return True
        
        #return False
        
        
    def _indent_line(self, line, stripspace = ''):
        return re.sub(r"^%s" % stripspace, self.indentstring * self.indent, line)

    def _reset_multi_line_flags(self):
        (self.backslashed, self.triplequoted) = (False, False) 
        
    def _in_multi_line(self, line):
        # we are only looking for explicitly joined lines here,
        # not implicit ones (i.e. brackets, braces etc.).  this is just
        # to guard against the possibility of modifying the space inside 
        # of a literal multiline string with unfortunately placed whitespace
         
        current_state = (self.backslashed or self.triplequoted) 
                        
        if re.search(r"\\$", line):
            self.backslashed = True
        else:
            self.backslashed = False
            
        triples = len(re.findall(r"\"\"\"|\'\'\'", line))
        if triples == 1 or triples % 2 != 0:
            self.triplequoted = not self.triplequoted

        return current_state
