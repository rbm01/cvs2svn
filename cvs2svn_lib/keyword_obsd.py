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

from cvs2svn_lib.context import Ctx


# Print debug messages: 1 - enable debug messages   0 - disable debug messages
debug = 0

date_fmt_old = "%Y/%m/%d %H:%M:%S"    # CVS 1.11, rcs
date_fmt_new = "%Y-%m-%d %H:%M:%S"    # CVS 1.12

date_fmt = date_fmt_old

_kws = 'Author|Date|Header|Id|Locker|Log|Mdocdate|Name|OpenBSD|RCSfile|Revision|Source|State'

_kwo_re = re.compile(r'\$(' + _kws + r')\b(?!\s+\$)([^$\n]*)?' \
                     + r"(?<![.'" + r'"\\])\$(?:(?=\W)|(?=\w\s*\n))'
                     )


def do_keyword_expansion(match, text, rcsfile, rev, timestamp, author):
  """ Assemble the keyword expansion strings """

  keyword = match.group(1).lower()      # extract keyword and set to lower case
  if debug: print "     KEYWORD: " + keyword

  if (keyword == r'author'):
    return author
  if (keyword == r'date'):
    return time.strftime(date_fmt, time.gmtime(timestamp))
  if (keyword == r'header'):
    return '%s %s %s %s Exp' % (
      rcsfile, rev,
      time.strftime(date_fmt, time.gmtime(timestamp)),
      author,
    )
  if (keyword == r'id'):
    return  '%s %s %s %s Exp' % (
      os.path.basename(rcsfile), rev,
      time.strftime(date_fmt, time.gmtime(timestamp)),
      author,
    )
  if (keyword == r'locker'):
    return ''
  if (keyword == r'log'):
    return 'not supported by cvs2svn'
  if (keyword == r'mdocdate'):
    return '%s %d %s' % (
      time.strftime("%B", time.gmtime(timestamp)),
      time.gmtime(timestamp).tm_mday,
      time.strftime("%Y", time.gmtime(timestamp))
    )
  if (keyword == r'name'):
    return 'not supported by cvs2svn'
  if (keyword == r'openbsd'):
    return '%s %s %s %s Exp' % (
      os.path.basename(rcsfile), rev, time.strftime(date_fmt, time.gmtime(timestamp)),
      author,
    )
  if (keyword == r'rcsfile'):
    return os.path.basename(rcsfile)
  if (keyword == r'revision'):
    return rev
  if (keyword == r'source'):
    return rcsfile
  if (keyword == r'state'):
    return 'Exp'

def expand_keywords(text, rcsfile, rev, timestamp, author):
  """Return TEXT with keywords expanded for CVS_REV.

  E.g., '$Author$' -> '$Author: jrandom $'."""

  for match_obj in _kwo_re.finditer(text):
    # We have found a keyword if we get to this point. Replace the original
    # keyword text with the expanded keyword text.
    keywordReplacement = do_keyword_expansion(match_obj, text, rcsfile,
                                              rev, timestamp, author)

    text = text[:match_obj.start(1)] + match_obj.group(1) + ": " \
            + keywordReplacement + " " + text[match_obj.end(2):]

    if debug:
      print "KEYWORD_REPL: " + keywordReplacement
      print "     RCSFILE: " + rcsfile
      print "         REV: " + rev
      print "   TIMESTAMP: " + time.strftime(date_fmt, time.gmtime(timestamp))
      print "      AUTHOR: " + author
      print "     NEWTEXT: " + text

  return text


def collapse_keywords(text):
  """Return TEXT with keywords collapsed.

  E.g., '$Author: jrandom $' -> '$Author$'."""

  return _kwo_re.sub(r'$\1$', text)


