# (Be in -*- python -*- mode.)
#
# ====================================================================
# Copyright (c) 2007-2010 CollabNet.  All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.  The terms
# are also available at http://subversion.tigris.org/license-1.html.
# If newer versions of this license are posted there, you may use a
# newer version instead, at your option.
#
# This software consists of voluntary contributions made by many
# individuals.  For exact contribution history, see the revision
# history and logs, available at http://cvs2svn.tigris.org/.
# ====================================================================

"""Expand RCS/CVS keywords."""


import re
import time
import os.path


# Print debug messages: 1 - enable debug messages   0 - disable debug messages
debug = 0

_kws = 'Author|Date|Header|Id|Locker|Log|Mdocdate|Name|OpenBSD|RCSfile|Revision|Source|State'

# The following regexp finds collapsed and expanded keywords. Expanded keywords
# will never contain any of the following characters, except in the unlikely
# event that they occur in an RCS filename: $"&'
_kwo_re = re.compile(r'\$(' + _kws + r')\b(?!\s+\$)([^"&$' + r"'\n]*)?" \
                     + r'(?<![.\\])\$(?:(?=\W)|(?=\w\s*\n))'
                     )


class _KeywordExpander:
  """A class whose instances provide substitutions for CVS keywords.

  This class is used via its __call__() method, which should be called
  with a match object representing a match for a CVS keyword string.
  The method returns the replacement for the matched text.

  The __call__() method works by calling the method with the same name
  as that of the CVS keyword (converted to lower case).

  Instances of this class can be passed as the REPL argument to
  re.sub()."""

  date_fmt_old = "%Y/%m/%d %H:%M:%S"    # CVS 1.11, rcs
  date_fmt_new = "%Y-%m-%d %H:%M:%S"    # CVS 1.12

  date_fmt = date_fmt_old

  @classmethod
  def use_old_date_format(klass):
      """Class method to ensure exact compatibility with CVS 1.11
      output.  Use this if you want to verify your conversion and you're
      using CVS 1.11."""
      klass.date_fmt = klass.date_fmt_old

  def __init__(self, rcsFileName, rev, timestamp, authorName):
    # Ensure we don't have attributes and methods with the same name. If we
    # do, as I found out the hard way, __call__() screws up.
    self.rcsFileName = rcsFileName
    self.rev         = rev
    self.timestamp   = timestamp
    self.authorName  = authorName

  def __call__(self, match):
    keywordReplacement = '$%s: %s $' % (
        match.group(1), getattr(self, match.group(1).lower())(),
        )

    if debug:
      print "     KEYWORD: " + match.group(1).lower()
      print "KEYWORD_REPL: " + keywordReplacement

    return keywordReplacement

  def author(self):
    return self.authorName

  def date(self):
    return time.strftime(self.date_fmt, time.gmtime(self.timestamp))

  def header(self):
    return '%s %s %s %s Exp' % (
      self.rcsFileName, self.rev,
      time.strftime(self.date_fmt, time.gmtime(self.timestamp)),
      self.authorName,
    )

  def id(self):
    return  '%s %s %s %s Exp' % (
      os.path.basename(self.rcsFileName), self.rev,
      time.strftime(self.date_fmt, time.gmtime(self.timestamp)),
      self.authorName,
    )

  def locker(self):
    return ''

  def log(self):
    return 'not supported by cvs2svn'

  def mdocdate(self):
    return '%s %d %s' % (
      time.strftime("%B", time.gmtime(self.timestamp)),
      time.gmtime(self.timestamp).tm_mday,
      time.strftime("%Y", time.gmtime(self.timestamp))
    )

  def name(self):
    return 'not supported by cvs2svn'

  def openbsd(self):
    return '%s %s %s %s Exp' % (
      os.path.basename(self.rcsFileName), self.rev,
        time.strftime(self.date_fmt, time.gmtime(self.timestamp)),
      self.authorName,
    )

  def rcsfile(self):
    return os.path.basename(self.rcsFileName)

  def revision(self):
    return self.rev

  def source(self):
    return self.rcsFileName

  def state(self):
    return 'Exp'

def expand_keywords(text, rcsfile, rev, timestamp, author):
  """Return TEXT with keywords expanded for CVS_REV.

  E.g., '$Author$' -> '$Author: jrandom $'."""

  newText = _kwo_re.sub(_KeywordExpander(rcsfile, rev, timestamp, author), text)

  if debug:
    print "     RCSFILE: " + rcsfile
    print "         REV: " + rev
    print "   TIMESTAMP: " + time.strftime(_KeywordExpander.date_fmt, time.gmtime(timestamp))
    print "      AUTHOR: " + author
    print "     OLDTEXT: " + text,
    print "     NEWTEXT: " + newText

  return newText

def collapse_keywords(text):
  """Return TEXT with keywords collapsed.

  E.g., '$Author: jrandom $' -> '$Author$'."""

  newText = _kwo_re.sub(r'$\1$', text)
  if debug:
    print "     OLDTEXT: " + text,
    print "     NEWTEXT: " + newText

  return newText

# -------------------- Test code below --------------------

def main():
  '''Standalone self-test code. Run with command:
       python keyword_obsd.py'''

  global debug

  debug = 1

  # Some arbitary data for testing purposes
  myRcsfile   = r'usr.sbin/afs/src/cf/Attic/krb-version.m4,v'
  myRev       = r'1.7.0.2'
  myTimestamp = 814005529       # 1995/10/18 08:38:49 UTC
  myAuthor    = r'joe_blow'

  testText1 = r"#  $Author$ aaa bbb $Date $ ccc $Header: Hi there $ " \
    + r"zzz $Id: yadda $g ddd $Name$ eee fff" \
    + "'$Id: vvv$' XXX $Source: /usr/src/Makefile $g\n"

  # /home/cvs/src/lib/libcrypto/util/pl/Attic/BC-16.pl,v
  #             local($ex)=($Name eq "SSL")?' $(L_CRYPTO) winsock':"";
  testText2 = r'local($ex)=($Name eq "SSL")?' \
    + r"' $(L_CRYPTO) winsock':" + '"";\n'

  # /home/cvs/src/usr.sbin/afs/src/cf/Attic/krb-version.m4,v
  #            sed -e "s/@USER@/$User/" -e "s/@HOST@/$Host/" -e "s/@DATE@/$Date/" include/${PACKAGE}-version.h.in > include/${PACKAGE}-version.h
  testText3 = 'sed -e "s/@USER@/$User/" -e "s/@HOST@/$Host/" ' \
    + '-e "s/@DATE@/$Date/" include/${PACKAGE}-version.h.in ' \
    + '> include/${PACKAGE}-version.h\n'

  for j in [testText1, testText2, testText3]:
    expand_keywords(j, myRcsfile, myRev, myTimestamp, myAuthor)

# Start the main program
if __name__ == '__main__':
    main()
